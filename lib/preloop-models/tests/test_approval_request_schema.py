"""Tests for approval request Pydantic schemas."""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from spacemodels.schemas.approval_request import (
    ApprovalDecision,
    ApprovalRequestBase,
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalRequestUpdate,
)


class TestApprovalRequestBase:
    """Test ApprovalRequestBase schema."""

    def test_create_with_required_fields(self):
        """Test creating ApprovalRequestBase with required fields only."""
        request = ApprovalRequestBase(tool_name="test_tool")
        assert request.tool_name == "test_tool"
        assert request.tool_args == {}
        assert request.agent_reasoning is None
        assert request.execution_id is None

    def test_create_with_all_fields(self):
        """Test creating ApprovalRequestBase with all fields."""
        request = ApprovalRequestBase(
            tool_name="create_issue",
            tool_args={"project": "PROJ", "title": "Test"},
            agent_reasoning="User requested issue creation",
            execution_id="exec-123",
        )
        assert request.tool_name == "create_issue"
        assert request.tool_args == {"project": "PROJ", "title": "Test"}
        assert request.agent_reasoning == "User requested issue creation"
        assert request.execution_id == "exec-123"

    def test_tool_name_required(self):
        """Test that tool_name is required."""
        with pytest.raises(ValidationError):
            ApprovalRequestBase()


class TestApprovalRequestCreate:
    """Test ApprovalRequestCreate schema."""

    def test_create_with_required_fields(self):
        """Test creating ApprovalRequestCreate with required fields."""
        account_id = str(uuid4())
        tool_config_id = uuid4()
        policy_id = uuid4()

        request = ApprovalRequestCreate(
            tool_name="test_tool",
            account_id=account_id,
            tool_configuration_id=tool_config_id,
            approval_policy_id=policy_id,
        )

        assert request.tool_name == "test_tool"
        assert request.account_id == account_id
        assert request.tool_configuration_id == tool_config_id
        assert request.approval_policy_id == policy_id
        assert request.expires_at is None

    def test_create_with_expiration(self):
        """Test creating ApprovalRequestCreate with expiration."""
        account_id = str(uuid4())
        tool_config_id = uuid4()
        policy_id = uuid4()
        expires_at = datetime(2025, 12, 31, 23, 59, 59)

        request = ApprovalRequestCreate(
            tool_name="test_tool",
            account_id=account_id,
            tool_configuration_id=tool_config_id,
            approval_policy_id=policy_id,
            expires_at=expires_at,
        )

        assert request.expires_at == expires_at

    def test_inherits_from_base(self):
        """Test that ApprovalRequestCreate inherits from Base."""
        account_id = str(uuid4())
        tool_config_id = uuid4()
        policy_id = uuid4()

        request = ApprovalRequestCreate(
            tool_name="test_tool",
            account_id=account_id,
            tool_configuration_id=tool_config_id,
            approval_policy_id=policy_id,
            tool_args={"key": "value"},
            agent_reasoning="Test reasoning",
        )

        assert request.tool_args == {"key": "value"}
        assert request.agent_reasoning == "Test reasoning"


class TestApprovalRequestUpdate:
    """Test ApprovalRequestUpdate schema."""

    def test_create_empty_update(self):
        """Test creating empty update (all fields optional)."""
        update = ApprovalRequestUpdate()
        assert update.status is None
        assert update.approver_comment is None
        assert update.resolved_at is None
        assert update.webhook_posted_at is None
        assert update.webhook_error is None

    def test_update_status(self):
        """Test updating status."""
        update = ApprovalRequestUpdate(status="approved")
        assert update.status == "approved"

    def test_update_with_comment(self):
        """Test updating with approver comment."""
        update = ApprovalRequestUpdate(
            status="declined", approver_comment="Not authorized"
        )
        assert update.status == "declined"
        assert update.approver_comment == "Not authorized"

    def test_update_with_timestamps(self):
        """Test updating with timestamps."""
        resolved_at = datetime.now()
        webhook_posted_at = datetime.now()

        update = ApprovalRequestUpdate(
            status="approved",
            resolved_at=resolved_at,
            webhook_posted_at=webhook_posted_at,
        )

        assert update.resolved_at == resolved_at
        assert update.webhook_posted_at == webhook_posted_at

    def test_update_with_webhook_error(self):
        """Test updating with webhook error."""
        update = ApprovalRequestUpdate(
            webhook_error="Failed to post to Slack: Connection timeout"
        )
        assert update.webhook_error == "Failed to post to Slack: Connection timeout"


