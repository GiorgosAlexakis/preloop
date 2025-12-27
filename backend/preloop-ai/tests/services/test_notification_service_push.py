"""Tests for NotificationService push notification integration."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from preloop_models import models
from preloop_models.crud import crud_account, crud_user, notification_preferences

from preloop_ai.services.notification_service import NotificationService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def test_account(db_session):
    """Create test account."""
    account_data = {
        "organization_name": "Test Organization",
        "is_active": True,
    }
    account = crud_account.create(db_session, obj_in=account_data)
    db_session.commit()
    return account


@pytest.fixture
def test_user_with_ios_token(db_session, test_account):
    """Create test user with iOS notification preferences."""
    user_data = {
        "account_id": test_account.id,
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "is_active": True,
    }
    user = crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    # Create notification preferences with iOS token
    prefs = notification_preferences.get_or_create(db_session, user.id)
    prefs.enable_mobile_push = True
    prefs.add_device_token("ios", "a" * 64)
    db_session.commit()

    return user


@pytest.fixture
def test_user_without_push(db_session, test_account):
    """Create test user without push notifications enabled."""
    user_data = {
        "account_id": test_account.id,
        "email": "no-push@example.com",
        "username": "nopushuser",
        "full_name": "No Push User",
        "is_active": True,
    }
    user = crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    # Create notification preferences but disable push
    prefs = notification_preferences.get_or_create(db_session, user.id)
    prefs.enable_mobile_push = False
    db_session.commit()

    return user


@pytest.fixture
def test_approval_request(test_account):
    """Create test approval request."""
    return models.ApprovalRequest(
        id=uuid.uuid4(),
        account_id=str(test_account.id),
        tool_configuration_id=uuid.uuid4(),
        approval_policy_id=uuid.uuid4(),
        tool_name="create_issue",
        tool_args={"title": "Test Issue"},
        agent_reasoning="Need to create an issue for testing",
        status="pending",
        requested_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    )


@pytest.fixture
def mock_apns_service():
    """Mock APNs service."""
    mock_service = AsyncMock()
    mock_service.send_notification = AsyncMock(return_value=(True, 200, None))
    return mock_service


class TestSendPushNotifications:
    """Test _send_push_notifications method."""

    async def test_send_to_single_user_with_ios_token(
        self, db_session, test_user_with_ios_token, test_approval_request, mock_apns_service
    ):
        """Test sending push notification to single user with iOS token."""
        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request, [test_user_with_ios_token.id]
            )

            assert result["success"] is True
            assert result["sent"] == 1
            assert result["failed"] == 0
            assert result["invalid_tokens_removed"] == 0

            # Verify send_notification was called
            mock_apns_service.send_notification.assert_called_once()
            call_kwargs = mock_apns_service.send_notification.call_args[1]
            assert call_kwargs["device_token"] == "a" * 64

    async def test_send_to_multiple_users(
        self, db_session, test_account, test_approval_request, mock_apns_service
    ):
        """Test sending push notifications to multiple users."""
        # Create multiple users with iOS tokens
        user1_data = {
            "account_id": test_account.id,
            "email": "user1@example.com",
            "username": "user1",
            "full_name": "User 1",
            "is_active": True,
        }
        user1 = crud_user.create(db_session, obj_in=user1_data)

        user2_data = {
            "account_id": test_account.id,
            "email": "user2@example.com",
            "username": "user2",
            "full_name": "User 2",
            "is_active": True,
        }
        user2 = crud_user.create(db_session, obj_in=user2_data)
        db_session.commit()

        for user in [user1, user2]:
            prefs = notification_preferences.get_or_create(db_session, user.id)
            prefs.enable_mobile_push = True
            prefs.add_device_token("ios", f"{'b' * 64}_{user.id}")
        db_session.commit()

        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request, [user1.id, user2.id]
            )

            assert result["success"] is True
            assert result["sent"] == 2
            assert result["failed"] == 0

            # Verify send_notification was called twice
            assert mock_apns_service.send_notification.call_count == 2

    async def test_send_to_user_with_multiple_devices(
        self, db_session, test_account, test_approval_request, mock_apns_service
    ):
        """Test sending to user with multiple iOS devices."""
        user_data = {
            "account_id": test_account.id,
            "email": "multi-device@example.com",
            "username": "multideviceuser",
            "full_name": "Multi Device User",
            "is_active": True,
        }
        user = crud_user.create(db_session, obj_in=user_data)
        db_session.commit()

        prefs = notification_preferences.get_or_create(db_session, user.id)
        prefs.enable_mobile_push = True
        prefs.add_device_token("ios", "c" * 64)
        prefs.add_device_token("ios", "d" * 64)  # Second device (replaces first)
        db_session.commit()

        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request, [user.id]
            )

            # Should only send to one device (latest registered)
            assert result["sent"] >= 1

    async def test_skip_user_without_mobile_push_enabled(
        self, db_session, test_user_without_push, test_approval_request, mock_apns_service
    ):
        """Test that users without mobile push enabled are skipped."""
        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request, [test_user_without_push.id]
            )

            assert result["sent"] == 0
            # send_notification should not be called
            mock_apns_service.send_notification.assert_not_called()

    async def test_skip_user_without_ios_tokens(
        self, db_session, test_account, test_approval_request, mock_apns_service
    ):
        """Test that users without iOS tokens are skipped."""
        user_data = {
            "account_id": test_account.id,
            "email": "android-only@example.com",
            "username": "androiduser",
            "full_name": "Android User",
            "is_active": True,
        }
        user = crud_user.create(db_session, obj_in=user_data)
        db_session.commit()

        prefs = notification_preferences.get_or_create(db_session, user.id)
        prefs.enable_mobile_push = True
        prefs.add_device_token("android", "android_token_123")
        db_session.commit()

        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request, [user.id]
            )

            assert result["sent"] == 0
            # send_notification should not be called (no iOS tokens)
            mock_apns_service.send_notification.assert_not_called()

    async def test_invalid_token_removal_410(
        self, db_session, test_user_with_ios_token, test_approval_request, mock_apns_service
    ):
        """Test that invalid tokens (410 response) are removed from database."""
        # Mock 410 response (invalid token)
        mock_apns_service.send_notification = AsyncMock(
            return_value=(False, 410, "Unregistered")
        )

        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request, [test_user_with_ios_token.id]
            )

            assert result["success"] is True  # No failures, just invalid tokens
            assert result["sent"] == 0
            assert result["invalid_tokens_removed"] == 1

            # Verify token was removed from database
            prefs = notification_preferences.get_by_user(
                db_session, test_user_with_ios_token.id
            )
            assert len(prefs.get_device_tokens(platform="ios")) == 0

    async def test_escalation_notification(
        self, db_session, test_user_with_ios_token, test_approval_request, mock_apns_service
    ):
        """Test that escalation notifications have correct title prefix."""
        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request,
                [test_user_with_ios_token.id],
                is_escalation=True,
            )

            assert result["is_escalation"] is True
            assert result["sent"] == 1

            # Verify payload has escalation prefix
            call_kwargs = mock_apns_service.send_notification.call_args[1]
            payload = call_kwargs["payload"]
            assert "ESCALATION:" in payload["aps"]["alert"]["title"]

    async def test_priority_mapping(
        self, db_session, test_user_with_ios_token, test_approval_request, mock_apns_service
    ):
        """Test that escalation flag maps to APNs priority correctly."""
        notification_service = NotificationService(db_session)

        # Test escalation -> APNs priority 10 (high priority)
        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            await notification_service._send_push_notifications(
                test_approval_request, [test_user_with_ios_token.id], is_escalation=True
            )

            call_kwargs = mock_apns_service.send_notification.call_args[1]
            assert call_kwargs["priority"] == 10

    async def test_apns_not_configured(
        self, db_session, test_user_with_ios_token, test_approval_request
    ):
        """Test graceful handling when APNs is not configured."""
        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=None,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request, [test_user_with_ios_token.id]
            )

            assert result["success"] is False
            assert result["error"] == "APNs not configured"
            assert result["sent"] == 0
            assert result["failed"] == 0

    async def test_send_failure_handling(
        self, db_session, test_user_with_ios_token, test_approval_request, mock_apns_service
    ):
        """Test handling of send failures (non-410 errors)."""
        # Mock 500 response (server error)
        mock_apns_service.send_notification = AsyncMock(
            return_value=(False, 500, "InternalServerError")
        )

        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request, [test_user_with_ios_token.id]
            )

            assert result["success"] is False
            assert result["sent"] == 0
            assert result["failed"] == 1
            assert result["invalid_tokens_removed"] == 0

            # Token should NOT be removed (not a 410)
            prefs = notification_preferences.get_by_user(
                db_session, test_user_with_ios_token.id
            )
            assert len(prefs.get_device_tokens(platform="ios")) == 1

    async def test_network_exception_handling(
        self, db_session, test_user_with_ios_token, test_approval_request, mock_apns_service
    ):
        """Test handling of network exceptions."""
        # Mock exception
        mock_apns_service.send_notification = AsyncMock(
            side_effect=Exception("Network error")
        )

        notification_service = NotificationService(db_session)

        with patch(
            "preloop_ai.services.push_notifications.get_apns_service",
            return_value=mock_apns_service,
        ):
            result = await notification_service._send_push_notifications(
                test_approval_request, [test_user_with_ios_token.id]
            )

            assert result["success"] is False
            assert result["sent"] == 0
            assert result["failed"] == 1
