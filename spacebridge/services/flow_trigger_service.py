import logging
import asyncio
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from spacemodels.crud import crud_flow
from spacemodels.models import Flow
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
