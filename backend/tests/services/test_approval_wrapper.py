"""Tests for approval wrapper service (MCP tool approval decorator)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from preloop.services.approval_wrapper import with_approval


pytestmark = pytest.mark.asyncio


def create_mock_db_session():
    """Create a mock async database session."""
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)
    return mock_db


@pytest.fixture
def mock_tool_func():
    """Create a mock async tool function."""

    async def tool_func(**kwargs):
        return "tool_result"

    return tool_func


@pytest.fixture
def mock_user_context():
    """Create mock user context."""
    ctx = MagicMock()
    ctx.account_id = uuid4()
    ctx.user_id = uuid4()
    ctx.execution_id = None
    return ctx


class TestWithApprovalNoUserContext:
    """Test when no user context is available."""

    async def test_no_user_context_returns_error(self, mock_tool_func):
        """When get_current_user_context returns None, return error message."""
        wrapped = with_approval(mock_tool_func)

        with patch(
            "preloop.services.dynamic_fastmcp_http.get_current_user_context",
            return_value=None,
        ):
            result = await wrapped()

        assert "Error" in result
        assert "user context" in result.lower()


class TestWithApprovalDenyAction:
    """Test when policy evaluates to deny."""

    async def test_deny_action_returns_denied_message(
        self, mock_tool_func, mock_user_context
    ):
        """When action is deny, return denial message without executing tool."""
        wrapped = with_approval(mock_tool_func)

        with (
            patch(
                "preloop.services.dynamic_fastmcp_http.get_current_user_context",
                return_value=mock_user_context,
            ),
            patch(
                "preloop.models.db.session.get_async_db_session",
            ) as mock_get_db,
            patch(
                "preloop.models.crud.tool_configuration.get_tool_config_by_name_and_source_async",
                new_callable=AsyncMock,
                return_value=MagicMock(id=uuid4()),
            ),
            patch(
                "preloop.services.policy_evaluator.evaluate_policy_async",
                new_callable=AsyncMock,
                return_value=("deny", None, "High-risk operation blocked"),
            ),
        ):
            mock_db = create_mock_db_session()
            mock_get_db.return_value = mock_db

            result = await wrapped(arg1="value")

        assert "denied" in result.lower()
        assert "High-risk operation blocked" in result


class TestWithApprovalAllowAction:
    """Test when policy evaluates to allow."""

    async def test_allow_action_executes_tool(self, mock_tool_func, mock_user_context):
        """When action is allow, execute tool and return result."""
        wrapped = with_approval(mock_tool_func)

        with (
            patch(
                "preloop.services.dynamic_fastmcp_http.get_current_user_context",
                return_value=mock_user_context,
            ),
            patch(
                "preloop.models.db.session.get_async_db_session",
            ) as mock_get_db,
            patch(
                "preloop.models.crud.tool_configuration.get_tool_config_by_name_and_source_async",
                new_callable=AsyncMock,
                return_value=MagicMock(id=uuid4()),
            ),
            patch(
                "preloop.services.policy_evaluator.evaluate_policy_async",
                new_callable=AsyncMock,
                return_value=("allow", None, "No rules matched"),
            ),
        ):
            mock_db = create_mock_db_session()
            mock_get_db.return_value = mock_db

            result = await wrapped(arg1="value")

        assert result == "tool_result"


class TestWithApprovalRequireApprovalNoWorkflow:
    """Test when require_approval but no workflow configured."""

    async def test_require_approval_no_workflow_returns_error(
        self, mock_tool_func, mock_user_context
    ):
        """When action is require_approval but no workflow, return error."""
        mock_config = MagicMock()
        mock_config.id = uuid4()
        mock_config.approval_workflow_id = None

        wrapped = with_approval(mock_tool_func)

        with (
            patch(
                "preloop.services.dynamic_fastmcp_http.get_current_user_context",
                return_value=mock_user_context,
            ),
            patch(
                "preloop.models.db.session.get_async_db_session",
            ) as mock_get_db,
            patch(
                "preloop.models.crud.tool_configuration.get_tool_config_by_name_and_source_async",
                new_callable=AsyncMock,
                return_value=mock_config,
            ),
            patch(
                "preloop.services.policy_evaluator.evaluate_policy_async",
                new_callable=AsyncMock,
                return_value=("require_approval", None, "Requires approval"),
            ),
        ):
            mock_db = create_mock_db_session()
            mock_get_db.return_value = mock_db

            result = await wrapped()

        assert "workflow" in result.lower()
        assert "configured" in result.lower()


class TestWithApprovalRequireApprovalWorkflowNotFound:
    """Test when require_approval but workflow not found."""

    async def test_workflow_not_found_returns_error(
        self, mock_tool_func, mock_user_context
    ):
        """When workflow lookup returns None, return error."""
        workflow_id = uuid4()
        mock_config = MagicMock()
        mock_config.id = uuid4()
        mock_config.approval_workflow_id = workflow_id

        wrapped = with_approval(mock_tool_func)

        with (
            patch(
                "preloop.services.dynamic_fastmcp_http.get_current_user_context",
                return_value=mock_user_context,
            ),
            patch(
                "preloop.models.db.session.get_async_db_session",
            ) as mock_get_db,
            patch(
                "preloop.models.crud.tool_configuration.get_tool_config_by_name_and_source_async",
                new_callable=AsyncMock,
                return_value=mock_config,
            ),
            patch(
                "preloop.services.policy_evaluator.evaluate_policy_async",
                new_callable=AsyncMock,
                return_value=("require_approval", workflow_id, "Requires approval"),
            ),
            patch(
                "preloop.models.crud.approval_workflow.get_approval_workflow_async",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            mock_db = create_mock_db_session()
            mock_get_db.return_value = mock_db

            result = await wrapped()

        assert "Error" in result
        assert "workflow" in result.lower()


class TestWithApprovalPolicyEvaluationError:
    """Test when policy evaluation raises an exception."""

    async def test_policy_error_blocks_execution(
        self, mock_tool_func, mock_user_context
    ):
        """When evaluate_policy_async raises, return block message."""
        wrapped = with_approval(mock_tool_func)

        with (
            patch(
                "preloop.services.dynamic_fastmcp_http.get_current_user_context",
                return_value=mock_user_context,
            ),
            patch(
                "preloop.models.db.session.get_async_db_session",
            ) as mock_get_db,
            patch(
                "preloop.models.crud.tool_configuration.get_tool_config_by_name_and_source_async",
                new_callable=AsyncMock,
                return_value=MagicMock(id=uuid4()),
            ),
            patch(
                "preloop.services.policy_evaluator.evaluate_policy_async",
                new_callable=AsyncMock,
                side_effect=Exception("DB connection failed"),
            ),
        ):
            mock_db = create_mock_db_session()
            mock_get_db.return_value = mock_db

            result = await wrapped()

        assert "blocked" in result.lower()
        assert "Error" in result


class TestWithApprovalNoConfig:
    """Test when no tool config exists (evaluate_policy returns allow)."""

    async def test_no_config_allows_execution(self, mock_tool_func, mock_user_context):
        """When get_tool_config returns None, evaluate_policy gets config_id=None."""
        wrapped = with_approval(mock_tool_func)

        with (
            patch(
                "preloop.services.dynamic_fastmcp_http.get_current_user_context",
                return_value=mock_user_context,
            ),
            patch(
                "preloop.models.db.session.get_async_db_session",
            ) as mock_get_db,
            patch(
                "preloop.models.crud.tool_configuration.get_tool_config_by_name_and_source_async",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "preloop.services.policy_evaluator.evaluate_policy_async",
                new_callable=AsyncMock,
                return_value=("allow", None, "No tool configuration found"),
            ),
        ):
            mock_db = create_mock_db_session()
            mock_get_db.return_value = mock_db

            result = await wrapped()

        assert result == "tool_result"
