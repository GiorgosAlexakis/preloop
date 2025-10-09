import logging
import uuid
import json
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import re

from sqlalchemy.orm import Session
from nats.aio.client import Client

from spacemodels import schemas
from spacemodels.crud import crud_flow_execution
from spacemodels.models.flow import Flow
from spacemodels.models.ai_model import AIModel
from spacebridge.agents import create_agent_executor, AgentStatus
from spacebridge.services.prompt_resolvers import (
    resolver_registry,
    ResolverContext,
    TriggerEventResolver,
    ProjectResolver,
    AccountResolver,
)
from spacebridge.services.flow_execution_logger import FlowExecutionLogger

logger = logging.getLogger(__name__)


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

    async def _publish_update(self, message_type: str, payload: Dict[str, Any]):
        """Publishes a structured message to the NATS stream for real-time updates."""
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
        self.flow = self.db.query(Flow).filter(Flow.id == flow_id_str).first()
        if not self.flow:
            raise ValueError(f"Flow with id {self.flow_id} not found")

        logger.info(
            f"Found flow: {self.flow.name} (agent_type: {self.flow.agent_type})"
        )

        # Get AI model if specified
        if self.flow.ai_model_id:
            from sqlalchemy import cast, String

            ai_model_id_str = (
                str(self.flow.ai_model_id)
                if isinstance(self.flow.ai_model_id, uuid.UUID)
                else self.flow.ai_model_id
            )
            self.ai_model = (
                self.db.query(AIModel)
                .filter(cast(AIModel.id, String) == ai_model_id_str)
                .first()
            )
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
        from spacemodels.models import Account, ApiKey

        try:
            account = (
                self.db.query(Account)
                .filter(Account.id == self.flow.account_id)
                .first()
            )

            if not account:
                logger.warning(f"Account {self.flow.account_id} not found")
                return None, None

            # Generate a secure random token
            token_key = f"flow_{secrets.token_urlsafe(32)}"

            # Create API key that expires in 2 hours
            expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

            api_key = ApiKey(
                name=f"Flow Execution {self.execution_log.id if self.execution_log else 'temp'}",
                key=token_key,
                created_by=account.username,
                expires_at=expires_at,
                is_active=True,
                scopes=["mcp:read", "mcp:write"],  # Limited scopes for MCP access
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
            from spacemodels.models import ApiKey

            api_key = (
                self.db.query(ApiKey)
                .filter(ApiKey.id == self.temporary_api_key_id)
                .first()
            )

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
            "execution_id": str(self.execution_log.id),
            "prompt": resolved_prompt,
            "agent_type": self.flow.agent_type,
            "agent_config": self.flow.agent_config,
            "allowed_mcp_servers": self.flow.allowed_mcp_servers,
            "allowed_mcp_tools": self.flow.allowed_mcp_tools,
            "account_id": self.flow.account_id,
            "account_api_token": account_api_token,
        }

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

        try:
            async for log_line in agent_executor.stream_logs(session_reference):
                # Parse log line for structured data
                self.execution_logger.parse_agent_logs([log_line])

                # Publish to NATS
                await self._publish_update(
                    "agent_log_line",
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "line": log_line,
                    },
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

    async def _start_agent_session(self, execution_context: Dict[str, Any]) -> str:
        """
        Launch an agent session via Agent Execution Infrastructure.

        Args:
            execution_context: Context for agent execution

        Returns:
            agent_session_reference: Reference to the agent session (container ID, job ID, etc.)
        """
        agent_type = execution_context["agent_type"]
        agent_config = execution_context["agent_config"]

        logger.info(f"Starting {agent_type} agent session")

        try:
            # Create agent executor using factory
            agent_executor = create_agent_executor(agent_type, agent_config)

            # Start the agent
            session_reference = await agent_executor.start(execution_context)

            logger.info(f"Agent session started: {session_reference}")
            return session_reference

        except Exception as e:
            logger.error(f"Failed to start {agent_type} agent: {e}", exc_info=True)
            raise

    async def _monitor_agent_execution(self, session_reference: str) -> Dict[str, Any]:
        """
        Monitor agent execution until completion with real-time log streaming.

        Args:
            session_reference: Reference to the agent session

        Returns:
            Dict with execution results including status, output, errors
        """
        agent_type = self.flow.agent_type
        agent_config = self.flow.agent_config

        logger.info(f"Monitoring agent execution {session_reference}")
        self.execution_logger.log_milestone(
            "agent_monitoring_started", {"session_reference": session_reference}
        )

        # Create agent executor to monitor the session
        agent_executor = create_agent_executor(agent_type, agent_config)

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

            while elapsed < max_wait_time:
                # Check if user requested stop
                if self._stop_requested.is_set():
                    logger.info(
                        f"User requested stop for execution {self.execution_log.id}"
                    )
                    await agent_executor.stop(session_reference)
                    await self._publish_update("user_stopped", {"elapsed": elapsed})
                    break
                status = await agent_executor.get_status(session_reference)

                # Publish status update
                await self._publish_update(
                    "agent_status", {"status": status.value, "elapsed": elapsed}
                )

                if status in (
                    AgentStatus.SUCCEEDED,
                    AgentStatus.FAILED,
                    AgentStatus.STOPPED,
                ):
                    # Agent finished, get final result
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

    def _create_execution_log(self):
        """Create an initial record in FlowExecutions."""
        logger.info("Creating initial execution log")

        execution_create = schemas.FlowExecutionCreate(
            flow_id=self.flow_id,
            status="PENDING",
            trigger_event_details=self.trigger_event_data,
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

        update_data = schemas.FlowExecutionUpdate(status=status, **kwargs)
        updated_log = crud_flow_execution.update(
            self.db, db_obj=self.execution_log, obj_in=update_data
        )
        self.db.commit()
        self.db.refresh(updated_log)
        self.execution_log = updated_log

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
            # Stage 1: Create execution log
            self._create_execution_log()
            await self._publish_update("status_update", {"status": "PENDING"})
            logger.info(f"Flow execution started: {self.execution_log.id}")

            # Stage 2: Retrieve flow and AI model details
            self._get_flow_details()
            await self._update_execution_log(status="INITIALIZING")

            # Stage 3: Prepare execution context
            execution_context = await self._prepare_execution_context()

            # Store resolved prompt for debugging/audit
            await self._update_execution_log(
                status="RUNNING",
                resolved_input_prompt=execution_context["prompt"],
            )

            # Stage 4: Start agent session
            session_reference = await self._start_agent_session(execution_context)

            # Update with session reference
            await self._update_execution_log(
                status="RUNNING",
                agent_session_reference=session_reference,
            )

            # Stage 5: Monitor agent execution and collect results
            agent_result = await self._monitor_agent_execution(session_reference)

            # Update execution log with final results including detailed logs
            final_status = agent_result.get("status", "FAILED")
            await self._update_execution_log(
                status=final_status,
                model_output_summary=agent_result.get("output_summary"),
                error_message=agent_result.get("error_message"),
                actions_taken_summary=agent_result.get("actions_taken"),
                mcp_usage_logs=agent_result.get("mcp_usage_logs"),
                end_time=datetime.now(timezone.utc),
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
