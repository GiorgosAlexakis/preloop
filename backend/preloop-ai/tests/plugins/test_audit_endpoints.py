"""Tests for audit log API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from preloop_models.crud import crud_audit_log
from preloop_models.models.user import User


@pytest.fixture
def audit_user(test_user: User) -> User:
    """Return test user who already has owner role with view_audit_logs permission."""
    # test_user fixture already has owner role assigned which includes view_audit_logs
    return test_user


class TestAuditLogEndpoints:
    """Test audit log API endpoints."""

    def test_list_audit_logs(
        self, audit_client: TestClient, db_session: Session, audit_user: User
    ):
        """Test listing audit logs."""
        # Create some audit logs
        for i in range(5):
            crud_audit_log.log_action(
                db_session,
                account_id=audit_user.account_id,
                user_id=audit_user.id,
                action=f"test_action_{i}",
                status="success",
            )

        response = audit_client.get("/api/v1/audit-logs")
        assert response.status_code == 200
        data = response.json()

        assert "logs" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data

        # Filter out automatic permission check logs from RBAC
        test_logs = [log for log in data["logs"] if log["action"] != "permission_check"]
        assert len(test_logs) == 5
        # Total includes the permission check log
        assert data["total"] >= 5

    def test_list_audit_logs_with_action_filter(
        self, audit_client: TestClient, db_session: Session, audit_user: User
    ):
        """Test filtering audit logs by action."""
        # Create logs with different actions (use a unique action name to avoid confusion)
        crud_audit_log.log_action(
            db_session,
            account_id=audit_user.account_id,
            user_id=audit_user.id,
            action="custom_action",
            status="success",
        )
        crud_audit_log.log_action(
            db_session,
            account_id=audit_user.account_id,
            user_id=audit_user.id,
            action="role_assigned",
            status="success",
        )

        response = audit_client.get("/api/v1/audit-logs?action=custom_action")
        assert response.status_code == 200
        data = response.json()

        assert len(data["logs"]) == 1
        assert data["logs"][0]["action"] == "custom_action"

    def test_list_audit_logs_with_status_filter(
        self, audit_client: TestClient, db_session: Session, audit_user: User
    ):
        """Test filtering audit logs by status."""
        crud_audit_log.log_action(
            db_session,
            account_id=audit_user.account_id,
            user_id=audit_user.id,
            action="permission_check",
            status="success",
        )
        crud_audit_log.log_action(
            db_session,
            account_id=audit_user.account_id,
            user_id=audit_user.id,
            action="permission_check",
            status="denied",
        )

        response = audit_client.get("/api/v1/audit-logs?status_filter=denied")
        assert response.status_code == 200
        data = response.json()

        assert len(data["logs"]) == 1
        assert data["logs"][0]["status"] == "denied"

    def test_list_audit_logs_with_pagination(
        self, audit_client: TestClient, db_session: Session, audit_user: User
    ):
        """Test pagination of audit logs."""
        # Create 10 logs
        for i in range(10):
            crud_audit_log.log_action(
                db_session,
                account_id=audit_user.account_id,
                user_id=audit_user.id,
                action=f"action_{i}",
                status="success",
            )

        # Get first page
        response = audit_client.get("/api/v1/audit-logs?skip=0&limit=5")
        assert response.status_code == 200
        data = response.json()

        assert len(data["logs"]) == 5
        # Total includes our 10 logs plus the permission check log
        assert data["total"] >= 10
        assert data["skip"] == 0
        assert data["limit"] == 5

        # Get second page
        response = audit_client.get("/api/v1/audit-logs?skip=5&limit=5")
        assert response.status_code == 200
        data = response.json()

        assert len(data["logs"]) == 5
        assert data["total"] >= 10

    def test_get_audit_stats(
        self, audit_client: TestClient, db_session: Session, audit_user: User
    ):
        """Test getting audit statistics."""
        # Create various logs
        for _ in range(3):
            crud_audit_log.log_action(
                db_session,
                account_id=audit_user.account_id,
                user_id=audit_user.id,
                action="permission_check",
                status="success",
            )
        for _ in range(2):
            crud_audit_log.log_action(
                db_session,
                account_id=audit_user.account_id,
                user_id=audit_user.id,
                action="permission_check",
                status="denied",
            )

        response = audit_client.get("/api/v1/audit-logs/stats?days=30")
        assert response.status_code == 200
        data = response.json()

        assert "action_stats" in data
        assert "user_activity" in data
        assert "total_count" in data
        assert "period_days" in data
        assert data["period_days"] == 30
        # Total includes our 5 logs plus the permission check log from RBAC
        assert data["total_count"] >= 5

        # Verify action stats
        assert len(data["action_stats"]) > 0
        success_stat = next(
            s
            for s in data["action_stats"]
            if s["action"] == "permission_check" and s["status"] == "success"
        )
        # Should have at least 3 (may have more from RBAC)
        assert success_stat["count"] >= 3

    def test_get_user_audit_logs(
        self, audit_client: TestClient, db_session: Session, audit_user: User
    ):
        """Test getting audit logs for a specific user."""
        # Create logs for the user
        for i in range(3):
            crud_audit_log.log_action(
                db_session,
                account_id=audit_user.account_id,
                user_id=audit_user.id,
                action=f"user_action_{i}",
                status="success",
            )

        response = audit_client.get(f"/api/v1/audit-logs/user/{audit_user.id}?days=30")
        assert response.status_code == 200
        data = response.json()

        # Filter out automatic permission check logs from RBAC
        user_action_logs = [
            log for log in data["logs"] if log["action"].startswith("user_action_")
        ]
        assert len(user_action_logs) == 3
        assert all(log["user_id"] == str(audit_user.id) for log in data["logs"])

    def test_get_permission_denials(
        self, audit_client: TestClient, db_session: Session, audit_user: User
    ):
        """Test getting permission denial events."""
        # Create permission checks
        crud_audit_log.log_action(
            db_session,
            account_id=audit_user.account_id,
            user_id=audit_user.id,
            action="permission_check",
            status="success",
        )
        for _ in range(2):
            crud_audit_log.log_action(
                db_session,
                account_id=audit_user.account_id,
                user_id=audit_user.id,
                action="permission_check",
                status="denied",
            )

        response = audit_client.get("/api/v1/audit-logs/denials?days=7")
        assert response.status_code == 200
        data = response.json()

        assert len(data["logs"]) == 2
        assert all(log["status"] == "denied" for log in data["logs"])
        assert all(log["action"] == "permission_check" for log in data["logs"])

    def test_list_audit_logs_requires_permission(
        self, audit_client: TestClient, db_session: Session, test_viewer_user: User
    ):
        """Test that listing audit logs requires view_audit_logs permission."""
        import os

        # Temporarily disable RBAC to test permission denial
        old_disable_rbac = os.environ.get("DISABLE_RBAC")
        if "DISABLE_RBAC" in os.environ:
            del os.environ["DISABLE_RBAC"]

        # Create app with viewer user (no audit permissions)
        from preloop_ai.api.app import create_app
        from preloop_ai.api.auth import get_current_active_user
        from preloop_models.db.session import get_db_session as get_db
        from preloop_ai.plugins.proprietary.audit import endpoints as audit_endpoints

        def override_get_current_active_user():
            return test_viewer_user

        def override_get_db():
            yield db_session

        app = create_app()
        # Include audit router
        app.include_router(audit_endpoints.router, prefix="/api/v1", tags=["Audit"])
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_active_user
        )

        test_client = TestClient(app)
        response = test_client.get("/api/v1/audit-logs")

        # Restore DISABLE_RBAC
        if old_disable_rbac is not None:
            os.environ["DISABLE_RBAC"] = old_disable_rbac

        # Should be denied (viewer role doesn't have view_audit_logs permission)
        assert response.status_code == 403

    def test_account_isolation_in_audit_logs(
        self, audit_client: TestClient, db_session: Session, audit_user: User
    ):
        """Test that users can only see audit logs from their own account."""
        from preloop_models.crud import crud_account

        # Create another account
        other_account_data = {"organization_name": "Other Org", "is_active": True}
        other_account = crud_account.create(db_session, obj_in=other_account_data)

        # Create logs for both accounts
        crud_audit_log.log_action(
            db_session,
            account_id=audit_user.account_id,
            user_id=audit_user.id,
            action="my_account_action",
            status="success",
        )
        crud_audit_log.log_action(
            db_session,
            account_id=other_account.id,
            user_id=audit_user.id,
            action="other_account_action",
            status="success",
        )

        response = audit_client.get("/api/v1/audit-logs")
        assert response.status_code == 200
        data = response.json()

        # Should only see logs from own account (plus the permission check log from RBAC)
        # Filter to get only our test logs
        my_account_logs = [
            log for log in data["logs"] if log["action"] == "my_account_action"
        ]
        other_account_logs = [
            log for log in data["logs"] if log["action"] == "other_account_action"
        ]

        assert len(my_account_logs) == 1
        assert len(other_account_logs) == 0
        assert my_account_logs[0]["action"] == "my_account_action"

    def test_audit_log_response_format(
        self, audit_client: TestClient, db_session: Session, audit_user: User
    ):
        """Test that audit log response has correct format."""
        crud_audit_log.log_action(
            db_session,
            account_id=audit_user.account_id,
            user_id=audit_user.id,
            action="test_action",
            resource_type="issue",
            resource_id="123",
            status="success",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            details={"key": "value"},
        )

        response = audit_client.get("/api/v1/audit-logs")
        assert response.status_code == 200
        data = response.json()

        # Find the test_action log (filter out permission_check logs from RBAC)
        test_log = next(
            (log for log in data["logs"] if log["action"] == "test_action"), None
        )
        assert test_log is not None, "test_action log not found"

        log = test_log
        assert "id" in log
        assert "account_id" in log
        assert "user_id" in log
        assert "action" in log
        assert "resource_type" in log
        assert "resource_id" in log
        assert "status" in log
        assert "ip_address" in log
        assert "user_agent" in log
        assert "details" in log
        assert "timestamp" in log

        assert log["action"] == "test_action"
        assert log["resource_type"] == "issue"
        assert log["resource_id"] == "123"
        assert log["status"] == "success"
        assert log["ip_address"] == "192.168.1.1"
        assert log["details"]["key"] == "value"
