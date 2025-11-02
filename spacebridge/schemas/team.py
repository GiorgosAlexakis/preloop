"""Team management schemas for request and response validation."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TeamBase(BaseModel):
    """Base team schema with common attributes."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class TeamCreate(TeamBase):
    """Schema for creating a new team."""

    pass


class TeamUpdate(BaseModel):
    """Schema for updating a team."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class TeamMemberAdd(BaseModel):
    """Schema for adding a member to a team."""

    user_id: UUID
    role: Optional[str] = Field(None, max_length=50)


class TeamMemberUpdate(BaseModel):
    """Schema for updating a team member's role."""

    role: Optional[str] = Field(None, max_length=50)


class TeamMemberResponse(BaseModel):
    """Response schema for team member data."""

    id: UUID
    team_id: UUID
    user_id: UUID
    role: Optional[str]
    added_at: datetime
    added_by: Optional[UUID]

    # Nested user info
    username: str
    email: str
    full_name: Optional[str]

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    """Response schema for team data."""

    id: UUID
    account_id: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    roles: Optional[List[dict]] = None

    class Config:
        from_attributes = True


class TeamDetailResponse(TeamResponse):
    """Detailed response schema for team with members."""

    members: List[TeamMemberResponse] = []

    class Config:
        from_attributes = True


class TeamListResponse(BaseModel):
    """Response schema for paginated team list."""

    teams: List[TeamResponse]
    total: int
    skip: int
    limit: int
