"""User invitation endpoints."""

import logging
from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from preloop_ai.api.auth.jwt import get_current_active_user, get_password_hash
from preloop_ai.schemas.invitation import (
    InvitationAccept,
    InvitationCreate,
    InvitationListResponse,
    InvitationPublicInfo,
    InvitationResponse,
)
from preloop_ai.utils.email import send_invitation_email
from preloop_models.crud import crud_account, crud_user, crud_user_invitation
from preloop_models.db.session import get_db_session
from preloop_models.models.user import User
from preloop_models.models.user_invitation import UserInvitationStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    invitation_data: InvitationCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Create a new user invitation.

    Args:
        invitation_data: Invitation data with email, optional role IDs, and optional team IDs
        current_user: Current authenticated user
        db: Database session

    Returns:
        InvitationResponse: Created invitation data

    Raises:
        HTTPException: If user already exists or invitation already pending
    """
    # TODO: Add permission check - only admins should be able to invite users

    # Check if user with this email already exists in the account
    existing_user = crud_user.get_by_email(
        db=db, email=invitation_data.email, account_id=current_user.account_id
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists in the account",
        )

    # Check if there's already a pending invitation
    pending_invitation = crud_user_invitation.get_by_email(
        db=db, email=invitation_data.email, account_id=current_user.account_id
    )
    if pending_invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending invitation already exists for this email",
        )

    # Validate that all role_ids belong to the current account
    # Security: Prevent cross-account role assignment
    validated_role_ids = []
    if invitation_data.role_ids:
        from preloop_models.crud import crud_role

        for role_id in invitation_data.role_ids:
            role = crud_role.get(db=db, id=role_id, account_id=current_user.account_id)
            if not role:
                # Check if it's a system role (account_id is None)
                role = crud_role.get(db=db, id=role_id)
                if not role or role.account_id is not None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Role {role_id} does not exist or does not belong to your account",
                    )
            validated_role_ids.append(str(role_id))

    # Validate that all team_ids belong to the current account
    # Security: Prevent cross-account team assignment
    validated_team_ids = []
    if invitation_data.team_ids:
        from preloop_models.crud import crud_team

        for team_id in invitation_data.team_ids:
            team = crud_team.get(db=db, id=team_id, account_id=current_user.account_id)
            if not team:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Team {team_id} does not exist or does not belong to your account",
                )
            validated_team_ids.append(str(team_id))

    # Convert role_ids list to comma-separated string
    role_ids_str = ",".join(validated_role_ids) if validated_role_ids else None

    # Convert team_ids list to comma-separated string
    team_ids_str = ",".join(validated_team_ids) if validated_team_ids else None

    # Create invitation
    invitation_dict = {
        "account_id": current_user.account_id,
        "email": invitation_data.email,
        "invited_by": current_user.id,
        "role_ids": role_ids_str,
        "team_ids": team_ids_str,
    }

    invitation = crud_user_invitation.create(db=db, obj_in=invitation_dict)
    db.commit()
    db.refresh(invitation)

    logger.info(
        f"Invitation created for {invitation_data.email} by {current_user.username}"
    )

    # Send invitation email
    account = crud_account.get(db, id=current_user.account_id)
    if account:
        # Get role names (already validated above, but double-check for email)
        role_names = []
        if invitation.role_ids:
            from preloop_models.crud import crud_role

            role_ids = [
                UUID(rid.strip())
                for rid in invitation.role_ids.split(",")
                if rid.strip()
            ]
            for role_id in role_ids:
                # Try account-specific role first, then system role
                role = crud_role.get(
                    db=db, id=role_id, account_id=current_user.account_id
                )
                if not role:
                    # Check for system role
                    role = crud_role.get(db=db, id=role_id)
                    if role and role.account_id is not None:
                        # Skip roles from other accounts (shouldn't happen due to validation above)
                        logger.warning(
                            f"Skipping role {role_id} in invitation email - belongs to different account"
                        )
                        continue
                if role:
                    role_names.append(role.name)

        # Get team names (already validated above, but double-check for email)
        team_names = []
        if invitation.team_ids:
            from preloop_models.crud import crud_team

            team_ids = [
                UUID(tid.strip())
                for tid in invitation.team_ids.split(",")
                if tid.strip()
            ]
            for team_id in team_ids:
                # Validate team belongs to the same account
                team = crud_team.get(
                    db=db, id=team_id, account_id=current_user.account_id
                )
                if not team:
                    # Shouldn't happen due to validation above
                    logger.warning(
                        f"Skipping team {team_id} in invitation email - not found or belongs to different account"
                    )
                    continue
                team_names.append(team.name)

        send_invitation_email(
            user_email=invitation.email,
            token=invitation.token,
            organization_name=account.organization_name or "your organization",
            invited_by=current_user.email or current_user.username,
            role_names=role_names if role_names else None,
            team_names=team_names if team_names else None,
        )
    else:
        logger.warning(
            f"Could not send invitation email: account {current_user.account_id} not found"
        )

    return InvitationResponse.model_validate(invitation)


@router.get("/invitations", response_model=InvitationListResponse)
async def list_invitations(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
):
    """List all invitations in the current account.

    Args:
        current_user: Current authenticated user
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        status_filter: Optional status filter (pending, accepted, expired, cancelled)

    Returns:
        InvitationListResponse: Paginated list of invitations
    """
    # TODO: Add permission check - only admins should be able to list invitations

    if status_filter:
        invitations = crud_user_invitation.get_by_account(
            db=db,
            account_id=current_user.account_id,
            status=status_filter,
            skip=skip,
            limit=limit,
        )
        total = len(invitations)  # Simple count for filtered results
    else:
        from preloop_models.models.user_invitation import UserInvitation

        invitations = (
            db.query(UserInvitation)
            .filter(UserInvitation.account_id == current_user.account_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
        total = (
            db.query(UserInvitation)
            .filter(UserInvitation.account_id == current_user.account_id)
            .count()
        )

    return InvitationListResponse(
        invitations=[InvitationResponse.model_validate(inv) for inv in invitations],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/invitations/{invitation_id}", response_model=InvitationResponse)
async def get_invitation(
    invitation_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Get a specific invitation by ID.

    Args:
        invitation_id: Invitation ID to retrieve
        current_user: Current authenticated user
        db: Database session

    Returns:
        InvitationResponse: Invitation data

    Raises:
        HTTPException: If invitation not found or not in same account
    """
    invitation = crud_user_invitation.get(db=db, id=invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Verify invitation is in the same account
    if invitation.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access invitation from different account",
        )

    return InvitationResponse.model_validate(invitation)


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(
    invitation_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Cancel a pending invitation.

    Args:
        invitation_id: Invitation ID to cancel
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If invitation not found, not in same account, or already accepted
    """
    # TODO: Add permission check - only admins should be able to cancel invitations

    invitation = crud_user_invitation.get(db=db, id=invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Verify invitation is in the same account
    if invitation.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot cancel invitation from different account",
        )

    # Check if invitation is already accepted
    if invitation.status == UserInvitationStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel an accepted invitation",
        )

    # Cancel the invitation
    crud_user_invitation.cancel(db=db, invitation_id=invitation_id)
    db.commit()

    logger.info(f"Invitation {invitation_id} cancelled by {current_user.username}")


@router.post(
    "/invitations/{invitation_id}/resend", status_code=status.HTTP_204_NO_CONTENT
)
async def resend_invitation(
    invitation_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Resend an invitation email.

    Args:
        invitation_id: Invitation ID to resend
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If invitation not found, not in same account, or not pending
    """
    # TODO: Add permission check - only admins should be able to resend invitations

    invitation = crud_user_invitation.get(db=db, id=invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Verify invitation is in the same account
    if invitation.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot resend invitation from different account",
        )

    # Check if invitation is pending
    if invitation.status != UserInvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resend invitation with status: {invitation.status}",
        )

    # Check if invitation is expired
    if invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resend expired invitation. Please create a new one.",
        )

    logger.info(f"Invitation {invitation_id} resent by {current_user.username}")

    # Send invitation email
    account = crud_account.get(db, id=current_user.account_id)
    if account:
        # Get role names (with account validation for defense in depth)
        role_names = []
        if invitation.role_ids:
            from preloop_models.crud import crud_role

            role_ids = [
                UUID(rid.strip())
                for rid in invitation.role_ids.split(",")
                if rid.strip()
            ]
            for role_id in role_ids:
                # Try account-specific role first, then system role
                role = crud_role.get(
                    db=db, id=role_id, account_id=current_user.account_id
                )
                if not role:
                    # Check for system role
                    role = crud_role.get(db=db, id=role_id)
                    if role and role.account_id is not None:
                        # Skip roles from other accounts
                        logger.warning(
                            f"Skipping role {role_id} in invitation {invitation_id} - belongs to different account"
                        )
                        continue
                if role:
                    role_names.append(role.name)

        # Get team names (with account validation for defense in depth)
        team_names = []
        if invitation.team_ids:
            from preloop_models.crud import crud_team

            team_ids = [
                UUID(tid.strip())
                for tid in invitation.team_ids.split(",")
                if tid.strip()
            ]
            for team_id in team_ids:
                # Validate team belongs to the same account
                team = crud_team.get(
                    db=db, id=team_id, account_id=current_user.account_id
                )
                if not team:
                    logger.warning(
                        f"Skipping team {team_id} in invitation {invitation_id} - not found or belongs to different account"
                    )
                    continue
                team_names.append(team.name)

        send_invitation_email(
            user_email=invitation.email,
            token=invitation.token,
            organization_name=account.organization_name or "your organization",
            invited_by=current_user.email or current_user.username,
            role_names=role_names if role_names else None,
            team_names=team_names if team_names else None,
        )
    else:
        logger.warning(
            f"Could not send invitation email: account {current_user.account_id} not found"
        )


