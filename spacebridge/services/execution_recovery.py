"""Service for recovering orphaned flow executions after pod restarts."""

import asyncio
import logging
from typing import List

from sqlalchemy.orm import Session

from spacemodels import models
from spacemodels.crud import crud_flow_execution
from spacesync.services.event_bus import get_nats_client
from .flow_orchestrator import FlowExecutionOrchestrator

logger = logging.getLogger(__name__)


class ExecutionRecoveryService:
    """Recovers and resumes monitoring for orphaned flow executions."""

    def __init__(self):
        self.recovery_tasks: List[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()

    async def recover_orphaned_executions(self, db: Session) -> int:
        """
        Find and resume monitoring for executions that were running when pod restarted.

        Args:
            db: Database session

        Returns:
            Number of executions recovered
        """
        logger.info("Checking for orphaned flow executions to recover...")

        # Find all executions that are in RUNNING/STARTING/INITIALIZING/PENDING state
        running_statuses = ["RUNNING", "STARTING", "INITIALIZING", "PENDING"]

        orphaned_executions = []
        for status in running_statuses:
            executions = crud_flow_execution.get_multi(
                db,
                skip=0,
                limit=1000,  # Reasonable limit
                status=status,
            )
            orphaned_executions.extend(executions)

        if not orphaned_executions:
            logger.info("No orphaned executions found")
            return 0

        logger.info(
            f"Found {len(orphaned_executions)} orphaned execution(s) to recover"
        )

        # Get NATS client
        try:
            nats_client = await get_nats_client()
        except Exception as e:
            logger.error(f"Failed to connect to NATS for recovery: {e}")
            nats_client = None

        recovered_count = 0
        for execution in orphaned_executions:
            try:
                await self._resume_execution_monitoring(db, execution, nats_client)
                recovered_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to recover execution {execution.id}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Successfully recovered {recovered_count}/{len(orphaned_executions)} executions"
        )
        return recovered_count

    async def _resume_execution_monitoring(
        self,
        db: Session,
        execution: models.FlowExecution,
        nats_client,
    ):
        """Resume monitoring for a specific execution."""
        logger.info(
            f"Resuming monitoring for execution {execution.id} "
            f"(status: {execution.status}, agent_session: {execution.agent_session_reference})"
        )

        # If execution doesn't have an agent session yet, it failed during startup
        if not execution.agent_session_reference:
            logger.warning(
                f"Execution {execution.id} has no agent session - marking as FAILED"
            )
            from datetime import datetime, timezone
            from spacemodels.schemas.flow_execution import FlowExecutionUpdate

            update_data = FlowExecutionUpdate(
                status="FAILED",
                error_message="Execution interrupted during startup (pod restart)",
                end_time=datetime.now(timezone.utc),
            )
            crud_flow_execution.update(db, db_obj=execution, obj_in=update_data)
            db.commit()
            return

        # Create orchestrator and resume monitoring
        orchestrator = FlowExecutionOrchestrator(
            db,
            flow_id=execution.flow_id,
            trigger_event_data=execution.trigger_event_details or {},
            nats_client=nats_client,
        )
        orchestrator.execution_log = execution

        # Resume monitoring as a background task
        task = asyncio.create_task(
            self._resume_monitoring_task(
                orchestrator, execution.agent_session_reference
            )
        )
        self.recovery_tasks.append(task)

    async def _resume_monitoring_task(self, orchestrator, session_reference: str):
        """Background task that resumes monitoring an agent execution."""
        try:
            logger.info(f"Resumed monitoring task for session {session_reference}")

            # Get the agent executor
            from spacemodels.db.session import get_db_session

            db = next(get_db_session())
            try:
                flow = crud_flow_execution.get(
                    db, id=orchestrator.execution_log.id
                ).flow

                # Create appropriate agent executor based on flow agent type
                from spacebridge.agents.codex import CodexAgent
                from spacebridge.agents.container import ContainerAgentExecutor
                import os

                use_kubernetes = (
                    os.getenv("USE_KUBERNETES_FOR_AGENTS", "false").lower() == "true"
                )

                # CodexAgent auto-detects Kubernetes environment, no need to pass use_kubernetes
                if flow.agent_type == "codex":
                    agent_executor = CodexAgent(config={})
                else:
                    agent_executor = ContainerAgentExecutor(
                        agent_type=flow.agent_type,
                        config={},
                        image="dummy-image",
                        use_kubernetes=use_kubernetes,
                    )

                # Resume monitoring
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

                logger.info(
                    f"Resumed execution {orchestrator.execution_log.id} completed with status {final_status}"
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(
                f"Error in resumed monitoring task for {session_reference}: {e}",
                exc_info=True,
            )
            # Mark as failed
            try:
                from datetime import datetime, timezone
                from spacemodels.schemas.flow_execution import FlowExecutionUpdate

                update_data = FlowExecutionUpdate(
                    status="FAILED",
                    error_message=f"Resumed monitoring failed: {str(e)}",
                    end_time=datetime.now(timezone.utc),
                )
                crud_flow_execution.update(
                    orchestrator.db,
                    db_obj=orchestrator.execution_log,
                    obj_in=update_data,
                )
                orchestrator.db.commit()
            except Exception as update_error:
                logger.error(f"Failed to mark execution as failed: {update_error}")

    async def wait_for_completion(self, timeout: int = 300):
        """
        Wait for all recovery tasks to complete before shutdown.

        Args:
            timeout: Maximum time to wait in seconds (default 5 minutes)
        """
        if not self.recovery_tasks:
            logger.info("No recovery tasks to wait for")
            return

        logger.info(
            f"Waiting for {len(self.recovery_tasks)} recovery tasks to complete..."
        )

        try:
            await asyncio.wait_for(
                asyncio.gather(*self.recovery_tasks, return_exceptions=True),
                timeout=timeout,
            )
            logger.info("All recovery tasks completed")
        except asyncio.TimeoutError:
            logger.warning(
                f"Recovery tasks did not complete within {timeout}s - proceeding with shutdown"
            )
            # Cancel remaining tasks
            for task in self.recovery_tasks:
                if not task.done():
                    task.cancel()


# Global singleton instance
_recovery_service = None


def get_recovery_service() -> ExecutionRecoveryService:
    """Get the global recovery service instance."""
    global _recovery_service
    if _recovery_service is None:
        _recovery_service = ExecutionRecoveryService()
    return _recovery_service
