"""Tests for the audit logging service."""

from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import Request
from sqlalchemy.orm import Session

from spacebridge.plugins.proprietary.audit.service import (
    AuditService,
    get_audit_service,
)
from spacemodels.crud import crud_account, crud_audit_log, crud_user


@pytest.fixture
def test_account(db_session: Session):
    """Create a test account."""
    account_data = {
        "organization_name": "Audit Service Test Org",
        "is_active": True,
    }
    return crud_account.create(db_session, obj_in=account_data)


@pytest.fixture
def test_user_for_service(db_session: Session, test_account):
    """Create a test user for service testing."""
    user_data = {
        "account_id": test_account.id,
        "email": "serviceuser@example.com",
        "username": "serviceuser",
        "full_name": "Service User",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    return crud_user.create(db_session, obj_in=user_data)


@pytest.fixture
def audit_service():
    """Create an audit service instance."""
    return AuditService()


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = MagicMock(spec=Request)
    # Create a headers mock that behaves like a dict
    headers = MagicMock()
    headers.get = MagicMock(return_value=None)
    request.headers = headers
    request.client = None
    return request


class TestAuditService:
    """Test the audit service."""

    def test_get_audit_service_singleton(self):
        """Test that get_audit_service returns a singleton."""
        service1 = get_audit_service()
        service2 = get_audit_service()
        assert service1 is service2

    def test_log_permission_check_granted(
        self, db_session: Session, test_account, test_user_for_service, audit_service
    ):
        """Test logging a granted permission check."""
        audit_service.log_permission_check(
            db=db_session,
            account_id=test_account.id,
            user=test_user_for_service,
            permission="view_issues",
            granted=True,
            resource_type="issue",
            resource_id="123",
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 1
        assert logs[0].action == "permission_check"
        assert logs[0].status == "success"
        assert logs[0].user_id == test_user_for_service.id
        assert logs[0].details["permission"] == "view_issues"
        assert logs[0].details["granted"] is True

    def test_log_permission_check_denied(
        self, db_session: Session, test_account, test_user_for_service, audit_service
    ):
        """Test logging a denied permission check."""
        audit_service.log_permission_check(
            db=db_session,
            account_id=test_account.id,
            user=test_user_for_service,
            permission="delete_issues",
            granted=False,
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 1
        assert logs[0].status == "denied"
        assert logs[0].details["granted"] is False

    def test_log_permission_check_with_request(
        self,
        db_session: Session,
        test_account,
        test_user_for_service,
        audit_service,
    ):
        """Test logging permission check with request context."""
        # Create a fresh mock request without spec to allow full mocking
        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(
            side_effect=lambda key: {
                "X-Forwarded-For": "192.168.1.100",
                "User-Agent": "Mozilla/5.0 Test Browser",
            }.get(key)
        )

        audit_service.log_permission_check(
            db=db_session,
            account_id=test_account.id,
            user=test_user_for_service,
            permission="view_issues",
            granted=True,
            request=mock_request,
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 1
        assert logs[0].ip_address == "192.168.1.100"
        assert logs[0].user_agent == "Mozilla/5.0 Test Browser"

    def test_log_authentication_success(
        self, db_session: Session, test_account, test_user_for_service, audit_service
    ):
        """Test logging successful authentication."""
        audit_service.log_authentication(
            db=db_session,
            account_id=test_account.id,
            user_id=test_user_for_service.id,
            username="serviceuser",
            success=True,
            method="jwt",
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 1
        assert logs[0].action == "authentication"
        assert logs[0].status == "success"
        assert logs[0].details["username"] == "serviceuser"
        assert logs[0].details["method"] == "jwt"

    def test_log_authentication_failure(
        self, db_session: Session, test_account, audit_service
    ):
        """Test logging failed authentication."""
        audit_service.log_authentication(
            db=db_session,
            account_id=test_account.id,
            user_id=None,
            username="baduser",
            success=False,
            method="jwt",
            failure_reason="Invalid credentials",
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 1
        assert logs[0].action == "authentication"
        assert logs[0].status == "failure"
        assert logs[0].user_id is None
        assert logs[0].details["failure_reason"] == "Invalid credentials"

    def test_log_role_assignment(
        self, db_session: Session, test_account, test_user_for_service, audit_service
    ):
        """Test logging role assignment."""
        target_user_id = test_user_for_service.id

        audit_service.log_role_assignment(
            db=db_session,
            account_id=test_account.id,
            actor=test_user_for_service,
            target_user_id=target_user_id,
            role_name="editor",
            action="assigned",
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 1
        assert logs[0].action == "role_assigned"
        assert logs[0].status == "success"
        assert logs[0].details["role"] == "editor"
        assert logs[0].details["action"] == "assigned"

    def test_log_resource_access(
        self, db_session: Session, test_account, test_user_for_service, audit_service
    ):
        """Test logging resource access."""
        audit_service.log_resource_access(
            db=db_session,
            account_id=test_account.id,
            user=test_user_for_service,
            resource_type="issue",
            resource_id="123",
            action="view",
            status="success",
            details={"query": "filter=open"},
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 1
        assert logs[0].action == "issue_view"
        assert logs[0].resource_type == "issue"
        assert logs[0].resource_id == "123"
        assert logs[0].details["query"] == "filter=open"

    def test_log_configuration_change(
        self, db_session: Session, test_account, test_user_for_service, audit_service
    ):
        """Test logging configuration change."""
        audit_service.log_configuration_change(
            db=db_session,
            account_id=test_account.id,
            user=test_user_for_service,
            config_type="approval_policy",
            action="update",
            old_value="require_2_approvals",
            new_value="require_3_approvals",
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 1
        assert logs[0].action == "configuration_change"
        assert logs[0].details["config_type"] == "approval_policy"
        assert logs[0].details["old_value"] == "require_2_approvals"
        assert logs[0].details["new_value"] == "require_3_approvals"

    def test_get_client_ip_from_forwarded(self, audit_service):
        """Test extracting IP from X-Forwarded-For header."""
        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(
            side_effect=(
                lambda key: "192.168.1.100, 10.0.0.1"
                if key == "X-Forwarded-For"
                else None
            )
        )

        ip = audit_service._get_client_ip(mock_request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_from_real_ip(self, audit_service):
        """Test extracting IP from X-Real-IP header."""
        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(
            side_effect=(lambda key: "192.168.1.200" if key == "X-Real-IP" else None)
        )

        ip = audit_service._get_client_ip(mock_request)
        assert ip == "192.168.1.200"

    def test_get_client_ip_from_client(self, audit_service):
        """Test extracting IP from request.client."""
        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.300"

        ip = audit_service._get_client_ip(mock_request)
        assert ip == "192.168.1.300"

    def test_get_client_ip_none(self, audit_service):
        """Test getting IP when request is None."""
        ip = audit_service._get_client_ip(None)
        assert ip is None

    def test_get_user_agent(self, audit_service):
        """Test extracting user agent."""
        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(
            side_effect=(lambda key: "Mozilla/5.0" if key == "User-Agent" else None)
        )

        user_agent = audit_service._get_user_agent(mock_request)
        assert user_agent == "Mozilla/5.0"

    def test_get_user_agent_none(self, audit_service):
        """Test getting user agent when request is None."""
        user_agent = audit_service._get_user_agent(None)
        assert user_agent is None

    def test_enable_disable(self, audit_service):
        """Test enabling and disabling audit logging."""
        assert audit_service.enabled is True

        audit_service.disable()
        assert audit_service.enabled is False

        audit_service.enable()
        assert audit_service.enabled is True

    def test_disabled_service_does_not_log(
        self, db_session: Session, test_account, test_user_for_service, audit_service
    ):
        """Test that disabled service does not create logs."""
        audit_service.disable()

        audit_service.log_permission_check(
            db=db_session,
            account_id=test_account.id,
            user=test_user_for_service,
            permission="view_issues",
            granted=True,
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 0

    def test_logging_with_uuid_account_id(
        self, db_session: Session, test_account, test_user_for_service, audit_service
    ):
        """Test that service handles UUID account IDs correctly."""
        # This tests the Union[UUID, str] handling

        account_uuid = UUID(test_account.id)

        audit_service.log_permission_check(
            db=db_session,
            account_id=account_uuid,
            user=test_user_for_service,
            permission="test_permission",
            granted=True,
        )

        logs = crud_audit_log.get_by_account(db_session, account_id=test_account.id)
        assert len(logs) == 1
        assert logs[0].account_id == test_account.id  # Should be string
