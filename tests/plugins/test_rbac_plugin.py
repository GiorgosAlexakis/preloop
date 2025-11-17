"""Tests for the proprietary RBAC plugin.

This module tests the RBAC plugin functionality including:
- Plugin registration and lifecycle
- Permission checking
- Permission decorators
- Multi-tenancy enforcement
"""

import os
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from spacebridge.plugins.base import get_plugin_manager, reset_plugin_manager
from spacebridge.plugins.proprietary.rbac.permissions import (
    has_permission,
    get_user_permissions,
    require_permission,
    require_any_permission,
    require_all_permissions,
)
from spacemodels.models.user import User
from spacemodels.crud import crud_role, crud_user_role, crud_account, crud_user


@pytest.fixture(autouse=True)
def enable_rbac():
    """Enable RBAC for these tests (conftest.py disables it by default)."""
    old_disable_rbac = os.environ.get("DISABLE_RBAC")
    old_disable_proprietary = os.environ.get("DISABLE_PROPRIETARY_PLUGINS")

    # Remove the disable flags
    if "DISABLE_RBAC" in os.environ:
        del os.environ["DISABLE_RBAC"]
    if "DISABLE_PROPRIETARY_PLUGINS" in os.environ:
        del os.environ["DISABLE_PROPRIETARY_PLUGINS"]

    yield

    # Restore original values
    if old_disable_rbac is not None:
        os.environ["DISABLE_RBAC"] = old_disable_rbac
    elif "DISABLE_RBAC" in os.environ:
        del os.environ["DISABLE_RBAC"]

    if old_disable_proprietary is not None:
        os.environ["DISABLE_PROPRIETARY_PLUGINS"] = old_disable_proprietary
    elif "DISABLE_PROPRIETARY_PLUGINS" in os.environ:
        del os.environ["DISABLE_PROPRIETARY_PLUGINS"]


@pytest.fixture(autouse=True)
def reset_plugins():
    """Reset plugin manager before each test."""
    reset_plugin_manager()
    yield
    reset_plugin_manager()


class TestRBACPluginRegistration:
    """Test RBAC plugin registration and lifecycle."""

    def test_plugin_loads_automatically(self):
        """Test that RBAC plugin loads automatically."""
        plugin_manager = get_plugin_manager()

        # Check that RBAC plugin is registered
        assert "rbac" in plugin_manager._plugins
        rbac_plugin = plugin_manager._plugins["rbac"]

        # Verify metadata
        assert rbac_plugin.metadata.name == "rbac"
        assert rbac_plugin.metadata.is_proprietary is True
        assert rbac_plugin.metadata.version == "1.0.0"

    def test_plugin_provides_services(self):
        """Test that RBAC plugin provides permission services."""
        plugin_manager = get_plugin_manager()

        # Check that permission services are registered
        assert plugin_manager.get_service("has_permission") is not None
        assert plugin_manager.get_service("get_user_permissions") is not None

    @pytest.mark.asyncio
    async def test_plugin_startup_lifecycle(self):
        """Test plugin startup lifecycle."""
        plugin_manager = get_plugin_manager()
        # Startup should not raise
        await plugin_manager.startup_all()

    @pytest.mark.asyncio
    async def test_plugin_shutdown_lifecycle(self):
        """Test plugin shutdown lifecycle."""
        plugin_manager = get_plugin_manager()
        await plugin_manager.startup_all()
        # Shutdown should not raise
        await plugin_manager.shutdown_all()


