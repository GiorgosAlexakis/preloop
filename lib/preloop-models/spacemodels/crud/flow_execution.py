import uuid
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.future import select

from spacemodels.models.flow_execution import FlowExecution
from spacemodels.models.flow import Flow
from spacemodels.schemas.flow_execution import (
    FlowExecutionCreate,
    FlowExecutionUpdate,
)


async def get_flow_execution(
    db: Session, flow_execution_id: uuid.UUID
) -> Optional[FlowExecution]:
    """
    Retrieve a flow execution by its ID.
    """
    result = await db.execute(
        select(FlowExecution).filter(FlowExecution.id == flow_execution_id)
    )
    return result.scalars().first()


async def get_flow_executions_by_flow(
    db: Session,
    flow_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    account_id: Optional[str] = None,
) -> List[FlowExecution]:
    """
    Retrieve flow executions for a specific flow.
    """
    query = (
        select(FlowExecution)
        .filter(FlowExecution.flow_id == flow_id)
        .order_by(FlowExecution.start_time.desc())
    )
    if account_id:
        query = query.join(Flow).filter(Flow.created_by_user_id == account_id)

    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


async def create_flow_execution(
    db: Session, flow_execution_in: FlowExecutionCreate
) -> FlowExecution:
    """
    Create a new flow execution.
    This is typically called by the Flow Trigger Service.
    """
    db_flow_execution = FlowExecution(**flow_execution_in.model_dump())
    db.add(db_flow_execution)
    await db.commit()
    await db.refresh(db_flow_execution)
    return db_flow_execution


async def update_flow_execution(
    db: Session, flow_execution: FlowExecution, flow_execution_in: FlowExecutionUpdate
) -> FlowExecution:
    """
    Update an existing flow execution.
    This is typically called by the Flow Execution Orchestrator to update status, logs, etc.
    """
    update_data = flow_execution_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(flow_execution, field, value)

    await db.commit()
    await db.refresh(flow_execution)
    return flow_execution


async def delete_flow_execution(
    db: Session, flow_execution_id: uuid.UUID
) -> Optional[FlowExecution]:
    """
    Delete a flow execution (primarily for cleanup or testing, not a standard operation).
    """
    db_flow_execution = await get_flow_execution(db, flow_execution_id)
    if db_flow_execution:
        await db.delete(db_flow_execution)
        await db.commit()
    return db_flow_execution
