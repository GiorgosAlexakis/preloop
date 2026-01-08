"""Tests for Permission, Role, UserRole, and TeamRole CRUD operations."""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from preloop.models.crud.permission import (
    CRUDPermission,
    CRUDRole,
    CRUDUserRole,
    CRUDTeamRole,
)
from preloop.models.models.permission import (
    Permission,
    Role,
    RolePermission,
    UserRole,
    TeamRole,
)


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def crud_permission():
    """Fixture for a CRUDPermission instance."""
    return CRUDPermission(Permission)


@pytest.fixture
def crud_role():
    """Fixture for a CRUD Role instance."""
    return CRUDRole(Role)


@pytest.fixture
def crud_user_role():
    """Fixture for a CRUDUserRole instance."""
    return CRUDUserRole(UserRole)


@pytest.fixture
def crud_team_role():
    """Fixture for a CRUDTeamRole instance."""
    return CRUDTeamRole(TeamRole)


# CRUDPermission tests


def test_permission_get_by_name(crud_permission, mock_db_session):
    """Test retrieving permission by name."""
    # Arrange
    name = "manage_users"
    mock_perm = Permission(id=uuid4(), name=name)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_perm

    # Act
    result = crud_permission.get_by_name(mock_db_session, name=name)

    # Assert
    assert result.name == name


