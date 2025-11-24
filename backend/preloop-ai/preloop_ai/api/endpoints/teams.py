"""Team management endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from preloop_ai.api.auth.jwt import get_current_active_user
from preloop_ai.schemas.team import (
    TeamCreate,
    TeamDetailResponse,
    TeamListResponse,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamMemberUpdate,
    TeamResponse,
    TeamUpdate,
)
from preloop_models.crud import crud_team
from preloop_models.db.session import get_db_session
from preloop_models.models.team import Team, TeamMembership
from preloop_models.models.user import User
from preloop_ai.utils.permissions import require_permission

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
@require_permission("create_teams")
async def create_team(
    team_data: TeamCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Create a new team in the current account.

    Args:
        team_data: Team creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        TeamResponse: Created team data
    """
    # TODO: Add permission check - only admins should be able to create teams

    team_dict = team_data.model_dump()
    team_dict["account_id"] = current_user.account_id

    team = crud_team.create(db=db, obj_in=team_dict)
    db.commit()
    db.refresh(team)

    logger.info(f"Team '{team.name}' created by user {current_user.username}")

    return TeamResponse.model_validate(team)


@router.get("/teams", response_model=TeamListResponse)
@require_permission("view_teams")
async def list_teams(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
    skip: int = 0,
    limit: int = 100,
):
    """List all teams in the current account.

    Args:
        current_user: Current authenticated user
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        TeamListResponse: Paginated list of teams
    """
    teams = (
        db.query(Team)
        .filter(Team.account_id == current_user.account_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    total = db.query(Team).filter(Team.account_id == current_user.account_id).count()

    # Get roles for each team
    from preloop_models.crud import crud_team_role

    team_responses = []
    for team in teams:
        # Build team dict manually to avoid validation issues with roles relationship
        team_dict = {
            "id": team.id,
            "account_id": team.account_id,
            "name": team.name,
            "description": team.description,
            "created_at": team.created_at,
            "updated_at": team.updated_at,
        }

        # Get team's roles
        team_roles = crud_team_role.get_team_roles(db=db, team_id=team.id)
        team_dict["roles"] = [
            {
                "id": str(role.id),
                "name": role.name,
                "description": role.description,
            }
            for role in team_roles
        ]

        team_responses.append(team_dict)

    return {
        "teams": team_responses,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/teams/{team_id}", response_model=TeamDetailResponse)
@require_permission("view_teams")
async def get_team(
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Get a specific team by ID with its members.

    Args:
        team_id: Team ID to retrieve
        current_user: Current authenticated user
        db: Database session

    Returns:
        TeamDetailResponse: Team data with members

    Raises:
        HTTPException: If team not found or not in same account
    """
    team = crud_team.get(db=db, id=team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Verify team is in the same account
    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access team from different account",
        )

    # Get members with user info
    members = crud_team.get_members(db=db, team_id=team_id)

    # Build response with member details
    member_responses = []
    for user in members:
        # Get the membership record for this user
        membership = (
            db.query(TeamMembership)
            .filter(
                TeamMembership.team_id == team_id, TeamMembership.user_id == user.id
            )
            .first()
        )

        if membership:
            member_responses.append(
                TeamMemberResponse(
                    id=membership.id,
                    team_id=membership.team_id,
                    user_id=membership.user_id,
                    role=membership.role,
                    added_at=membership.added_at,
                    added_by=membership.added_by,
                    username=user.username,
                    email=user.email,
                    full_name=user.full_name,
                )
            )

    return TeamDetailResponse(
        id=team.id,
        account_id=team.account_id,
        name=team.name,
        description=team.description,
        created_at=team.created_at,
        updated_at=team.updated_at,
        members=member_responses,
    )


@router.patch("/teams/{team_id}", response_model=TeamResponse)
@require_permission("edit_teams")
async def update_team(
    team_id: UUID,
    team_data: TeamUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Update a team's information.

    Args:
        team_id: Team ID to update
        team_data: Team update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        TeamResponse: Updated team data

    Raises:
        HTTPException: If team not found or not in same account
    """
    # TODO: Add permission check - only admins should be able to update teams

    team = crud_team.get(db=db, id=team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Verify team is in the same account
    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update team from different account",
        )

    updated_team = crud_team.update(
        db=db, db_obj=team, obj_in=team_data.model_dump(exclude_unset=True)
    )
    db.commit()
    db.refresh(updated_team)

    return TeamResponse.model_validate(updated_team)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission("delete_teams")
async def delete_team(
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Delete a team.

    Args:
        team_id: Team ID to delete
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If team not found or not in same account
    """
    # TODO: Add permission check - only admins should be able to delete teams

    team = crud_team.get(db=db, id=team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Verify team is in the same account
    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete team from different account",
        )

    crud_team.delete(db=db, id=team_id)
    db.commit()

    logger.info(f"Team {team_id} deleted by user {current_user.username}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/teams/{team_id}/members", status_code=status.HTTP_201_CREATED)
@require_permission("manage_teams")
async def add_team_member(
    team_id: UUID,
    member_data: TeamMemberAdd,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Add a member to a team.

    Args:
        team_id: Team ID
        member_data: Member data (user_id and optional role)
        current_user: Current authenticated user
        db: Database session

    Returns:
        TeamMemberResponse: Added member data

    Raises:
        HTTPException: If team not found, user not found, or not in same account
    """
    # TODO: Add permission check - only team admins or account admins should be able to add members

    team = crud_team.get(db=db, id=team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Verify team is in the same account
    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify team from different account",
        )

    # Verify user exists and is in the same account
    from preloop_models.crud import crud_user

    user = crud_user.get(db=db, id=member_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add user from different account to team",
        )

    # Add member to team
    membership = crud_team.add_member(
        db=db,
        team_id=team_id,
        user_id=member_data.user_id,
        role=member_data.role,
        added_by=current_user.id,
    )
    db.commit()

    logger.info(
        f"User {member_data.user_id} added to team {team_id} by {current_user.username}"
    )

    return TeamMemberResponse(
        id=membership.id,
        team_id=membership.team_id,
        user_id=membership.user_id,
        role=membership.role,
        added_at=membership.added_at,
        added_by=membership.added_by,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
    )


@router.delete(
    "/teams/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
@require_permission("manage_teams")
async def remove_team_member(
    team_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Remove a member from a team.

    Args:
        team_id: Team ID
        user_id: User ID to remove
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If team not found or not in same account
    """
    # TODO: Add permission check - only team admins or account admins should be able to remove members

    team = crud_team.get(db=db, id=team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Verify team is in the same account
    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify team from different account",
        )

    success = crud_team.remove_member(db=db, team_id=team_id, user_id=user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this team",
        )

    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

    logger.info(
        f"User {user_id} removed from team {team_id} by {current_user.username}"
    )


@router.get("/teams/{team_id}/members", response_model=list[TeamMemberResponse])
@require_permission("view_teams")
async def get_team_members(
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Get all members of a team.

    Args:
        team_id: Team ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        list[TeamMemberResponse]: List of team members

    Raises:
        HTTPException: If team not found or not in same account
    """
    team = crud_team.get(db=db, id=team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Verify team is in the same account
    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access team from different account",
        )

    # Get members with user info
    members = crud_team.get_members(db=db, team_id=team_id)

    # Build response with member details
    member_responses = []
    for user in members:
        # Get the membership record for this user
        membership = (
            db.query(TeamMembership)
            .filter(
                TeamMembership.team_id == team_id, TeamMembership.user_id == user.id
            )
            .first()
        )

        if membership:
            member_responses.append(
                TeamMemberResponse(
                    id=membership.id,
                    team_id=membership.team_id,
                    user_id=membership.user_id,
                    role=membership.role,
                    added_at=membership.added_at,
                    added_by=membership.added_by,
                    username=user.username,
                    email=user.email,
                    full_name=user.full_name,
                )
            )

    return member_responses


@router.patch("/teams/{team_id}/members/{user_id}")
@require_permission("manage_teams")
async def update_team_member(
    team_id: UUID,
    user_id: UUID,
    member_data: TeamMemberUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Update a team member's role.

    Args:
        team_id: Team ID
        user_id: User ID to update
        member_data: Member update data (role)
        current_user: Current authenticated user
        db: Database session

    Returns:
        TeamMemberResponse: Updated member data

    Raises:
        HTTPException: If team not found, member not found, or not in same account
    """
    # TODO: Add permission check - only team admins or account admins should be able to update members

    team = crud_team.get(db=db, id=team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Verify team is in the same account
    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify team from different account",
        )

    # Get the membership
    membership = (
        db.query(TeamMembership)
        .filter(TeamMembership.team_id == team_id, TeamMembership.user_id == user_id)
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this team",
        )

    # Update the role
    membership.role = member_data.role
    db.commit()
    db.refresh(membership)

    # Get user info
    from preloop_models.crud import crud_user

    user = crud_user.get(db=db, id=user_id)

    logger.info(
        f"User {user_id} role updated in team {team_id} by {current_user.username}"
    )

    return TeamMemberResponse(
        id=membership.id,
        team_id=membership.team_id,
        user_id=membership.user_id,
        role=membership.role,
        added_at=membership.added_at,
        added_by=membership.added_by,
        username=user.username if user else "Unknown",
        email=user.email if user else "",
        full_name=user.full_name if user else None,
    )


@router.get("/teams/{team_id}/roles", response_model=list[dict])
@require_permission("view_teams")
async def get_team_roles(
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Get roles assigned to a team.

    Args:
        team_id: Team ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        list[dict]: List of roles assigned to the team

    Raises:
        HTTPException: If team not found or not in same account
    """
    # Verify team exists and is in the same account
    team = crud_team.get(db=db, id=team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access team from different account",
        )

    # Get team roles
    from preloop_models.crud import crud_team_role

    team_roles = crud_team_role.get_team_roles(db=db, team_id=team_id)

    return [
        {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
        }
        for role in team_roles
    ]


@router.post("/teams/{team_id}/roles", status_code=status.HTTP_201_CREATED)
@require_permission("manage_teams")
async def assign_team_role(
    team_id: UUID,
    role_data: dict,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Assign a role to a team.

    Args:
        team_id: Team ID
        role_data: Dict with role_id
        current_user: Current authenticated user
        db: Database session

    Returns:
        dict: Success message

    Raises:
        HTTPException: If team not found, role not found, or not in same account
    """
    # Verify team exists and is in the same account
    team = crud_team.get(db=db, id=team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify team from different account",
        )

    # Verify role exists
    from preloop_models.crud import crud_role, crud_team_role

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

    # Check if team already has this role
    from preloop_models.models.permission import TeamRole as TeamRoleModel

    existing = (
        db.query(TeamRoleModel)
        .filter(TeamRoleModel.team_id == team_id, TeamRoleModel.role_id == role_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team already has this role",
        )

    # Assign role using CRUD method
    crud_team_role.assign_role(
        db=db, team_id=team_id, role_id=role_id, granted_by=current_user.id
    )

    logger.info(f"Role {role_id} assigned to team {team_id} by {current_user.username}")

    return {"message": "Role assigned successfully"}


@router.delete(
    "/teams/{team_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT
)
@require_permission("manage_teams")
async def remove_team_role(
    team_id: UUID,
    role_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db_session),
):
    """Remove a role from a team.

    Args:
        team_id: Team ID
        role_id: Role ID to remove
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If team not found, role not found, or not in same account
    """
    # Verify team exists and is in the same account
    team = crud_team.get(db=db, id=team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if team.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify team from different account",
        )

    # Remove role using CRUD method
    from preloop_models.crud import crud_team_role

    success = crud_team_role.remove_role(db=db, team_id=team_id, role_id=role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team does not have this role",
        )

    logger.info(
        f"Role {role_id} removed from team {team_id} by {current_user.username}"
    )
