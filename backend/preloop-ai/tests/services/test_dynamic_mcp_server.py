"""Tests for DynamicMCPServer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


from preloop_ai.services.dynamic_mcp_server import (
    UserContext,
    DynamicMCPServer,
    get_dynamic_mcp_server,
    has_tracker,
    register_default_tools,
    initialize_dynamic_mcp_server,
)

pytestmark = pytest.mark.asyncio


class TestUserContext:
    """Test UserContext class."""

    def test_init_with_defaults(self):
        """Test UserContext initialization with default values."""
        ctx = UserContext(
            user_id="user-1",
            account_id="account-1",
            username="testuser",
        )

        assert ctx.user_id == "user-1"
        assert ctx.account_id == "account-1"
        assert ctx.username == "testuser"
        assert ctx.has_tracker is False
        assert ctx.enabled_default_tools == []
        assert ctx.enabled_proxied_tools == []

    def test_init_with_all_params(self):
        """Test UserContext initialization with all parameters."""
        ctx = UserContext(
            user_id="user-1",
            account_id="account-1",
            username="testuser",
            has_tracker=True,
            enabled_default_tools=["tool1", "tool2"],
            enabled_proxied_tools=["proxy1"],
        )

        assert ctx.has_tracker is True
        assert ctx.enabled_default_tools == ["tool1", "tool2"]
        assert ctx.enabled_proxied_tools == ["proxy1"]


class TestDynamicMCPServerInit:
    """Test DynamicMCPServer initialization."""

    def test_init_creates_server(self):
        """Test that initialization creates server and registries."""
        server = DynamicMCPServer()

        assert server.server is not None
        assert server._default_tools_registry == {}
        assert server._proxied_tools_registry == {}
        assert server._tool_handlers == {}

    def test_register_default_tool(self):
        """Test registering a default tool."""
        server = DynamicMCPServer()

        async def mock_handler(**kwargs):
            return "result"

        server.register_default_tool(
            name="test_tool",
            description="Test Tool",
            input_schema={"properties": {}},
            handler=mock_handler,
        )

        assert "test_tool" in server._default_tools_registry
        assert "test_tool" in server._tool_handlers
        assert server._tool_handlers["test_tool"] == mock_handler

    def test_register_proxied_tool(self):
        """Test registering a proxied tool."""
        server = DynamicMCPServer()

        async def mock_handler(**kwargs):
            return "result"

        server.register_proxied_tool(
            name="proxied_tool",
            description="Proxied Tool",
            input_schema={"properties": {}},
            handler=mock_handler,
        )

        assert "proxied_tool" in server._proxied_tools_registry
        assert "proxied_tool" in server._tool_handlers

    def test_get_registered_tool_names(self):
        """Test getting registered tool names."""
        server = DynamicMCPServer()

        async def handler(**kwargs):
            return "result"

        server.register_default_tool("default1", "Desc", {}, handler)
        server.register_proxied_tool("proxied1", "Desc", {}, handler)

        names = server.get_registered_tool_names()

        assert names["default"] == ["default1"]
        assert names["proxied"] == ["proxied1"]


class TestGetToolsForUser:
    """Test _get_tools_for_user method."""

    def test_user_without_tracker_gets_no_default_tools(self):
        """Test that user without tracker gets no default tools."""
        server = DynamicMCPServer()

        async def handler(**kwargs):
            return "result"

        server.register_default_tool("tool1", "Tool 1", {}, handler)

        user_context = UserContext(
            user_id="1",
            account_id="1",
            username="test",
            has_tracker=False,
        )

        tools = server._get_tools_for_user(user_context)

        assert len(tools) == 0

    def test_user_with_tracker_gets_all_default_tools(self):
        """Test that user with tracker gets all default tools."""
        server = DynamicMCPServer()

        async def handler(**kwargs):
            return "result"

        server.register_default_tool("tool1", "Tool 1", {}, handler)
        server.register_default_tool("tool2", "Tool 2", {}, handler)

        user_context = UserContext(
            user_id="1",
            account_id="1",
            username="test",
            has_tracker=True,
        )

        tools = server._get_tools_for_user(user_context)

        assert len(tools) == 2
        assert any(t.name == "tool1" for t in tools)
        assert any(t.name == "tool2" for t in tools)

    def test_user_with_enabled_tools_list(self):
        """Test filtering tools by enabled_default_tools list."""
        server = DynamicMCPServer()

        async def handler(**kwargs):
            return "result"

        server.register_default_tool("tool1", "Tool 1", {}, handler)
        server.register_default_tool("tool2", "Tool 2", {}, handler)

        user_context = UserContext(
            user_id="1",
            account_id="1",
            username="test",
            has_tracker=True,
            enabled_default_tools=["tool1"],  # Only tool1 enabled
        )

        tools = server._get_tools_for_user(user_context)

        assert len(tools) == 1
        assert tools[0].name == "tool1"

    def test_proxied_tools_included(self):
        """Test that proxied tools are included in tool list."""
        server = DynamicMCPServer()

        async def handler(**kwargs):
            return "result"

        server.register_proxied_tool("proxied1", "Proxied 1", {}, handler)

        user_context = UserContext(
            user_id="1",
            account_id="1",
            username="test",
            has_tracker=False,
            enabled_proxied_tools=["proxied1"],
        )

        tools = server._get_tools_for_user(user_context)

        assert len(tools) == 1
        assert tools[0].name == "proxied1"


class TestExtractUserContext:
    """Test _extract_user_context method."""

    def test_extract_from_session_meta(self):
        """Test extracting user context from session.meta."""
        server = DynamicMCPServer()

        # Mock request context with session.meta
        request_context = MagicMock()
        request_context.session = MagicMock()
        request_context.session.meta = {
            "user_id": "user-1",
            "account_id": "account-1",
            "username": "testuser",
            "has_tracker": True,
        }

        ctx = server._extract_user_context(request_context)

        assert ctx is not None
        assert ctx.user_id == "user-1"
        assert ctx.account_id == "account-1"
        assert ctx.username == "testuser"
        assert ctx.has_tracker is True

    def test_extract_from_meta(self):
        """Test extracting user context from meta directly."""
        server = DynamicMCPServer()

        # Mock request context with meta (no session)
        request_context = MagicMock()
        del request_context.session  # Remove session attribute
        request_context.meta = {
            "user_id": "user-1",
            "account_id": "account-1",
            "username": "testuser",
            "has_tracker": False,
        }

        ctx = server._extract_user_context(request_context)

        assert ctx is not None
        assert ctx.user_id == "user-1"
        assert ctx.has_tracker is False

    def test_extract_no_meta(self):
        """Test extracting when no meta is available."""
        server = DynamicMCPServer()

        # Mock request context without meta
        request_context = MagicMock(spec=[])  # No attributes

        ctx = server._extract_user_context(request_context)

        assert ctx is None

    def test_extract_error_handling(self):
        """Test error handling in extraction."""
        server = DynamicMCPServer()

        # Mock request context where user_data.get() raises error
        request_context = MagicMock()
        request_context.session = MagicMock()
        mock_user_data = MagicMock()
        mock_user_data.get = MagicMock(side_effect=Exception("Error"))
        request_context.session.meta = mock_user_data

        ctx = server._extract_user_context(request_context)

        assert ctx is None


class TestCheckApprovalRequired:
    """Test _check_approval_required method."""

    async def test_no_config_returns_false(self):
        """Test that no config returns false."""
        server = DynamicMCPServer()
        user_context = UserContext("1", "1", "test", has_tracker=True)

        with patch("preloop_models.db.session.get_async_db_session") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=None)

            # Mock execute to return no config
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_db.execute = AsyncMock(return_value=mock_result)

            mock_get_db.return_value = mock_db

            result = await server._check_approval_required(user_context, "test_tool")

        assert result is False

    async def test_config_with_approval_returns_true(self):
        """Test that config with approval required returns true."""
        server = DynamicMCPServer()
        user_context = UserContext("1", "1", "test", has_tracker=True)

        mock_config = MagicMock()
        mock_config.approval_policy_id = (
            "some-policy-id"  # Tool requires approval if this is set
        )

        with patch("preloop_models.db.session.get_async_db_session") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=None)

            # Mock execute to return config
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_config)
            mock_db.execute = AsyncMock(return_value=mock_result)

            mock_get_db.return_value = mock_db

            result = await server._check_approval_required(user_context, "test_tool")

        assert result is True

    async def test_check_error_returns_false(self):
        """Test that errors default to false."""
        server = DynamicMCPServer()
        user_context = UserContext("1", "1", "test", has_tracker=True)

        with patch(
            "preloop_models.db.session.get_async_db_session",
            side_effect=Exception("DB Error"),
        ):
            result = await server._check_approval_required(user_context, "test_tool")

        assert result is False


class TestRequestAndWaitForApproval:
    """Test _request_and_wait_for_approval method."""

    async def test_approval_granted(self):
        """Test successful approval."""
        server = DynamicMCPServer()
        user_context = UserContext("1", "1", "test", has_tracker=True)

        mock_config = MagicMock()
        mock_config.id = str(uuid4())
        mock_config.approval_policy_id = str(uuid4())

        mock_policy = MagicMock()

        mock_approval_request = MagicMock()
        mock_approval_request.id = str(uuid4())
        mock_approval_request.status = "approved"

        with patch("preloop_models.db.session.get_async_db_session") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=None)

            # Mock execute to return config and policy
            mock_config_result = MagicMock()
            mock_config_result.scalar_one_or_none = MagicMock(return_value=mock_config)

            mock_policy_result = MagicMock()
            mock_policy_result.scalar_one_or_none = MagicMock(return_value=mock_policy)

            mock_db.execute = AsyncMock(
                side_effect=[mock_config_result, mock_policy_result]
            )

            mock_get_db.return_value = mock_db

            # Mock approval service
            with patch(
                "preloop_ai.services.approval_service.ApprovalService"
            ) as mock_approval_service:
                mock_service = AsyncMock()
                mock_service.create_and_notify = AsyncMock(
                    return_value=mock_approval_request
                )
                mock_service.wait_for_approval = AsyncMock(
                    return_value=mock_approval_request
                )
                mock_approval_service.return_value = mock_service

                # Should not raise
                await server._request_and_wait_for_approval(
                    user_context, "test_tool", {}
                )

    async def test_approval_declined_raises_permission_error(self):
        """Test that declined approval raises PermissionError."""
        server = DynamicMCPServer()
        user_context = UserContext("1", "1", "test", has_tracker=True)

        mock_config = MagicMock()
        mock_config.id = str(uuid4())
        mock_config.approval_policy_id = str(uuid4())

        mock_policy = MagicMock()

        mock_approval_request = MagicMock()
        mock_approval_request.id = str(uuid4())
        mock_approval_request.status = "declined"
        mock_approval_request.approver_comment = "Not safe"

        with patch("preloop_models.db.session.get_async_db_session") as mock_get_db:
            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=None)

            mock_config_result = MagicMock()
            mock_config_result.scalar_one_or_none = MagicMock(return_value=mock_config)

            mock_policy_result = MagicMock()
            mock_policy_result.scalar_one_or_none = MagicMock(return_value=mock_policy)

            mock_db.execute = AsyncMock(
                side_effect=[mock_config_result, mock_policy_result]
            )

            mock_get_db.return_value = mock_db

            with patch(
                "preloop_ai.services.approval_service.ApprovalService"
            ) as mock_approval_service:
                mock_service = AsyncMock()
                mock_service.create_and_notify = AsyncMock(
                    return_value=mock_approval_request
                )
                mock_service.wait_for_approval = AsyncMock(
                    return_value=mock_approval_request
                )
                mock_approval_service.return_value = mock_service

                with pytest.raises(PermissionError) as exc_info:
                    await server._request_and_wait_for_approval(
                        user_context, "test_tool", {}
                    )

                assert "declined" in str(exc_info.value).lower()


class TestHelperFunctions:
    """Test helper functions."""

    def test_has_tracker_with_trackers(self):
        """Test has_tracker returns True when account has trackers."""
        mock_account = MagicMock()
        mock_account.id = str(uuid4())

        mock_db = MagicMock()
        # Mock the query chain to return a tracker
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.first.return_value = MagicMock()  # Has tracker
        mock_db.query.return_value = mock_query

        result = has_tracker(mock_account, mock_db)

        assert result is True

    def test_has_tracker_without_trackers(self):
        """Test has_tracker returns False when no trackers."""
        mock_account = MagicMock()
        mock_account.id = str(uuid4())

        mock_db = MagicMock()
        # Mock the query chain to return None
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.first.return_value = None  # No trackers
        mock_db.query.return_value = mock_query

        result = has_tracker(mock_account, mock_db)

        assert result is False

    def test_get_dynamic_mcp_server_creates_singleton(self):
        """Test that get_dynamic_mcp_server creates singleton."""
        # Clear global if exists
        import preloop_ai.services.dynamic_mcp_server as module

        if "_dynamic_mcp_server" in dir(module):
            delattr(module, "_dynamic_mcp_server")

        server1 = get_dynamic_mcp_server()
        server2 = get_dynamic_mcp_server()

        assert server1 is server2

    def test_register_default_tools(self):
        """Test registering all default tools."""
        server = DynamicMCPServer()

        # Mock individual router functions at the module level
        with patch("preloop_ai.api.endpoints.mcp.get_issue", AsyncMock()):
            with patch("preloop_ai.api.endpoints.mcp.create_issue", AsyncMock()):
                with patch("preloop_ai.api.endpoints.mcp.update_issue", AsyncMock()):
                    with patch("preloop_ai.api.endpoints.mcp.search", AsyncMock()):
                        with patch(
                            "preloop_ai.api.endpoints.mcp.estimate_compliance",
                            AsyncMock(),
                        ):
                            with patch(
                                "preloop_ai.api.endpoints.mcp.improve_compliance",
                                AsyncMock(),
                            ):
                                register_default_tools(server)

        # Check that 6 tools were registered
        names = server.get_registered_tool_names()
        assert len(names["default"]) == 6
        assert "get_issue" in names["default"]
        assert "create_issue" in names["default"]
        assert "update_issue" in names["default"]
        assert "search" in names["default"]
        assert "estimate_compliance" in names["default"]
        assert "improve_compliance" in names["default"]

    def test_initialize_dynamic_mcp_server(self):
        """Test initializing dynamic MCP server."""
        # Mock individual router functions at the module level
        with patch("preloop_ai.api.endpoints.mcp.get_issue", AsyncMock()):
            with patch("preloop_ai.api.endpoints.mcp.create_issue", AsyncMock()):
                with patch("preloop_ai.api.endpoints.mcp.update_issue", AsyncMock()):
                    with patch("preloop_ai.api.endpoints.mcp.search", AsyncMock()):
                        with patch(
                            "preloop_ai.api.endpoints.mcp.estimate_compliance",
                            AsyncMock(),
                        ):
                            with patch(
                                "preloop_ai.api.endpoints.mcp.improve_compliance",
                                AsyncMock(),
                            ):
                                server = initialize_dynamic_mcp_server()

        assert server is not None
        names = server.get_registered_tool_names()
        assert len(names["default"]) == 6
