"""Account-related endpoints."""

import html
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from preloop.api.auth.jwt import get_current_active_user
from preloop.api.common import get_account_for_user
from preloop.models.crud import (
    crud_account,
    crud_api_key,
    crud_managed_agent,
    crud_managed_agent_credential,
    crud_managed_agent_enrollment,
    crud_runtime_session,
    crud_runtime_session_activity,
    crud_user,
)
from preloop.models.db.session import get_db_session
from preloop.models.models.account import Account
from preloop.models.models.user import User as UserModel
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
    ManagedAgentCredentialCreateRequest,
    ManagedAgentCredentialCreateResponse,
    ManagedAgentCredentialSummary,
    ManagedAgentEnrollmentCreateRequest,
    ManagedAgentEnrollmentSummary,
    ManagedAgentToolActivitySummary,
    ManagedAgentUpdateRequest,
    RuntimeSessionSummary,
    RuntimeSessionUpdateRequest,
)
from preloop.services.account_realtime import (
    ACCOUNT_TOPIC_MANAGED_AGENTS,
    ACCOUNT_TOPIC_AUDIT,
    ACCOUNT_TOPIC_RUNTIME_SESSIONS,
    build_account_event,
    emit_account_event,
)
from preloop.services.model_gateway_usage import ModelGatewayUsageService
from preloop.services.runtime_session_explorer import RuntimeSessionExplorerService

logger = logging.getLogger(__name__)

router = APIRouter()
public_router = APIRouter()  # Public endpoints (no auth required)


def _build_managed_agent_detail_response(
    db: Session, *, account_id: str, agent_id: str
) -> Optional[ManagedAgentDetailResponse]:
    summary = crud_managed_agent.get_summary_for_account(
        db, account_id=account_id, agent_id=agent_id
    )
    if summary is None:
        return None
    aggregate = crud_managed_agent.get_usage_aggregate_for_account(
        db, account_id=account_id, agent_id=agent_id
    )
    usage_by_model = crud_managed_agent.get_usage_by_model_for_account(
        db, account_id=account_id, agent_id=agent_id
    )
    activity_by_server = crud_runtime_session_activity.get_server_summary_for_principal(
        db,
        account_id=account_id,
        runtime_principal_type=summary["session_source_type"],
        runtime_principal_id=summary["session_source_id"],
    )
    activity_by_tool = crud_runtime_session_activity.get_tool_summary_for_principal(
        db,
        account_id=account_id,
        runtime_principal_type=summary["session_source_type"],
        runtime_principal_id=summary["session_source_id"],
    )
    sessions = crud_runtime_session.list_account_sessions(
        db,
        account_id=account_id,
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
        credentials=[
            ManagedAgentCredentialSummary(**item)
            for item in crud_managed_agent_credential.list_for_agent(
                db, account_id=account_id, agent_id=agent_id
            )
        ],
        enrollments=[
            ManagedAgentEnrollmentSummary(**item)
            for item in crud_managed_agent_enrollment.list_for_agent(
                db, account_id=account_id, agent_id=agent_id
            )
        ],
    )


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


@router.get("/agents", response_model=AccountManagedAgentListResponse)
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


@router.get("/agents/{agent_id}", response_model=ManagedAgentDetailResponse)
async def get_account_managed_agent(
    agent_id: str,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
):
    """Return one enrolled external agent for the current account."""
    response = _build_managed_agent_detail_response(
        db, account_id=str(account.id), agent_id=agent_id
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Managed agent not found"
        )
    return response


@router.get(
    "/agents/{agent_id}/credentials",
    response_model=list[ManagedAgentCredentialSummary],
)
async def list_account_managed_agent_credentials(
    agent_id: str,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
):
    """List durable credentials for one managed agent."""
    agent = crud_managed_agent.get_for_account(
        db, account_id=str(account.id), agent_id=agent_id
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Managed agent not found"
        )
    return [
        ManagedAgentCredentialSummary(**item)
        for item in crud_managed_agent_credential.list_for_agent(
            db, account_id=str(account.id), agent_id=agent_id
        )
    ]


