"""Tests for ApprovalService push notification integration."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from preloop_models.models import ApprovalPolicy, ApprovalRequest

from preloop_ai.services.approval_service import ApprovalService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_db():
    """Create mock async database session."""
    mock = AsyncMock()
    # Mock the bind.sync_engine for Session creation
    mock.bind.sync_engine = MagicMock()
    return mock


@pytest.fixture
def approval_service(mock_db):
    """Create ApprovalService instance with mocked database."""
    return ApprovalService(mock_db, "https://app.test.com")


@pytest.fixture
def sample_approval_policy():
    """Create sample approval policy with mobile_push channel."""
    policy = MagicMock(spec=ApprovalPolicy)
    policy.id = uuid.uuid4()
    policy.notification_channels = ["mobile_push"]
    policy.approver_user_ids = [uuid.uuid4(), uuid.uuid4()]
    return policy


@pytest.fixture
def sample_approval_request():
    """Create sample approval request."""
    request = MagicMock(spec=ApprovalRequest)
    request.id = uuid.uuid4()
    request.account_id = "test_account"
    request.tool_configuration_id = uuid.uuid4()
    request.approval_policy_id = uuid.uuid4()
    request.tool_name = "create_issue"
    request.tool_args = {"title": "Test Issue"}
    request.agent_reasoning = "Need to create an issue"
    request.status = "pending"
    request.requested_at = datetime.utcnow()
    request.expires_at = datetime.utcnow() + timedelta(minutes=5)
    request.priority = "medium"
    return request


@pytest.fixture
def mock_apns_service():
    """Mock APNs service."""
    mock_service = AsyncMock()
    mock_service.send_notification = AsyncMock(return_value=(True, 200, None))
    return mock_service


class TestSendPushNotification:
    """Test _send_push_notification method."""

    async def test_send_push_notification_success(
        self,
        approval_service,
        sample_approval_request,
        sample_approval_policy,
        mock_apns_service,
    ):
        """Test successful push notification send."""
        # Mock notification preferences and sync session
        mock_prefs = MagicMock()
        mock_prefs.enable_mobile_push = True
        mock_prefs.get_device_tokens.return_value = ["a" * 64]

        mock_sync_session = MagicMock()
        mock_sync_session.__enter__.return_value = mock_sync_session
        mock_sync_session.__exit__.return_value = None

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            with patch(
                "preloop_models.crud.notification_preferences.get_by_user",
                return_value=mock_prefs,
            ):
                with patch(
                    "sqlalchemy.orm.Session",
                    return_value=mock_sync_session,
                ):
                    result = await approval_service._send_push_notification(
                        sample_approval_request, sample_approval_policy
                    )

                    assert result["success"] is True
                    # Should send to both approvers
                    assert result["sent"] >= 1

    async def test_send_push_notification_multiple_approvers(
        self,
        approval_service,
        sample_approval_request,
        sample_approval_policy,
        mock_apns_service,
    ):
        """Test sending to multiple approvers."""
        # Mock notification preferences for multiple users
        mock_prefs = MagicMock()
        mock_prefs.enable_mobile_push = True
        mock_prefs.get_device_tokens.return_value = ["b" * 64]

        mock_sync_session = MagicMock()

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            with patch(
                "preloop_models.crud.notification_preferences.get_by_user",
                return_value=mock_prefs,
            ):
                with patch(
                    "sqlalchemy.orm.Session",
                    return_value=mock_sync_session,
                ):
                    result = await approval_service._send_push_notification(
                        sample_approval_request, sample_approval_policy
                    )

                    # Should attempt to send to all approvers
                    assert result["sent"] == 2  # Two approvers in policy

    async def test_send_push_notification_no_approvers(
        self, approval_service, sample_approval_request, mock_apns_service
    ):
        """Test handling when no approvers are configured."""
        policy_no_approvers = MagicMock(spec=ApprovalPolicy)
        policy_no_approvers.id = uuid.uuid4()
        policy_no_approvers.approver_user_ids = []

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await approval_service._send_push_notification(
                sample_approval_request, policy_no_approvers
            )

            assert result["success"] is False
            assert result["error"] == "No approvers configured"

    async def test_send_push_notification_apns_not_configured(
        self, approval_service, sample_approval_request, sample_approval_policy
    ):
        """Test graceful handling when APNs is not configured."""
        with patch(
            "preloop_ai.services.push_notifications.get_apns_service", return_value=None
        ):
            result = await approval_service._send_push_notification(
                sample_approval_request, sample_approval_policy
            )

            assert result["success"] is False
            assert result["error"] == "APNs not configured"

    async def test_send_push_notification_invalid_token_removal(
        self,
        approval_service,
        sample_approval_request,
        sample_approval_policy,
        mock_apns_service,
    ):
        """Test that invalid tokens are removed (410 response)."""
        # Mock 410 response
        mock_apns_service.send_notification = AsyncMock(
            return_value=(False, 410, "Unregistered")
        )

        mock_prefs = MagicMock()
        mock_prefs.enable_mobile_push = True
        mock_prefs.get_device_tokens.return_value = ["c" * 64]

        mock_sync_session = MagicMock()
        mock_remove = MagicMock()

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            with patch(
                "preloop_models.crud.notification_preferences.get_by_user",
                return_value=mock_prefs,
            ):
                with patch(
                    "preloop_models.crud.notification_preferences.remove_device_token",
                    mock_remove,
                ):
                    with patch(
                        "sqlalchemy.orm.Session",
                        return_value=mock_sync_session,
                    ):
                        result = await approval_service._send_push_notification(
                            sample_approval_request, sample_approval_policy
                        )

                        assert result["invalid_tokens_removed"] == 2  # Both approvers

    async def test_create_approval_request_triggers_push(
        self, approval_service, sample_approval_policy, mock_apns_service
    ):
        """Test that creating approval request triggers push notification."""
        # Mock database operations
        approval_service.db.add = MagicMock()
        approval_service.db.commit = AsyncMock()
        approval_service.db.refresh = AsyncMock()
        approval_service.db.execute = AsyncMock()

        # Mock query result for approval policy
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_approval_policy
        approval_service.db.execute.return_value = mock_result

        # Mock broadcast method
        approval_service._broadcast_approval_update = AsyncMock()

        # Mock push notification method
        with patch.object(
            approval_service, "_send_push_notification", new=AsyncMock()
        ) as mock_send_push:
            await approval_service.create_approval_request(
                account_id="test_account",
                tool_configuration_id=uuid.uuid4(),
                approval_policy_id=sample_approval_policy.id,
                tool_name="create_issue",
                tool_args={"title": "Test"},
            )

            # Verify _send_push_notification was called
            mock_send_push.assert_called_once()

    async def test_create_approval_request_skip_push_when_not_in_channels(
        self, approval_service, mock_apns_service
    ):
        """Test that push is skipped when not in notification channels."""
        # Create policy without mobile_push channel
        policy_no_push = MagicMock(spec=ApprovalPolicy)
        policy_no_push.id = uuid.uuid4()
        policy_no_push.notification_channels = ["email"]  # No mobile_push

        # Mock database operations
        approval_service.db.add = MagicMock()
        approval_service.db.commit = AsyncMock()
        approval_service.db.refresh = AsyncMock()
        approval_service.db.execute = AsyncMock()

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = policy_no_push
        approval_service.db.execute.return_value = mock_result

        # Mock broadcast method
        approval_service._broadcast_approval_update = AsyncMock()

        # Mock push notification method
        with patch.object(
            approval_service, "_send_push_notification", new=AsyncMock()
        ) as mock_send_push:
            await approval_service.create_approval_request(
                account_id="test_account",
                tool_configuration_id=uuid.uuid4(),
                approval_policy_id=policy_no_push.id,
                tool_name="create_issue",
                tool_args={"title": "Test"},
            )

            # Verify _send_push_notification was NOT called
            mock_send_push.assert_not_called()

    async def test_send_push_notification_handles_exceptions(
        self,
        approval_service,
        sample_approval_request,
        sample_approval_policy,
        mock_apns_service,
    ):
        """Test that exceptions in push notification don't crash the service."""
        # Mock exception
        mock_apns_service.send_notification = AsyncMock(
            side_effect=Exception("Network error")
        )

        mock_prefs = MagicMock()
        mock_prefs.enable_mobile_push = True
        mock_prefs.get_device_tokens.return_value = ["d" * 64]

        mock_sync_session = MagicMock()

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            with patch(
                "preloop_models.crud.notification_preferences.get_by_user",
                return_value=mock_prefs,
            ):
                with patch(
                    "sqlalchemy.orm.Session",
                    return_value=mock_sync_session,
                ):
                    result = await approval_service._send_push_notification(
                        sample_approval_request, sample_approval_policy
                    )

                    # Should handle exception gracefully
                    assert result["failed"] == 2  # Both approvers failed
                    assert result["sent"] == 0
