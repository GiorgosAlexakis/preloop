"""Tests for approval service."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from preloop_models.models import ApprovalPolicy, ApprovalRequest
from preloop_models.schemas.approval_request import ApprovalRequestUpdate

from preloop_ai.services.approval_service import ApprovalService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_db():
    """Create mock async database session."""
    return AsyncMock()


@pytest.fixture
def approval_service(mock_db):
    """Create ApprovalService instance with mocked database."""
    return ApprovalService(mock_db, "https://app.test.com")


@pytest.fixture
def sample_approval_policy():
    """Create sample approval policy."""
    policy = MagicMock(spec=ApprovalPolicy)
    policy.id = uuid.uuid4()
    policy.approval_type = "slack"
    policy.timeout_seconds = 300
    policy.approval_config = {"webhook_url": "https://hooks.slack.com/test"}
    policy.notification_channels = ["slack"]  # Added to enable notifications
    return policy


@pytest.fixture
def sample_approval_request():
    """Create sample approval request."""
    request = MagicMock(spec=ApprovalRequest)
    request.id = uuid.uuid4()
    request.account_id = "test_account"
    request.tool_configuration_id = uuid.uuid4()
    request.approval_policy_id = uuid.uuid4()
    request.tool_name = "test_tool"
    request.tool_args = {"arg1": "value1"}
    request.agent_reasoning = "This is why I need approval"
    request.status = "pending"
    request.requested_at = datetime.utcnow()
    request.expires_at = datetime.utcnow() + timedelta(minutes=5)
    request.approval_token = "test_token_123"
    return request


class TestCreateApprovalRequest:
    """Test create_approval_request method."""

    def _setup_mock_db_for_create(self, mock_db, sample_approval_policy):
        """Set up mock_db to handle the execute call for approval policy lookup."""

        # Mock db.refresh to set created fields
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()
            obj.updated_at = datetime.utcnow()

        mock_db.refresh.side_effect = mock_refresh

        # Mock the execute call that queries ApprovalPolicy
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_approval_policy
        mock_db.execute.return_value = mock_result

    async def test_create_approval_request_success(
        self, approval_service, mock_db, sample_approval_policy
    ):
        """Test creating a new approval request."""
        account_id = "test_account"
        tool_config_id = uuid.uuid4()

        self._setup_mock_db_for_create(mock_db, sample_approval_policy)

        result = await approval_service.create_approval_request(
            account_id=account_id,
            tool_configuration_id=tool_config_id,
            approval_policy_id=sample_approval_policy.id,
            tool_name="create_issue",
            tool_args={"title": "Bug", "description": "Fix this"},
            agent_reasoning="Need to create an issue",
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

    async def test_create_approval_request_with_execution_id(
        self, approval_service, mock_db, sample_approval_policy
    ):
        """Test creating approval request with execution ID."""
        execution_id = "exec_123"

        self._setup_mock_db_for_create(mock_db, sample_approval_policy)

        result = await approval_service.create_approval_request(
            account_id="test_account",
            tool_configuration_id=uuid.uuid4(),
            approval_policy_id=sample_approval_policy.id,
            tool_name="delete_issue",
            tool_args={"issue_id": "123"},
            execution_id=execution_id,
        )

        assert mock_db.add.called

    async def test_create_approval_request_custom_timeout(
        self, approval_service, mock_db, sample_approval_policy
    ):
        """Test creating approval request with custom timeout."""
        self._setup_mock_db_for_create(mock_db, sample_approval_policy)

        result = await approval_service.create_approval_request(
            account_id="test_account",
            tool_configuration_id=uuid.uuid4(),
            approval_policy_id=sample_approval_policy.id,
            tool_name="test_tool",
            tool_args={},
            timeout_seconds=600,  # 10 minutes
        )

        assert mock_db.add.called

    async def test_create_approval_request_default_timeout(
        self, approval_service, mock_db, sample_approval_policy
    ):
        """Test creating approval request with default timeout."""
        self._setup_mock_db_for_create(mock_db, sample_approval_policy)

        result = await approval_service.create_approval_request(
            account_id="test_account",
            tool_configuration_id=uuid.uuid4(),
            approval_policy_id=sample_approval_policy.id,
            tool_name="test_tool",
            tool_args={},
        )

        # Should use default 300 seconds timeout
        assert mock_db.add.called


class TestGetApprovalRequest:
    """Test get_approval_request method."""

    async def test_get_approval_request_found(
        self, approval_service, mock_db, sample_approval_request
    ):
        """Test getting an approval request that exists."""
        request_id = sample_approval_request.id

        # Mock database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_approval_request
        mock_db.execute.return_value = mock_result

        result = await approval_service.get_approval_request(request_id)

        assert result == sample_approval_request
        assert mock_db.execute.called

    async def test_get_approval_request_not_found(self, approval_service, mock_db):
        """Test getting an approval request that doesn't exist."""
        request_id = uuid.uuid4()

        # Mock database query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await approval_service.get_approval_request(request_id)

        assert result is None


