import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from spacemodels import schemas
from spacemodels.crud.flow import CRUDFlow
from spacemodels.crud.flow_execution import CRUDFlowExecution
from spacemodels.db.session import get_db_session as get_db
from spacebridge.api.auth import get_current_active_user
from spacemodels.models.account import Account

router = APIRouter()
crud_flow = CRUDFlow()
crud_flow_execution = CRUDFlowExecution()


@router.post("/flows", response_model=schemas.FlowResponse)
def create_flow(
    *,
    db: Session = Depends(get_db),
    flow_in: schemas.FlowCreate,
    current_user: Account = Depends(get_current_active_user),
):
    """Create new flow."""
    flow = crud_flow.create(db=db, flow_in=flow_in, account_id=current_user.id)
    return flow


@router.get("/flows", response_model=List[schemas.FlowResponse])
def read_flows(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Account = Depends(get_current_active_user),
):
    """Retrieve flows for the account."""
    flows = crud_flow.get_multi(db, account_id=current_user.id, skip=skip, limit=limit)
    return flows


@router.get("/flows/presets", response_model=List[schemas.FlowResponse])
def read_presets(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """Retrieve flow presets for the account."""
    global_presets = crud_flow.get_multi(db, is_preset=True)
    account_presets = crud_flow.get_multi(
        db, account_id=current_user.id, is_preset=False
    )
    return global_presets + account_presets


@router.post("/flows/presets/{flow_id}/clone", response_model=schemas.FlowResponse)
def clone_preset(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: Account = Depends(get_current_active_user),
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
        account_id=current_user.id,
    )
    cloned_flow = crud_flow.create(
        db=db, flow_in=cloned_flow_in, account_id=current_user.id
    )
    return cloned_flow


@router.get("/flows/executions", response_model=List[schemas.FlowExecutionResponse])
def read_flow_executions(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Account = Depends(get_current_active_user),
):
    """Retrieve flow executions for the account."""
    executions = crud_flow_execution.get_multi(
        db, account_id=current_user.id, skip=skip, limit=limit
    )
    return executions


@router.get(
    "/flows/executions/{execution_id}", response_model=schemas.FlowExecutionResponse
)
def read_flow_execution(
    *,
    db: Session = Depends(get_db),
    execution_id: uuid.UUID,
    current_user: Account = Depends(get_current_active_user),
):
    """Get flow execution by ID."""
    execution = crud_flow_execution.get(
        db=db, id=execution_id, account_id=current_user.id
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Flow execution not found")
    return execution


@router.post("/flows/executions/{execution_id}/command")
async def send_execution_command(
    *,
    db: Session = Depends(get_db),
    execution_id: uuid.UUID,
    command: str,
    payload: dict = None,
    current_user: Account = Depends(get_current_active_user),
):
    """Send a command to a running flow execution."""
    # Verify execution exists and user has access
    execution = crud_flow_execution.get(
        db=db, id=execution_id, account_id=current_user.id
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Flow execution not found")

    # Send command via NATS
    from spacebridge.services.flow_orchestrator import FlowExecutionOrchestrator

    orchestrator = FlowExecutionOrchestrator()
    await orchestrator.send_command(
        execution_id=str(execution_id), command=command, payload=payload
    )

    return {"status": "command_sent"}


@router.post("/flows/{flow_id}/trigger")
async def trigger_flow_execution(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: Account = Depends(get_current_active_user),
):
    """Trigger a test execution for a flow."""
    # Verify flow exists and user has access
    flow = crud_flow.get(db=db, id=flow_id, account_id=current_user.id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    # Trigger flow execution
    from spacebridge.services.flow_trigger_service import FlowTriggerService

    trigger_service = FlowTriggerService(db)
    result = await trigger_service.trigger_flow(flow_id=flow_id, test_mode=True)

    return result


@router.get("/flows/{flow_id}", response_model=schemas.FlowResponse)
def read_flow(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: Account = Depends(get_current_active_user),
):
    """Get flow by ID."""
    flow = crud_flow.get(db=db, id=flow_id, account_id=current_user.id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.put("/flows/{flow_id}", response_model=schemas.FlowResponse)
def update_flow(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    flow_in: schemas.FlowUpdate,
    current_user: Account = Depends(get_current_active_user),
):
    """Update a flow."""
    flow = crud_flow.get(db=db, id=flow_id, account_id=current_user.id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    flow = crud_flow.update(
        db=db, db_obj=flow, flow_in=flow_in, account_id=current_user.id
    )
    return flow


@router.delete("/flows/{flow_id}", response_model=schemas.FlowResponse)
def delete_flow(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: Account = Depends(get_current_active_user),
):
    """Delete a flow."""
    flow = crud_flow.get(db=db, id=flow_id, account_id=current_user.id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    crud_flow.remove(db=db, id=flow_id, account_id=current_user.id)
    return flow