# Public endpoint (no authentication required)
@router.get("/invitations/public/{token}", response_model=InvitationPublicInfo)
async def get_invitation_info(
    token: str,
    db: Session = Depends(get_db_session),
):
    """Get public information about an invitation (for the accept page).

    This endpoint is public and doesn't require authentication.

    Args:
        token: Invitation token
        db: Database session

    Returns:
        InvitationPublicInfo: Public invitation information
    """
    invitation = crud_user_invitation.get_by_token(db=db, token=token)

    if not invitation:
        return InvitationPublicInfo(
            email=None,
            organization_name=None,
            expires_at=datetime.now(timezone.utc),
            is_valid=False,
            error_message="Invalid invitation token",
        )

    # Check if invitation is expired
    if invitation.expires_at < datetime.now(timezone.utc):
        return InvitationPublicInfo(
            email=invitation.email,
            organization_name=None,
            expires_at=invitation.expires_at,
            is_valid=False,
            error_message="This invitation has expired",
        )

    # Check if invitation is already accepted
    if invitation.status == UserInvitationStatus.ACCEPTED:
        return InvitationPublicInfo(
            email=invitation.email,
            organization_name=None,
            expires_at=invitation.expires_at,
            is_valid=False,
            error_message="This invitation has already been accepted",
        )

    # Check if invitation is cancelled
    if invitation.status == UserInvitationStatus.CANCELLED:
        return InvitationPublicInfo(
            email=invitation.email,
            organization_name=None,
            expires_at=invitation.expires_at,
            is_valid=False,
            error_message="This invitation has been cancelled",
        )

    # Get account info for organization name
    account = crud_account.get(db=db, id=invitation.account_id)

    # Get role names
    role_names = []
    if invitation.role_ids:
        from preloop_models.crud import crud_role
        from uuid import UUID

        role_ids = [
            UUID(rid.strip()) for rid in invitation.role_ids.split(",") if rid.strip()
        ]
        for role_id in role_ids:
            role = crud_role.get(db=db, id=role_id)
            if role:
                role_names.append(role.name)

    # Get team names
    team_names = []
    if invitation.team_ids:
        from preloop_models.crud import crud_team
        from uuid import UUID

        team_ids = [
            UUID(tid.strip()) for tid in invitation.team_ids.split(",") if tid.strip()
        ]
        for team_id in team_ids:
            team = crud_team.get(db=db, id=team_id)
            if team:
                team_names.append(team.name)

    return InvitationPublicInfo(
        email=invitation.email,
        organization_name=account.organization_name if account else None,
        expires_at=invitation.expires_at,
        is_valid=True,
        role_names=role_names,
        team_names=team_names,
    )