@router.post(
    "/agents/{agent_id}/credentials",
    response_model=ManagedAgentCredentialCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account_managed_agent_credential(
    agent_id: str,
    payload: ManagedAgentCredentialCreateRequest,
    account: Annotated[Account, Depends(get_account_for_user)],
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
):
    """Create a durable credential for one managed agent."""
    agent = crud_managed_agent.get_for_account(
        db, account_id=str(account.id), agent_id=agent_id
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Managed agent not found"
        )
    if agent.lifecycle_state != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Durable credentials can only be created for active agents",
        )
    existing_names = {
        item["name"]
        for item in crud_managed_agent_credential.list_for_agent(
            db, account_id=str(account.id), agent_id=agent_id
        )
    }
    if payload.name in existing_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Managed agent credential with this name already exists",
        )

    expires_at = None
    if payload.expires_in_days is not None:
        expires_at = datetime.now(UTC) + timedelta(days=payload.expires_in_days)
    token_value = f"agt_{secrets.token_urlsafe(32)}"
    api_key, presented_token = crud_api_key.create_runtime_key(
        db,
        name=f"Managed Agent Credential: {agent.display_name} / {payload.name}",
        account_id=current_user.account_id,
        user_id=current_user.id,
        scopes=payload.scopes,
        expires_at=expires_at,
        key_value=token_value,
        commit=False,
        context_data={
            "managed_agent_id": str(agent.id),
            "credential_kind": "managed_agent_durable",
            "allowed_mcp_servers": agent.managed_mcp_servers,
            "runtime_principal": {
                "type": agent.session_source_type,
                "id": agent.session_source_id,
                "name": agent.display_name,
                "user_id": str(current_user.id),
                "username": current_user.username,
            },
        },
    )
    credential = crud_managed_agent_credential.create_for_agent(
        db,
        account_id=account.id,
        agent_id=agent.id,
        api_key_id=api_key.id,
        created_by_user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        scopes=payload.scopes,
        key_prefix=api_key.key_prefix,
        commit=True,
    )
    emit_account_event(
        build_account_event(
            account_id=str(account.id),
            topic=ACCOUNT_TOPIC_AUDIT,
            event_type="audit_event",
            payload={
                "action": "managed_agent_credential_created",
                "agent_id": str(agent.id),
                "credential_id": str(credential.id),
                "credential_name": credential.name,
            },
            runtime_session_id=str(agent.runtime_session_id)
            if agent.runtime_session_id
            else None,
        )
    )
    return ManagedAgentCredentialCreateResponse(
        credential=ManagedAgentCredentialSummary(
            **crud_managed_agent_credential._row_to_summary(credential, api_key)
        ),
        token=presented_token,
    )


@router.delete(
    "/agents/{agent_id}/credentials/{credential_id}",
    response_model=ManagedAgentCredentialSummary,
)
async def revoke_account_managed_agent_credential(
    agent_id: str,
    credential_id: str,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
):
    """Revoke one durable credential for a managed agent."""
    credential = crud_managed_agent_credential.revoke_for_agent(
        db,
        account_id=str(account.id),
        agent_id=agent_id,
        credential_id=credential_id,
        reason="revoked by operator",
        commit=True,
    )
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Managed agent credential not found",
        )
    emit_account_event(
        build_account_event(
            account_id=str(account.id),
            topic=ACCOUNT_TOPIC_AUDIT,
            event_type="audit_event",
            payload={
                "action": "managed_agent_credential_revoked",
                "agent_id": agent_id,
                "credential_id": credential_id,
            },
        )
    )
    return ManagedAgentCredentialSummary(
        **crud_managed_agent_credential._row_to_summary(credential, credential.api_key)
    )


@router.get(
    "/agents/{agent_id}/enrollments",
    response_model=list[ManagedAgentEnrollmentSummary],
)
async def list_account_managed_agent_enrollments(
    agent_id: str,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
):
    """List durable enrollment records for one managed agent."""
    agent = crud_managed_agent.get_for_account(
        db, account_id=str(account.id), agent_id=agent_id
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Managed agent not found"
        )
    return [
        ManagedAgentEnrollmentSummary(**item)
        for item in crud_managed_agent_enrollment.list_for_agent(
            db, account_id=str(account.id), agent_id=agent_id
        )
    ]