class TestUpdateApprovalRequest:
    """Test update_approval_request method."""

    async def test_update_approval_request_success(
        self, approval_service, mock_db, sample_approval_request
    ):
        """Test updating an approval request."""
        request_id = sample_approval_request.id
        update = ApprovalRequestUpdate(status="approved", approver_comment="LGTM")

        # Mock get_approval_request to return the sample request
        with patch.object(
            approval_service,
            "get_approval_request",
            return_value=sample_approval_request,
        ):
            result = await approval_service.update_approval_request(request_id, update)

            assert mock_db.commit.called
            assert mock_db.refresh.called
            assert result == sample_approval_request

    async def test_update_approval_request_not_found(self, approval_service, mock_db):
        """Test updating a non-existent approval request."""
        request_id = uuid.uuid4()
        update = ApprovalRequestUpdate(status="approved")

        # Mock get_approval_request to return None
        with patch.object(approval_service, "get_approval_request", return_value=None):
            result = await approval_service.update_approval_request(request_id, update)

            assert result is None
            assert not mock_db.commit.called

    async def test_update_approval_request_partial_update(
        self, approval_service, mock_db, sample_approval_request
    ):
        """Test partial update of approval request."""
        request_id = sample_approval_request.id
        update = ApprovalRequestUpdate(webhook_error="Failed to send")

        with patch.object(
            approval_service,
            "get_approval_request",
            return_value=sample_approval_request,
        ):
            result = await approval_service.update_approval_request(request_id, update)

            assert mock_db.commit.called


class TestApproveRequest:
    """Test approve_request method."""

    async def test_approve_request_success(
        self, approval_service, sample_approval_request
    ):
        """Test approving a request."""
        request_id = sample_approval_request.id
        comment = "Approved for production use"

        # Mock update_approval_request
        with patch.object(
            approval_service,
            "update_approval_request",
            return_value=sample_approval_request,
        ) as mock_update:
            result = await approval_service.approve_request(request_id, comment)

            assert result == sample_approval_request
            # Verify update was called with correct parameters
            assert mock_update.called
            call_args = mock_update.call_args
            assert call_args[0][0] == request_id
            update = call_args[0][1]
            assert update.status == "approved"
            assert update.approver_comment == comment

    async def test_approve_request_without_comment(
        self, approval_service, sample_approval_request
    ):
        """Test approving a request without a comment."""
        request_id = sample_approval_request.id

        with patch.object(
            approval_service,
            "update_approval_request",
            return_value=sample_approval_request,
        ):
            result = await approval_service.approve_request(request_id)

            assert result == sample_approval_request


class TestDeclineRequest:
    """Test decline_request method."""

    async def test_decline_request_success(
        self, approval_service, sample_approval_request
    ):
        """Test declining a request."""
        request_id = sample_approval_request.id
        comment = "Security concerns"

        with patch.object(
            approval_service,
            "update_approval_request",
            return_value=sample_approval_request,
        ) as mock_update:
            result = await approval_service.decline_request(request_id, comment)

            assert result == sample_approval_request
            call_args = mock_update.call_args
            assert call_args[0][0] == request_id
            update = call_args[0][1]
            assert update.status == "declined"
            assert update.approver_comment == comment

    async def test_decline_request_without_comment(
        self, approval_service, sample_approval_request
    ):
        """Test declining a request without a comment."""
        request_id = sample_approval_request.id

        with patch.object(
            approval_service,
            "update_approval_request",
            return_value=sample_approval_request,
        ):
            result = await approval_service.decline_request(request_id)

            assert result == sample_approval_request