# Public endpoint (no authentication required)
@router.post("/invitations/accept", status_code=status.HTTP_201_CREATED)
async def accept_invitation(
    accept_data: InvitationAccept,
    db: Session = Depends(get_db_session),
):
    """Accept an invitation and create a new user account.

    This endpoint is public and doesn't require authentication.

    Args:
        accept_data: Invitation acceptance data (token, username, password, full_name)
        db: Database session

    Returns:
        dict: Success message with user ID

    Raises:
        HTTPException: If invitation invalid, expired, or username already exists
    """
    invitation = crud_user_invitation.get_by_token(db=db, token=accept_data.token)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invitation token",
        )

    # Validate invitation
    # Check if invitation is expired
    if invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired",
        )

    # Check if invitation is not pending
    if invitation.status != UserInvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This invitation has status: {invitation.status}",
        )

    # Check if username is already taken
    existing_user = crud_user.get_by_username(db=db, username=accept_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Create the new user
    user_dict = {
        "account_id": invitation.account_id,
        "username": accept_data.username,
        "email": invitation.email,
        "email_verified": True,  # Email is verified through invitation
        "full_name": accept_data.full_name,
        "hashed_password": get_password_hash(accept_data.password),
        "is_active": True,
        "user_source": "local",
    }

    user = crud_user.create(db=db, obj_in=user_dict)

    # Mark invitation as accepted
    crud_user_invitation.accept(db=db, invitation_id=invitation.id, user_id=user.id)

    # Assign roles if specified (with strict account validation)
    # Security: Prevent cross-account role assignment during invitation acceptance
    if invitation.role_ids:
        from preloop_models.crud import crud_user_role, crud_role

        role_ids = [
            UUID(rid.strip()) for rid in invitation.role_ids.split(",") if rid.strip()
        ]
        for role_id in role_ids:
            # Validate role belongs to the invitation's account or is a system role
            role = crud_role.get(db=db, id=role_id, account_id=invitation.account_id)
            if not role:
                # Check if it's a system role
                role = crud_role.get(db=db, id=role_id)
                if not role or role.account_id is not None:
                    # Role doesn't exist or belongs to a different account
                    logger.error(
                        f"Security: Skipping role {role_id} during invitation acceptance - "
                        f"not found or belongs to different account. Invitation ID: {invitation.id}"
                    )
                    continue

            user_role_dict = {
                "user_id": user.id,
                "role_id": role_id,
                "granted_by": invitation.invited_by,
            }
            crud_user_role.create(db=db, obj_in=user_role_dict)

    # Assign teams if specified (with strict account validation)
    # Security: Prevent cross-account team assignment during invitation acceptance
    if invitation.team_ids:
        from preloop_models.crud import crud_team

        team_ids = [
            UUID(tid.strip()) for tid in invitation.team_ids.split(",") if tid.strip()
        ]
        for team_id in team_ids:
            # Validate team belongs to the invitation's account
            team = crud_team.get(db=db, id=team_id, account_id=invitation.account_id)
            if not team:
                # Team doesn't exist or belongs to a different account - skip it
                logger.error(
                    f"Security: Skipping team {team_id} during invitation acceptance - "
                    f"not found or belongs to different account. Invitation ID: {invitation.id}"
                )
                continue

            crud_team.add_member(
                db=db,
                team_id=team_id,
                user_id=user.id,
                role="member",
                added_by=invitation.invited_by,
            )

    db.commit()
    db.refresh(user)

    logger.info(f"User {user.username} created by accepting invitation {invitation.id}")

    # Update Stripe subscription quantity to reflect new user count
    try:
        from preloop_ai.plugins.proprietary.billing.service import BillingService

        billing_service = BillingService(db)
        billing_service.update_subscription_quantity(str(invitation.account_id))
    except Exception as e:
        logger.warning(f"Failed to update Stripe subscription quantity: {e}")
        # Don't fail user creation if billing update fails

    return {
        "message": "Account created successfully",
        "user_id": str(user.id),
        "username": user.username,
    }
