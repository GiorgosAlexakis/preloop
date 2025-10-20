"""Public approval endpoints (token-based authentication, no login required)."""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from spacemodels.db.session import get_async_db_session
from spacemodels.models import ApprovalRequest
from spacebridge.services.approval_service import ApprovalService
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public/approval", tags=["public-approval"])


class ApprovalDecisionRequest(BaseModel):
    """Request to approve or decline."""

    action: str  # "approve" or "decline"
    comment: Optional[str] = None


class ApprovalRequestPublic(BaseModel):
    """Public view of approval request (no sensitive account data)."""

    id: str
    tool_name: str
    tool_args: dict
    agent_reasoning: Optional[str]
    status: str
    requested_at: str
    expires_at: Optional[str]


@router.get("/{request_id}")
async def get_approval_request_public(
    request_id: uuid.UUID,
    token: str = Query(..., description="Approval token"),
) -> ApprovalRequestPublic:
    """Get approval request details using token (no authentication required).

    Args:
        request_id: UUID of the approval request
        token: Secure token from the approval link

    Returns:
        Public approval request details

    Raises:
        HTTPException: If token is invalid or request not found
    """
    async with get_async_db_session() as db:
        # Get approval request and validate token
        result = await db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.id == request_id,
                ApprovalRequest.approval_token == token,
            )
        )
        approval_request = result.scalar_one_or_none()

        if not approval_request:
            logger.warning(f"Invalid token or request not found: {request_id}")
            raise HTTPException(
                status_code=404, detail="Approval request not found or invalid token"
            )

        # Return public data only
        return ApprovalRequestPublic(
            id=str(approval_request.id),
            tool_name=approval_request.tool_name,
            tool_args=approval_request.tool_args,
            agent_reasoning=approval_request.agent_reasoning,
            status=approval_request.status,
            requested_at=approval_request.requested_at.isoformat(),
            expires_at=approval_request.expires_at.isoformat()
            if approval_request.expires_at
            else None,
        )


@router.post("/{request_id}/decide")
async def decide_approval_request_public(
    request_id: uuid.UUID,
    decision: ApprovalDecisionRequest,
    token: str = Query(..., description="Approval token"),
) -> ApprovalRequestPublic:
    """Approve or decline an approval request using token (no authentication required).

    Args:
        request_id: UUID of the approval request
        decision: Approval decision (approve/decline) and optional comment
        token: Secure token from the approval link

    Returns:
        Updated approval request

    Raises:
        HTTPException: If token is invalid, request not found, or already resolved
    """
    async with get_async_db_session() as db:
        # Get approval request and validate token
        result = await db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.id == request_id,
                ApprovalRequest.approval_token == token,
            )
        )
        approval_request = result.scalar_one_or_none()

        if not approval_request:
            logger.warning(f"Invalid token or request not found: {request_id}")
            raise HTTPException(
                status_code=404, detail="Approval request not found or invalid token"
            )

        # Check if already resolved
        if approval_request.status in ["approved", "declined", "cancelled", "expired"]:
            logger.warning(
                f"Approval request {request_id} already resolved: {approval_request.status}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Approval request already {approval_request.status}",
            )

        # Process decision
        approval_service = ApprovalService(
            db, ""
        )  # base_url not needed for this operation

        if decision.action == "approve":
            logger.info(f"Approving request {request_id}")
            updated_request = await approval_service.approve_request(
                request_id, decision.comment
            )
        elif decision.action == "decline":
            logger.info(f"Declining request {request_id}")
            updated_request = await approval_service.decline_request(
                request_id, decision.comment
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Invalid action: {decision.action}"
            )

        if not updated_request:
            raise HTTPException(
                status_code=500, detail="Failed to update approval request"
            )

        # Return updated data
        return ApprovalRequestPublic(
            id=str(updated_request.id),
            tool_name=updated_request.tool_name,
            tool_args=updated_request.tool_args,
            agent_reasoning=updated_request.agent_reasoning,
            status=updated_request.status,
            requested_at=updated_request.requested_at.isoformat(),
            expires_at=updated_request.expires_at.isoformat()
            if updated_request.expires_at
            else None,
        )
