"""Tests for approval service."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from preloop.models.models import ApprovalWorkflow, ApprovalRequest
from preloop.models.schemas.approval_request import ApprovalRequestUpdate

from preloop.services.approval_service import ApprovalService

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
def sample_approval_workflow():
    """Create sample approval workflow."""
    policy = MagicMock(spec=ApprovalWorkflow)
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
    request.approval_workflow_id = uuid.uuid4()
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

    def _setup_mock_db_for_create(self, mock_db, sample_approval_workflow):
        """Set up mock_db to handle the execute call for approval workflow lookup."""

        # Mock db.refresh to set created fields
        def mock_refresh(obj):
            obj.created_at = datetime.utcnow()
            obj.updated_at = datetime.utcnow()

        mock_db.refresh.side_effect = mock_refresh

        # Mock the execute call that queries ApprovalWorkflow
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_approval_workflow
        mock_db.execute.return_value = mock_result

    async def test_create_approval_request_success(
        self, approval_service, mock_db, sample_approval_workflow
    ):
        """Test creating a new approval request."""
        account_id = "test_account"
        tool_config_id = uuid.uuid4()

        self._setup_mock_db_for_create(mock_db, sample_approval_workflow)

        result = await approval_service.create_approval_request(
            account_id=account_id,
            tool_configuration_id=tool_config_id,
            approval_workflow_id=sample_approval_workflow.id,
            tool_name="create_issue",
            tool_args={"title": "Bug", "description": "Fix this"},
            agent_reasoning="Need to create an issue",
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

    async def test_create_approval_request_with_execution_id(
        self, approval_service, mock_db, sample_approval_workflow
    ):
        """Test creating approval request with execution ID."""
        execution_id = "exec_123"

        self._setup_mock_db_for_create(mock_db, sample_approval_workflow)

        result = await approval_service.create_approval_request(
            account_id="test_account",
            tool_configuration_id=uuid.uuid4(),
            approval_workflow_id=sample_approval_workflow.id,
            tool_name="delete_issue",
            tool_args={"issue_id": "123"},
            execution_id=execution_id,
        )

        assert mock_db.add.called

    async def test_create_approval_request_custom_timeout(
        self, approval_service, mock_db, sample_approval_workflow
    ):
        """Test creating approval request with custom timeout."""
        self._setup_mock_db_for_create(mock_db, sample_approval_workflow)

        result = await approval_service.create_approval_request(
            account_id="test_account",
            tool_configuration_id=uuid.uuid4(),
            approval_workflow_id=sample_approval_workflow.id,
            tool_name="test_tool",
            tool_args={},
            timeout_seconds=600,  # 10 minutes
        )

        assert mock_db.add.called

    async def test_create_approval_request_default_timeout(
        self, approval_service, mock_db, sample_approval_workflow
    ):
        """Test creating approval request with default timeout."""
        self._setup_mock_db_for_create(mock_db, sample_approval_workflow)

        result = await approval_service.create_approval_request(
            account_id="test_account",
            tool_configuration_id=uuid.uuid4(),
            approval_workflow_id=sample_approval_workflow.id,
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
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test approving a request."""
        request_id = sample_approval_request.id
        comment = "Approved for production use"

        # Set up the approval request with policy (quorum=1 by default)
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = []
        sample_approval_workflow.approvals_required = 1

        # Mock get_approval_request_for_update and update_approval_request
        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            with patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
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
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test approving a request without a comment."""
        request_id = sample_approval_request.id

        # Set up the approval request with policy
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = []
        sample_approval_workflow.approvals_required = 1

        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            with patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
                return_value=sample_approval_request,
            ):
                result = await approval_service.approve_request(request_id)

                assert result == sample_approval_request


class TestDeclineRequest:
    """Test decline_request method."""

    async def test_decline_request_success(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test declining a request."""
        request_id = sample_approval_request.id
        comment = "Security concerns"

        # Set up the approval request with policy
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = []
        sample_approval_workflow.approvals_required = 1

        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            with patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
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
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test declining a request without a comment."""
        request_id = sample_approval_request.id

        # Set up the approval request with policy
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = []
        sample_approval_workflow.approvals_required = 1

        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            with patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
                return_value=sample_approval_request,
            ):
                result = await approval_service.decline_request(request_id)

                assert result == sample_approval_request


class TestPostWebhookNotification:
    """Test post_webhook_notification method."""

    @patch("preloop.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_slack_success(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_workflow,
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
                sample_approval_request, sample_approval_workflow
            )

            assert result is True
            assert mock_client.post.called
            # Verify webhook was marked as posted
            assert mock_update.called

    @patch("preloop.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_mattermost_success(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_workflow,
    ):
        """Test posting webhook notification to Mattermost."""
        sample_approval_workflow.approval_type = "mattermost"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with patch.object(approval_service, "update_approval_request"):
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_workflow
            )

            assert result is True

    @patch("preloop.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_generic_success(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_workflow,
    ):
        """Test posting webhook notification to generic webhook."""
        sample_approval_workflow.approval_type = "webhook"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with patch.object(approval_service, "update_approval_request"):
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_workflow
            )

            assert result is True

    async def test_post_webhook_no_webhook_url(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test posting webhook when no webhook URL is configured."""
        sample_approval_workflow.approval_config = {}

        with patch.object(approval_service, "update_approval_request") as mock_update:
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_workflow
            )

            assert result is False
            # Verify error was recorded
            assert mock_update.called
            call_args = mock_update.call_args
            update = call_args[0][1]
            assert "webhook_error" in update.model_dump(exclude_unset=True)

    async def test_post_webhook_no_config(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test posting webhook when approval_config is None."""
        sample_approval_workflow.approval_config = None

        with patch.object(approval_service, "update_approval_request"):
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_workflow
            )

            assert result is False

    @patch("preloop.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_http_error(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_workflow,
    ):
        """Test posting webhook when HTTP error occurs."""
        # Mock httpx client to raise error
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection failed")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        with patch.object(approval_service, "update_approval_request") as mock_update:
            result = await approval_service.post_webhook_notification(
                sample_approval_request, sample_approval_workflow
            )

            assert result is False
            # Verify error was recorded
            assert mock_update.called
            call_args = mock_update.call_args
            update = call_args[0][1]
            assert "webhook_error" in update.model_dump(exclude_unset=True)

    @patch("preloop.services.approval_service.httpx.AsyncClient")
    async def test_post_webhook_with_agent_reasoning(
        self,
        mock_client_class,
        approval_service,
        sample_approval_request,
        sample_approval_workflow,
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
                sample_approval_request, sample_approval_workflow
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
        self, approval_service, mock_db, sample_approval_workflow
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
                approval_workflow=sample_approval_workflow,
                tool_name="create_issue",
                tool_args={"title": "Bug"},
                agent_reasoning="Need approval",
            )

            assert result == mock_approval_request
            assert mock_create.called
            # Verify webhook notification was sent (not scheduled as background task)
            assert mock_webhook.called

    async def test_create_and_notify_with_execution_id(
        self, approval_service, sample_approval_workflow
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
                approval_workflow=sample_approval_workflow,
                tool_name="test_tool",
                tool_args={},
                execution_id=execution_id,
            )

            assert result == mock_approval_request

    async def test_create_and_notify_stores_raw_tool_args_for_execution(
        self, approval_service, sample_approval_workflow
    ):
        """Tool args with sensitive keys must be stored raw for execution after approval.

        Redaction is applied only for logging/notifications, not for storage.
        See ARCHITECTURE.md Redaction Policy.
        """
        tool_args_with_secret = {
            "command": "deploy to production",
            "api_key": "sk-secret-123",
            "environment": "prod",
        }

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                AsyncMock(return_value=MagicMock(spec=ApprovalRequest)),
            ) as mock_create,
            patch.object(
                approval_service,
                "send_notifications",
                AsyncMock(return_value={}),
            ),
        ):
            sample_approval_workflow.approval_mode = "manual"
            await approval_service.create_and_notify(
                account_id="test_account",
                tool_configuration_id=uuid.uuid4(),
                approval_workflow=sample_approval_workflow,
                tool_name="bash",
                tool_args=tool_args_with_secret,
            )

            # create_approval_request must receive raw args (not redacted)
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["tool_args"]["api_key"] == "sk-secret-123"
            assert call_kwargs["tool_args"]["command"] == "deploy to production"


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

    @patch("preloop.services.approval_service.asyncio.sleep")
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


class TestQuorumVoteTracking:
    """Regression tests for quorum > 1 vote tracking."""

    async def test_approve_request_quorum_not_met_records_vote(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test that approval vote is recorded when quorum is not yet met."""
        request_id = sample_approval_request.id
        user_id = uuid.uuid4()

        # Set up quorum > 1
        sample_approval_workflow.approvals_required = 2
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = []
        sample_approval_request.status = "pending"

        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            with patch.object(
                approval_service,
                "_broadcast_approval_update",
                new_callable=AsyncMock,
            ) as mock_broadcast:
                result = await approval_service.approve_request(
                    request_id, "First approval", user_id=user_id
                )

                # Vote should be recorded but status still pending
                assert result.status == "pending"
                assert len(result.responses) == 1
                assert result.responses[0]["user_id"] == str(user_id)
                assert result.responses[0]["decision"] == "approved"

                # Should broadcast vote_received, not approved
                mock_broadcast.assert_called()
                call_args = mock_broadcast.call_args
                assert call_args[0][1] == "vote_received"

    async def test_approve_request_quorum_met_resolves(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test that request resolves when quorum is met."""
        request_id = sample_approval_request.id
        user_id_1 = uuid.uuid4()
        user_id_2 = uuid.uuid4()

        # Set up quorum = 2 with one existing vote
        sample_approval_workflow.approvals_required = 2
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = [
            {
                "user_id": str(user_id_1),
                "decision": "approved",
                "timestamp": "2026-01-01T00:00:00",
            }
        ]
        sample_approval_request.status = "pending"

        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            with patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
                return_value=sample_approval_request,
            ) as mock_update:
                with patch.object(
                    approval_service,
                    "_broadcast_approval_update",
                    new_callable=AsyncMock,
                ):
                    result = await approval_service.approve_request(
                        request_id, "Second approval", user_id=user_id_2
                    )

                    # Should call update_approval_request with approved status
                    assert mock_update.called
                    update_arg = mock_update.call_args[0][1]
                    assert update_arg.status == "approved"

    async def test_approve_request_duplicate_vote_rejected(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test that duplicate votes from same user are rejected."""
        request_id = sample_approval_request.id
        user_id = uuid.uuid4()

        # Set up with existing vote from same user
        sample_approval_workflow.approvals_required = 2
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = [
            {
                "user_id": str(user_id),
                "decision": "approved",
                "timestamp": "2026-01-01T00:00:00",
            }
        ]
        sample_approval_request.status = "pending"

        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            result = await approval_service.approve_request(
                request_id, "Duplicate vote", user_id=user_id
            )

            # Should return unchanged - no new vote added
            assert len(result.responses) == 1

    async def test_anonymous_vote_capped_at_one(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test that only one anonymous vote is allowed per request."""
        request_id = sample_approval_request.id

        # Set up with existing anonymous vote
        sample_approval_workflow.approvals_required = 3
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = [
            {
                "user_id": "anonymous",
                "decision": "approved",
                "timestamp": "2026-01-01T00:00:00",
            }
        ]
        sample_approval_request.status = "pending"

        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            # Try to add another anonymous vote (no user_id)
            result = await approval_service.approve_request(
                request_id, "Second anonymous vote", user_id=None
            )

            # Should return unchanged - duplicate anonymous vote rejected
            assert len(result.responses) == 1

    async def test_anonymous_cannot_vote_approve_and_decline(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test that anonymous user cannot vote both approve AND decline (double-vote attack)."""
        request_id = sample_approval_request.id

        # Set up with existing anonymous APPROVAL
        sample_approval_workflow.approvals_required = 2
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = [
            {
                "user_id": "anonymous",
                "decision": "approved",
                "timestamp": "2026-01-01T00:00:00",
            }
        ]
        sample_approval_request.status = "pending"

        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            # Try to add an anonymous DECLINE (should be rejected as double-vote)
            result = await approval_service.decline_request(
                request_id, "Anonymous decline after approval", user_id=None
            )

            # Should return unchanged - anonymous already voted
            assert len(result.responses) == 1
            assert result.responses[0]["decision"] == "approved"

    async def test_anonymous_cannot_vote_decline_and_approve(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test that anonymous user cannot vote decline then approve (reverse double-vote attack)."""
        request_id = sample_approval_request.id

        # Set up with existing anonymous DECLINE
        sample_approval_workflow.approvals_required = 2
        sample_approval_request.approval_workflow = sample_approval_workflow
        sample_approval_request.responses = [
            {
                "user_id": "anonymous",
                "decision": "declined",
                "timestamp": "2026-01-01T00:00:00",
            }
        ]
        sample_approval_request.status = "pending"

        with patch.object(
            approval_service,
            "get_approval_request_for_update",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            # Try to add an anonymous APPROVAL (should be rejected as double-vote)
            result = await approval_service.approve_request(
                request_id, "Anonymous approval after decline", user_id=None
            )

            # Should return unchanged - anonymous already voted
            assert len(result.responses) == 1
            assert result.responses[0]["decision"] == "declined"


class TestEscalationBehavior:
    """Regression tests for escalation timeout behavior."""

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_wait_for_approval_triggers_escalation(
        self,
        mock_sleep,
        approval_service,
        sample_approval_request,
        sample_approval_workflow,
    ):
        """Test that escalation is triggered when timeout expires with escalation configured."""
        # Set up expired request with escalation configured
        sample_approval_request.status = "pending"
        sample_approval_request.expires_at = datetime.utcnow() - timedelta(seconds=10)
        sample_approval_request.escalation_triggered_at = None
        sample_approval_workflow.escalation_user_ids = [uuid.uuid4()]
        sample_approval_workflow.timeout_seconds = 60
        sample_approval_request.approval_workflow = sample_approval_workflow

        call_count = 0

        async def mock_get_request(request_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: expired, escalation not triggered
                return sample_approval_request
            else:
                # After escalation: return approved
                approved = MagicMock(spec=ApprovalRequest)
                approved.status = "approved"
                return approved

        with patch.object(
            approval_service,
            "get_approval_request",
            side_effect=mock_get_request,
        ):
            with patch.object(
                approval_service,
                "_send_escalation_notifications",
                new_callable=AsyncMock,
                return_value={"success": True},
            ) as mock_escalation:
                with patch.object(
                    approval_service,
                    "_broadcast_approval_update",
                    new_callable=AsyncMock,
                ):
                    result = await approval_service.wait_for_approval(
                        sample_approval_request.id, poll_interval=0.1
                    )

                    # Escalation should have been triggered
                    assert mock_escalation.called
                    assert result.status == "approved"

    async def test_wait_for_approval_no_escalation_when_already_triggered(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test that escalation is not triggered twice."""
        # Set up expired request with escalation already triggered
        sample_approval_request.status = "pending"
        sample_approval_request.expires_at = datetime.utcnow() - timedelta(seconds=10)
        sample_approval_request.escalation_triggered_at = datetime.utcnow() - timedelta(
            seconds=5
        )
        sample_approval_workflow.escalation_user_ids = [uuid.uuid4()]
        sample_approval_request.approval_workflow = sample_approval_workflow

        with patch.object(
            approval_service,
            "get_approval_request",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            with patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
                return_value=sample_approval_request,
            ):
                with patch.object(
                    approval_service,
                    "_send_escalation_notifications",
                    new_callable=AsyncMock,
                ) as mock_escalation:
                    with patch.object(
                        approval_service,
                        "_broadcast_approval_update",
                        new_callable=AsyncMock,
                    ):
                        with pytest.raises(TimeoutError):
                            await approval_service.wait_for_approval(
                                sample_approval_request.id, poll_interval=0.1
                            )

                        # Escalation should NOT have been called again
                        assert not mock_escalation.called

    async def test_wait_for_approval_expires_without_escalation(
        self, approval_service, sample_approval_request, sample_approval_workflow
    ):
        """Test that request expires normally when no escalation configured."""
        sample_approval_request.status = "pending"
        sample_approval_request.expires_at = datetime.utcnow() - timedelta(seconds=10)
        sample_approval_request.escalation_triggered_at = None
        sample_approval_workflow.escalation_user_ids = None
        sample_approval_workflow.escalation_team_ids = None
        sample_approval_request.approval_workflow = sample_approval_workflow

        with patch.object(
            approval_service,
            "get_approval_request",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ):
            with patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
                return_value=sample_approval_request,
            ):
                with patch.object(
                    approval_service,
                    "_broadcast_approval_update",
                    new_callable=AsyncMock,
                ):
                    with pytest.raises(TimeoutError) as exc_info:
                        await approval_service.wait_for_approval(
                            sample_approval_request.id, poll_interval=0.1
                        )

                    assert "expired without response" in str(exc_info.value)


class TestAutoApproveRequest:
    """Test _auto_approve_request method."""

    async def test_auto_approve_sets_status_and_ai_fields(
        self, approval_service, sample_approval_request
    ):
        """Test that _auto_approve_request sets correct fields."""
        request_id = sample_approval_request.id

        with patch.object(
            approval_service,
            "update_approval_request",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ) as mock_update:
            with patch.object(
                approval_service,
                "_broadcast_approval_update",
                new_callable=AsyncMock,
            ) as mock_broadcast:
                result = await approval_service._auto_approve_request(
                    request_id=request_id,
                    reason="Safe tool call",
                    decided_by_ai=True,
                    ai_model="gpt-4o-mini",
                    ai_confidence=0.95,
                )

                assert result == sample_approval_request
                mock_update.assert_called_once()
                update_arg = mock_update.call_args[0][1]
                assert update_arg.status == "approved"
                assert update_arg.decided_by_ai is True
                assert update_arg.ai_model == "gpt-4o-mini"
                assert update_arg.ai_confidence == 0.95
                assert update_arg.ai_reasoning == "Safe tool call"
                mock_broadcast.assert_called_once_with(
                    sample_approval_request, "approved"
                )

    async def test_auto_approve_returns_none_when_not_found(self, approval_service):
        """Test that _auto_approve_request returns None if request not found."""
        with patch.object(
            approval_service,
            "update_approval_request",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await approval_service._auto_approve_request(
                request_id=uuid.uuid4(),
                reason="Reason",
            )
            assert result is None


class TestAutoDenyRequest:
    """Test _auto_deny_request method."""

    async def test_auto_deny_sets_status_and_ai_fields(
        self, approval_service, sample_approval_request
    ):
        """Test that _auto_deny_request sets correct fields."""
        request_id = sample_approval_request.id

        with patch.object(
            approval_service,
            "update_approval_request",
            new_callable=AsyncMock,
            return_value=sample_approval_request,
        ) as mock_update:
            with patch.object(
                approval_service,
                "_broadcast_approval_update",
                new_callable=AsyncMock,
            ) as mock_broadcast:
                result = await approval_service._auto_deny_request(
                    request_id=request_id,
                    reason="Dangerous operation",
                    decided_by_ai=True,
                    ai_model="gpt-4o-mini",
                    ai_confidence=0.92,
                )

                assert result == sample_approval_request
                mock_update.assert_called_once()
                update_arg = mock_update.call_args[0][1]
                assert update_arg.status == "declined"
                assert update_arg.decided_by_ai is True
                assert update_arg.ai_model == "gpt-4o-mini"
                assert update_arg.ai_confidence == 0.92
                assert update_arg.ai_reasoning == "Dangerous operation"
                mock_broadcast.assert_called_once_with(
                    sample_approval_request, "declined"
                )

    async def test_auto_deny_returns_none_when_not_found(self, approval_service):
        """Test that _auto_deny_request returns None if request not found."""
        with patch.object(
            approval_service,
            "update_approval_request",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await approval_service._auto_deny_request(
                request_id=uuid.uuid4(),
                reason="Reason",
            )
            assert result is None


class TestAIDrivenApprovalFlow:
    """Test AI-driven approval flow in create_and_notify."""

    @pytest.fixture
    def ai_driven_policy(self):
        """Create an AI-driven approval workflow."""
        policy = MagicMock(spec=ApprovalWorkflow)
        policy.id = uuid.uuid4()
        policy.name = "AI Review Policy"
        policy.approval_mode = "ai_driven"
        policy.approval_type = "slack"
        policy.timeout_seconds = 300
        policy.ai_confidence_threshold = 0.8
        policy.ai_fallback_behavior = "escalate"
        policy.escalation_workflow_id = None
        policy.notification_channels = ["slack"]
        policy.approval_config = {"webhook_url": "https://hooks.slack.com/test"}
        return policy

    def _mock_ai_result(
        self, decision="approve", confidence=0.95, reasoning="Looks safe"
    ):
        """Helper to create a mock AIApprovalResult."""
        result = MagicMock()
        result.decision = decision
        result.confidence = confidence
        result.reasoning = reasoning
        result.model_used = "gpt-4o-mini"
        return result

    async def test_high_confidence_approve(
        self, approval_service, mock_db, ai_driven_policy
    ):
        """Test AI auto-approves when confidence >= threshold and decision is approve."""
        mock_request = MagicMock(spec=ApprovalRequest)
        mock_request.id = uuid.uuid4()
        approved_request = MagicMock(spec=ApprovalRequest)
        approved_request.status = "approved"

        ai_result = self._mock_ai_result(decision="approve", confidence=0.95)

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                new_callable=AsyncMock,
                return_value=mock_request,
            ),
            patch(
                "preloop.services.approval_service.get_ai_approval_service"
            ) as mock_get_ai,
            patch.object(
                approval_service,
                "_auto_approve_request",
                new_callable=AsyncMock,
                return_value=approved_request,
            ) as mock_auto_approve,
        ):
            mock_ai_svc = AsyncMock()
            mock_ai_svc.evaluate.return_value = ai_result
            mock_get_ai.return_value = mock_ai_svc

            result = await approval_service.create_and_notify(
                account_id="acct-1",
                tool_configuration_id=uuid.uuid4(),
                approval_workflow=ai_driven_policy,
                tool_name="get_issue",
                tool_args={"issue_id": "123"},
            )

            assert result == approved_request
            mock_auto_approve.assert_called_once_with(
                request_id=mock_request.id,
                reason=ai_result.reasoning,
                decided_by_ai=True,
                ai_model=ai_result.model_used,
                ai_confidence=ai_result.confidence,
            )

    async def test_high_confidence_deny(
        self, approval_service, mock_db, ai_driven_policy
    ):
        """Test AI auto-denies when confidence >= threshold and decision is deny."""
        mock_request = MagicMock(spec=ApprovalRequest)
        mock_request.id = uuid.uuid4()
        denied_request = MagicMock(spec=ApprovalRequest)
        denied_request.status = "declined"

        ai_result = self._mock_ai_result(decision="deny", confidence=0.90)

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                new_callable=AsyncMock,
                return_value=mock_request,
            ),
            patch(
                "preloop.services.approval_service.get_ai_approval_service"
            ) as mock_get_ai,
            patch.object(
                approval_service,
                "_auto_deny_request",
                new_callable=AsyncMock,
                return_value=denied_request,
            ) as mock_auto_deny,
        ):
            mock_ai_svc = AsyncMock()
            mock_ai_svc.evaluate.return_value = ai_result
            mock_get_ai.return_value = mock_ai_svc

            result = await approval_service.create_and_notify(
                account_id="acct-1",
                tool_configuration_id=uuid.uuid4(),
                approval_workflow=ai_driven_policy,
                tool_name="shell_exec",
                tool_args={"command": "rm -rf /"},
            )

            assert result == denied_request
            mock_auto_deny.assert_called_once_with(
                request_id=mock_request.id,
                reason=ai_result.reasoning,
                decided_by_ai=True,
                ai_model=ai_result.model_used,
                ai_confidence=ai_result.confidence,
            )

    async def test_low_confidence_fallback_approve(
        self, approval_service, mock_db, ai_driven_policy
    ):
        """Test fallback behavior 'approve' when AI confidence is below threshold."""
        ai_driven_policy.ai_fallback_behavior = "approve"

        mock_request = MagicMock(spec=ApprovalRequest)
        mock_request.id = uuid.uuid4()
        approved_request = MagicMock(spec=ApprovalRequest)

        ai_result = self._mock_ai_result(
            decision="approve", confidence=0.5, reasoning="Not sure"
        )

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                new_callable=AsyncMock,
                return_value=mock_request,
            ),
            patch(
                "preloop.services.approval_service.get_ai_approval_service"
            ) as mock_get_ai,
            patch.object(
                approval_service,
                "_auto_approve_request",
                new_callable=AsyncMock,
                return_value=approved_request,
            ) as mock_auto_approve,
        ):
            mock_ai_svc = AsyncMock()
            mock_ai_svc.evaluate.return_value = ai_result
            mock_get_ai.return_value = mock_ai_svc

            result = await approval_service.create_and_notify(
                account_id="acct-1",
                tool_configuration_id=uuid.uuid4(),
                approval_workflow=ai_driven_policy,
                tool_name="test_tool",
                tool_args={},
            )

            assert result == approved_request
            call_kwargs = mock_auto_approve.call_args[1]
            assert "Fallback approval" in call_kwargs["reason"]

    async def test_low_confidence_fallback_deny(
        self, approval_service, mock_db, ai_driven_policy
    ):
        """Test fallback behavior 'deny' when AI confidence is below threshold."""
        ai_driven_policy.ai_fallback_behavior = "deny"

        mock_request = MagicMock(spec=ApprovalRequest)
        mock_request.id = uuid.uuid4()
        denied_request = MagicMock(spec=ApprovalRequest)

        ai_result = self._mock_ai_result(
            decision="uncertain", confidence=0.3, reasoning="Too ambiguous"
        )

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                new_callable=AsyncMock,
                return_value=mock_request,
            ),
            patch(
                "preloop.services.approval_service.get_ai_approval_service"
            ) as mock_get_ai,
            patch.object(
                approval_service,
                "_auto_deny_request",
                new_callable=AsyncMock,
                return_value=denied_request,
            ) as mock_auto_deny,
        ):
            mock_ai_svc = AsyncMock()
            mock_ai_svc.evaluate.return_value = ai_result
            mock_get_ai.return_value = mock_ai_svc

            result = await approval_service.create_and_notify(
                account_id="acct-1",
                tool_configuration_id=uuid.uuid4(),
                approval_workflow=ai_driven_policy,
                tool_name="test_tool",
                tool_args={},
            )

            assert result == denied_request
            call_kwargs = mock_auto_deny.call_args[1]
            assert "Fallback denial" in call_kwargs["reason"]

    async def test_low_confidence_fallback_escalate(
        self, approval_service, mock_db, ai_driven_policy
    ):
        """Test fallback behavior 'escalate' (default) sends to human review."""
        ai_driven_policy.ai_fallback_behavior = "escalate"
        ai_driven_policy.escalation_workflow_id = None

        mock_request = MagicMock(spec=ApprovalRequest)
        mock_request.id = uuid.uuid4()
        refreshed_request = MagicMock(spec=ApprovalRequest)

        ai_result = self._mock_ai_result(
            decision="uncertain", confidence=0.4, reasoning="Edge case"
        )

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                new_callable=AsyncMock,
                return_value=mock_request,
            ),
            patch(
                "preloop.services.approval_service.get_ai_approval_service"
            ) as mock_get_ai,
            patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
            ) as mock_update,
            patch.object(
                approval_service,
                "get_approval_request",
                new_callable=AsyncMock,
                return_value=refreshed_request,
            ),
            patch.object(
                approval_service,
                "send_notifications",
                new_callable=AsyncMock,
                return_value={"email": {"success": True}},
            ) as mock_notify,
        ):
            mock_ai_svc = AsyncMock()
            mock_ai_svc.evaluate.return_value = ai_result
            mock_get_ai.return_value = mock_ai_svc

            result = await approval_service.create_and_notify(
                account_id="acct-1",
                tool_configuration_id=uuid.uuid4(),
                approval_workflow=ai_driven_policy,
                tool_name="test_tool",
                tool_args={},
            )

            assert result == refreshed_request
            # Should update request with AI info
            mock_update.assert_called()
            update_arg = mock_update.call_args[0][1]
            assert update_arg.ai_model == "gpt-4o-mini"
            assert update_arg.ai_confidence == 0.4
            assert "Escalated to human review" in update_arg.ai_reasoning
            # Should send human notifications using original policy
            mock_notify.assert_called_once_with(refreshed_request, ai_driven_policy)

    async def test_escalation_with_escalation_workflow(
        self, approval_service, mock_db, ai_driven_policy
    ):
        """Test that escalation uses the escalation_workflow for notifications when set."""
        escalation_workflow_id = uuid.uuid4()
        ai_driven_policy.ai_fallback_behavior = "escalate"
        ai_driven_policy.escalation_workflow_id = escalation_workflow_id

        mock_request = MagicMock(spec=ApprovalRequest)
        mock_request.id = uuid.uuid4()
        refreshed_request = MagicMock(spec=ApprovalRequest)

        escalation_workflow = MagicMock(spec=ApprovalWorkflow)
        escalation_workflow.id = escalation_workflow_id
        escalation_workflow.name = "Human Escalation Policy"

        ai_result = self._mock_ai_result(
            decision="uncertain", confidence=0.3, reasoning="Needs human"
        )

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                new_callable=AsyncMock,
                return_value=mock_request,
            ),
            patch(
                "preloop.services.approval_service.get_ai_approval_service"
            ) as mock_get_ai,
            patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
            ),
            patch.object(
                approval_service,
                "get_approval_request",
                new_callable=AsyncMock,
                return_value=refreshed_request,
            ),
            patch.object(
                approval_service,
                "send_notifications",
                new_callable=AsyncMock,
                return_value={"email": {"success": True}},
            ) as mock_notify,
            patch(
                "preloop.models.crud.approval_workflow.get_approval_workflow_async",
                new_callable=AsyncMock,
                return_value=escalation_workflow,
            ),
        ):
            mock_ai_svc = AsyncMock()
            mock_ai_svc.evaluate.return_value = ai_result
            mock_get_ai.return_value = mock_ai_svc

            result = await approval_service.create_and_notify(
                account_id="acct-1",
                tool_configuration_id=uuid.uuid4(),
                approval_workflow=ai_driven_policy,
                tool_name="test_tool",
                tool_args={},
            )

            assert result == refreshed_request
            # Should send notifications using the escalation policy, not original
            mock_notify.assert_called_once_with(refreshed_request, escalation_workflow)

    async def test_escalation_workflow_not_found_falls_back(
        self, approval_service, mock_db, ai_driven_policy
    ):
        """Test that missing escalation policy falls back to original policy."""
        ai_driven_policy.ai_fallback_behavior = "escalate"
        ai_driven_policy.escalation_workflow_id = uuid.uuid4()

        mock_request = MagicMock(spec=ApprovalRequest)
        mock_request.id = uuid.uuid4()
        refreshed_request = MagicMock(spec=ApprovalRequest)

        ai_result = self._mock_ai_result(
            decision="uncertain", confidence=0.3, reasoning="Needs human"
        )

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                new_callable=AsyncMock,
                return_value=mock_request,
            ),
            patch(
                "preloop.services.approval_service.get_ai_approval_service"
            ) as mock_get_ai,
            patch.object(
                approval_service,
                "update_approval_request",
                new_callable=AsyncMock,
            ),
            patch.object(
                approval_service,
                "get_approval_request",
                new_callable=AsyncMock,
                return_value=refreshed_request,
            ),
            patch.object(
                approval_service,
                "send_notifications",
                new_callable=AsyncMock,
                return_value={},
            ) as mock_notify,
            patch(
                "preloop.models.crud.approval_workflow.get_approval_workflow_async",
                new_callable=AsyncMock,
                return_value=None,  # Escalation policy not found
            ),
        ):
            mock_ai_svc = AsyncMock()
            mock_ai_svc.evaluate.return_value = ai_result
            mock_get_ai.return_value = mock_ai_svc

            result = await approval_service.create_and_notify(
                account_id="acct-1",
                tool_configuration_id=uuid.uuid4(),
                approval_workflow=ai_driven_policy,
                tool_name="test_tool",
                tool_args={},
            )

            assert result == refreshed_request
            # Should fall back to original policy for notifications
            mock_notify.assert_called_once_with(refreshed_request, ai_driven_policy)

    async def test_standard_mode_skips_ai_evaluation(
        self, approval_service, mock_db, ai_driven_policy
    ):
        """Test that standard (non-AI) policies skip AI evaluation entirely."""
        ai_driven_policy.approval_mode = "standard"

        mock_request = MagicMock(spec=ApprovalRequest)
        mock_request.id = uuid.uuid4()

        with (
            patch.object(
                approval_service,
                "create_approval_request",
                new_callable=AsyncMock,
                return_value=mock_request,
            ),
            patch(
                "preloop.services.approval_service.get_ai_approval_service"
            ) as mock_get_ai,
            patch.object(
                approval_service,
                "send_notifications",
                new_callable=AsyncMock,
                return_value={},
            ) as mock_notify,
        ):
            result = await approval_service.create_and_notify(
                account_id="acct-1",
                tool_configuration_id=uuid.uuid4(),
                approval_workflow=ai_driven_policy,
                tool_name="test_tool",
                tool_args={},
            )

            assert result == mock_request
            mock_get_ai.assert_not_called()
            mock_notify.assert_called_once_with(mock_request, ai_driven_policy)