def test_permission_get_by_category(crud_permission, mock_db_session):
    """Test retrieving permissions by category."""
    # Arrange
    category = "users"
    mock_perms = [
        Permission(id=uuid4(), name="manage_users", category=category, is_active=True),
        Permission(id=uuid4(), name="view_users", category=category, is_active=True),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_perms

    # Act
    result = crud_permission.get_by_category(mock_db_session, category=category)

    # Assert
    assert len(result) == 2
    assert all(p.category == category for p in result)


def test_permission_get_active(crud_permission, mock_db_session):
    """Test retrieving active permissions."""
    # Arrange
    mock_perms = [
        Permission(id=uuid4(), name="perm1", is_active=True),
        Permission(id=uuid4(), name="perm2", is_active=True),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_perms

    # Act
    result = crud_permission.get_active(mock_db_session)

    # Assert
    assert len(result) == 2
    assert all(p.is_active for p in result)


# CRUDRole tests


def test_role_get_by_name_system(crud_role, mock_db_session):
    """Test retrieving system role by name."""
    # Arrange
    name = "owner"
    mock_role = Role(id=uuid4(), name=name, account_id=None, is_system_role=True)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_role

    # Act
    result = crud_role.get_by_name(mock_db_session, name=name, account_id=None)

    # Assert
    assert result.name == name
    assert result.is_system_role


def test_role_get_by_name_custom(crud_role, mock_db_session):
    """Test retrieving custom role by name."""
    # Arrange
    name = "custom_role"
    account_id = str(uuid4())
    mock_role = Role(id=uuid4(), name=name, account_id=account_id, is_system_role=False)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_role

    # Act
    result = crud_role.get_by_name(mock_db_session, name=name, account_id=account_id)

    # Assert
    assert result.name == name
    assert result.account_id == account_id


def test_role_get_system_roles(crud_role, mock_db_session):
    """Test retrieving system roles."""
    # Arrange
    mock_roles = [
        Role(id=uuid4(), name="owner", is_system_role=True),
        Role(id=uuid4(), name="admin", is_system_role=True),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_roles

    # Act
    result = crud_role.get_system_roles(mock_db_session)

    # Assert
    assert len(result) == 2
    assert all(r.is_system_role for r in result)


def test_role_get_custom_roles(crud_role, mock_db_session):
    """Test retrieving custom roles for account."""
    # Arrange
    account_id = str(uuid4())
    mock_roles = [
        Role(id=uuid4(), name="custom1", account_id=account_id, is_system_role=False),
        Role(id=uuid4(), name="custom2", account_id=account_id, is_system_role=False),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_roles

    # Act
    result = crud_role.get_custom_roles(mock_db_session, account_id=account_id)

    # Assert
    assert len(result) == 2
    assert all(not r.is_system_role for r in result)


def test_role_get_all_for_account(crud_role, mock_db_session):
    """Test retrieving all roles for account (system + custom)."""
    # Arrange
    account_id = str(uuid4())
    mock_roles = [
        Role(id=uuid4(), name="owner", is_system_role=True),
        Role(id=uuid4(), name="custom", account_id=account_id, is_system_role=False),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_roles

    # Act
    result = crud_role.get_all_for_account(mock_db_session, account_id=account_id)

    # Assert
    assert len(result) == 2


def test_role_get_permissions(crud_role, mock_db_session):
    """Test retrieving permissions for a role."""
    # Arrange
    role_id = uuid4()
    mock_perms = [
        Permission(id=uuid4(), name="perm1"),
        Permission(id=uuid4(), name="perm2"),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_perms

    # Act
    result = crud_role.get_permissions(mock_db_session, role_id=role_id)

    # Assert
    assert len(result) == 2


def test_role_assign_permission(crud_role, mock_db_session):
    """Test assigning permission to role."""
    # Arrange
    role_id = uuid4()
    permission_id = uuid4()

    # Act
    crud_role.assign_permission(
        mock_db_session, role_id=role_id, permission_id=permission_id
    )

    # Assert
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


def test_role_remove_permission_success(crud_role, mock_db_session):
    """Test removing permission from role."""
    # Arrange
    role_id = uuid4()
    permission_id = uuid4()
    mock_role_perm = RolePermission(
        id=uuid4(), role_id=role_id, permission_id=permission_id
    )

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_role_perm

    # Act
    result = crud_role.remove_permission(
        mock_db_session, role_id=role_id, permission_id=permission_id
    )

    # Assert
    assert result is True
    mock_db_session.delete.assert_called_once_with(mock_role_perm)
    mock_db_session.commit.assert_called_once()


def test_role_remove_permission_not_found(crud_role, mock_db_session):
    """Test removing non-existent permission from role."""
    # Arrange
    role_id = uuid4()
    permission_id = uuid4()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    # Act
    result = crud_role.remove_permission(
        mock_db_session, role_id=role_id, permission_id=permission_id
    )

    # Assert
    assert result is False
    mock_db_session.delete.assert_not_called()


# CRUDUserRole tests


def test_user_role_get_by_user(crud_user_role, mock_db_session):
    """Test retrieving user roles for a user."""
    # Arrange
    user_id = uuid4()
    mock_user_roles = [
        UserRole(id=uuid4(), user_id=user_id, role_id=uuid4()),
        UserRole(id=uuid4(), user_id=user_id, role_id=uuid4()),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_user_roles

    # Act
    result = crud_user_role.get_by_user(mock_db_session, user_id=user_id)

    # Assert
    assert len(result) == 2
    assert all(ur.user_id == user_id for ur in result)


def test_user_role_get_user_roles(crud_user_role, mock_db_session):
    """Test retrieving roles for a user."""
    # Arrange
    user_id = uuid4()
    mock_roles = [
        Role(id=uuid4(), name="owner"),
        Role(id=uuid4(), name="admin"),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_roles

    # Act
    result = crud_user_role.get_user_roles(mock_db_session, user_id=user_id)

    # Assert
    assert len(result) == 2


def test_user_role_assign_role(crud_user_role, mock_db_session):
    """Test assigning role to user."""
    # Arrange
    user_id = uuid4()
    role_id = uuid4()
    granted_by = uuid4()

    # Act
    crud_user_role.assign_role(
        mock_db_session, user_id=user_id, role_id=role_id, granted_by=granted_by
    )

    # Assert
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


def test_user_role_assign_role_without_granted_by(crud_user_role, mock_db_session):
    """Test assigning role to user without granted_by."""
    # Arrange
    user_id = uuid4()
    role_id = uuid4()

    # Act
    crud_user_role.assign_role(mock_db_session, user_id=user_id, role_id=role_id)

    # Assert
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


def test_user_role_remove_role_success(crud_user_role, mock_db_session):
    """Test removing role from user."""
    # Arrange
    user_id = uuid4()
    role_id = uuid4()
    mock_user_role = UserRole(id=uuid4(), user_id=user_id, role_id=role_id)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_user_role

    # Act
    result = crud_user_role.remove_role(
        mock_db_session, user_id=user_id, role_id=role_id
    )

    # Assert
    assert result is True
    mock_db_session.delete.assert_called_once_with(mock_user_role)
    mock_db_session.commit.assert_called_once()


def test_user_role_remove_role_not_found(crud_user_role, mock_db_session):
    """Test removing non-existent role from user."""
    # Arrange
    user_id = uuid4()
    role_id = uuid4()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    # Act
    result = crud_user_role.remove_role(
        mock_db_session, user_id=user_id, role_id=role_id
    )

    # Assert
    assert result is False
    mock_db_session.delete.assert_not_called()


# CRUDTeamRole tests


def test_team_role_get_team_roles(crud_team_role, mock_db_session):
    """Test retrieving roles for a team."""
    # Arrange
    team_id = uuid4()
    mock_roles = [
        Role(id=uuid4(), name="role1"),
        Role(id=uuid4(), name="role2"),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.join.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_roles

    # Act
    result = crud_team_role.get_team_roles(mock_db_session, team_id=team_id)

    # Assert
    assert len(result) == 2


def test_team_role_assign_role(crud_team_role, mock_db_session):
    """Test assigning role to team."""
    # Arrange
    team_id = uuid4()
    role_id = uuid4()
    granted_by = uuid4()

    # Act
    crud_team_role.assign_role(
        mock_db_session, team_id=team_id, role_id=role_id, granted_by=granted_by
    )

    # Assert
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


def test_team_role_assign_role_without_granted_by(crud_team_role, mock_db_session):
    """Test assigning role to team without granted_by."""
    # Arrange
    team_id = uuid4()
    role_id = uuid4()

    # Act
    crud_team_role.assign_role(mock_db_session, team_id=team_id, role_id=role_id)

    # Assert
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


def test_team_role_remove_role_success(crud_team_role, mock_db_session):
    """Test removing role from team."""
    # Arrange
    team_id = uuid4()
    role_id = uuid4()
    mock_team_role = TeamRole(id=uuid4(), team_id=team_id, role_id=role_id)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_team_role

    # Act
    result = crud_team_role.remove_role(
        mock_db_session, team_id=team_id, role_id=role_id
    )

    # Assert
    assert result is True
    mock_db_session.delete.assert_called_once_with(mock_team_role)
    mock_db_session.commit.assert_called_once()


def test_team_role_remove_role_not_found(crud_team_role, mock_db_session):
    """Test removing non-existent role from team."""
    # Arrange
    team_id = uuid4()
    role_id = uuid4()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    # Act
    result = crud_team_role.remove_role(
        mock_db_session, team_id=team_id, role_id=role_id
    )

    # Assert
    assert result is False
    mock_db_session.delete.assert_not_called()
