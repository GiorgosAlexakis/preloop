"""API endpoints for approval requests."""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from spacebridge.api.auth import get_current_active_user
from spacebridge.services.approval_service import ApprovalService
from spacemodels.db.session import get_async_db_session
from spacemodels.models import Account, ApprovalRequest
from spacemodels.schemas.approval_request import (
    ApprovalRequestResponse,
    ApprovalDecision,
)

router = APIRouter(
    prefix="/approval-requests",
    tags=["approval_requests"],
)


@router.get("/{request_id}", response_model=ApprovalRequestResponse)
async def get_approval_request(
    request_id: uuid.UUID,
    current_account: Account = Depends(get_current_active_user),
) -> ApprovalRequest:
    """Get an approval request by ID.

    Args:
        request_id: Approval request ID
        current_account: Current authenticated account

    Returns:
        Approval request

    Raises:
        HTTPException: If request not found or unauthorized
    """
    async with get_async_db_session() as db:
        result = await db.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == request_id)
        )
        approval_request = result.scalar_one_or_none()

        if not approval_request:
            raise HTTPException(status_code=404, detail="Approval request not found")

        # Check authorization
        if approval_request.account_id != current_account.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to view this approval request"
            )

        return approval_request


@router.get("/", response_model=list[ApprovalRequestResponse])
async def list_approval_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    execution_id: Optional[str] = Query(None, description="Filter by execution ID"),
    limit: int = Query(50, le=100, description="Maximum number of results"),
    skip: int = Query(0, description="Number of results to skip"),
    current_account: Account = Depends(get_current_active_user),
) -> list[ApprovalRequest]:
    """List approval requests for the current account.

    Args:
        status: Filter by status (pending, approved, declined, etc.)
        execution_id: Filter by execution ID
        limit: Maximum number of results
        skip: Number of results to skip
        current_account: Current authenticated account

    Returns:
        List of approval requests
    """
    async with get_async_db_session() as db:
        # Build query
        query = select(ApprovalRequest).where(
            ApprovalRequest.account_id == current_account.id
        )

        # Apply filters
        if status:
            query = query.where(ApprovalRequest.status == status)
        if execution_id:
            query = query.where(ApprovalRequest.execution_id == execution_id)

        # Apply pagination
        query = query.limit(limit).offset(skip)

        # Order by requested_at descending
        query = query.order_by(ApprovalRequest.requested_at.desc())

        # Execute query
        result = await db.execute(query)
        return list(result.scalars().all())


@router.post("/{request_id}/approve", response_model=ApprovalRequestResponse)
async def approve_request(
    request_id: uuid.UUID,
    decision: ApprovalDecision,
    request: Request,
    current_account: Account = Depends(get_current_active_user),
) -> ApprovalRequest:
    """Approve an approval request.

    Args:
        request_id: Approval request ID
        decision: Approval decision with optional comment
        request: HTTP request
        current_account: Current authenticated account

    Returns:
        Updated approval request

    Raises:
        HTTPException: If request not found or unauthorized
    """
    # Get base URL from request
    base_url = os.getenv("BASE_URL", str(request.base_url).rstrip("/"))

    async with get_async_db_session() as db:
        approval_service = ApprovalService(db, base_url)

        # Get approval request
        approval_request = await approval_service.get_approval_request(request_id)
        if not approval_request:
            raise HTTPException(status_code=404, detail="Approval request not found")

        # Check authorization
        if approval_request.account_id != current_account.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to approve this request"
            )

        # Check if already resolved
        if approval_request.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Request already {approval_request.status}",
            )

        # Approve
        updated = await approval_service.approve_request(request_id, decision.comment)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to approve request")

        return updated


@router.post("/{request_id}/decline", response_model=ApprovalRequestResponse)
async def decline_request(
    request_id: uuid.UUID,
    decision: ApprovalDecision,
    request: Request,
    current_account: Account = Depends(get_current_active_user),
) -> ApprovalRequest:
    """Decline an approval request.

    Args:
        request_id: Approval request ID
        decision: Approval decision with optional comment
        request: HTTP request
        current_account: Current authenticated account

    Returns:
        Updated approval request

    Raises:
        HTTPException: If request not found or unauthorized
    """
    # Get base URL from request
    base_url = os.getenv("BASE_URL", str(request.base_url).rstrip("/"))

    async with get_async_db_session() as db:
        approval_service = ApprovalService(db, base_url)

        # Get approval request
        approval_request = await approval_service.get_approval_request(request_id)
        if not approval_request:
            raise HTTPException(status_code=404, detail="Approval request not found")

        # Check authorization
        if approval_request.account_id != current_account.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to decline this request"
            )

        # Check if already resolved
        if approval_request.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Request already {approval_request.status}",
            )

        # Decline
        updated = await approval_service.decline_request(request_id, decision.comment)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to decline request")

        return updated


@router.post("/{request_id}/decide", response_model=ApprovalRequestResponse)
async def decide_request(
    request_id: uuid.UUID,
    decision: ApprovalDecision,
    request: Request,
    current_account: Account = Depends(get_current_active_user),
) -> ApprovalRequest:
    """Approve or decline an approval request based on decision.approved.

    This is a convenience endpoint that calls approve or decline based on
    the decision.approved boolean.

    Args:
        request_id: Approval request ID
        decision: Approval decision with approved flag and optional comment
        request: HTTP request
        current_account: Current authenticated account

    Returns:
        Updated approval request

    Raises:
        HTTPException: If request not found or unauthorized
    """
    # Get base URL from request
    base_url = os.getenv("BASE_URL", str(request.base_url).rstrip("/"))

    async with get_async_db_session() as db:
        approval_service = ApprovalService(db, base_url)

        # Get approval request
        approval_request = await approval_service.get_approval_request(request_id)
        if not approval_request:
            raise HTTPException(status_code=404, detail="Approval request not found")

        # Check authorization
        if approval_request.account_id != current_account.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to decide on this request"
            )

        # Check if already resolved
        if approval_request.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Request already {approval_request.status}",
            )

        # Approve or decline based on decision
        if decision.approved:
            updated = await approval_service.approve_request(
                request_id, decision.comment
            )
        else:
            updated = await approval_service.decline_request(
                request_id, decision.comment
            )

        if not updated:
            raise HTTPException(status_code=500, detail="Failed to process decision")

        return updated
