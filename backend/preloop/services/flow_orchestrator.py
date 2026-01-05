import logging
import uuid
import json
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import re

from sqlalchemy.orm import Session
from nats.aio.client import Client

from preloop.models import schemas
from preloop.models.crud import (
    crud_account,
    crud_ai_model,
    crud_api_key,
    crud_flow,
    crud_flow_execution,
)
from preloop.models.models.flow import Flow
from preloop.models.models.ai_model import AIModel
from preloop.agents import create_agent_executor, AgentStatus
from preloop.services.prompt_resolvers import (
    resolver_registry,
    ResolverContext,
    TriggerEventResolver,
    ProjectResolver,
    AccountResolver,
)
from preloop.services.flow_execution_logger import FlowExecutionLogger

logger = logging.getLogger(__name__)


def _make_json_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types to serializable ones."""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    return obj


class FlowExecutionOrchestrator:
    """Manages the end-to-end lifecycle of a single Flow invocation."""

    def __init__(
        self,
        db: Session,
        flow_id: uuid.UUID,
        trigger_event_data: Dict[str, Any],
        nats_client: Client,
    ):
        self.db = db
        self.flow_id = flow_id
        self.trigger_event_data = trigger_event_data
        self.flow: Optional[Flow] = None
        self.ai_model: Optional[AIModel] = None
        self.execution_log = None
        self.nats_client: Client = nats_client
        self.execution_logger = FlowExecutionLogger()
        self.temporary_api_key_id: Optional[uuid.UUID] = None
        self._log_streaming_task: Optional[asyncio.Task] = None
        self._command_subscription: Optional[Any] = None
        self._stop_requested = asyncio.Event()
        self._user_messages: asyncio.Queue = asyncio.Queue()

        # Execution metrics tracked during execution
        self.total_tokens: int = 0
        self.tool_calls_count: int = 0
        self.estimated_cost: float = 0.0

    @staticmethod
    async def send_command(
        execution_id: str,
        command: str,
        payload: Optional[Dict[str, Any]] = None,
        nats_client: Optional[Client] = None,
    ):
        """
        Send a command to a running flow execution via NATS.

        Args:
            execution_id: ID of the flow execution
            command: Command to send (e.g., 'stop', 'send_message')
            payload: Optional command payload
            nats_client: Optional NATS client (if not provided, will try to get from app state)

        Raises:
            RuntimeError: If NATS client is not available
        """
        # If nats_client not provided, try to get it from app state
        if not nats_client:
            try:
                import inspect

                # Try to find the app instance in the call stack
                for frame_info in inspect.stack():
                    frame_locals = frame_info.frame.f_locals
                    if "request" in frame_locals:
                        request = frame_locals["request"]
                        if hasattr(request, "app") and hasattr(request.app, "state"):
                            nats_client = getattr(request.app.state, "nats", None)
                            break
            except Exception:
                pass

        if not nats_client or not nats_client.is_connected:
            raise RuntimeError("NATS client not available or not connected")

        try:
            command_subject = f"flow-commands.{execution_id}"
            command_data = {"command": command, "payload": payload or {}}

            await nats_client.publish(
                command_subject, json.dumps(command_data).encode()
            )
            logger.info(
                f"Sent command '{command}' to execution {execution_id} via NATS"
            )
        except Exception as e:
            logger.error(f"Failed to send command via NATS: {e}", exc_info=True)
            raise

    async def _publish_update(self, message_type: str, payload: Dict[str, Any]):
        """
        Publishes a structured message to the NATS stream for real-time updates.
        Includes account_id for proper filtering to prevent cross-account data leaks.
        """
        if not self.nats_client or not self.nats_client.is_connected:
            logger.warning("NATS client not available, skipping update publish.")
            return

        if not self.execution_log:
            logger.warning("Execution log not created yet, skipping update publish.")
            return

        try:
            message = {
                "execution_id": str(self.execution_log.id),
                "flow_id": str(self.flow_id),
                "account_id": str(self.flow.account_id)
                if self.flow and self.flow.account_id
                else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": message_type,
                "payload": payload,
            }
            subject = f"flow-updates.{self.execution_log.id}"
            await self.nats_client.publish(subject, json.dumps(message).encode())
            logger.debug(f"Published {message_type} to NATS subject '{subject}'")
        except Exception as e:
            logger.error(f"Failed to publish update to NATS: {e}", exc_info=True)

    def _get_flow_details(self):
        """Retrieve the Flow definition and associated AIModel."""
        logger.info(f"Retrieving flow details for flow_id: {self.flow_id}")

        # Get flow - convert UUID to string for comparison
        flow_id_str = (
            str(self.flow_id) if isinstance(self.flow_id, uuid.UUID) else self.flow_id
        )
        # Use CRUD layer without account filtering since this is an internal service
        # and we don't have the account_id yet (it's a property of the flow itself)
        self.flow = crud_flow.get(self.db, id=flow_id_str)
        if not self.flow:
            raise ValueError(f"Flow with id {self.flow_id} not found")

        logger.info(
            f"Found flow: {self.flow.name} (agent_type: {self.flow.agent_type})"
        )

        # Get AI model if specified
        if self.flow.ai_model_id:
            ai_model_id_str = (
                str(self.flow.ai_model_id)
                if isinstance(self.flow.ai_model_id, uuid.UUID)
                else self.flow.ai_model_id
            )
            self.ai_model = crud_ai_model.get(self.db, id=ai_model_id_str)
            if not self.ai_model:
                logger.warning(
                    f"AI model {self.flow.ai_model_id} not found for flow {self.flow_id}"
                )
            else:
                logger.info(
                    f"Loaded AI model: {self.ai_model.name} ({self.ai_model.model_identifier})"
                )
        else:
            logger.info("No AI model specified for this flow")

    async def _resolve_prompt(self) -> str:
        """
        Resolve dynamic placeholders in the prompt template using registered resolvers.

        Supports placeholders like:
        - {{trigger_event.payload.issue.title}}
        - {{project.name}}
        - {{account.email}}
        """
        logger.info("Resolving prompt template")

        # Ensure resolvers are registered
        self._ensure_resolvers_registered()

        prompt_template = self.flow.prompt_template
        resolved_prompt = prompt_template

        # Create resolver context
        resolver_context = ResolverContext(
            db=self.db,
            trigger_event_data=self.trigger_event_data,
            flow_id=str(self.flow_id),
            execution_id=str(self.execution_log.id) if self.execution_log else "",
        )

        # Extract all {{placeholder}} patterns
        placeholders = re.findall(r"\{\{(\w+(?:\.\w+)*)\}\}", prompt_template)

        for placeholder in placeholders:
            # Split prefix and path (e.g., "trigger_event.payload.title" -> "trigger_event" + "payload.title")
            parts = placeholder.split(".", 1)
            prefix = parts[0]
            path = parts[1] if len(parts) > 1 else ""

            # Get resolver for this prefix
            resolver = resolver_registry.get(prefix)

            if resolver:
                try:
                    # Resolve the placeholder
                    value = await resolver.resolve(path, resolver_context)

                    if value is not None:
                        # Replace the placeholder with the value
                        resolved_prompt = resolved_prompt.replace(
                            f"{{{{{placeholder}}}}}", str(value)
                        )
                        logger.debug(f"Resolved {{{{{placeholder}}}}}: {value}")
                    else:
                        logger.warning(
                            f"Placeholder {{{{{placeholder}}}}} resolved to None, leaving as-is"
                        )
                except Exception as e:
                    logger.error(
                        f"Error resolving placeholder {{{{{placeholder}}}}}: {e}",
                        exc_info=True,
                    )
            else:
                # Try simple replacement from trigger_event_data for backwards compatibility
                value = self._simple_resolve(placeholder, self.trigger_event_data)
                if value is not None:
                    resolved_prompt = resolved_prompt.replace(
                        f"{{{{{placeholder}}}}}", str(value)
                    )
                    logger.debug(f"Simple resolved {{{{{placeholder}}}}}: {value}")
                else:
                    logger.warning(
                        f"No resolver found for prefix '{prefix}' and simple resolution failed for {{{{{placeholder}}}}}"
                    )

        logger.info("Prompt resolution complete")
        return resolved_prompt

    def _ensure_resolvers_registered(self):
        """Ensure all built-in resolvers are registered."""
        # Register built-in resolvers if not already registered
        if not resolver_registry.get("trigger_event"):
            resolver_registry.register(TriggerEventResolver())
        if not resolver_registry.get("project"):
            resolver_registry.register(ProjectResolver())
        if not resolver_registry.get("account"):
            resolver_registry.register(AccountResolver())

    def _create_temporary_api_token(self) -> tuple[Optional[str], Optional[uuid.UUID]]:
        """
        Create a temporary API token for this flow execution.

        Returns:
            Tuple of (token_key, token_id) or (None, None) if creation failed
        """
        import secrets
        from datetime import timedelta
        from preloop.models.models import ApiKey
        from preloop.models.crud import crud_user

        try:
            account = crud_account.get(self.db, id=self.flow.account_id)

            if not account:
                logger.warning(f"Account {self.flow.account_id} not found")
                return None, None

            # Get the first user from the account to associate with the API key
            # For flow executions, we use the first available user in the organization
            users = crud_user.get_by_account(self.db, account_id=self.flow.account_id)
            if not users:
                logger.warning(
                    f"No users found for account {self.flow.account_id}, "
                    f"cannot create API token"
                )
                return None, None

            first_user = users[0]

            # Generate a secure random token
            token_key = f"flow_{secrets.token_urlsafe(32)}"

            # Create API key that expires in 2 hours
            expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

            # Store flow execution context in the token for tool filtering
            context_data = {
                "flow_execution_id": str(self.execution_log.id)
                if self.execution_log
                else None,
                "flow_id": str(self.flow_id),
                "allowed_mcp_tools": self.flow.allowed_mcp_tools or [],
                "allowed_mcp_servers": self.flow.allowed_mcp_servers or [],
            }

            api_key = ApiKey(
                name=f"Flow Execution {self.execution_log.id if self.execution_log else 'temp'}",
                key=token_key,
                account_id=self.flow.account_id,
                user_id=first_user.id,
                expires_at=expires_at,
                is_active=True,
                scopes=["mcp:read", "mcp:write"],  # Limited scopes for MCP access
                context_data=context_data,  # Store flow context for tool restrictions
            )

            self.db.add(api_key)
            self.db.commit()
            self.db.refresh(api_key)

            logger.info(
                f"Created temporary API token {api_key.id} for flow execution, expires at {expires_at}"
            )

            return token_key, api_key.id

        except Exception as e:
            logger.error(f"Failed to create temporary API token: {e}", exc_info=True)
            self.db.rollback()
            return None, None

    def _cleanup_temporary_api_token(self):
        """Delete the temporary API token created for this flow execution."""
        if not self.temporary_api_key_id:
            return

        try:
            api_key = crud_api_key.get(self.db, id=self.temporary_api_key_id)

            if api_key:
                self.db.delete(api_key)
                self.db.commit()
                logger.info(f"Deleted temporary API token {self.temporary_api_key_id}")
            else:
                logger.warning(
                    f"Temporary API token {self.temporary_api_key_id} not found for cleanup"
                )

        except Exception as e:
            logger.error(f"Failed to cleanup temporary API token: {e}", exc_info=True)
            self.db.rollback()

    def _simple_resolve(self, placeholder: str, data: Dict[str, Any]) -> Optional[str]:
        """
        Simple fallback resolver for backwards compatibility.

        Args:
            placeholder: Placeholder string (e.g., "payload.issue.title")
            data: Dictionary to resolve from

        Returns:
            Resolved value or None
        """
        keys = placeholder.split(".")
        value = data

        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None

            return str(value) if value is not None else None
        except Exception:
            return None

    async def _perform_git_clone(self, work_dir: str) -> Optional[str]:
        """
        Perform git clone operation if configured.

        Args:
            work_dir: Working directory where the clone should happen

        Returns:
            Path to cloned repository or None if not configured/failed
        """
        if not self.flow.git_clone_config:
            logger.debug("Git clone not configured for this flow")
            return None

        git_config = self.flow.git_clone_config
        if not git_config.get("enabled", False):
            logger.debug("Git clone is disabled")
            return None

        logger.info("Performing git clone operation")

        try:
            # Get repository URL
            repo_url = git_config.get("repository_url")
            if not repo_url:
                # Try to get from trigger event (GitHub/GitLab)
                repo_url = self._resolve_repository_url_from_trigger()

            if not repo_url:
                logger.error("No repository URL configured or found in trigger event")
                return None

            # Get clone path
            clone_path = git_config.get("clone_path", "./workspace")
            full_clone_path = f"{work_dir}/{clone_path}"

            # Get branch
            branch = git_config.get("branch")
            branch_arg = f" -b {branch}" if branch else ""

            # Prepare git clone command
            use_tracker_creds = git_config.get("use_tracker_credentials", True)
            if use_tracker_creds:
                # Get tracker credentials from trigger event
                credentials = await self._get_tracker_credentials()
                if credentials:
                    # Inject credentials into URL
                    repo_url = self._inject_credentials_into_url(repo_url, credentials)

            clone_cmd = (
                f"git clone --recursive{branch_arg} {repo_url} {full_clone_path}"
            )

            logger.info(f"Executing git clone to {full_clone_path}")

            # Execute git clone
            process = await asyncio.create_subprocess_shell(
                clone_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(
                    f"Git clone failed with code {process.returncode}: {stderr.decode()}"
                )
                return None

            logger.info(f"Git clone successful: {stdout.decode()}")
            return full_clone_path

        except Exception as e:
            logger.error(f"Error during git clone: {e}", exc_info=True)
            return None

    def _resolve_repository_url_from_trigger(self) -> Optional[str]:
        """Extract repository URL from trigger event data."""
        try:
            # GitHub structure
            if "repository" in self.trigger_event_data:
                repo = self.trigger_event_data["repository"]
                if isinstance(repo, dict):
                    return repo.get("clone_url") or repo.get("html_url")

            # GitLab structure
            if "project" in self.trigger_event_data:
                project = self.trigger_event_data["project"]
                if isinstance(project, dict):
                    return project.get("http_url_to_repo") or project.get("web_url")

            return None
        except Exception as e:
            logger.error(f"Error extracting repository URL from trigger: {e}")
            return None

    async def _get_tracker_credentials(self) -> Optional[Dict[str, str]]:
        """Get tracker credentials from the database (deprecated - use _get_tracker_credentials_by_id)."""
        try:
            # Get tracker_id from trigger event or flow config
            tracker_id = self.trigger_event_data.get("tracker_id")
            if not tracker_id:
                logger.warning("No tracker_id in trigger event data")
                return None

            return await self._get_tracker_credentials_by_id(tracker_id)

        except Exception as e:
            logger.error(f"Error getting tracker credentials: {e}", exc_info=True)
            return None

    async def _get_tracker_credentials_by_id(
        self, tracker_id: str
    ) -> Optional[Dict[str, str]]:
        """Get tracker credentials by tracker ID."""
        try:
            from preloop.models.crud import crud_tracker

            tracker = crud_tracker.get(self.db, id=tracker_id)
            if not tracker:
                logger.warning(f"Tracker {tracker_id} not found")
                return None

            # Return credentials (api_key is encrypted in DB, should be decrypted here)
            return {
                "tracker_id": tracker_id,
                "token": tracker.api_key,  # TODO: Decrypt api_key
                "tracker_type": tracker.tracker_type,
            }

        except Exception as e:
            logger.error(
                f"Error getting tracker credentials for {tracker_id}: {e}",
                exc_info=True,
            )
            return None

    def _inject_credentials_into_url(
        self, repo_url: str, credentials: Dict[str, str]
    ) -> str:
        """Inject credentials into repository URL for authentication."""
        try:
            token = credentials.get("token")
            tracker_type = credentials.get("tracker_type")

            if not token:
                return repo_url

            # For GitHub: https://oauth2:TOKEN@github.com/owner/repo
            # For GitLab: https://oauth2:TOKEN@gitlab.com/owner/repo
            if "github.com" in repo_url or tracker_type == "github":
                if "https://" in repo_url:
                    return repo_url.replace("https://", f"https://oauth2:{token}@")
            elif "gitlab.com" in repo_url or tracker_type == "gitlab":
                if "https://" in repo_url:
                    return repo_url.replace("https://", f"https://oauth2:{token}@")

            # If we can't inject, return original URL
            logger.warning("Could not inject credentials into repository URL")
            return repo_url

        except Exception as e:
            logger.error(f"Error injecting credentials: {e}", exc_info=True)
            return repo_url

    async def _execute_custom_commands(self, work_dir: str) -> bool:
        """
        Execute custom commands if configured (admin-only feature).

        Args:
            work_dir: Working directory where commands should run

        Returns:
            True if successful or not configured, False if failed
        """
        if not self.flow.custom_commands:
            logger.debug("Custom commands not configured for this flow")
            return True

        custom_cmds = self.flow.custom_commands
        if not custom_cmds.get("enabled", False):
            logger.debug("Custom commands are disabled")
            return True

        # Security check: Verify the flow was created by a superuser
        # This prevents non-admin users from executing arbitrary commands
        try:
            from preloop.models.crud import crud_user

            # Get all users from the account
            users = crud_user.get_by_account(self.db, account_id=self.flow.account_id)

            # Check if ANY user with owner role exists in this account
            # (Flow creation/update should have been blocked if user wasn't admin)
            has_admin = any(user.is_superuser for user in users)
            if not has_admin:
                logger.error(
                    "Custom commands configured but no admin users found for account. "
                    "This is a security violation - skipping custom commands."
                )
                return False

        except Exception as e:
            logger.error(f"Error verifying admin status: {e}", exc_info=True)
            return False

        commands = custom_cmds.get("commands", [])
        if not commands:
            logger.debug("No custom commands to execute")
            return True

        logger.info(f"Executing {len(commands)} custom command(s)")

        try:
            for idx, cmd in enumerate(commands):
                logger.info(
                    f"Executing custom command {idx + 1}/{len(commands)}: {cmd}"
                )

                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=work_dir,
                )

                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    logger.error(
                        f"Custom command failed with code {process.returncode}: {stderr.decode()}"
                    )
                    return False

                logger.info(f"Custom command output: {stdout.decode()}")

            logger.info("All custom commands executed successfully")
            return True

        except Exception as e:
            logger.error(f"Error executing custom commands: {e}", exc_info=True)
            return False

    async def _prepare_execution_context(self) -> Dict[str, Any]:
        """Prepare the full execution context for the agent."""
        logger.info(
            f"Preparing execution context for agent type: {self.flow.agent_type}"
        )

        resolved_prompt = await self._resolve_prompt()

        # Create short-lived API token for this flow execution
        account_api_token = None
        if self.flow.account_id:
            account_api_token, self.temporary_api_key_id = (
                self._create_temporary_api_token()
            )
            if not account_api_token:
                logger.warning(
                    f"Could not create temporary API token for account {self.flow.account_id}"
                )

        execution_context = {
            "flow_id": str(self.flow_id),
            "flow_name": self.flow.name,  # Used for generating git branch names
            "execution_id": str(self.execution_log.id),
            "prompt": resolved_prompt,
            "agent_type": self.flow.agent_type,
            "agent_config": self.flow.agent_config,
            "allowed_mcp_servers": self.flow.allowed_mcp_servers,
            "allowed_mcp_tools": self.flow.allowed_mcp_tools,
            "account_id": self.flow.account_id,
            "account_api_token": account_api_token,
            "git_clone_config": self.flow.git_clone_config,
            "custom_commands": self.flow.custom_commands,
            "trigger_event_data": self.trigger_event_data,
            "trigger_project_id": str(self.flow.trigger_project_id)
            if self.flow.trigger_project_id
            else None,  # For git clone fallback
        }

        # Prepare git credentials if repositories are configured
        if self.flow.git_clone_config:
            repositories = self.flow.git_clone_config.get("repositories", [])
            if repositories:
                logger.info(
                    f"Preparing git credentials for {len(repositories)} configured repositories"
                )
                # Get unique tracker IDs from repositories
                tracker_ids = set(
                    repo.get("tracker_id")
                    for repo in repositories
                    if repo.get("tracker_id")
                )

                # Fetch credentials for each tracker
                credentials_map = {}
                for tracker_id in tracker_ids:
                    creds = await self._get_tracker_credentials_by_id(tracker_id)
                    if creds:
                        credentials_map[tracker_id] = creds

                if credentials_map:
                    execution_context["git_credentials_map"] = credentials_map
                    logger.info(
                        f"Prepared git credentials for {len(credentials_map)} tracker(s)"
                    )
                else:
                    logger.warning(
                        "Git clone enabled but could not get tracker credentials"
                    )

        # Add AI model details if available
        if self.ai_model:
            logger.info(
                f"AI model loaded: id={self.ai_model.id}, "
                f"identifier={self.ai_model.model_identifier}, "
                f"provider={self.ai_model.provider_name}"
            )
            execution_context.update(
                {
                    "model_identifier": self.ai_model.model_identifier,
                    "model_provider": self.ai_model.provider_name,
                    "model_endpoint": self.ai_model.api_endpoint,
                    "model_api_key": self.ai_model.api_key,  # TODO: Decrypt in Task 5.1
                    "model_parameters": self.ai_model.model_parameters,
                }
            )
        else:
            logger.warning(
                f"No AI model configured for flow {self.flow.id}, "
                f"ai_model_id={self.flow.ai_model_id if hasattr(self.flow, 'ai_model_id') else 'N/A'}, "
                "agent will need to use defaults"
            )

        logger.info("Execution context prepared successfully")
        return execution_context

    async def _stream_logs_to_nats(self, agent_executor, session_reference: str):
        """
        Background task to stream agent logs to NATS in real-time.

        Args:
            agent_executor: Agent executor instance
            session_reference: Container/Job reference
        """
        logger.info(f"Starting log streaming for {session_reference}")
        log_count = 0

        # Track previous line for token parsing (tokens used pattern spans 2 lines)
        previous_line = ""

        try:
            async for log_line in agent_executor.stream_logs(session_reference):
                log_count += 1
                logger.debug(f"Streamed log line #{log_count}: {log_line[:100]}")

                # Store the log line for later summary
                self.execution_logger.log_agent_output(log_line)

                # Parse log line for structured data (includes tool call detection)
                self.execution_logger.parse_agent_logs([log_line])

                # Check for token usage pattern: "tokens used" followed by number on next line
                if "tokens used" in previous_line.lower():
                    # Try to extract token count from current line
                    import re

                    # Pattern: number with optional commas (e.g., "1,234" or "1234")
                    token_match = re.search(r"(\d{1,3}(?:,\d{3})*)", log_line.strip())
                    if token_match:
                        tokens = int(token_match.group(1).replace(",", ""))
                        self.total_tokens += tokens

                        # Estimate cost based on tokens (using average of $5 per million tokens)
                        # This is a rough estimate - actual costs vary by model and input/output ratio
                        cost_per_million_tokens = 5.0  # Average cost
                        tokens_cost = (tokens / 1_000_000) * cost_per_million_tokens
                        self.estimated_cost += tokens_cost

                        logger.info(
                            f"Detected token usage: {tokens} tokens (total: {self.total_tokens}, estimated cost: ${self.estimated_cost:.4f})"
                        )

                        # Emit token usage update
                        await self._publish_update(
                            "token_usage_update",
                            {
                                "total_tokens": self.total_tokens,
                                "estimated_cost": self.estimated_cost,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            },
                        )

                # Check if this log line indicates a tool call was detected
                previous_tool_calls_count = len(self.execution_logger.mcp_usage_logs)
                if previous_tool_calls_count > self.tool_calls_count:
                    self.tool_calls_count = previous_tool_calls_count
                    logger.info(f"Tool call detected (total: {self.tool_calls_count})")

                    # Emit tool call count update
                    await self._publish_update(
                        "tool_calls_update",
                        {
                            "tool_calls": self.tool_calls_count,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                # Publish log line to NATS
                await self._publish_update(
                    "agent_log_line",
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "line": log_line,
                    },
                )

                # Update previous line for next iteration
                previous_line = log_line

            logger.info(
                f"Log streaming completed. Total logs streamed: {log_count}, tokens: {self.total_tokens}, tool calls: {self.tool_calls_count}"
            )

        except asyncio.CancelledError:
            logger.info(f"Log streaming cancelled for {session_reference}")
        except Exception as e:
            logger.error(
                f"Error streaming logs for {session_reference}: {e}", exc_info=True
            )
            await self._publish_update(
                "agent_log_error", {"error": f"Log streaming error: {str(e)}"}
            )

    async def _listen_for_commands(self):
        """
        Subscribe to NATS commands for user intervention.

        Listens on subject: flow-commands.{execution_id}
        """
        if not self.nats_client or not self.nats_client.is_connected:
            logger.warning("NATS not connected, cannot listen for commands")
            return

        command_subject = f"flow-commands.{self.execution_log.id}"

        try:

            async def command_handler(msg):
                try:
                    command_data = json.loads(msg.data.decode())
                    command_type = command_data.get("command")

                    logger.info(
                        f"Received command: {command_type} for execution {self.execution_log.id}"
                    )

                    if command_type == "stop":
                        logger.info("User requested stop")
                        self._stop_requested.set()
                    elif command_type == "send_message":
                        message = command_data.get("message", "")
                        logger.info(f"User sent message: {message}")
                        await self._user_messages.put(message)
                    elif command_type == "pause":
                        logger.info("User requested pause (not yet implemented)")
                        # TODO: Implement pause functionality
                    else:
                        logger.warning(f"Unknown command type: {command_type}")

                except Exception as e:
                    logger.error(f"Error handling command: {e}", exc_info=True)

            # Subscribe to commands
            self._command_subscription = await self.nats_client.subscribe(
                command_subject, cb=command_handler
            )
            logger.info(f"Listening for commands on {command_subject}")

        except Exception as e:
            logger.error(f"Failed to setup command subscription: {e}", exc_info=True)

    async def _cleanup_monitoring(self):
        """Cleanup monitoring resources (log streaming, command subscription)."""
        # Cancel log streaming task
        if self._log_streaming_task and not self._log_streaming_task.done():
            self._log_streaming_task.cancel()
            try:
                await self._log_streaming_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe from commands
        if self._command_subscription:
            try:
                await self._command_subscription.unsubscribe()
            except Exception as e:
                logger.error(f"Error unsubscribing from commands: {e}")

    async def _start_agent_session(
        self, execution_context: Dict[str, Any]
    ) -> tuple[str, Any]:
        """
        Launch an agent session via Agent Execution Infrastructure.

        Args:
            execution_context: Context for agent execution

        Returns:
            Tuple of (agent_session_reference, agent_executor)
            - agent_session_reference: Reference to the agent session (container ID, job ID, etc.)
            - agent_executor: The agent executor instance (caller must clean up)
        """
        agent_type = execution_context["agent_type"]
        agent_config = execution_context["agent_config"]

        logger.info(f"Starting {agent_type} agent session")

        agent_executor = None
        try:
            # Create agent executor using factory
            agent_executor = create_agent_executor(agent_type, agent_config)

            # Start the agent
            session_reference = await agent_executor.start(execution_context)

            logger.info(f"Agent session started: {session_reference}")
            # Return both session reference and executor (caller is responsible for cleanup)
            return session_reference, agent_executor

        except Exception as e:
            logger.error(f"Failed to start {agent_type} agent: {e}", exc_info=True)
            # Cleanup agent executor on failure
            if agent_executor:
                try:
                    await agent_executor.cleanup()
                except Exception as cleanup_error:
                    logger.warning(
                        f"Error during agent cleanup after failure: {cleanup_error}"
                    )
            raise

    async def _monitor_agent_execution(
        self, session_reference: str, agent_executor: Any
    ) -> Dict[str, Any]:
        """
        Monitor agent execution until completion with real-time log streaming.

        Args:
            session_reference: Reference to the agent session
            agent_executor: Agent executor instance to use for monitoring

        Returns:
            Dict with execution results including status, output, errors
        """
        logger.info(f"Monitoring agent execution {session_reference}")
        self.execution_logger.log_milestone(
            "agent_monitoring_started", {"session_reference": session_reference}
        )

        try:
            # Start listening for user commands
            await self._listen_for_commands()

            # Start background task for log streaming
            self._log_streaming_task = asyncio.create_task(
                self._stream_logs_to_nats(agent_executor, session_reference)
            )

            # Poll agent status until completion
            max_wait_time = 3600  # 1 hour max execution time
            poll_interval = 5  # Check status every 5 seconds
            elapsed = 0
            consecutive_failures = 0
            max_consecutive_failures = (
                3  # Fail after 3 consecutive status check failures
            )

            while elapsed < max_wait_time:
                # Check if user requested stop
                if self._stop_requested.is_set():
                    logger.info(
                        f"User requested stop for execution {self.execution_log.id}"
                    )
                    await agent_executor.stop(session_reference)
                    await self._publish_update("user_stopped", {"elapsed": elapsed})
                    break

                # Get status with error handling
                try:
                    status = await agent_executor.get_status(session_reference)
                    logger.debug(f"Agent status at {elapsed}s: {status.value}")
                    consecutive_failures = 0  # Reset failure counter on success
                except Exception as status_error:
                    logger.error(
                        f"Error getting agent status at {elapsed}s: {status_error}",
                        exc_info=True,
                    )
                    # Retry once after a short delay
                    await asyncio.sleep(2)
                    try:
                        status = await agent_executor.get_status(session_reference)
                        logger.info(f"Status check recovered: {status.value}")
                        consecutive_failures = 0  # Reset on successful retry
                    except Exception as retry_error:
                        logger.error(
                            f"Status check retry failed: {retry_error}",
                            exc_info=True,
                        )
                        consecutive_failures += 1

                        # Fail execution if too many consecutive failures
                        if consecutive_failures >= max_consecutive_failures:
                            logger.error(
                                f"Agent monitoring failed after {consecutive_failures} consecutive failures"
                            )
                            self.execution_logger.log_milestone(
                                "agent_monitoring_failed",
                                {"consecutive_failures": consecutive_failures},
                            )
                            return {
                                "status": "FAILED",
                                "error_message": f"Monitoring error: {str(retry_error)}",
                                "actions_taken": self.execution_logger.get_actions_taken(),
                                "mcp_usage_logs": self.execution_logger.get_mcp_usage_logs(),
                            }

                        # Continue polling for transient errors
                        await asyncio.sleep(poll_interval)
                        elapsed += poll_interval
                        continue

                # Publish status update (best effort - don't fail if NATS is down)
                try:
                    await self._publish_update(
                        "agent_status", {"status": status.value, "elapsed": elapsed}
                    )
                except Exception as publish_error:
                    logger.warning(f"Failed to publish status update: {publish_error}")

                if status in (
                    AgentStatus.SUCCEEDED,
                    AgentStatus.FAILED,
                    AgentStatus.STOPPED,
                ):
                    # Agent finished, get final result
                    logger.info(
                        f"Agent finished with status {status.value} at {elapsed}s"
                    )
                    result = await agent_executor.get_result(session_reference)

                    self.execution_logger.log_milestone(
                        "agent_execution_completed",
                        {"status": status.value, "exit_code": result.exit_code},
                    )

                    return {
                        "status": result.status.value,
                        "output_summary": result.output_summary,
                        "error_message": result.error_message,
                        "actions_taken": self.execution_logger.get_actions_taken(),
                        "mcp_usage_logs": self.execution_logger.get_mcp_usage_logs(),
                        "exit_code": result.exit_code,
                    }

                # Wait before next poll
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            # Timeout reached
            logger.warning(
                f"Agent execution {session_reference} timed out after {max_wait_time}s"
            )
            self.execution_logger.log_milestone("agent_execution_timeout")
            await agent_executor.stop(session_reference)

            return {
                "status": "FAILED",
                "error_message": f"Execution timed out after {max_wait_time} seconds",
                "actions_taken": self.execution_logger.get_actions_taken(),
                "mcp_usage_logs": self.execution_logger.get_mcp_usage_logs(),
            }

        except Exception as e:
            logger.error(
                f"Error monitoring agent execution {session_reference}: {e}",
                exc_info=True,
            )
            self.execution_logger.log_milestone(
                "agent_execution_error", {"error": str(e)}
            )
            return {
                "status": "FAILED",
                "error_message": f"Monitoring error: {str(e)}",
                "actions_taken": self.execution_logger.get_actions_taken(),
                "mcp_usage_logs": self.execution_logger.get_mcp_usage_logs(),
            }
        finally:
            # Always cleanup monitoring resources
            await self._cleanup_monitoring()
            # Cleanup agent executor resources (close Kubernetes/Docker clients)
            try:
                await agent_executor.cleanup()
            except Exception as cleanup_error:
                logger.warning(f"Error during agent cleanup: {cleanup_error}")

    def _create_execution_log(self):
        """Create an initial record in FlowExecutions."""
        logger.info("Creating initial execution log")

        # Ensure trigger_event_data is JSON serializable (convert UUIDs, datetimes, etc.)
        serializable_event_data = _make_json_serializable(self.trigger_event_data)

        execution_create = schemas.FlowExecutionCreate(
            flow_id=self.flow_id,
            status="PENDING",
            trigger_event_details=serializable_event_data,
            trigger_event_id=self.trigger_event_data.get("event_id"),
        )

        db_execution_log = crud_flow_execution.create(self.db, obj_in=execution_create)
        self.db.commit()
        self.db.refresh(db_execution_log)
        self.execution_log = db_execution_log

        logger.info(f"Execution log created with ID: {self.execution_log.id}")

    async def _update_execution_log(self, status: str, **kwargs):
        """Update the execution log and publish the update to NATS."""
        logger.info(f"Updating execution log to status: {status}")

        # Debug logging for metrics
        if "tool_calls_count" in kwargs or "total_tokens" in kwargs:
            logger.info(
                f"Updating execution metrics: tool_calls_count={kwargs.get('tool_calls_count')}, "
                f"total_tokens={kwargs.get('total_tokens')}, estimated_cost={kwargs.get('estimated_cost')}"
            )

        update_data = schemas.FlowExecutionUpdate(status=status, **kwargs)

        # Debug: Log what fields are actually in the update
        update_dict = update_data.model_dump(exclude_unset=True)
        logger.info(f"Update data fields: {list(update_dict.keys())}")
        if "tool_calls_count" in update_dict or "total_tokens" in update_dict:
            logger.info(
                f"Update dict metrics: tool_calls_count={update_dict.get('tool_calls_count')}, "
                f"total_tokens={update_dict.get('total_tokens')}, estimated_cost={update_dict.get('estimated_cost')}"
            )

        updated_log = crud_flow_execution.update(
            self.db, db_obj=self.execution_log, obj_in=update_data
        )
        self.db.commit()
        self.db.refresh(updated_log)
        self.execution_log = updated_log

        # Debug: Verify the values were actually set
        if "tool_calls_count" in kwargs or "total_tokens" in kwargs:
            logger.info(
                f"After update - DB values: tool_calls_count={updated_log.tool_calls_count}, "
                f"total_tokens={updated_log.total_tokens}, estimated_cost={updated_log.estimated_cost}"
            )

        # Publish update to NATS for real-time UI updates
        # Convert datetime objects to ISO format strings for JSON serialization
        serializable_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, datetime):
                serializable_kwargs[key] = value.isoformat()
            else:
                serializable_kwargs[key] = value

        await self._publish_update(
            "status_update", {"status": status, **serializable_kwargs}
        )

        logger.debug(f"Execution log updated: status={status}")

    async def run(self):
        """
        Execute the flow through its full lifecycle.

        Lifecycle stages:
        1. PENDING: Execution log created
        2. INITIALIZING: Flow and AI model details retrieved
        3. RUNNING: Agent session started
        4. SUCCEEDED/FAILED: Execution completed
        """
        try:
            # Stage 1: Retrieve flow details first (needed for account_id in messages)
            self._get_flow_details()

            # Stage 2: Create execution log
            self._create_execution_log()

            # Publish execution_started event for UI notification
            # This allows the flow executions list to update automatically
            await self._publish_update(
                "execution_started",
                {
                    "status": "PENDING",
                    "flow_id": str(self.flow_id),
                    "flow_name": self.flow.name if self.flow else None,
                },
            )

            await self._publish_update("status_update", {"status": "PENDING"})
            logger.info(f"Flow execution started: {self.execution_log.id}")

            # Stage 3: Mark as initializing
            await self._update_execution_log(status="INITIALIZING")

            # Stage 3: Prepare execution context
            execution_context = await self._prepare_execution_context()

            # Store resolved prompt for debugging/audit and mark as STARTING
            await self._update_execution_log(
                status="STARTING",
                resolved_input_prompt=execution_context["prompt"],
            )

            # Stage 4: Start agent session (returns both session reference and executor)
            session_reference, agent_executor = await self._start_agent_session(
                execution_context
            )

            # Agent started successfully - now mark as RUNNING with session reference
            await self._update_execution_log(
                status="RUNNING",
                agent_session_reference=session_reference,
            )

            # Stage 5: Monitor agent execution and collect results
            # Pass the executor so we don't create a duplicate instance
            agent_result = await self._monitor_agent_execution(
                session_reference, agent_executor
            )

            # Update execution log with final results including detailed logs
            final_status = agent_result.get("status", "FAILED")

            # Use output_summary from agent result, or fallback to stored logs
            output_summary = agent_result.get("output_summary")
            if not output_summary:
                logger.warning(
                    "Agent result has no output_summary, using stored logs as fallback"
                )
                output_summary = self.execution_logger.get_agent_output_summary()
                if output_summary:
                    logger.info(
                        f"Using stored logs for output_summary ({len(output_summary)} chars)"
                    )

            await self._update_execution_log(
                status=final_status,
                model_output_summary=output_summary,
                error_message=agent_result.get("error_message"),
                actions_taken_summary=agent_result.get("actions_taken"),
                mcp_usage_logs=agent_result.get("mcp_usage_logs"),
                end_time=datetime.now(timezone.utc),
                tool_calls_count=self.tool_calls_count,
                total_tokens=self.total_tokens,
                estimated_cost=self.estimated_cost,
            )

            logger.info(
                f"Flow execution completed with status {final_status}: {self.execution_log.id}"
            )

        except Exception as e:
            logger.error(
                f"Flow execution {self.execution_log.id if self.execution_log else 'unknown'} failed: {e}",
                exc_info=True,
            )

            if self.execution_log:
                try:
                    await self._update_execution_log(
                        status="FAILED",
                        error_message=str(e),
                        end_time=datetime.now(timezone.utc),
                        tool_calls_count=self.tool_calls_count,
                        total_tokens=self.total_tokens,
                        estimated_cost=self.estimated_cost,
                    )
                except Exception as update_error:
                    logger.error(
                        f"Failed to update execution log with error status: {update_error}",
                        exc_info=True,
                    )
            else:
                logger.error("Cannot update execution log - not created yet")
        finally:
            # Always cleanup the temporary API token
            self._cleanup_temporary_api_token()