class TestHasPermission:
    """Test has_permission function."""

    def test_inactive_user_has_no_permissions(self, db_session: Session):
        """Test that inactive users have no permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "inactive_user",
                "email": "inactive@test.com",
                "is_active": False,
                "hashed_password": "test",
            },
        )
        db_session.commit()

        assert has_permission(user, "create_issues", db_session) is False

    def test_user_with_no_roles_has_no_permissions(self, db_session: Session):
        """Test that users without roles have no permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "norole_user",
                "email": "norole@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )
        db_session.commit()

        assert has_permission(user, "create_issues", db_session) is False

    def test_owner_role_has_all_permissions(self, db_session: Session):
        """Test that owner role has all permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "owner_user",
                "email": "owner@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )

        # Get owner role
        owner_role = crud_role.get_by_name(db_session, name="owner")
        assert owner_role is not None

        # Assign owner role to user
        crud_user_role.create(
            db_session,
            obj_in={"user_id": user.id, "role_id": owner_role.id},
        )
        db_session.commit()

        # Owner should have all permissions
        assert has_permission(user, "create_issues", db_session) is True
        assert has_permission(user, "delete_issues", db_session) is True
        assert has_permission(user, "manage_users", db_session) is True
        assert has_permission(user, "any_permission", db_session) is True

    def test_user_with_specific_permission(self, db_session: Session):
        """Test that user with specific permission has it."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "dev_user",
                "email": "dev@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )

        # Get editor role (has create_issues permission)
        editor_role = crud_role.get_by_name(db_session, name="editor")
        assert editor_role is not None

        # Assign editor role
        crud_user_role.create(
            db_session,
            obj_in={"user_id": user.id, "role_id": editor_role.id},
        )
        db_session.commit()

        # Editor should have create_issues but not delete_issues
        assert has_permission(user, "create_issues", db_session) is True
        assert has_permission(user, "delete_issues", db_session) is False


class TestGetUserPermissions:
    """Test get_user_permissions function."""

    def test_inactive_user_has_empty_permissions(self, db_session: Session):
        """Test that inactive users have no permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "inactive_perm_user",
                "email": "inactive_perm@test.com",
                "is_active": False,
                "hashed_password": "test",
            },
        )
        db_session.commit()

        permissions = get_user_permissions(user, db_session)
        assert permissions == []

    def test_user_with_no_roles_has_empty_permissions(self, db_session: Session):
        """Test that users without roles have no permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "norole_perm_user",
                "email": "norole_perm@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )
        db_session.commit()

        permissions = get_user_permissions(user, db_session)
        assert permissions == []

    def test_owner_role_returns_all_permissions(self, db_session: Session):
        """Test that owner role returns all permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "owner_perm_user",
                "email": "owner_perm@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )

        # Get owner role
        owner_role = crud_role.get_by_name(db_session, name="owner")
        assert owner_role is not None

        # Assign owner role
        crud_user_role.create(
            db_session,
            obj_in={"user_id": user.id, "role_id": owner_role.id},
        )
        db_session.commit()

        permissions = get_user_permissions(user, db_session)
        # Owner should have all permissions
        assert len(permissions) > 0
        assert "create_issues" in permissions
        assert "delete_issues" in permissions

    def test_user_with_multiple_roles(self, db_session: Session):
        """Test that user with multiple roles has combined permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "multirole_user",
                "email": "multirole@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )

        # Get editor and viewer roles
        editor_role = crud_role.get_by_name(db_session, name="editor")
        viewer_role = crud_role.get_by_name(db_session, name="viewer")

        # Assign both roles
        crud_user_role.create(
            db_session,
            obj_in={"user_id": user.id, "role_id": editor_role.id},
        )
        crud_user_role.create(
            db_session,
            obj_in={"user_id": user.id, "role_id": viewer_role.id},
        )
        db_session.commit()

        permissions = get_user_permissions(user, db_session)
        # Should have combined permissions from both roles
        assert len(permissions) > 0


