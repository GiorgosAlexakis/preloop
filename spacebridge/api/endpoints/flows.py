import uuid
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from spacemodels import schemas
from spacemodels.crud.flow import CRUDFlow
from spacemodels.crud.flow_execution import CRUDFlowExecution
from spacemodels.db.session import get_db_session as get_db
from spacebridge.api.auth import get_current_active_user
from spacemodels.models.user import User
from spacebridge.plugins.proprietary.rbac.permissions import require_permission

router = APIRouter()
crud_flow = CRUDFlow()
crud_flow_execution = CRUDFlowExecution()


@router.post("/flows", response_model=schemas.FlowResponse)
@require_permission("create_flows")
def create_flow(
    *,
    db: Session = Depends(get_db),
    flow_in: schemas.FlowCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Create new flow."""
    # Security check: Only superusers can configure custom commands
    if flow_in.custom_commands and flow_in.custom_commands.enabled:
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Only administrators can configure custom commands for security reasons",
            )

    # If this is a webhook trigger, auto-generate a secure webhook secret
    if flow_in.trigger_event_source == "webhook" or (
        not flow_in.trigger_event_source and not flow_in.trigger_event_type
    ):
        # Generate a secure 32-byte URL-safe token
        webhook_secret = secrets.token_urlsafe(32)
        flow_in.webhook_config = schemas.WebhookConfig(webhook_secret=webhook_secret)
        flow_in.trigger_event_source = "webhook"
        flow_in.trigger_event_type = "webhook"

    flow = crud_flow.create(db=db, flow_in=flow_in, account_id=current_user.account_id)
    return flow


@router.get("/flows", response_model=List[schemas.FlowResponse])
@require_permission("view_flows")
def read_flows(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve flows for the account."""
    flows = crud_flow.get_multi(
        db, account_id=current_user.account_id, skip=skip, limit=limit
    )
    return flows


@router.get("/flows/presets", response_model=List[schemas.FlowResponse])
@require_permission("view_flows")
def read_presets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve flow presets for the account."""
    global_presets = crud_flow.get_multi(db, is_preset=True)
    account_presets = crud_flow.get_multi(
        db, account_id=current_user.account_id, is_preset=False
    )
    return global_presets + account_presets


@router.post("/flows/presets/{flow_id}/clone", response_model=schemas.FlowResponse)
@require_permission("create_flows")
def clone_preset(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Clone a flow preset."""
    preset = crud_flow.get(db=db, id=flow_id)
    if not preset or not preset.is_preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    # Build dict excluding fields we want to override or that aren't in FlowCreate
    preset_dict = {
        k: v
        for k, v in preset.__dict__.items()
        if k
        not in [
            "_sa_instance_state",
            "id",
            "created_at",
            "updated_at",
            "name",
            "is_preset",
            "account_id",
        ]
    }

    cloned_flow_in = schemas.FlowCreate(
        **preset_dict,
        name=f"Copy of {preset.name}",
        is_preset=False,
        account_id=str(current_user.account_id),
    )
    cloned_flow = crud_flow.create(
        db=db, flow_in=cloned_flow_in, account_id=current_user.account_id
    )
    return cloned_flow


@router.get("/flows/executions", response_model=List[schemas.FlowExecutionResponse])
@require_permission("view_flows")
def read_flow_executions(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve flow executions for the account."""
    executions = crud_flow_execution.get_multi(
        db, account_id=current_user.account_id, skip=skip, limit=limit
    )

    # Enrich with flow names
    for execution in executions:
        flow = crud_flow.get(
            db, id=execution.flow_id, account_id=current_user.account_id
        )
        execution.flow_name = flow.name if flow else None

    return executions


@router.get(
    "/flows/executions/{execution_id}", response_model=schemas.FlowExecutionResponse
)
@require_permission("view_flows")
def read_flow_execution(
    *,
    db: Session = Depends(get_db),
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Get flow execution by ID."""
    execution = crud_flow_execution.get(
        db=db, id=execution_id, account_id=current_user.account_id
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Flow execution not found")
    return execution


@router.get("/flows/executions/{execution_id}/logs")
@require_permission("view_flows")
async def get_flow_execution_logs(
    *,
    db: Session = Depends(get_db),
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    tail: int = 1000,
) -> Dict[str, Any]:
    """Get execution logs from the container (if running) or database (if finished).

    For running executions, fetches logs directly from the Docker/Kubernetes container.
    For finished executions, returns persisted logs from the database.

    Args:
        execution_id: ID of the execution
        tail: Number of recent log lines to retrieve (default: 1000)

    Returns:
        Dictionary with:
        - logs: List of log lines
        - source: Where logs were fetched from ("container" or "database")
    """
    from spacebridge.agents.container import ContainerAgentExecutor
    from spacebridge.agents.codex import CodexAgent

    # Verify execution exists and user has access
    execution = crud_flow_execution.get(
        db=db, id=execution_id, account_id=current_user.account_id
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Flow execution not found")

    # Check if execution is running
    is_running = execution.status in ["RUNNING", "STARTING", "INITIALIZING", "PENDING"]

    if is_running and execution.agent_session_reference:
        # Fetch logs directly from container
        try:
            # Get the flow to determine agent type
            flow = crud_flow.get(
                db=db, id=execution.flow_id, account_id=current_user.account_id
            )
            if not flow:
                raise HTTPException(status_code=404, detail="Flow not found")

            # Determine if using Kubernetes or Docker
            import os

            use_kubernetes = (
                os.getenv("USE_KUBERNETES_FOR_AGENTS", "false").lower() == "true"
            )

            # Create agent executor to access logs
            # Note: We don't need the full agent config, just need the get_logs method
            if flow.agent_type == "codex":
                agent = CodexAgent(config={}, use_kubernetes=use_kubernetes)
            else:
                agent = ContainerAgentExecutor(
                    agent_type=flow.agent_type,
                    config={},
                    image="dummy-image",  # Not used for get_logs
                    use_kubernetes=use_kubernetes,
                )

            # Fetch logs from container
            container_logs = await agent.get_logs(
                execution.agent_session_reference, tail=tail
            )

            # Format logs as execution updates (matching the WebSocket format)
            formatted_logs = []
            for log_line in container_logs:
                formatted_logs.append(
                    {
                        "execution_id": str(execution_id),
                        "timestamp": execution.start_time.isoformat(),  # Use start time as fallback
                        "type": "agent_log_line",
                        "payload": {"content": log_line},
                    }
                )

            return {"logs": formatted_logs, "source": "container"}

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to fetch container logs for execution {execution_id}: {e}"
            )
            # Fall back to database logs if container logs fail
            pass

    # For finished executions or if container logs failed, return database logs
    if execution.execution_logs and isinstance(execution.execution_logs, list):
        return {"logs": execution.execution_logs, "source": "database"}
    else:
        return {"logs": [], "source": "database"}


@router.get("/flows/executions/{execution_id}/metrics")
@require_permission("view_flows")
def get_flow_execution_metrics(
    *,
    db: Session = Depends(get_db),
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Get execution metrics including tool calls, API usage, and costs.

    Returns:
        Dictionary with:
        - tool_calls: Number of MCP tool calls made
        - api_requests: Number of API requests made during execution
        - token_usage: Token usage statistics
        - estimated_cost: Estimated cost based on token usage (0.0 if no pricing)
        - has_pricing: Whether pricing is configured in AI model metadata
    """
    from spacebridge.services.execution_metrics import ExecutionMetricsService

    # Verify execution exists and user has access
    execution = crud_flow_execution.get(
        db=db, id=execution_id, account_id=current_user.account_id
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Flow execution not found")

    # Calculate metrics
    metrics_service = ExecutionMetricsService(db)
    try:
        metrics = metrics_service.get_execution_metrics(str(execution_id))
        return metrics
    except Exception as e:
        # Log error but return zero metrics instead of failing
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to calculate metrics for execution {execution_id}: {e}")
        return {
            "tool_calls": 0,
            "api_requests": 0,
            "token_usage": {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0},
            "estimated_cost": 0.0,
            "has_pricing": False,
        }


@router.post("/flows/executions/{execution_id}/command")
@require_permission("execute_flows")
async def send_execution_command(
    *,
    db: Session = Depends(get_db),
    execution_id: uuid.UUID,
    command_data: schemas.FlowExecutionCommand,
    current_user: User = Depends(get_current_active_user),
):
    """Send a command to a running flow execution."""
    # Verify execution exists and user has access
    execution = crud_flow_execution.get(
        db=db, id=execution_id, account_id=current_user.account_id
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Flow execution not found")

    # For stuck executions, allow manual cleanup by directly updating the status
    if command_data.command == "stop":
        # If execution is in a "stuck" state (RUNNING/STARTING but container never started),
        # or if NATS is unavailable, update the status directly
        if execution.status in ["RUNNING", "STARTING", "PENDING"]:
            from datetime import datetime, timezone

            update_data = schemas.FlowExecutionUpdate(
                status="STOPPED",
                error_message="Manually stopped by user",
                end_time=datetime.now(timezone.utc),
            )
            crud_flow_execution.update(db=db, db_obj=execution, obj_in=update_data)
            db.commit()
            return {"status": "stopped"}

    # Try to send command via NATS for running executions
    try:
        from spacebridge.services.flow_orchestrator import FlowExecutionOrchestrator

        await FlowExecutionOrchestrator.send_command(
            execution_id=str(execution_id),
            command=command_data.command,
            payload=command_data.payload,
        )
        return {"status": "command_sent"}
    except Exception as e:
        # If NATS fails but this is a stop command, still mark as stopped
        if command_data.command == "stop":
            from datetime import datetime, timezone

            update_data = schemas.FlowExecutionUpdate(
                status="STOPPED",
                error_message=f"Stopped by user (NATS unavailable: {str(e)})",
                end_time=datetime.now(timezone.utc),
            )
            crud_flow_execution.update(db=db, db_obj=execution, obj_in=update_data)
            db.commit()
            return {"status": "stopped"}
        raise


@router.post("/flows/{flow_id}/trigger")
@require_permission("execute_flows")
async def trigger_flow_execution(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    trigger_event_data: Optional[Dict[str, Any]] = None,
):
    """
    Trigger a test execution for a flow.

    Args:
        flow_id: Flow to trigger
        trigger_event_data: Optional custom trigger event data for testing template variables

    Returns:
        Execution details
    """
    # Verify flow exists and user has access
    flow = crud_flow.get(db=db, id=flow_id, account_id=current_user.account_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    # Trigger flow execution
    from spacebridge.services.flow_trigger_service import FlowTriggerService

    trigger_service = FlowTriggerService(db)
    result = await trigger_service.trigger_flow(
        flow_id=flow_id, test_mode=True, trigger_event_data=trigger_event_data
    )

    return result


@router.get("/flows/{flow_id}", response_model=schemas.FlowResponse)
@require_permission("view_flows")
def read_flow(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Get flow by ID."""
    flow = crud_flow.get(db=db, id=flow_id, account_id=current_user.account_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.put("/flows/{flow_id}", response_model=schemas.FlowResponse)
@require_permission("edit_flows")
def update_flow(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    flow_in: schemas.FlowUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update a flow."""
    flow = crud_flow.get(db=db, id=flow_id, account_id=current_user.account_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    # Security check: Only superusers can configure custom commands
    if flow_in.custom_commands and flow_in.custom_commands.enabled:
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Only administrators can configure custom commands for security reasons",
            )

    flow = crud_flow.update(
        db=db, db_obj=flow, flow_in=flow_in, account_id=current_user.account_id
    )
    return flow


@router.delete("/flows/{flow_id}", response_model=schemas.FlowResponse)
@require_permission("delete_flows")
def delete_flow(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a flow."""
    flow = crud_flow.get(db=db, id=flow_id, account_id=current_user.account_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    crud_flow.remove(db=db, id=flow_id, account_id=current_user.account_id)
    return flow


@router.post("/webhooks/flows/{flow_id}/{webhook_secret}")
async def trigger_flow_via_webhook(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    webhook_secret: str,
    request: Request,
):
    """
    Trigger a flow via webhook (no authentication required - uses secret token in URL).

    This endpoint allows external services to trigger flows without authentication.
    Security is provided by the unguessable webhook_secret in the URL.
    """
    # Get the flow without account filtering
    flow = crud_flow.get(db=db, id=flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    # Verify this is a webhook trigger
    if flow.trigger_event_source != "webhook":
        raise HTTPException(
            status_code=400, detail="This flow is not configured for webhook triggers"
        )

    # Verify webhook secret
    if (
        not flow.webhook_config
        or flow.webhook_config.get("webhook_secret") != webhook_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    # Check if flow is enabled
    if not flow.is_enabled:
        raise HTTPException(status_code=400, detail="Flow is disabled")

    # Parse webhook payload
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # Trigger flow execution with webhook payload
    from spacebridge.services.flow_trigger_service import FlowTriggerService

    trigger_service = FlowTriggerService(db)

    # Create event data from webhook payload
    event_data = {
        "source": "webhook",
        "type": "webhook",
        "payload": payload,
        "account_id": flow.account_id,
    }

    # Process the event (will trigger flow execution)
    await trigger_service.process_event(event_data)

    return {"status": "triggered", "flow_id": str(flow_id)}
