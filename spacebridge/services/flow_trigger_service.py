import logging
import asyncio
from typing import Any, Dict

from sqlalchemy.orm import Session

from spacemodels.crud import crud_flow
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

    async def process_event(self, event_data: Dict[str, Any]):
        """
        Process an incoming event and trigger any matching flows.
        """
        event_source = event_data.get("source")
        event_type = event_data.get("type")

        if not event_source or not event_type:
            logger.warning("Event data is missing source or type")
            return

        logger.info(
            f"Processing event from source '{event_source}' with type '{event_type}'"
        )

        matching_flows = crud_flow.get_by_trigger(
            self.db,
            event_source=event_source,
            event_type=event_type,
            account_id=event_data.get("account_id"),
        )

        if not matching_flows:
            return

        nats_client = await get_nats_client()

        for flow in matching_flows:
            if flow.is_enabled:
                logger.info(f"Triggering flow {flow.name} ({flow.id})")
                orchestrator = FlowExecutionOrchestrator(
                    self.db,
                    flow_id=flow.id,
                    trigger_event_data=event_data,
                    nats_client=nats_client,
                )
                asyncio.create_task(orchestrator.run())
            else:
                logger.info(f"Skipping disabled flow {flow.name} ({flow.id})")
