"""Tests for team schemas."""

from datetime import datetime
from uuid import uuid4

from preloop.schemas.team import (
    TeamBase,
    TeamCreate,
    TeamDetailResponse,
    TeamListResponse,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamMemberUpdate,
    TeamResponse,
    TeamUpdate,
)


class TestTeamBase:
    """Test TeamBase schema."""

    def test_valid(self):
        """Valid team base."""
        data = TeamBase(name="Engineering", description="Dev team")
        assert data.name == "Engineering"
        assert data.description == "Dev team"

    def test_description_optional(self):
        """Description is optional."""
        data = TeamBase(name="Team")
        assert data.description is None


class TestTeamCreate:
    """Test TeamCreate schema."""

    def test_inherits_from_base(self):
        """TeamCreate inherits TeamBase fields."""
        data = TeamCreate(name="Backend", description="Backend team")
        assert data.name == "Backend"


class TestTeamUpdate:
    """Test TeamUpdate schema."""

    def test_partial_update(self):
        """Partial update with optional fields."""
        data = TeamUpdate(name="New Name")
        assert data.name == "New Name"
        assert data.description is None

    def test_update_description_only(self):
        """Update description only."""
        data = TeamUpdate(description="Updated desc")
        assert data.name is None
        assert data.description == "Updated desc"


class TestTeamMemberAdd:
    """Test TeamMemberAdd schema."""

    def test_valid(self):
        """Valid member add."""
        user_id = uuid4()
        data = TeamMemberAdd(user_id=user_id, role="developer")
        assert data.user_id == user_id
        assert data.role == "developer"

    def test_role_optional(self):
        """Role is optional."""
        data = TeamMemberAdd(user_id=uuid4())
        assert data.role is None


class TestTeamMemberUpdate:
    """Test TeamMemberUpdate schema."""

    def test_valid(self):
        """Valid member update."""
        data = TeamMemberUpdate(role="lead")
        assert data.role == "lead"


class TestTeamMemberResponse:
    """Test TeamMemberResponse schema."""

    def test_serialize_uuids(self):
        """UUIDs serialize to strings."""
        mid = uuid4()
        tid = uuid4()
        uid = uuid4()
        data = TeamMemberResponse(
            id=mid,
            team_id=tid,
            user_id=uid,
            role="dev",
            added_at=datetime.now(),
            added_by=None,
            username="user",
            email="u@ex.com",
            full_name="User",
        )
        dumped = data.model_dump()
        assert dumped["id"] == str(mid)
        assert dumped["team_id"] == str(tid)
        assert dumped["user_id"] == str(uid)


class TestTeamResponse:
    """Test TeamResponse schema."""

    def test_valid(self):
        """Valid team response."""
        tid = uuid4()
        acc_id = uuid4()
        data = TeamResponse(
            id=tid,
            account_id=acc_id,
            name="Team",
            description=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            roles=None,
        )
        assert data.name == "Team"
        dumped = data.model_dump()
        assert dumped["id"] == str(tid)
        assert dumped["account_id"] == str(acc_id)


class TestTeamDetailResponse:
    """Test TeamDetailResponse schema."""

    def test_inherits_members(self):
        """TeamDetailResponse has members list."""
        tid = uuid4()
        acc_id = uuid4()
        data = TeamDetailResponse(
            id=tid,
            account_id=acc_id,
            name="Team",
            description=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            roles=None,
            members=[],
        )
        assert data.members == []


class TestTeamListResponse:
    """Test TeamListResponse schema."""

    def test_valid(self):
        """Valid list response."""
        data = TeamListResponse(
            teams=[],
            total=0,
            skip=0,
            limit=10,
        )
        assert data.total == 0
        assert data.limit == 10
