import uuid
from typing import List, Optional, Any

from sqlalchemy.orm import Session
from sqlalchemy.future import select

from preloop.models.models.flow_execution import FlowExecution
from preloop.models.models.flow import Flow
from preloop.models.schemas.flow_execution import (
    FlowExecutionCreate,
    FlowExecutionUpdate,
)
from .base import CRUDBase


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
        query = query.join(Flow).filter(Flow.account_id == account_id)

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


class CRUDFlowExecution(CRUDBase[FlowExecution]):
    """CRUD operations for FlowExecution model."""

    def __init__(self):
        """Initialize with the FlowExecution model."""
        super().__init__(model=FlowExecution)

    def get(
        self, db: Session, id: Any, *, account_id: Optional[str] = None
    ) -> Optional[FlowExecution]:
        """Get flow execution by ID.

        Overrides base get to properly filter by account_id through Flow relationship.
        """
        query = db.query(FlowExecution).filter(FlowExecution.id == id)
        if account_id:
            query = query.join(Flow).filter(Flow.account_id == account_id)
        return query.first()

    def create(self, db: Session, obj_in: FlowExecutionCreate) -> FlowExecution:
        """Create a new flow execution (synchronous)."""
        db_obj = FlowExecution(**obj_in.model_dump())
        db.add(db_obj)
        db.flush()  # Use flush instead of commit to stay in transaction
        return db_obj

    def update(
        self, db: Session, db_obj: FlowExecution, obj_in: FlowExecutionUpdate
    ) -> FlowExecution:
        """Update an existing flow execution (synchronous)."""
        import logging

        logger = logging.getLogger(__name__)

        update_data = obj_in.model_dump(exclude_unset=True)

        # Debug logging for metrics updates
        if "tool_calls_count" in update_data or "total_tokens" in update_data:
            logger.info(
                f"CRUD update - Setting metrics on FlowExecution {db_obj.id}: "
                f"tool_calls_count={update_data.get('tool_calls_count')}, "
                f"total_tokens={update_data.get('total_tokens')}, "
                f"estimated_cost={update_data.get('estimated_cost')}"
            )
            logger.info(
                f"Current DB values before update: tool_calls_count={db_obj.tool_calls_count}, "
                f"total_tokens={db_obj.total_tokens}, estimated_cost={db_obj.estimated_cost}"
            )

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.flush()  # Use flush instead of commit to stay in transaction

        # Debug logging after flush
        if "tool_calls_count" in update_data or "total_tokens" in update_data:
            logger.info(
                f"After flush: tool_calls_count={db_obj.tool_calls_count}, "
                f"total_tokens={db_obj.total_tokens}, estimated_cost={db_obj.estimated_cost}"
            )

        return db_obj

    def get_by_flow(
        self,
        db: Session,
        flow_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[str] = None,
    ) -> List[FlowExecution]:
        """Get flow executions for a specific flow (synchronous)."""
        query = (
            db.query(FlowExecution)
            .filter(FlowExecution.flow_id == flow_id)
            .order_by(FlowExecution.start_time.desc())
        )
        if account_id:
            query = query.join(Flow).filter(Flow.account_id == account_id)
        return query.offset(skip).limit(limit).all()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[str] = None,
        **filters,
    ) -> List[FlowExecution]:
        """Get multiple flow executions with optional filtering.

        Overrides base get_multi to properly filter by account_id through Flow relationship.
        """
        query = db.query(FlowExecution)

        # Filter by account_id through the Flow relationship
        if account_id:
            query = query.join(Flow).filter(Flow.account_id == account_id)

        # Apply any additional filters
        for key, value in filters.items():
            if hasattr(FlowExecution, key):
                query = query.filter(getattr(FlowExecution, key) == value)

        # Order by start_time descending (most recent first)
        query = query.order_by(FlowExecution.start_time.desc())

        return query.offset(skip).limit(limit).all()

    def get_by_statuses(
        self, db: Session, statuses: List[str], account_id: Optional[str] = None
    ) -> List[FlowExecution]:
        """Get flow executions filtered by status list."""
        query = db.query(FlowExecution).filter(FlowExecution.status.in_(statuses))
        if account_id:
            query = query.join(Flow).filter(Flow.account_id == account_id)
        return query.all()

    def append_log(self, db: Session, execution_id: str, log_data: dict) -> None:
        """Append a log entry to the execution_logs array.

        Uses PostgreSQL's JSONB append operator to add log to array.
        If execution_logs is NULL, initializes it as an empty array first.

        Args:
            db: Database session
            execution_id: ID of the flow execution
            log_data: Log message data to append
        """
        import json
        from sqlalchemy import text

        log_json = json.dumps(log_data)
        db.execute(
            text("""
                UPDATE flow_execution
                SET execution_logs = COALESCE(execution_logs, '[]'::jsonb) || CAST(:log_entry AS jsonb)
                WHERE id = :execution_id
            """),
            {"execution_id": execution_id, "log_entry": log_json},
        )
        db.commit()
