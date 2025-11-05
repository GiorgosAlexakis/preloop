import uuid
import secrets
from typing import List

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
):
    """Trigger a test execution for a flow."""
    # Verify flow exists and user has access
    flow = crud_flow.get(db=db, id=flow_id, account_id=current_user.account_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    # Trigger flow execution
    from spacebridge.services.flow_trigger_service import FlowTriggerService

    trigger_service = FlowTriggerService(db)
    result = await trigger_service.trigger_flow(flow_id=flow_id, test_mode=True)

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
