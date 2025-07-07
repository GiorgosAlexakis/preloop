import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from spacemodels import schemas
from spacemodels.crud.flow import CRUDFlow
from spacemodels.models.account import Account
from spacemodels.db.session import get_db_session as get_db
from spacebridge.api.auth import get_current_active_user

router = APIRouter()
crud_flow = CRUDFlow()


@router.post("/", response_model=schemas.FlowResponse)
def create_flow(
    *, 
    db: Session = Depends(get_db),
    flow_in: schemas.FlowCreate,
    current_user: Account = Depends(get_current_active_user)
):
    """Create new flow."""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=400, detail="User does not belong to an organization."
        )
    flow_in.organization_id = current_user.organization_id
    flow_in.created_by_user_id = current_user.id
    flow = crud_flow.create(db=db, flow_in=flow_in)
    return flow


@router.get("/", response_model=List[schemas.FlowResponse])
def read_flows(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Account = Depends(get_current_active_user),
):
    """Retrieve flows for the user's organization."""
    if not current_user.organization_id:
        raise HTTPException(
            status_code=400, detail="User does not belong to an organization."
        )
    flows = crud_flow.get_by_organization(
        db, organization_id=current_user.organization_id, skip=skip, limit=limit
    )
    return flows


@router.get("/{flow_id}", response_model=schemas.FlowResponse)
def read_flow(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: Account = Depends(get_current_active_user),
):
    """Get flow by ID."""
    flow = crud_flow.get(db=db, id=flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return flow


@router.put("/{flow_id}", response_model=schemas.FlowResponse)
def update_flow(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    flow_in: schemas.FlowUpdate,
    current_user: Account = Depends(get_current_active_user),
):
    """Update a flow."""
    flow = crud_flow.get(db=db, id=flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    flow = crud_flow.update(db=db, db_obj=flow, flow_in=flow_in)
    return flow


@router.delete("/{flow_id}", response_model=schemas.FlowResponse)
def delete_flow(
    *,
    db: Session = Depends(get_db),
    flow_id: uuid.UUID,
    current_user: Account = Depends(get_current_active_user),
):
    """Delete a flow."""
    flow = crud_flow.get(db=db, id=flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    flow = crud_flow.remove(db=db, id=flow_id)
    return flow
