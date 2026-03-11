"""Account-related endpoints."""

import html
import logging
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from preloop.api.common import get_account_for_user
from preloop.models.crud import (
    crud_account,
    crud_managed_agent,
    crud_runtime_session,
    crud_runtime_session_activity,
)
from preloop.models.db.session import get_db_session
from preloop.models.models.account import Account
from preloop.schemas.gateway_usage import (
    ManagedAgentDetailResponse,
    AccountManagedAgentListResponse,
    AccountRuntimeSessionDetailResponse,
    AccountRuntimeSessionListResponse,
    AccountGatewayUsageSearchResponse,
    AccountGatewayUsageSummaryResponse,
    GatewayTokenUsage,
    ManagedAgentUsageAggregate,
    ManagedAgentServerActivitySummary,
    ManagedAgentSummary,
    ManagedAgentToolActivitySummary,
)
from preloop.services.model_gateway_usage import ModelGatewayUsageService
from preloop.services.runtime_session_explorer import RuntimeSessionExplorerService

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


@router.get(
    "/account/gateway-usage/search",
    response_model=AccountGatewayUsageSearchResponse,
)
async def search_account_gateway_usage(
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
    query: Optional[str] = Query(None, min_length=1),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    provider_name: Optional[str] = Query(None),
    model_alias: Optional[str] = Query(None),
    flow_id: Optional[str] = Query(None),
    runtime_session_id: Optional[str] = Query(None),
    session_source_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Search or list indexed gateway interactions for the current account."""
    return ModelGatewayUsageService(db).search_account_interactions(
        account=account,
        query=query,
        start_date=start_date,
        end_date=end_date,
        provider_name=provider_name,
        model_alias=model_alias,
        flow_id=flow_id,
        runtime_session_id=runtime_session_id,
        session_source_type=session_source_type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/account/agents",
    response_model=AccountManagedAgentListResponse,
)
async def list_account_managed_agents(
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
    query: Optional[str] = Query(None, min_length=1),
    session_source_type: Optional[str] = Query(None),
    status: str = Query("all", pattern="^(all|active|ended)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List enrolled external agents for the current account."""
    result = crud_managed_agent.list_for_account(
        db,
        account_id=str(account.id),
        query=query,
        session_source_type=session_source_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return AccountManagedAgentListResponse(
        query=query,
        session_source_type=session_source_type,
        status=status,
        total=result["total"],
        limit=limit,
        offset=offset,
        items=result["items"],
    )


@router.get(
    "/account/agents/{agent_id}",
    response_model=ManagedAgentDetailResponse,
)
async def get_account_managed_agent(
    agent_id: str,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
):
    """Return one enrolled external agent for the current account."""
    summary = crud_managed_agent.get_summary_for_account(
        db, account_id=str(account.id), agent_id=agent_id
    )
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Managed agent not found"
        )
    aggregate = crud_managed_agent.get_usage_aggregate_for_account(
        db, account_id=str(account.id), agent_id=agent_id
    )
    usage_by_model = crud_managed_agent.get_usage_by_model_for_account(
        db, account_id=str(account.id), agent_id=agent_id
    )
    activity_by_server = crud_runtime_session_activity.get_server_summary_for_principal(
        db,
        account_id=str(account.id),
        runtime_principal_type=summary["session_source_type"],
        runtime_principal_id=summary["session_source_id"],
    )
    activity_by_tool = crud_runtime_session_activity.get_tool_summary_for_principal(
        db,
        account_id=str(account.id),
        runtime_principal_type=summary["session_source_type"],
        runtime_principal_id=summary["session_source_id"],
    )
    sessions = crud_runtime_session.list_account_sessions(
        db,
        account_id=str(account.id),
        runtime_principal_type=summary["session_source_type"],
        runtime_principal_id=summary["session_source_id"],
        status="all",
        limit=20,
        offset=0,
    )
    return ManagedAgentDetailResponse(
        agent=ManagedAgentSummary(**summary),
        aggregate=ManagedAgentUsageAggregate(
            session_count=aggregate["session_count"] if aggregate else 0,
            total_requests=aggregate["total_requests"] if aggregate else 0,
            successful_requests=aggregate["successful_requests"] if aggregate else 0,
            failed_requests=aggregate["failed_requests"] if aggregate else 0,
            token_usage=GatewayTokenUsage(
                prompt_tokens=aggregate["prompt_tokens"] if aggregate else 0,
                completion_tokens=aggregate["completion_tokens"] if aggregate else 0,
                total_tokens=aggregate["total_tokens"] if aggregate else 0,
            ),
            estimated_cost=aggregate["estimated_cost"] if aggregate else 0.0,
            latest_model_alias=aggregate["latest_model_alias"] if aggregate else None,
            latest_provider_name=(
                aggregate["latest_provider_name"] if aggregate else None
            ),
            last_request_at=aggregate["last_request_at"] if aggregate else None,
        ),
        usage_by_model=[
            ModelGatewayUsageService._model_row_to_schema(row) for row in usage_by_model
        ],
        activity_by_server=[
            ManagedAgentServerActivitySummary(**row) for row in activity_by_server
        ],
        activity_by_tool=[
            ManagedAgentToolActivitySummary(**row) for row in activity_by_tool
        ],
        sessions=[
            RuntimeSessionExplorerService._summary_row_to_schema(item)
            for item in sessions["items"]
        ],
    )


@router.get(
    "/account/runtime-sessions",
    response_model=AccountRuntimeSessionListResponse,
)
async def list_account_runtime_sessions(
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
    query: Optional[str] = Query(None, min_length=1),
    session_source_type: Optional[str] = Query(None),
    status: str = Query("all", pattern="^(all|active|ended)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List runtime sessions for the current account."""
    return RuntimeSessionExplorerService(db).list_account_sessions(
        account=account,
        query=query,
        session_source_type=session_source_type,
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/account/runtime-sessions/{runtime_session_id}",
    response_model=AccountRuntimeSessionDetailResponse,
)
async def get_account_runtime_session_detail(
    runtime_session_id: str,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
    interaction_query: Optional[str] = Query(None, min_length=1),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    interaction_limit: int = Query(50, ge=1, le=200),
    interaction_offset: int = Query(0, ge=0),
):
    """Return one runtime session with captured interaction details."""
    return RuntimeSessionExplorerService(db).get_account_session_detail(
        account=account,
        runtime_session_id=runtime_session_id,
        interaction_query=interaction_query,
        start_date=start_date,
        end_date=end_date,
        interaction_limit=interaction_limit,
        interaction_offset=interaction_offset,
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