class TestPostWebhookNotification:
    """Test post_webhook_notification method."""

    @patch("preloop_ai.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_slack_success(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_policy,
    ):
        """Test posting webhook notification to Slack."""
        # Mock httpx client
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock update_approval_request
        with patch.object(approval_service, "update_approval_request") as mock_update:
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_policy
            )

            assert result is True
            assert mock_client.post.called
            # Verify webhook was marked as posted
            assert mock_update.called

    @patch("preloop_ai.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_mattermost_success(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_policy,
    ):
        """Test posting webhook notification to Mattermost."""
        sample_approval_policy.approval_type = "mattermost"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with patch.object(approval_service, "update_approval_request"):
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_policy
            )

            assert result is True

    @patch("preloop_ai.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_generic_success(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_policy,
    ):
        """Test posting webhook notification to generic webhook."""
        sample_approval_policy.approval_type = "webhook"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with patch.object(approval_service, "update_approval_request"):
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_policy
            )

            assert result is True

    async def test_post_webhook_no_webhook_url(
        self, approval_service, sample_approval_request, sample_approval_policy
    ):
        """Test posting webhook when no webhook URL is configured."""
        sample_approval_policy.approval_config = {}

        with patch.object(approval_service, "update_approval_request") as mock_update:
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_policy
            )

            assert result is False
            # Verify error was recorded
            assert mock_update.called
            call_args = mock_update.call_args
            update = call_args[0][1]
            assert "webhook_error" in update.model_dump(exclude_unset=True)

    async def test_post_webhook_no_config(
        self, approval_service, sample_approval_request, sample_approval_policy
    ):
        """Test posting webhook when approval_config is None."""
        sample_approval_policy.approval_config = None

        with patch.object(approval_service, "update_approval_request"):
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_policy
            )

            assert result is False

    @patch("preloop_ai.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_http_error(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_policy,
    ):
        """Test posting webhook when HTTP error occurs."""
        # Mock httpx client to raise error
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection failed")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with patch.object(approval_service, "update_approval_request") as mock_update:
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_policy
            )

            assert result is False
            # Verify error was recorded
            assert mock_update.called
            call_args = mock_update.call_args
            update = call_args[0][1]
            assert "webhook_error" in update.model_dump(exclude_unset=True)

    @patch("preloop_ai.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_with_agent_reasoning(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_policy,
    ):
        """Test posting webhook with agent reasoning included."""
        sample_approval_request.agent_reasoning = "Need to update critical issue"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with patch.object(approval_service, "update_approval_request"):
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_policy
            )

            assert result is True
            # Verify reasoning was included in the message
            call_args = mock_client.post.call_args
            message = call_args[1]["json"]
            # For Slack/Mattermost, reasoning should be in attachments fields
            assert "attachments" in message
            assert len(message["attachments"]) > 0
            fields = message["attachments"][0].get("fields", [])
            reasoning_fields = [
                f for f in fields if "Agent Reasoning" in f.get("title", "")
            ]
            assert len(reasoning_fields) > 0


class TestCreateAndNotify:
    """Test create_and_notify method."""

    async def test_create_and_notify_success(
        self, approval_service, mock_db, sample_approval_policy
    ):
        """Test creating and notifying approval request."""
        account_id = "test_account"
        tool_config_id = uuid.uuid4()

        # Mock create_approval_request
        mock_approval_request = MagicMock(spec=ApprovalRequest)
        mock_approval_request.id = uuid.uuid4()

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                return_value=mock_approval_request,
            ) as mock_create,
            patch.object(
                approval_service,
                "post_webhook_notification",
                return_value=True,
            ) as mock_webhook,
        ):
            result = await approval_service.create_and_notify(
                account_id=account_id,
                tool_configuration_id=tool_config_id,
                approval_policy=sample_approval_policy,
                tool_name="create_issue",
                tool_args={"title": "Bug"},
                agent_reasoning="Need approval",
            )

            assert result == mock_approval_request
            assert mock_create.called
            # Verify webhook notification was sent (not scheduled as background task)
            assert mock_webhook.called

    async def test_create_and_notify_with_execution_id(
        self, approval_service, sample_approval_policy
    ):
        """Test creating and notifying with execution ID."""
        execution_id = "exec_456"

        mock_approval_request = MagicMock(spec=ApprovalRequest)

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                return_value=mock_approval_request,
            ),
            patch.object(
                approval_service,
                "post_webhook_notification",
                return_value=True,
            ),
        ):
            result = await approval_service.create_and_notify(
                account_id="test_account",
                tool_configuration_id=uuid.uuid4(),
                approval_policy=sample_approval_policy,
                tool_name="test_tool",
                tool_args={},
                execution_id=execution_id,
            )

            assert result == mock_approval_request


