"""User management endpoints."""

import logging
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from preloop_ai.api.auth.jwt import get_current_active_user
from preloop_ai.schemas.user import (
    UserCreate,
    UserListResponse,
    UserPasswordUpdate,
    UserResponse,
    UserSummary,
    UserUpdate,
)
from preloop_models.crud import crud_user
from preloop_models.db.session import get_db_session
from preloop_models.models.user import User
from preloop_ai.utils.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/users/me", response_model=UserResponse)
@require_permission("view_users")
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Get current user's information.

    Returns:
        UserResponse: Current user's profile data
    """
    # Manually serialize roles to avoid ORM object serialization issues
    user_dict = {
        "id": current_user.id,
        "account_id": str(current_user.account_id),
        "username": current_user.username,
        "email": current_user.email,
        "email_verified": current_user.email_verified,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "user_source": current_user.user_source,
        "oauth_provider": current_user.oauth_provider,
        "last_login": current_user.last_login,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "roles": [
            {"role_id": str(r.role_id), "user_id": str(r.user_id)}
            for r in (current_user.roles or [])
        ],
        "inherited_roles": None,
    }
    return UserResponse(**user_dict)


@router.patch("/users/me", response_model=UserResponse)
@require_permission("edit_users")
async def update_current_user(
    update_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Update current user's profile.

    Args:
        update_data: User update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        UserResponse: Updated user data
    """
    updated_user = crud_user.update(
        db=db, db_obj=current_user, obj_in=update_data.model_dump(exclude_unset=True)
    )
    db.commit()
    db.refresh(updated_user)

    # Manually serialize roles to avoid ORM object serialization issues
    user_dict = {
        "id": updated_user.id,
        "account_id": str(updated_user.account_id),
        "username": updated_user.username,
        "email": updated_user.email,
        "email_verified": updated_user.email_verified,
        "full_name": updated_user.full_name,
        "is_active": updated_user.is_active,
        "user_source": updated_user.user_source,
        "oauth_provider": updated_user.oauth_provider,
        "last_login": updated_user.last_login,
        "created_at": updated_user.created_at,
        "updated_at": updated_user.updated_at,
        "roles": [
            {"role_id": str(r.role_id), "user_id": str(r.user_id)}
            for r in (updated_user.roles or [])
        ],
        "inherited_roles": None,
    }
    return UserResponse(**user_dict)


