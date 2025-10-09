import logging
import asyncio
import uuid
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from spacemodels.crud import crud_flow, crud_flow_execution
from spacemodels.models import Flow, FlowExecution
from spacemodels.schemas.flow_execution import FlowExecutionCreate
from .flow_orchestrator import FlowExecutionOrchestrator
from spacesync.services.event_bus import get_nats_client

logger = logging.getLogger(__name__)


class FlowTriggerService:
    """
    Matches incoming tracker events against active Flow definitions and
    initiates the corresponding Flow Executions if needed.
    """

    def __init__(self, db: Session):
        self.db = db

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

        payload = event_data.get("payload", {})

        for key, expected_value in flow.trigger_config.items():
            actual_value = payload.get(key)

            if isinstance(expected_value, list):
                # For list conditions, check if any value matches
                if not actual_value or not any(
                    item in actual_value
                    if isinstance(actual_value, list)
                    else item == actual_value
                    for item in expected_value
                ):
                    logger.debug(
                        f"Flow {flow.id} trigger_config mismatch: "
                        f"{key}={actual_value} not in {expected_value}"
                    )
                    return False
            else:
                # For single value conditions, exact match required
                if actual_value != expected_value:
                    logger.debug(
                        f"Flow {flow.id} trigger_config mismatch: "
                        f"{key}={actual_value} != {expected_value}"
                    )
                    return False

        return True

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
                logger.debug(
                    f"No flows found matching source='{event_source}', type='{event_type}'"
                )
                return

            logger.info(f"Found {len(matching_flows)} potential matching flow(s)")

            # Filter flows by trigger_config and enabled status
            flows_to_trigger = []
            for flow in matching_flows:
                if not flow.is_enabled:
                    logger.debug(f"Skipping disabled flow '{flow.name}' ({flow.id})")
                    continue

                if not self._matches_trigger_config(flow, event_data):
                    logger.debug(
                        f"Skipping flow '{flow.name}' ({flow.id}) - trigger_config does not match"
                    )
                    continue

                flows_to_trigger.append(flow)

            if not flows_to_trigger:
                logger.info("No enabled flows with matching trigger_config found")
                return

            # Get NATS client for publishing updates
            nats_client = await get_nats_client()

            # Trigger each matching flow
            for flow in flows_to_trigger:
                try:
                    logger.info(
                        f"Triggering flow '{flow.name}' ({flow.id}) for event {event_type}"
                    )
                    orchestrator = FlowExecutionOrchestrator(
                        self.db,
                        flow_id=flow.id,
                        trigger_event_data=event_data,
                        nats_client=nats_client,
                    )
                    # Create async task to run orchestrator without blocking
                    asyncio.create_task(orchestrator.run())
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
        self, flow_id: uuid.UUID, test_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Manually trigger a flow execution for testing purposes.

        Args:
            flow_id: The ID of the flow to trigger
            test_mode: Whether this is a test execution

        Returns:
            Dict with execution_id and status
        """
        # Get the flow
        flow_id_str = str(flow_id)
        flow = crud_flow.get(self.db, id=flow_id_str, account_id="")
        if not flow:
            # Try without account_id filter for test mode
            flow = self.db.query(Flow).filter(Flow.id == flow_id_str).first()

        if not flow:
            raise ValueError(f"Flow {flow_id} not found")

        logger.info(f"Triggering test execution for flow '{flow.name}' ({flow.id})")

        # Pre-create the execution record so we can return its ID immediately
        execution_data = FlowExecutionCreate(
            flow_id=flow_id,
            status="PENDING",
            trigger_event_details={"test_mode": test_mode},
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
        from spacemodels.db.session import get_db_session

        # Get new session for orchestrator
        orchestrator_db = next(get_db_session())

        try:
            # Get the execution in the new session
            exec_in_new_session = (
                orchestrator_db.query(FlowExecution)
                .filter(FlowExecution.id == execution_id)
                .first()
            )

            if not exec_in_new_session:
                raise ValueError(
                    f"Failed to retrieve execution {execution_id} in new session"
                )

            orchestrator = FlowExecutionOrchestrator(
                orchestrator_db,
                flow_id=uuid.UUID(flow.id) if isinstance(flow.id, str) else flow.id,
                trigger_event_data={"test_mode": test_mode},
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
            # Stage 2: Retrieve flow and AI model details
            orchestrator._get_flow_details()
            await orchestrator._update_execution_log(status="INITIALIZING")

            # Stage 3: Prepare execution context
            execution_context = await orchestrator._prepare_execution_context()

            # Store resolved prompt
            await orchestrator._update_execution_log(
                status="RUNNING",
                resolved_input_prompt=execution_context["prompt"],
            )

            # Stage 4: Start agent session
            session_reference = await orchestrator._start_agent_session(
                execution_context
            )

            # Update with session reference
            await orchestrator._update_execution_log(
                status="RUNNING",
                agent_session_reference=session_reference,
            )

            # Stage 5: Monitor agent execution
            agent_result = await orchestrator._monitor_agent_execution(
                session_reference
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
