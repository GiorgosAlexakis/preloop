"""Integration test for audit logging system.

This test verifies that the audit logging plugin integrates correctly
with RBAC and logs permission checks as expected.
"""

import os
import pytest
from sqlalchemy.orm import Session

from preloop_ai.plugins.base import get_plugin_manager, reset_plugin_manager
from preloop_models.crud import crud_account, crud_audit_log, crud_user


@pytest.fixture(autouse=True)
def enable_proprietary_plugins():
    """Enable proprietary plugins for these tests."""
    old_disable_rbac = os.environ.get("DISABLE_RBAC")
    old_disable_proprietary = os.environ.get("DISABLE_PROPRIETARY_PLUGINS")

    # Remove the disable flags
    if "DISABLE_RBAC" in os.environ:
        del os.environ["DISABLE_RBAC"]
    if "DISABLE_PROPRIETARY_PLUGINS" in os.environ:
        del os.environ["DISABLE_PROPRIETARY_PLUGINS"]

    # Reset plugin manager to force re-discovery
    reset_plugin_manager()

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

    # Reset plugin manager again
    reset_plugin_manager()


class TestAuditIntegration:
    """Test audit logging integration with RBAC."""

    def test_plugin_manager_has_audit_service(self):
        """Test that plugin manager provides audit_service."""
        plugin_manager = get_plugin_manager()
        audit_service = plugin_manager.get_service("audit_service")

        assert audit_service is not None
        assert hasattr(audit_service, "log_permission_check")
        assert hasattr(audit_service, "log_authentication")
        assert hasattr(audit_service, "log_role_assignment")

    def test_audit_service_logs_permission_check(self, db_session: Session):
        """Test that audit service can log a permission check."""
        # Create test account and user
        account_data = {
            "organization_name": "Integration Test Org",
            "is_active": True,
        }
        account = crud_account.create(db_session, obj_in=account_data)

        user_data = {
            "account_id": account.id,
            "email": "integration@example.com",
            "username": "integrationuser",
            "full_name": "Integration User",
            "is_active": True,
            "email_verified": True,
            "hashed_password": "testpassword",
            "user_source": "local",
        }
        user = crud_user.create(db_session, obj_in=user_data)

        # Get audit service
        plugin_manager = get_plugin_manager()
        audit_service = plugin_manager.get_service("audit_service")

        # Log a permission check
        audit_service.log_permission_check(
            db=db_session,
            account_id=account.id,
            user=user,
            permission="view_issues",
            granted=True,
            resource_type="issue",
            resource_id="123",
        )

        # Verify the log was created
        logs = crud_audit_log.get_by_account(db_session, account_id=account.id)
        assert len(logs) == 1
        assert logs[0].action == "permission_check"
        assert logs[0].status == "success"
        assert logs[0].user_id == user.id
        assert logs[0].details["permission"] == "view_issues"

    def test_audit_service_is_enabled_by_default(self):
        """Test that audit service is enabled by default."""
        plugin_manager = get_plugin_manager()
        audit_service = plugin_manager.get_service("audit_service")

        assert audit_service.enabled is True

    def test_audit_plugin_registered(self):
        """Test that audit plugin is registered in plugin manager."""
        plugin_manager = get_plugin_manager()

        # Check that audit plugin is registered
        assert "audit" in plugin_manager._plugins

        # Check plugin metadata
        audit_plugin = plugin_manager._plugins["audit"]
        assert audit_plugin.metadata.name == "audit"
        assert audit_plugin.metadata.is_proprietary is True

    def test_audit_logging_with_denied_permission(self, db_session: Session):
        """Test logging denied permission checks."""
        # Create test account and user
        account_data = {
            "organization_name": "Denied Test Org",
            "is_active": True,
        }
        account = crud_account.create(db_session, obj_in=account_data)

        user_data = {
            "account_id": account.id,
            "email": "denied@example.com",
            "username": "denieduser",
            "full_name": "Denied User",
            "is_active": True,
            "email_verified": True,
            "hashed_password": "testpassword",
            "user_source": "local",
        }
        user = crud_user.create(db_session, obj_in=user_data)

        # Get audit service
        plugin_manager = get_plugin_manager()
        audit_service = plugin_manager.get_service("audit_service")

        # Log a denied permission check
        audit_service.log_permission_check(
            db=db_session,
            account_id=account.id,
            user=user,
            permission="delete_account",
            granted=False,
        )

        # Verify the log was created with denied status
        logs = crud_audit_log.get_permission_denials(
            db_session, account_id=account.id, days=1
        )
        assert len(logs) == 1
        assert logs[0].status == "denied"
        assert logs[0].details["granted"] is False