@router.post("/users/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
@require_permission("edit_users")
async def change_password(
    password_data: UserPasswordUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Change current user's password.

    Args:
        password_data: Current and new password
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If current password is incorrect or user uses external auth
    """
    # Check if user can change password (local users only)
    if not current_user.is_local_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change password for external authentication users",
        )

    # Verify current password
    from preloop_ai.api.auth.jwt import verify_password

    if not verify_password(
        password_data.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Update password
    from preloop_ai.api.auth.jwt import get_password_hash

    crud_user.update(
        db=db,
        db_obj=current_user,
        obj_in={"hashed_password": get_password_hash(password_data.new_password)},
    )
    db.commit()

    logger.info(f"Password changed for user {current_user.username}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@require_permission("manage_users")
async def create_user(
    user_data: UserCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Create a new user in the current account.

    Args:
        user_data: User creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        UserResponse: Created user data

    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username already exists
    existing_user = crud_user.get_by_username(db=db, username=user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Check if email already exists in this account
    existing_email = crud_user.get_by_email(
        db=db, email=user_data.email, account_id=current_user.account_id
    )
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists in this account",
        )

    # Create user with password hash
    from preloop_ai.api.auth.jwt import get_password_hash

    user_dict = user_data.model_dump()
    user_dict["account_id"] = current_user.account_id
    user_dict["hashed_password"] = get_password_hash(user_data.password)
    user_dict["is_active"] = True
    user_dict["email_verified"] = False
    user_dict["user_source"] = "local"

    # Remove password from dict as we already hashed it
    del user_dict["password"]

    user = crud_user.create(db=db, obj_in=user_dict)
    db.commit()
    db.refresh(user)

    logger.info(f"User {user.username} created by {current_user.username}")

    # Update Stripe subscription quantity to reflect new user count
    try:
        from preloop_ai.plugins.proprietary.billing.service import BillingService

        billing_service = BillingService(db)
        billing_service.update_subscription_quantity(str(current_user.account_id))
    except Exception as e:
        logger.warning(f"Failed to update Stripe subscription quantity: {e}")
        # Don't fail user creation if billing update fails

    return UserResponse.model_validate(user)


@router.get("/users", response_model=UserListResponse)
@require_permission("view_users")
async def list_users(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
    skip: int = 0,
    limit: int = 100,
):
    """List all users in the current user's account.

    Args:
        current_user: Current authenticated user
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        UserListResponse: Paginated list of users
    """
    users = crud_user.get_by_account(
        db=db, account_id=current_user.account_id, skip=skip, limit=limit
    )

    # Get total count
    total = db.query(User).filter(User.account_id == current_user.account_id).count()

    # Get roles for each user
    from preloop_models.crud import crud_user_role, crud_role

    user_responses = []
    for user in users:
        # Build user dict manually to avoid validation issues with roles relationship
        user_dict = {
            "id": user.id,
            "account_id": user.account_id,
            "username": user.username,
            "email": user.email,
            "email_verified": user.email_verified,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "user_source": user.user_source,
            "oauth_provider": user.oauth_provider,
            "last_login": user.last_login,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

        # Get user's directly assigned roles
        user_roles = crud_user_role.get_by_user(db=db, user_id=user.id)
        direct_roles = []
        for user_role in user_roles:
            role = crud_role.get(db=db, id=user_role.role_id)
            if role:
                direct_roles.append(
                    {
                        "id": str(role.id),
                        "name": role.name,
                        "description": role.description,
                    }
                )

        # Get user's inherited roles from team membership
        from preloop_models.models.team import TeamMembership
        from preloop_models.crud import crud_team_role

        team_memberships = (
            db.query(TeamMembership).filter(TeamMembership.user_id == user.id).all()
        )

        inherited_roles = []
        inherited_role_ids = set()  # Track IDs to avoid duplicates
        for membership in team_memberships:
            team_roles = crud_team_role.get_team_roles(
                db=db, team_id=membership.team_id
            )
            for role in team_roles:
                if role.id not in inherited_role_ids:
                    inherited_role_ids.add(role.id)
                    # Get team info for context
                    from preloop_models.crud import crud_team

                    team = crud_team.get(db=db, id=membership.team_id)
                    inherited_roles.append(
                        {
                            "id": str(role.id),
                            "name": role.name,
                            "description": role.description,
                            "team_name": team.name if team else "Unknown",
                        }
                    )

        user_dict["roles"] = direct_roles
        user_dict["inherited_roles"] = inherited_roles
        user_responses.append(user_dict)

    return {
        "users": user_responses,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/users/{user_id}", response_model=UserResponse)
@require_permission("view_users")
async def get_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Get a specific user by ID.

    Args:
        user_id: User ID to retrieve
        current_user: Current authenticated user
        db: Database session

    Returns:
        UserResponse: User data

    Raises:
        HTTPException: If user not found or not in same account
    """
    user = crud_user.get(db=db, id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify user is in the same account
    if user.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access user from different account",
        )

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
@require_permission("manage_users")
async def update_user(
    user_id: UUID,
    update_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Update a user's profile (admin only).

    Args:
        user_id: User ID to update
        update_data: User update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        UserResponse: Updated user data

    Raises:
        HTTPException: If user not found or not in same account
    """
    # TODO: Add permission check - only admins should be able to update other users

    user = crud_user.get(db=db, id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify user is in the same account
    if user.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update user from different account",
        )

    updated_user = crud_user.update(
        db=db, db_obj=user, obj_in=update_data.model_dump(exclude_unset=True)
    )
    db.commit()
    db.refresh(updated_user)

    return UserResponse.model_validate(updated_user)


@router.post("/users/{user_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
@require_permission("manage_users")
async def deactivate_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Deactivate a user (admin only).

    Args:
        user_id: User ID to deactivate
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If user not found, not in same account, or trying to deactivate self
    """
    # TODO: Add permission check - only admins should be able to deactivate users

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    user = crud_user.get(db=db, id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify user is in the same account
    if user.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate user from different account",
        )

    crud_user.deactivate(db=db, user_id=user_id)
    db.commit()

    logger.info(f"User {user_id} deactivated by {current_user.username}")

    # Update Stripe subscription quantity to reflect reduced user count
    try:
        from preloop_ai.plugins.proprietary.billing.service import BillingService

        billing_service = BillingService(db)
        billing_service.update_subscription_quantity(str(current_user.account_id))
    except Exception as e:
        logger.warning(f"Failed to update Stripe subscription quantity: {e}")
        # Don't fail user deactivation if billing update fails

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/search/{username}", response_model=List[UserSummary])
@require_permission("view_users")
async def search_users_by_username(
    username: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
    limit: int = 10,
):
    """Search users by username within the current account.

    Args:
        username: Username search string
        current_user: Current authenticated user
        db: Database session
        limit: Maximum number of results

    Returns:
        List[UserSummary]: List of matching users
    """
    # Use a simple LIKE query for username search
    from sqlalchemy import func

    users = (
        db.query(User)
        .filter(
            User.account_id == current_user.account_id,
            func.lower(User.username).contains(username.lower()),
            User.is_active,
        )
        .limit(limit)
        .all()
    )

    return [UserSummary.model_validate(user) for user in users]


@router.get("/users/{user_id}/roles", response_model=List[dict])
@require_permission("view_users")
async def get_user_roles(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Get roles assigned to a user.

    Args:
        user_id: User ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        List[dict]: List of roles assigned to the user

    Raises:
        HTTPException: If user not found or not in same account
    """
    # Verify user exists and is in the same account
    user = crud_user.get(db=db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access user from different account",
        )

    # Get user roles
    from preloop_models.crud import crud_user_role, crud_role

    user_roles = crud_user_role.get_by_user(db=db, user_id=user_id)

    roles = []
    for user_role in user_roles:
        role = crud_role.get(db=db, id=user_role.role_id)
        if role:
            roles.append(
                {
                    "id": str(role.id),
                    "name": role.name,
                    "description": role.description,
                    "granted_at": user_role.granted_at.isoformat()
                    if user_role.granted_at
                    else None,
                }
            )

    return roles


@router.post("/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
@require_permission("manage_users")
async def assign_user_role(
    user_id: UUID,
    role_data: dict,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Assign a role to a user.

    Args:
        user_id: User ID
        role_data: Dict with role_id
        current_user: Current authenticated user
        db: Database session

    Returns:
        dict: Success message

    Raises:
        HTTPException: If user not found, role not found, or not in same account
    """
    # Verify user exists and is in the same account
    user = crud_user.get(db=db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify user from different account",
        )

    # Verify role exists
    from preloop_models.crud import crud_role, crud_user_role

    role_id = role_data.get("role_id")
    if not role_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role_id is required",
        )

    role = crud_role.get(db=db, id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Check if user already has this role
    from preloop_models.models.permission import UserRole as UserRoleModel

    existing = (
        db.query(UserRoleModel)
        .filter(UserRoleModel.user_id == user_id, UserRoleModel.role_id == role_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has this role",
        )

    # Assign role using the CRUD method
    crud_user_role.assign_role(
        db=db, user_id=user_id, role_id=role_id, granted_by=current_user.id
    )

    logger.info(f"Role {role_id} assigned to user {user_id} by {current_user.username}")

    return {"message": "Role assigned successfully"}


@router.delete(
    "/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT
)
@require_permission("manage_users")
async def remove_user_role(
    user_id: UUID,
    role_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Remove a role from a user.

    Args:
        user_id: User ID
        role_id: Role ID to remove
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If user not found, role not found, or not in same account
    """
    # Verify user exists and is in the same account
    user = crud_user.get(db=db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify user from different account",
        )

    # Remove role using CRUD method
    from preloop_models.crud import crud_user_role

    success = crud_user_role.remove_role(db=db, user_id=user_id, role_id=role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not have this role",
        )

    logger.info(
        f"Role {role_id} removed from user {user_id} by {current_user.username}"
    )
