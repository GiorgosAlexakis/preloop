import logging
import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session
from nats.aio.client import Client

from spacemodels import crud, schemas
from spacemodels.models.flow import Flow
from spacesync.services.event_bus import get_nats_client

logger = logging.getLogger(__name__)


class FlowExecutionOrchestrator:
    """Manages the end-to-end lifecycle of a single Flow invocation."""

    def __init__(
        self, db: Session, flow_id: uuid.UUID, trigger_event_data: Dict[str, Any]
    ):
        self.db = db
        self.flow_id = flow_id
        self.trigger_event_data = trigger_event_data
        self.flow: Flow = None
        self.execution_log: schemas.FlowExecution = None
        self.nats_client: Client = get_nats_client()

    async def _publish_update(self, message_type: str, payload: Dict[str, Any]):
        """Publishes a structured message to the NATS stream."""
        if not self.nats_client or not self.nats_client.is_connected:
            logger.warning("NATS client not available, skipping update publish.")
            return

        message = {
            "execution_id": str(self.execution_log.id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": message_type,
            "payload": payload,
        }
        subject = f"flow-updates.{self.execution_log.id}"
        await self.nats_client.publish(subject, json.dumps(message).encode())
        logger.info(f"Published message to NATS subject '{subject}': {message_type}")

    def _get_flow_details(self):
        """Retrieve the Flow definition and associated AIModel."""
        logger.info(f"Retrieving flow details for flow_id: {self.flow_id}")
        self.flow = crud.flow.get(self.db, id=self.flow_id)
        if not self.flow:
            raise ValueError(f"Flow with id {self.flow_id} not found")

    def _resolve_prompt(self) -> str:
        """Resolve dynamic placeholders in the prompt template."""
        logger.info("Resolving prompt template")
        # This is a placeholder for the prompt resolution logic
        return self.flow.prompt_template.format(**self.trigger_event_data)

    def _prepare_execution_context(self) -> Dict[str, Any]:
        """Prepare the full execution context for OpenHands."""
        logger.info("Preparing execution context")
        resolved_prompt = self._resolve_prompt()
        # This is a placeholder for the execution context preparation logic
        return {
            "prompt": resolved_prompt,
            "model": self.flow.ai_model.model_identifier,
            "api_key": self.flow.ai_model.api_key,
            "agent_config": self.flow.openhands_agent_config,
            "mcp_servers": self.flow.allowed_mcp_servers,
            "mcp_tools": self.flow.allowed_mcp_tools,
        }

    def _start_openhands_session(self, execution_context: Dict[str, Any]):
        """Launch and monitor an OpenHands agent session."""
        logger.info("Starting OpenHands agent session")
        # This is a placeholder for the OpenHands integration logic
        pass

    def _create_execution_log(self):
        """Create an initial record in FlowExecutions."""
        logger.info("Creating initial execution log")
        self.execution_log = schemas.FlowExecutionCreate(
            flow_id=self.flow_id,
            status="PENDING",
            trigger_event_details=self.trigger_event_data,
        )
        db_execution_log = crud.flow_execution.create(
            self.db, obj_in=self.execution_log
        )
        self.db.refresh(db_execution_log)
        self.execution_log = db_execution_log

    async def _update_execution_log(self, status: str, **kwargs):
        """Update the execution log and publish the update to NATS."""
        logger.info(f"Updating execution log with status: {status}")
        update_data = schemas.FlowExecutionUpdate(status=status, **kwargs)
        crud.flow_execution.update(
            self.db, db_obj=self.execution_log, obj_in=update_data
        )
        await self._publish_update("status_update", {"status": status, **kwargs})

    async def run(self):
        """Execute the flow."""
        try:
            self._create_execution_log()
            await self._publish_update("status_update", {"status": "PENDING"})
            self._get_flow_details()
            await self._update_execution_log(status="INITIALIZING")
            execution_context = self._prepare_execution_context()
            await self._update_execution_log(status="RUNNING")
            self._start_openhands_session(execution_context)
            await self._update_execution_log(status="SUCCEEDED")
        except Exception as e:
            logger.error(f"Flow execution failed: {e}", exc_info=True)
            if self.execution_log:
                await self._update_execution_log(status="FAILED", error_message=str(e))
