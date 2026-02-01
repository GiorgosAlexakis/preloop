import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, sessionmaker

from preloop.models.crud import crud_flow, crud_flow_execution
from preloop.models.models import Flow
from preloop.models.schemas.flow_execution import FlowExecutionCreate
from .flow_orchestrator import FlowExecutionOrchestrator
from preloop.sync.services.event_bus import get_nats_client
from preloop.models.db.session import get_session_factory

logger = logging.getLogger(__name__)


class FlowTriggerService:
    """
    Matches incoming tracker events against active Flow definitions and
    initiates the corresponding Flow Executions if needed.
    """

    def __init__(self, db: Session, session_factory: sessionmaker | None = None):
        self.db = db
        self.session_factory = session_factory or get_session_factory()

    def _create_orchestrator_session(self) -> Session:
        return self.session_factory()

    def _extract_resource_key(self, event_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract a unique resource identifier from the event payload.

        This is used for deduplication - events about the same resource
        (e.g., the same PR/MR) can be coalesced or skipped if an execution
        is already running.

        Returns:
            A unique key like "github:owner/repo:pr:123" or None if not extractable.
        """
        source = event_data.get("source", "").lower()
        payload = event_data.get("payload", {})

        if source == "github":
            # GitHub PR events
            pr = payload.get("pull_request", {})
            if pr:
                repo = payload.get("repository", {})
                repo_full_name = repo.get("full_name", "")
                pr_number = pr.get("number")
                if repo_full_name and pr_number:
                    return f"github:{repo_full_name}:pr:{pr_number}"

            # GitHub issue events
            issue = payload.get("issue", {})
            if issue:
                repo = payload.get("repository", {})
                repo_full_name = repo.get("full_name", "")
                issue_number = issue.get("number")
                if repo_full_name and issue_number:
                    return f"github:{repo_full_name}:issue:{issue_number}"

        elif source == "gitlab":
            # GitLab MR/issue events
            obj_attrs = payload.get("object_attributes", {})
            project = payload.get("project", {})
            project_path = project.get("path_with_namespace", "")

            if obj_attrs:
                iid = obj_attrs.get("iid")
                obj_kind = payload.get("object_kind", "")
                if project_path and iid:
                    return f"gitlab:{project_path}:{obj_kind}:{iid}"

        return None

    def _has_running_execution(
        self, flow_id: uuid.UUID, resource_key: str, account_id: str
    ) -> bool:
        """
        Check if there's already a running execution for the same flow and resource.

        Args:
            flow_id: The flow to check
            resource_key: The resource identifier (e.g., "github:owner/repo:pr:123")
            account_id: Account ID for scoping

        Returns:
            True if there's already a running execution for this flow+resource.
        """
        # Query specifically for running executions (no limit - we need all of them)
        # This ensures we don't miss long-running executions that might have
        # fallen outside a limit window
        executions = crud_flow_execution.get_running_by_flow(
            self.db,
            flow_id=flow_id,
            account_id=uuid.UUID(account_id)
            if isinstance(account_id, str)
            else account_id,
        )

        for execution in executions:
            # Check if the trigger_event_details contain the same resource
            trigger_details = execution.trigger_event_details or {}
            exec_payload = trigger_details.get("payload", {})

            # Extract resource key from the execution's trigger event
            exec_event_data = {
                "source": trigger_details.get("source", ""),
                "payload": exec_payload,
            }
            exec_resource_key = self._extract_resource_key(exec_event_data)

            if exec_resource_key == resource_key:
                logger.info(
                    f"Found running execution {execution.id} for flow {flow_id} "
                    f"and resource {resource_key} (status: {execution.status})"
                )
                return True

        return False

    def _extract_commit_sha(self, event_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the commit SHA from the event data.

        Looks for commit SHA in common locations for different event types.
        """
        payload = event_data.get("payload", {})

        # Ensure payload is a dict
        if not isinstance(payload, dict):
            return None

        # GitHub push event
        # Note: head_commit can be None for branch deletions
        head_commit = payload.get("head_commit")
        if head_commit and isinstance(head_commit, dict):
            sha = head_commit.get("id")
            if sha:
                return sha

        # GitHub/GitLab pull request / merge request events
        object_attrs = payload.get("object_attributes", {})
        if object_attrs and isinstance(object_attrs, dict):
            # GitLab MR - last_commit (can be None)
            last_commit = object_attrs.get("last_commit")
            if last_commit and isinstance(last_commit, dict):
                sha = last_commit.get("id")
                if sha:
                    return sha
            # GitLab MR - sha
            if "sha" in object_attrs:
                sha = object_attrs["sha"]
                if sha:
                    return sha

        # GitHub PR event
        pr = payload.get("pull_request")
        if pr and isinstance(pr, dict):
            head = pr.get("head")
            if head and isinstance(head, dict):
                sha = head.get("sha")
                if sha:
                    return sha

        # Direct commit reference
        if "commit" in payload:
            commit = payload["commit"]
            if isinstance(commit, dict):
                sha = commit.get("sha") or commit.get("id")
                if sha:
                    return sha

        # Top-level sha
        if "sha" in payload:
            return payload["sha"]

        # Push events - after field
        if "after" in payload:
            return payload["after"]

        return None

    def _has_execution_for_commit(
        self, flow_id: uuid.UUID, commit_sha: str, account_id: str
    ) -> bool:
        """
        Check if there's already an execution (running or recent) for this commit.

        This prevents duplicate executions when multiple events are triggered
        for the same commit (e.g., push + PR description update).

        Args:
            flow_id: The flow to check
            commit_sha: The commit SHA to check
            account_id: Account ID for scoping

        Returns:
            True if there's already an execution for this commit.
        """
        # Query for executions of this flow
        executions = crud_flow_execution.get_running_by_flow(
            self.db,
            flow_id=flow_id,
            account_id=uuid.UUID(account_id)
            if isinstance(account_id, str)
            else account_id,
        )

        for execution in executions:
            trigger_details = execution.trigger_event_details or {}
            exec_sha = self._extract_commit_sha(trigger_details)

            if exec_sha and exec_sha == commit_sha:
                logger.info(
                    f"Found running execution {execution.id} for flow {flow_id} "
                    f"and commit {commit_sha[:8]} (status: {execution.status})"
                )
                return True

        return False

    async def _run_orchestrator_with_session(
        self,
        flow: Flow,
        event_data: Dict[str, Any],
        nats_client,
    ) -> None:
        orchestrator_db = self._create_orchestrator_session()
        try:
            orchestrator = FlowExecutionOrchestrator(
                orchestrator_db,
                flow_id=flow.id,
                trigger_event_data=event_data,
                nats_client=nats_client,
            )
            await orchestrator.run()
        finally:
            orchestrator_db.close()

    def _matches_trigger_config(self, flow: Flow, event_data: Dict[str, Any]) -> bool:
        """
        Check if the event matches the flow's trigger_config (if specified).

        Args:
            flow: The flow definition
            event_data: The event data containing payload and metadata

        Returns:
            True if the event matches the trigger config, False otherwise
        """
        if not flow.trigger_config:
            # No additional conditions, event matches
            return True

        # trigger_config can contain conditions like:
        # {"branch": "main"} - for commit events
        # {"labels": ["bug", "critical"]} - for issue events
        # {"status": "opened"} - for PR events
        # {"assignee": "username"} - for assignee filter
        # {"reviewer": "username"} - for reviewer filter
        #
        # For backward compatibility, also support nested filter_conditions:
        # {"assignee": "user", "filter_conditions": {"labels": [...]}}

        payload = event_data.get("payload", {})

        # Flatten trigger_config if it has filter_conditions wrapper
        flattened_config = {}
        for key, value in flow.trigger_config.items():
            if key == "filter_conditions" and isinstance(value, dict):
                # Unpack filter_conditions into top-level
                flattened_config.update(value)
            else:
                flattened_config[key] = value

        logger.info(
            f"Flow {flow.id} ({flow.name}): Checking trigger_config. "
            f"Original: {flow.trigger_config}, Flattened: {flattened_config}, "
            f"Payload keys: {list(payload.keys())}"
        )

        for key, expected_value in flattened_config.items():
            actual_value = payload.get(key)

            # Handle None/missing values
            if actual_value is None:
                logger.debug(
                    f"Flow {flow.id} trigger_config mismatch: "
                    f"{key} not present in payload"
                )
                return False

            if isinstance(expected_value, list):
                # Expected value is a list - check if any expected value matches actual value(s)
                if isinstance(actual_value, list):
                    # Both are lists - check if any expected value is in actual values
                    if not any(item in actual_value for item in expected_value):
                        logger.debug(
                            f"Flow {flow.id} trigger_config mismatch: "
                            f"none of {expected_value} found in {actual_value}"
                        )
                        return False
                else:
                    # Expected is list, actual is single value - check if actual is in expected
                    if actual_value not in expected_value:
                        logger.debug(
                            f"Flow {flow.id} trigger_config mismatch: "
                            f"{key}={actual_value} not in {expected_value}"
                        )
                        return False
            else:
                # Expected value is a single value
                if isinstance(actual_value, list):
                    # Actual is a list - check if expected value is in the list
                    if expected_value not in actual_value:
                        logger.debug(
                            f"Flow {flow.id} trigger_config mismatch: "
                            f"{key}: '{expected_value}' not in {actual_value}"
                        )
                        return False
                else:
                    # Both are single values - exact match required
                    if actual_value != expected_value:
                        logger.debug(
                            f"Flow {flow.id} trigger_config mismatch: "
                            f"{key}={actual_value} != {expected_value}"
                        )
                        return False

        return True

    def _is_preloop_triggered_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Check if an event was triggered by Preloop's own actions.

        This prevents infinite loops where:
        1. Flow runs and updates a PR (adds comment, modifies body, etc.)
        2. Update triggers a new webhook event (pull_request_updated, comment_created)
        3. Event matches another flow -> triggers another execution
        4. Repeat forever

        We detect Preloop-triggered events by checking the sender/actor field
        in the webhook payload for known Preloop bot usernames.
        """
        payload = event_data.get("payload", {})
        source = event_data.get("source", "").lower()

        # Get the sender/actor who triggered the event
        sender = None
        if source == "github":
            sender_obj = payload.get("sender", {})
            sender = sender_obj.get("login", "").lower() if sender_obj else ""
        elif source == "gitlab":
            # GitLab uses "user" for the actor in most events
            user_obj = payload.get("user", {})
            sender = user_obj.get("username", "").lower() if user_obj else ""
            # Some events have object_attributes.author
            if not sender:
                obj_attrs = payload.get("object_attributes", {})
                author = obj_attrs.get("author", {})
                if isinstance(author, dict):
                    sender = author.get("username", "").lower()

        if not sender:
            return False

        # Known Preloop bot username patterns
        # These are typically the usernames of GitHub Apps or GitLab service accounts
        # that Preloop uses to interact with trackers
        preloop_patterns = [
            "preloop",
            "preloop-bot",
            "preloop-staging",
            "preloop-dev",
            "preloop[bot]",  # GitHub App format
            "preloop-app",
        ]

        for pattern in preloop_patterns:
            if sender == pattern or sender.startswith("preloop"):
                logger.info(
                    f"Ignoring event triggered by Preloop bot account: {sender}"
                )
                return True

        return False

    async def process_event(self, event_data: Dict[str, Any]):
        """
        Process an incoming event and trigger any matching flows.

        Args:
            event_data: Dictionary containing:
                - source: Event source (e.g., 'github', 'gitlab', 'jira')
                - type: Event type (e.g., 'push', 'issue_created')
                - payload: Event payload from the tracker
                - account_id: Account ID for scoping
        """
        event_source = event_data.get("source")
        event_type = event_data.get("type")
        account_id = event_data.get("account_id")

        if not event_source or not event_type:
            logger.warning(
                f"Event data is missing required fields: source={event_source}, type={event_type}"
            )
            return

        # Check if this event was triggered by Preloop itself to prevent infinite loops
        if self._is_preloop_triggered_event(event_data):
            logger.info(
                f"Skipping event triggered by Preloop bot to prevent infinite loop: "
                f"source='{event_source}', type='{event_type}'"
            )
            return

        logger.info(
            f"Processing event from source='{event_source}', type='{event_type}', "
            f"account_id={account_id}"
        )

        try:
            # Query for flows that match the event source and type
            matching_flows: List[Flow] = crud_flow.get_by_trigger(
                self.db,
                event_source=event_source,
                event_type=event_type,
                account_id=account_id,
            )

            if not matching_flows:
                logger.warning(
                    f"No flows found matching source='{event_source}', type='{event_type}', account_id={account_id}. "
                    f"Check that flows are configured with the correct tracker ID as trigger_event_source."
                )
                return

            logger.info(f"Found {len(matching_flows)} potential matching flow(s)")

            # Filter flows by trigger_config and enabled status
            flows_to_trigger = []
            for flow in matching_flows:
                if not flow.is_enabled:
                    logger.warning(
                        f"Skipping disabled flow '{flow.name}' ({flow.id}). "
                        f"To enable this flow, set is_enabled=true via the API or UI."
                    )
                    continue

                if not self._matches_trigger_config(flow, event_data):
                    logger.info(
                        f"Skipping flow '{flow.name}' ({flow.id}) - trigger_config does not match. "
                        f"Config: {flow.trigger_config}"
                    )
                    continue

                flows_to_trigger.append(flow)

            if not flows_to_trigger:
                logger.info("No enabled flows with matching trigger_config found")
                return

            # Get NATS client for publishing updates
            nats_client = await get_nats_client()

            # Extract resource key for deduplication
            resource_key = self._extract_resource_key(event_data)
            if resource_key:
                logger.info(f"Extracted resource key for deduplication: {resource_key}")

            # Extract commit SHA for deduplication
            commit_sha = self._extract_commit_sha(event_data)
            if commit_sha:
                logger.info(f"Extracted commit SHA for deduplication: {commit_sha[:8]}")

            # Trigger each matching flow
            for flow in flows_to_trigger:
                try:
                    # Check for running execution on the same resource
                    if resource_key and account_id:
                        if self._has_running_execution(
                            flow.id, resource_key, account_id
                        ):
                            logger.info(
                                f"Skipping flow '{flow.name}' ({flow.id}) - "
                                f"already has a running execution for resource {resource_key}. "
                                f"To avoid duplicate executions, events about the same resource "
                                f"are not processed while an execution is in progress."
                            )
                            continue

                    # Check for running execution with the same commit SHA
                    # This catches cases where multiple events are triggered for the same
                    # commit (e.g., push event + PR update when description is edited)
                    if commit_sha and account_id:
                        if self._has_execution_for_commit(
                            flow.id, commit_sha, account_id
                        ):
                            logger.info(
                                f"Skipping flow '{flow.name}' ({flow.id}) - "
                                f"already has a running execution for commit {commit_sha[:8]}. "
                                f"This prevents duplicate executions when multiple events "
                                f"are triggered for the same commit."
                            )
                            continue

                    logger.info(
                        f"Triggering flow '{flow.name}' ({flow.id}) for event {event_type}"
                    )
                    # Launch orchestrator using a fresh DB session so it isn't tied
                    # to the request lifecycle (webhooks close the request session
                    # immediately after returning a response).
                    event_copy = dict(event_data)
                    asyncio.create_task(
                        self._run_orchestrator_with_session(
                            flow=flow,
                            event_data=event_copy,
                            nats_client=nats_client,
                        )
                    )
                    logger.info(f"Flow '{flow.name}' ({flow.id}) execution initiated")
                except Exception as e:
                    logger.error(
                        f"Error initiating flow '{flow.name}' ({flow.id}): {e}",
                        exc_info=True,
                    )

        except Exception as e:
            logger.error(
                f"Error processing event source='{event_source}', type='{event_type}': {e}",
                exc_info=True,
            )

    async def trigger_flow(
        self,
        flow_id: uuid.UUID,
        test_mode: bool = False,
        trigger_event_data: Optional[Dict[str, Any]] = None,
        retry_of_execution_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Manually trigger a flow execution for testing purposes or as a retry.

        Args:
            flow_id: The ID of the flow to trigger
            test_mode: Whether this is a test execution
            trigger_event_data: Optional custom trigger event data for testing
            retry_of_execution_id: If this is a retry, the ID of the original execution

        Returns:
            Dict with execution_id and status
        """
        # Get the flow
        flow_id_str = str(flow_id)
        # Use CRUD layer without account filtering for test mode
        flow = crud_flow.get(self.db, id=flow_id_str)

        if not flow:
            raise ValueError(f"Flow {flow_id} not found")

        if retry_of_execution_id:
            logger.info(
                f"Triggering retry execution for flow '{flow.name}' ({flow.id}), "
                f"retrying execution {retry_of_execution_id}"
            )
        else:
            logger.info(f"Triggering test execution for flow '{flow.name}' ({flow.id})")

        # Pre-create the execution record so we can return its ID immediately
        # Merge test_mode flag with custom trigger_event_data if provided
        trigger_details = {"test_mode": test_mode}
        if trigger_event_data:
            trigger_details.update(trigger_event_data)

        execution_data = FlowExecutionCreate(
            flow_id=flow_id,
            status="PENDING",
            trigger_event_details=trigger_details,
            retry_of_execution_id=retry_of_execution_id,
        )

        execution = crud_flow_execution.create(self.db, obj_in=execution_data)
        self.db.commit()
        self.db.refresh(execution)

        execution_id = execution.id
        execution_status = execution.status

        logger.info(f"Created flow execution: {execution_id}")

        # Get NATS client
        nats_client = await get_nats_client()

        # Create a new database session for the orchestrator to avoid session conflicts
        from preloop.models.db.session import get_db_session

        # Get new session for orchestrator
        orchestrator_db = next(get_db_session())

        try:
            # Get the execution in the new session using CRUD layer
            exec_in_new_session = crud_flow_execution.get(
                orchestrator_db, id=execution_id
            )

            if not exec_in_new_session:
                raise ValueError(
                    f"Failed to retrieve execution {execution_id} in new session"
                )

            orchestrator = FlowExecutionOrchestrator(
                orchestrator_db,
                flow_id=uuid.UUID(flow.id) if isinstance(flow.id, str) else flow.id,
                trigger_event_data=trigger_details,
                nats_client=nats_client,
            )

            # Set the pre-created execution log
            orchestrator.execution_log = exec_in_new_session

            # Start execution in background (skip execution log creation since we already have it)
            asyncio.create_task(self._run_orchestrator_without_creation(orchestrator))

            # Return the execution info
            return {
                "id": str(execution_id),
                "status": execution_status,
                "flow_id": flow_id_str,
            }
        except Exception as e:
            logger.error(f"Failed to start orchestrator: {e}", exc_info=True)
            orchestrator_db.close()
            raise

    async def _run_orchestrator_without_creation(self, orchestrator):
        """Run orchestrator starting from stage 2 (skip execution log creation)."""
        try:
            # Retrieve flow details first (needed for account_id in messages)
            orchestrator._get_flow_details()

            # Publish execution_started event for UI notification
            await orchestrator._publish_update(
                "execution_started",
                {
                    "status": "PENDING",
                    "flow_id": str(orchestrator.flow_id),
                    "flow_name": orchestrator.flow.name if orchestrator.flow else None,
                },
            )

            await orchestrator._update_execution_log(status="INITIALIZING")

            # Stage 3: Prepare execution context
            execution_context = await orchestrator._prepare_execution_context()

            # Store resolved prompt
            await orchestrator._update_execution_log(
                status="RUNNING",
                resolved_input_prompt=execution_context["prompt"],
            )

            # Stage 4: Start agent session (returns session reference and executor)
            session_reference, agent_executor = await orchestrator._start_agent_session(
                execution_context
            )

            # Update with session reference
            await orchestrator._update_execution_log(
                status="RUNNING",
                agent_session_reference=session_reference,
            )

            # Stage 5: Monitor agent execution (pass the executor to avoid creating duplicate)
            agent_result = await orchestrator._monitor_agent_execution(
                session_reference, agent_executor
            )

            # Update with final results
            from datetime import datetime, timezone

            final_status = agent_result.get("status", "FAILED")
            await orchestrator._update_execution_log(
                status=final_status,
                model_output_summary=agent_result.get("output_summary"),
                error_message=agent_result.get("error_message"),
                actions_taken_summary=agent_result.get("actions_taken"),
                mcp_usage_logs=agent_result.get("mcp_usage_logs"),
                end_time=datetime.now(timezone.utc),
            )

            logger.info(f"Flow execution completed: {orchestrator.execution_log.id}")

        except Exception as e:
            logger.error(f"Flow execution failed: {e}", exc_info=True)
            from datetime import datetime, timezone

            if orchestrator.execution_log:
                try:
                    await orchestrator._update_execution_log(
                        status="FAILED",
                        error_message=str(e),
                        end_time=datetime.now(timezone.utc),
                    )
                except Exception as update_error:
                    logger.error(f"Failed to update execution log: {update_error}")
        finally:
            orchestrator._cleanup_temporary_api_token()