class TestRequirePermissionDecorator:
    """Test @require_permission decorator."""

    @pytest.mark.asyncio
    async def test_decorator_allows_user_with_permission(self, db_session: Session):
        """Test that decorator allows users with permission."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "decorator_owner_user",
                "email": "decorator_owner@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )

        # Give user owner role
        owner_role = crud_role.get_by_name(db_session, name="owner")
        crud_user_role.create(
            db_session,
            obj_in={"user_id": user.id, "role_id": owner_role.id},
        )
        db_session.commit()

        @require_permission("create_issues")
        async def test_endpoint(current_user: User, db: Session):
            return {"success": True}

        # Should not raise
        result = await test_endpoint(current_user=user, db=db_session)
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_decorator_blocks_user_without_permission(self, db_session: Session):
        """Test that decorator blocks users without permission."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "decorator_norole_user",
                "email": "decorator_norole@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )
        db_session.commit()

        @require_permission("create_issues")
        async def test_endpoint(current_user: User, db: Session):
            return {"success": True}

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await test_endpoint(current_user=user, db=db_session)

        assert exc_info.value.status_code == 403
        assert "create_issues" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_decorator_requires_dependencies(self, db_session: Session):
        """Test that decorator requires current_user and db."""

        @require_permission("create_issue")
        async def test_endpoint():
            return {"success": True}

        # Should raise HTTPException for missing dependencies
        with pytest.raises(HTTPException) as exc_info:
            await test_endpoint()

        assert exc_info.value.status_code == 500
        assert "current_user and db dependencies" in str(exc_info.value.detail)


class TestRequireAnyPermissionDecorator:
    """Test @require_any_permission decorator."""

    @pytest.mark.asyncio
    async def test_allows_user_with_one_of_permissions(self, db_session: Session):
        """Test that decorator allows user with any one of the permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "any_perm_dev_user",
                "email": "any_perm_dev@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )

        # Give user editor role (has create_issues)
        editor_role = crud_role.get_by_name(db_session, name="editor")
        crud_user_role.create(
            db_session,
            obj_in={"user_id": user.id, "role_id": editor_role.id},
        )
        db_session.commit()

        @require_any_permission("create_issues", "delete_issues")
        async def test_endpoint(current_user: User, db: Session):
            return {"success": True}

        # Should not raise (has create_issues)
        result = await test_endpoint(current_user=user, db=db_session)
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_blocks_user_with_none_of_permissions(self, db_session: Session):
        """Test that decorator blocks user with none of the permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "any_perm_norole_user",
                "email": "any_perm_norole@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )
        db_session.commit()

        @require_any_permission("create_issues", "delete_issues")
        async def test_endpoint(current_user: User, db: Session):
            return {"success": True}

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await test_endpoint(current_user=user, db=db_session)

        assert exc_info.value.status_code == 403
        assert "one of" in str(exc_info.value.detail).lower()


class TestRequireAllPermissionsDecorator:
    """Test @require_all_permissions decorator."""

    @pytest.mark.asyncio
    async def test_allows_user_with_all_permissions(self, db_session: Session):
        """Test that decorator allows user with all permissions."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "all_perm_owner_user",
                "email": "all_perm_owner@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )

        # Give user owner role (has all permissions)
        owner_role = crud_role.get_by_name(db_session, name="owner")
        crud_user_role.create(
            db_session,
            obj_in={"user_id": user.id, "role_id": owner_role.id},
        )
        db_session.commit()

        @require_all_permissions("create_issues", "edit_issues")
        async def test_endpoint(current_user: User, db: Session):
            return {"success": True}

        # Should not raise
        result = await test_endpoint(current_user=user, db=db_session)
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_blocks_user_missing_any_permission(self, db_session: Session):
        """Test that decorator blocks user missing any permission."""
        account = crud_account.create(
            db_session, obj_in={"organization_name": "Test Org", "is_active": True}
        )
        user = crud_user.create(
            db_session,
            obj_in={
                "account_id": account.id,
                "username": "all_perm_dev_user",
                "email": "all_perm_dev@test.com",
                "is_active": True,
                "hashed_password": "test",
            },
        )

        # Give user editor role (has create_issues and edit_issues but not delete_issues)
        editor_role = crud_role.get_by_name(db_session, name="editor")
        crud_user_role.create(
            db_session,
            obj_in={"user_id": user.id, "role_id": editor_role.id},
        )
        db_session.commit()

        @require_all_permissions("create_issues", "delete_issues")
        async def test_endpoint(current_user: User, db: Session):
            return {"success": True}

        # Should raise HTTPException (missing delete_issues)
        with pytest.raises(HTTPException) as exc_info:
            await test_endpoint(current_user=user, db=db_session)

        assert exc_info.value.status_code == 403
        assert "missing" in str(exc_info.value.detail).lower()
        assert "delete_issues" in str(exc_info.value.detail)