@router.post(
    "/agents/{agent_id}/enrollments",
    response_model=ManagedAgentEnrollmentSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_account_managed_agent_enrollment(
    agent_id: str,
    payload: ManagedAgentEnrollmentCreateRequest,
    account: Annotated[Account, Depends(get_account_for_user)],
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
):
    """Persist one enrollment record for a managed agent."""
    agent = crud_managed_agent.get_for_account(
        db, account_id=str(account.id), agent_id=agent_id
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Managed agent not found"
        )
    enrollment = crud_managed_agent_enrollment.create_for_agent(
        db,
        account_id=account.id,
        agent_id=agent.id,
        created_by_user_id=current_user.id,
        enrollment_type=payload.enrollment_type,
        adapter_key=payload.adapter_key,
        status=payload.status,
        target_config_path=payload.target_config_path,
        discovered_config=payload.discovered_config,
        managed_config=payload.managed_config,
        backup_metadata=payload.backup_metadata,
        validation_result=payload.validation_result,
        restore_available=payload.restore_available,
        last_applied_at=payload.last_applied_at,
        last_validated_at=payload.last_validated_at,
        last_restored_at=payload.last_restored_at,
        commit=True,
    )
    emit_account_event(
        build_account_event(
            account_id=str(account.id),
            topic=ACCOUNT_TOPIC_AUDIT,
            event_type="audit_event",
            payload={
                "action": "managed_agent_enrollment_created",
                "agent_id": str(agent.id),
                "enrollment_id": str(enrollment.id),
                "enrollment_type": enrollment.enrollment_type,
                "status": enrollment.status,
            },
            runtime_session_id=str(agent.runtime_session_id)
            if agent.runtime_session_id
            else None,
        )
    )
    return ManagedAgentEnrollmentSummary(
        **crud_managed_agent_enrollment._to_summary(enrollment)
    )


@router.patch("/agents/{agent_id}", response_model=ManagedAgentSummary)
async def update_account_managed_agent(
    agent_id: str,
    update: ManagedAgentUpdateRequest,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
):
    """Update managed-agent ownership or lifecycle controls."""
    agent = crud_managed_agent.get_for_account(
        db, account_id=str(account.id), agent_id=agent_id
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Managed agent not found"
        )

    set_owner = "owner_user_id" in update.model_fields_set
    owner_user_id = None
    if set_owner and update.owner_user_id:
        owner = crud_user.get(db, id=update.owner_user_id)
        if owner is None or str(owner.account_id) != str(account.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owner must belong to the current account",
            )
        owner_user_id = owner.id

    lifecycle_state = None
    if update.lifecycle_action == "suspend":
        lifecycle_state = "suspended"
    elif update.lifecycle_action == "resume":
        lifecycle_state = "active"
    elif update.lifecycle_action == "decommission":
        lifecycle_state = "decommissioned"
    elif update.lifecycle_action == "reenroll":
        lifecycle_state = "active"

    updated = crud_managed_agent.update_operator_state(
        db,
        account_id=str(account.id),
        agent_id=agent_id,
        owner_user_id=owner_user_id,
        set_owner=set_owner,
        lifecycle_state=lifecycle_state,
        lifecycle_reason=update.reason,
        commit=True,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Managed agent not found"
        )

    detail = _build_managed_agent_detail_response(
        db, account_id=str(account.id), agent_id=agent_id
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Managed agent not found"
        )

    emit_account_event(
        build_account_event(
            account_id=str(account.id),
            topic=ACCOUNT_TOPIC_MANAGED_AGENTS,
            event_type=(
                "managed_agent_updated"
                if updated.lifecycle_state == "active"
                else f"managed_agent_{updated.lifecycle_state}"
            ),
            payload=detail.agent.model_dump(mode="json"),
            runtime_session_id=detail.agent.runtime_session_id,
        )
    )
    emit_account_event(
        build_account_event(
            account_id=str(account.id),
            topic=ACCOUNT_TOPIC_AUDIT,
            event_type="audit_event",
            payload={
                "action": "managed_agent_updated",
                "agent_id": detail.agent.id,
                "display_name": detail.agent.display_name,
                "owner_user_id": detail.agent.owner_user_id,
                "owner_username": detail.agent.owner_username,
                "lifecycle_state": detail.agent.lifecycle_state,
                "lifecycle_reason": detail.agent.lifecycle_reason,
            },
            runtime_session_id=detail.agent.runtime_session_id,
        )
    )
    return detail.agent


@router.get("/runtime-sessions", response_model=AccountRuntimeSessionListResponse)
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
    "/runtime-sessions/{runtime_session_id}",
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


@router.patch(
    "/runtime-sessions/{runtime_session_id}",
    response_model=RuntimeSessionSummary,
)
async def update_account_runtime_session(
    runtime_session_id: str,
    update: RuntimeSessionUpdateRequest,
    account: Annotated[Account, Depends(get_account_for_user)],
    db: Session = Depends(get_db_session),
):
    """Update runtime-session lifecycle controls for the current account."""
    session = crud_runtime_session.get_account_session(
        db, account_id=str(account.id), runtime_session_id=runtime_session_id
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Runtime session not found"
        )

    if update.action != "end":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported runtime session action",
        )

    ended_at = session.ended_at or datetime.now(UTC)
    updated = crud_runtime_session.update_operator_state(
        db,
        account_id=str(account.id),
        runtime_session_id=runtime_session_id,
        ended_at=ended_at,
        commit=True,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Runtime session not found"
        )

    crud_api_key.deactivate_runtime_keys_for_session(
        db,
        account_id=str(account.id),
        runtime_session_id=runtime_session_id,
        commit=True,
    )

    managed_agent_summary = None
    if updated.runtime_principal_type and updated.runtime_principal_id:
        managed_agent = crud_managed_agent.clear_runtime_session_binding(
            db,
            account_id=str(account.id),
            session_source_type=updated.runtime_principal_type,
            session_source_id=updated.runtime_principal_id,
            runtime_session_id=updated.id,
            commit=True,
        )
        if managed_agent is not None:
            managed_agent_summary = crud_managed_agent.get_summary_for_account(
                db, account_id=str(account.id), agent_id=str(managed_agent.id)
            )

    summary_row = crud_runtime_session.get_account_session_summary(
        db, account_id=str(account.id), runtime_session_id=runtime_session_id
    )
    if summary_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Runtime session not found"
        )
    summary = RuntimeSessionExplorerService._summary_row_to_schema(summary_row)

    try:
        from preloop.plugins.base import get_plugin_manager

        plugin_manager = get_plugin_manager()
        audit_service = plugin_manager.get_service("audit_service")
        if audit_service:
            audit_service.log_runtime_session_event(
                db=db,
                account_id=account.id,
                runtime_session_id=updated.id,
                event="ended",
                session_source_type=updated.session_source_type,
                session_source_id=updated.session_source_id,
                session_reference=updated.session_reference,
                runtime_principal_type=updated.runtime_principal_type,
                runtime_principal_id=updated.runtime_principal_id,
                runtime_principal_name=updated.runtime_principal_name,
            )
    except Exception:
        logger.debug("Failed to audit runtime session operator action", exc_info=True)

    emit_account_event(
        build_account_event(
            account_id=str(account.id),
            topic=ACCOUNT_TOPIC_RUNTIME_SESSIONS,
            event_type="runtime_session_ended",
            payload=summary.model_dump(mode="json"),
            runtime_session_id=summary.id,
            flow_id=summary.flow_id,
            execution_id=summary.flow_execution_id,
        )
    )
    emit_account_event(
        build_account_event(
            account_id=str(account.id),
            topic=ACCOUNT_TOPIC_AUDIT,
            event_type="audit_event",
            payload={
                "action": "runtime_session_ended",
                "runtime_session_id": summary.id,
                "session_source_type": summary.session_source_type,
                "session_source_id": summary.session_source_id,
                "session_reference": summary.session_reference,
                "runtime_principal_type": summary.runtime_principal_type,
                "runtime_principal_id": summary.runtime_principal_id,
                "runtime_principal_name": summary.runtime_principal_name,
                "reason": update.reason,
            },
            runtime_session_id=summary.id,
            flow_id=summary.flow_id,
            execution_id=summary.flow_execution_id,
        )
    )
    if managed_agent_summary is not None:
        emit_account_event(
            build_account_event(
                account_id=str(account.id),
                topic=ACCOUNT_TOPIC_MANAGED_AGENTS,
                event_type="managed_agent_updated",
                payload=managed_agent_summary,
                runtime_session_id=summary.id,
                flow_id=summary.flow_id,
                execution_id=summary.flow_execution_id,
            )
        )

    return summary


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