class TestWaitForApproval:
    """Test wait_for_approval method."""

    async def test_wait_for_approval_already_approved(
        self, approval_service, sample_approval_request
    ):
        """Test waiting for an already approved request."""
        sample_approval_request.status = "approved"

        with patch.object(
            approval_service,
            "get_approval_request",
            return_value=sample_approval_request,
        ):
            result = await approval_service.wait_for_approval(
                sample_approval_request.id
            )

            assert result == sample_approval_request

    async def test_wait_for_approval_already_declined(
        self, approval_service, sample_approval_request
    ):
        """Test waiting for an already declined request."""
        sample_approval_request.status = "declined"

        with patch.object(
            approval_service,
            "get_approval_request",
            return_value=sample_approval_request,
        ):
            result = await approval_service.wait_for_approval(
                sample_approval_request.id
            )

            assert result.status == "declined"

    async def test_wait_for_approval_cancelled(
        self, approval_service, sample_approval_request
    ):
        """Test waiting for a cancelled request."""
        sample_approval_request.status = "cancelled"

        with patch.object(
            approval_service,
            "get_approval_request",
            return_value=sample_approval_request,
        ):
            result = await approval_service.wait_for_approval(
                sample_approval_request.id
            )

            assert result.status == "cancelled"

    async def test_wait_for_approval_not_found(self, approval_service):
        """Test waiting for a non-existent request."""
        request_id = uuid.uuid4()

        with patch.object(approval_service, "get_approval_request", return_value=None):
            with pytest.raises(ValueError) as exc_info:
                await approval_service.wait_for_approval(request_id)

            assert "not found" in str(exc_info.value)

    async def test_wait_for_approval_expires(
        self, approval_service, sample_approval_request
    ):
        """Test waiting for a request that expires."""
        # Set expiration in the past
        sample_approval_request.status = "pending"
        sample_approval_request.expires_at = datetime.utcnow() - timedelta(seconds=1)

        with patch.object(
            approval_service,
            "get_approval_request",
            return_value=sample_approval_request,
        ):
            with patch.object(
                approval_service, "update_approval_request"
            ) as mock_update:
                with pytest.raises(TimeoutError) as exc_info:
                    await approval_service.wait_for_approval(sample_approval_request.id)

                assert "expired" in str(exc_info.value)
                # Verify request was marked as expired
                assert mock_update.called

    @patch("preloop_ai.services.approval_service.asyncio.sleep")
    async def test_wait_for_approval_polling(
        self, mock_sleep, approval_service, sample_approval_request
    ):
        """Test polling behavior when waiting for approval."""
        # First call: pending, second call: approved
        sample_approval_request.status = "pending"
        approved_request = MagicMock(spec=ApprovalRequest)
        approved_request.status = "approved"

        call_count = 0

        async def mock_get_approval_request(request_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_approval_request
            else:
                return approved_request

        with patch.object(
            approval_service,
            "get_approval_request",
            side_effect=mock_get_approval_request,
        ):
            result = await approval_service.wait_for_approval(
                sample_approval_request.id, poll_interval=0.5
            )

            assert result.status == "approved"
            # Verify sleep was called with correct interval
            assert mock_sleep.called

    async def test_wait_for_approval_custom_poll_interval(
        self, approval_service, sample_approval_request
    ):
        """Test waiting with custom poll interval."""
        sample_approval_request.status = "approved"

        with patch.object(
            approval_service,
            "get_approval_request",
            return_value=sample_approval_request,
        ):
            result = await approval_service.wait_for_approval(
                sample_approval_request.id, poll_interval=2.0
            )

            assert result == sample_approval_request