class TestApprovalRequestResponse:
    """Test ApprovalRequestResponse schema."""

    def test_create_response(self):
        """Test creating ApprovalRequestResponse."""
        request_id = uuid4()
        account_id = str(uuid4())
        tool_config_id = uuid4()
        policy_id = uuid4()
        requested_at = datetime.now()

        response = ApprovalRequestResponse(
            id=request_id,
            account_id=account_id,
            tool_configuration_id=tool_config_id,
            approval_policy_id=policy_id,
            tool_name="test_tool",
            status="pending",
            requested_at=requested_at,
            resolved_at=None,
            expires_at=None,
            approver_comment=None,
            webhook_posted_at=None,
            webhook_error=None,
        )

        assert response.id == request_id
        assert response.account_id == account_id
        assert response.tool_configuration_id == tool_config_id
        assert response.approval_policy_id == policy_id
        assert response.tool_name == "test_tool"
        assert response.status == "pending"
        assert response.requested_at == requested_at

    def test_response_with_all_fields(self):
        """Test creating response with all optional fields."""
        request_id = uuid4()
        account_id = str(uuid4())
        tool_config_id = uuid4()
        policy_id = uuid4()
        requested_at = datetime.now()
        resolved_at = datetime.now()
        expires_at = datetime(2025, 12, 31, 23, 59, 59)
        webhook_posted_at = datetime.now()

        response = ApprovalRequestResponse(
            id=request_id,
            account_id=account_id,
            tool_configuration_id=tool_config_id,
            approval_policy_id=policy_id,
            tool_name="create_issue",
            tool_args={"project": "PROJ"},
            agent_reasoning="User requested",
            execution_id="exec-123",
            status="approved",
            requested_at=requested_at,
            resolved_at=resolved_at,
            expires_at=expires_at,
            approver_comment="Approved by manager",
            webhook_posted_at=webhook_posted_at,
            webhook_error=None,
        )

        assert response.tool_args == {"project": "PROJ"}
        assert response.agent_reasoning == "User requested"
        assert response.execution_id == "exec-123"
        assert response.status == "approved"
        assert response.resolved_at == resolved_at
        assert response.expires_at == expires_at
        assert response.approver_comment == "Approved by manager"
        assert response.webhook_posted_at == webhook_posted_at

    def test_from_attributes_config(self):
        """Test that from_attributes is enabled in Config."""
        # This allows creating schema from ORM objects
        assert ApprovalRequestResponse.model_config.get("from_attributes") is True


class TestApprovalDecision:
    """Test ApprovalDecision schema."""

    def test_create_approved_decision(self):
        """Test creating approved decision."""
        decision = ApprovalDecision(approved=True)
        assert decision.approved is True
        assert decision.comment is None

    def test_create_declined_decision(self):
        """Test creating declined decision."""
        decision = ApprovalDecision(approved=False)
        assert decision.approved is False
        assert decision.comment is None

    def test_decision_with_comment(self):
        """Test creating decision with comment."""
        decision = ApprovalDecision(approved=True, comment="Approved by team lead")
        assert decision.approved is True
        assert decision.comment == "Approved by team lead"

    def test_approved_field_required(self):
        """Test that approved field is required."""
        with pytest.raises(ValidationError):
            ApprovalDecision()
