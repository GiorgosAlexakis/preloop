import logging
import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import re

from sqlalchemy.orm import Session
from nats.aio.client import Client

from spacemodels import schemas
from spacemodels.crud import crud_flow_execution
from spacemodels.models.flow import Flow
from spacemodels.models.ai_model import AIModel

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

        # Get flow - use correct CRUD method signature
        self.flow = self.db.query(Flow).filter(Flow.id == self.flow_id).first()
        if not self.flow:
            raise ValueError(f"Flow with id {self.flow_id} not found")

        logger.info(
            f"Found flow: {self.flow.name} (agent_type: {self.flow.agent_type})"
        )

        # Get AI model if specified
        if self.flow.ai_model_id:
            self.ai_model = (
                self.db.query(AIModel)
                .filter(AIModel.id == self.flow.ai_model_id)
                .first()
            )
            if not self.ai_model:
                logger.warning(
                    f"AI model {self.flow.ai_model_id} not found for flow {self.flow_id}"
                )
        else:
            logger.info("No AI model specified for this flow")

    def _resolve_prompt(self) -> str:
        """
        Resolve dynamic placeholders in the prompt template.

        This is a basic implementation that supports simple {{key}} placeholders.
        Task 4.4 will implement more sophisticated context resolution.
        """
        logger.info("Resolving prompt template")

        prompt_template = self.flow.prompt_template
        resolved_prompt = prompt_template

        # Extract all {{placeholder}} patterns
        placeholders = re.findall(r"\{\{(\w+(?:\.\w+)*)\}\}", prompt_template)

        for placeholder in placeholders:
            # Support nested keys like "payload.issue.title"
            keys = placeholder.split(".")
            value = self.trigger_event_data

            try:
                for key in keys:
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        value = None
                        break

                if value is not None:
                    # Replace the placeholder with the value
                    resolved_prompt = resolved_prompt.replace(
                        f"{{{{{placeholder}}}}}", str(value)
                    )
                    logger.debug(
                        f"Resolved {{{{placeholder}}}}: {placeholder} -> {value}"
                    )
                else:
                    logger.warning(
                        "Placeholder {{placeholder}} not found in trigger data, leaving as-is"
                    )
            except Exception as e:
                logger.warning(f"Error resolving placeholder {{{{placeholder}}}}: {e}")

        logger.info("Prompt resolution complete")
        return resolved_prompt

    def _prepare_execution_context(self) -> Dict[str, Any]:
        """Prepare the full execution context for the agent."""
        logger.info(
            f"Preparing execution context for agent type: {self.flow.agent_type}"
        )

        resolved_prompt = self._resolve_prompt()

        execution_context = {
            "flow_id": str(self.flow_id),
            "execution_id": str(self.execution_log.id),
            "prompt": resolved_prompt,
            "agent_type": self.flow.agent_type,
            "agent_config": self.flow.agent_config,
            "allowed_mcp_servers": self.flow.allowed_mcp_servers,
            "allowed_mcp_tools": self.flow.allowed_mcp_tools,
        }

        # Add AI model details if available
        if self.ai_model:
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
            logger.warning("No AI model configured, agent will need to use defaults")

        logger.info("Execution context prepared successfully")
        return execution_context

    def _start_agent_session(self, execution_context: Dict[str, Any]) -> str:
        """
        Launch and monitor an agent session via Agent Execution Infrastructure.

        This is a placeholder for Task 4.3 implementation.

        Returns:
            agent_session_reference: Reference to the agent session (e.g., container ID, job ID)
        """
        agent_type = execution_context["agent_type"]
        logger.info(f"Starting {agent_type} agent session (placeholder implementation)")

        # TODO (Task 4.3): Implement actual agent execution infrastructure
        # For now, return a mock session reference
        session_reference = f"mock-{agent_type}-session-{uuid.uuid4().hex[:8]}"

        logger.info(f"Agent session started: {session_reference}")
        return session_reference

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
        await self._publish_update("status_update", {"status": status, **kwargs})

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
            execution_context = self._prepare_execution_context()

            # Store resolved prompt for debugging/audit
            await self._update_execution_log(
                status="RUNNING",
                resolved_input_prompt=execution_context["prompt"],
            )

            # Stage 4: Start agent session
            # TODO (Task 4.3): This will actually start the agent
            session_reference = self._start_agent_session(execution_context)

            # Update with session reference
            await self._update_execution_log(
                status="RUNNING",
                agent_session_reference=session_reference,
            )

            # TODO (Task 4.3): Monitor agent execution and collect results
            # For now, we immediately mark as succeeded (placeholder)
            await self._update_execution_log(
                status="SUCCEEDED",
                model_output_summary="Placeholder: Agent execution not yet implemented (Task 4.3)",
            )

            logger.info(
                f"Flow execution completed successfully: {self.execution_log.id}"
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
