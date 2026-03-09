"""Account-related endpoints."""

import html
import logging
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from preloop.api.common import get_account_for_user
from preloop.models.crud import crud_account
from preloop.models.db.session import get_db_session
from preloop.models.models.account import Account
from preloop.schemas.gateway_usage import AccountGatewayUsageSummaryResponse
from preloop.services.model_gateway_usage import ModelGatewayUsageService

logger = logging.getLogger(__name__)

router = APIRouter()
public_router = APIRouter()  # Public endpoints (no auth required)


class AccountDetailsResponse(BaseModel):
    """Account details response."""

    id: str
    organization_name: Optional[str] = None
    created_at: str
    updated_at: str


class AccountDetailsUpdate(BaseModel):
    """Account details update request."""

    organization_name: Optional[str] = None


class AccountDeletionRequest(BaseModel):
    """Account deletion request from user."""

    email: EmailStr
    username: str
    account_id: str
    org_name: Optional[str] = None
    reason: Optional[str] = None


@router.get("/account/details", response_model=AccountDetailsResponse)
async def get_account_details(
    account: Annotated[Account, Depends(get_account_for_user)],
):
    """Get current account details.

    Returns:
        Account details including organization name
    """
    return AccountDetailsResponse(
        id=str(account.id),
        organization_name=account.organization_name,
        created_at=account.created_at.isoformat(),
        updated_at=account.updated_at.isoformat(),
    )


@router.patch("/account/details", response_model=AccountDetailsResponse)
async def update_account_details(
    update_data: AccountDetailsUpdate,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
):
    """Update current account details.

    Args:
        update_data: Account update data
        account: Current user's account
        db: Database session

    Returns:
        Updated account details
    """
    # Update account
    update_dict = update_data.model_dump(exclude_unset=True)
    updated_account = crud_account.update(db=db, db_obj=account, obj_in=update_dict)
    db.commit()
    db.refresh(updated_account)

    return AccountDetailsResponse(
        id=str(updated_account.id),
        organization_name=updated_account.organization_name,
        created_at=updated_account.created_at.isoformat(),
        updated_at=updated_account.updated_at.isoformat(),
    )


@router.get(
    "/account/gateway-usage/summary",
    response_model=AccountGatewayUsageSummaryResponse,
)
async def get_account_gateway_usage_summary(
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
):
    """Get account-scoped model gateway usage summary."""
    return ModelGatewayUsageService(db).get_account_summary(
        account=account,
        start_date=start_date,
        end_date=end_date,
    )


@public_router.post("/account/deletion-request")
async def request_account_deletion(
    deletion_request: AccountDeletionRequest,
):
    """Public endpoint to notify admins of account deletion request.

    This endpoint is called from the public delete-account page and sends
    notifications to admins via email and configured webhooks (Slack/Mattermost).

    Args:
        deletion_request: Account deletion request details

    Returns:
        Success message
    """
    from preloop.sync.tasks import notify_admins

    # Build notification message
    subject = f"Account Deletion Request: {deletion_request.username}"

    message_parts = [
        f"User: {deletion_request.username}",
        f"Email: {deletion_request.email}",
        f"Account ID: {deletion_request.account_id}",
    ]

    if deletion_request.org_name:
        message_parts.append(f"Organization: {deletion_request.org_name}")

    if deletion_request.reason:
        message_parts.append(f"\nReason: {deletion_request.reason}")

    message = "\n".join(message_parts)

    # Build HTML version for email
    # Escape user-controlled input to prevent HTML injection
    safe_username = html.escape(deletion_request.username)
    safe_email = html.escape(deletion_request.email)
    safe_account_id = html.escape(deletion_request.account_id)

    message_html = f"""
    <h2>Account Deletion Request</h2>
    <p><strong>User:</strong> {safe_username}</p>
    <p><strong>Email:</strong> {safe_email}</p>
    <p><strong>Account ID:</strong> {safe_account_id}</p>
    """

    if deletion_request.org_name:
        safe_org_name = html.escape(deletion_request.org_name)
        message_html += f"<p><strong>Organization:</strong> {safe_org_name}</p>"

    if deletion_request.reason:
        safe_reason = html.escape(deletion_request.reason)
        message_html += f"<p><strong>Reason:</strong> {safe_reason}</p>"

    # Send notifications
    try:
        notify_admins(subject, message, message_html)
        logger.info(
            f"Account deletion request notification sent for account {deletion_request.account_id}"
        )
        return {"status": "success", "message": "Deletion request received"}
    except Exception as e:
        logger.error(
            f"Failed to send account deletion notification: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="Failed to process deletion request"
        )
