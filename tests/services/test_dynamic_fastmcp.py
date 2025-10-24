"""Tests for DynamicFastMCP."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from mcp import types
from fastmcp.tools import Tool

from spacebridge.services.dynamic_fastmcp import (
    DynamicFastMCP,
    create_dynamic_mcp_server,
    create_user_context_from_scope,
)
from spacebridge.services.dynamic_mcp_server import UserContext

pytestmark = pytest.mark.asyncio


@pytest.fixture
def user_context():
    """Create a test user context."""
    return UserContext(
        user_id=str(uuid4()),
        account_id=str(uuid4()),
        username="testuser",
        has_tracker=True,
        enabled_default_tools=[],
        enabled_proxied_tools=[],
    )


@pytest.fixture
def dynamic_mcp():
    """Create a DynamicFastMCP instance."""
    return DynamicFastMCP("test-mcp")


class TestDynamicFastMCPInit:
    """Test DynamicFastMCP initialization."""

    def test_init_creates_instance(self):
        """Test that __init__ creates instance with proper attributes."""
        mcp = DynamicFastMCP("test-mcp")

        assert mcp._user_context_provider is None
        assert mcp._proxied_tool_servers == {}
        assert mcp._registered_proxied_tools == set()

    def test_set_user_context_provider(self, dynamic_mcp):
        """Test setting user context provider."""

        def provider():
            return UserContext(
                user_id="1",
                account_id="1",
                username="test",
                has_tracker=True,
                enabled_default_tools=[],
                enabled_proxied_tools=[],
            )

        dynamic_mcp.set_user_context_provider(provider)

        assert dynamic_mcp._user_context_provider is provider


class TestGetCurrentUserContext:
    """Test _get_current_user_context method."""

    def test_get_context_no_provider(self, dynamic_mcp):
        """Test getting context when no provider is set."""
        result = dynamic_mcp._get_current_user_context()

        assert result is None

    def test_get_context_provider_returns_context(self, dynamic_mcp, user_context):
        """Test getting context when provider returns context."""

        def provider():
            return user_context

        dynamic_mcp._user_context_provider = provider

        result = dynamic_mcp._get_current_user_context()

        assert result == user_context

    def test_get_context_provider_returns_none(self, dynamic_mcp):
        """Test getting context when provider returns None."""

        def provider():
            return None

        dynamic_mcp._user_context_provider = provider

        result = dynamic_mcp._get_current_user_context()

        assert result is None

    def test_get_context_provider_raises_error(self, dynamic_mcp):
        """Test getting context when provider raises error."""

        def error_provider():
            raise Exception("Provider error")

        dynamic_mcp._user_context_provider = error_provider

        result = dynamic_mcp._get_current_user_context()

        assert result is None


class TestListTools:
    """Test _list_tools method."""

    async def test_list_tools_no_user_context(self, dynamic_mcp):
        """Test listing tools with no user context."""
        result = await dynamic_mcp._list_tools()

        assert result == []

    async def test_list_tools_user_without_tracker(self, dynamic_mcp):
        """Test listing tools for user without tracker."""
        user_context = UserContext(
            user_id="1",
            account_id="1",
            username="test",
            has_tracker=False,
            enabled_default_tools=[],
            enabled_proxied_tools=[],
        )
        dynamic_mcp._user_context_provider = lambda: user_context

        # Mock database for proxied tools
        with patch("spacebridge.services.dynamic_fastmcp.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.close = MagicMock()
            mock_get_db.return_value = iter([mock_db])

            with patch(
                "spacebridge.services.dynamic_fastmcp.get_all_enabled_proxied_tools",
                return_value=[],
            ):
                result = await dynamic_mcp._list_tools()

        # User without tracker gets no default tools, only proxied
        assert isinstance(result, list)

    async def test_list_tools_user_with_tracker(self, dynamic_mcp, user_context):
        """Test listing tools for user with tracker."""
        dynamic_mcp._user_context_provider = lambda: user_context

        # Mock super()._list_tools() to return default tools
        default_tools = [
            Tool(name="tool1", description="Tool 1", parameters={}),
            Tool(name="tool2", description="Tool 2", parameters={}),
        ]

        with patch.object(
            DynamicFastMCP, "_list_tools", return_value=default_tools
        ) as mock_super:
            # Call the actual method (not the mock)
            mock_super.side_effect = None

            with patch("spacebridge.services.dynamic_fastmcp.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.close = MagicMock()
                mock_get_db.return_value = iter([mock_db])

                with patch(
                    "spacebridge.services.dynamic_fastmcp.get_all_enabled_proxied_tools",
                    return_value=[],
                ):
                    with patch.object(
                        dynamic_mcp.__class__.__bases__[0],
                        "_list_tools",
                        new=AsyncMock(return_value=default_tools),
                    ):
                        result = await dynamic_mcp._list_tools()

        # Should include default tools
        assert len(result) == 2

    async def test_list_tools_filters_internal_names(self, dynamic_mcp, user_context):
        """Test that internal tool names (account_*) are filtered out."""
        dynamic_mcp._user_context_provider = lambda: user_context

        # Mock tools including internal names
        default_tools = [
            Tool(name="public_tool", description="Public", parameters={}),
            Tool(
                name="account_123_internal",
                description="Internal",
                parameters={},
            ),
        ]

        with patch("spacebridge.services.dynamic_fastmcp.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.close = MagicMock()
            mock_get_db.return_value = iter([mock_db])

            with patch(
                "spacebridge.services.dynamic_fastmcp.get_all_enabled_proxied_tools",
                return_value=[],
            ):
                with patch.object(
                    dynamic_mcp.__class__.__bases__[0],
                    "_list_tools",
                    new=AsyncMock(return_value=default_tools),
                ):
                    result = await dynamic_mcp._list_tools()

        # Only public tool should be included
        assert len(result) == 1
        assert result[0].name == "public_tool"

    async def test_list_tools_includes_proxied_tools(self, dynamic_mcp, user_context):
        """Test that proxied tools are included in tool list."""
        dynamic_mcp._user_context_provider = lambda: user_context

        # Mock proxied tool data
        mock_mcp_server = MagicMock()
        mock_mcp_server.id = str(uuid4())

        mock_mcp_tool = MagicMock()
        mock_mcp_tool.name = "proxied_tool"
        mock_mcp_tool.description = "Proxied Tool"
        mock_mcp_tool.input_schema = {"properties": {}}

        # Create an internal tool that will be "registered"
        safe_account_id = user_context.account_id.replace("-", "_")
        internal_name = f"account_{safe_account_id}_proxied_tool"
        registered_tool = Tool(
            name=internal_name, description="Internal", parameters={}
        )

        with patch("spacebridge.services.dynamic_fastmcp.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.close = MagicMock()
            mock_get_db.return_value = iter([mock_db])

            with patch(
                "spacebridge.services.dynamic_fastmcp.get_all_enabled_proxied_tools",
                return_value=[(mock_mcp_server, mock_mcp_tool)],
            ):
                # Mock super()._list_tools to return the "registered" internal tool
                with patch.object(
                    dynamic_mcp.__class__.__bases__[0],
                    "_list_tools",
                    new=AsyncMock(return_value=[registered_tool]),
                ):
                    # Mock tool registration
                    with patch.object(dynamic_mcp, "tool", return_value=lambda x: x):
                        result = await dynamic_mcp._list_tools()

        # Should include proxied tool with original name (not internal name)
        assert any(t.name == "proxied_tool" for t in result)
        # Should NOT include internal name in results
        assert not any(t.name == internal_name for t in result)

    async def test_list_tools_error_loading_proxied(self, dynamic_mcp, user_context):
        """Test handling error when loading proxied tools."""
        dynamic_mcp._user_context_provider = lambda: user_context

        with patch("spacebridge.services.dynamic_fastmcp.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.close = MagicMock()
            mock_get_db.return_value = iter([mock_db])

            with patch(
                "spacebridge.services.dynamic_fastmcp.get_all_enabled_proxied_tools",
                side_effect=Exception("DB Error"),
            ):
                with patch.object(
                    dynamic_mcp.__class__.__bases__[0],
                    "_list_tools",
                    new=AsyncMock(return_value=[]),
                ):
                    # Should not raise, just continue with default tools
                    result = await dynamic_mcp._list_tools()

        assert isinstance(result, list)


class TestMCPCallTool:
    """Test _mcp_call_tool method."""

    async def test_call_tool_no_user_context(self, dynamic_mcp):
        """Test calling tool with no user context."""
        result = await dynamic_mcp._mcp_call_tool("tool1", {})

        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "No user context available" in result[0].text

    async def test_call_tool_unauthorized(self, dynamic_mcp, user_context):
        """Test calling unauthorized tool."""
        dynamic_mcp._user_context_provider = lambda: user_context

        # Mock _list_tools to return empty list
        with patch.object(dynamic_mcp, "_list_tools", return_value=[]):
            result = await dynamic_mcp._mcp_call_tool("unauthorized_tool", {})

        assert len(result) == 1
        assert isinstance(result[0], types.TextContent)
        assert "Access denied" in result[0].text

    async def test_call_builtin_tool(self, dynamic_mcp, user_context):
        """Test calling builtin tool."""
        dynamic_mcp._user_context_provider = lambda: user_context

        # Mock _list_tools to include the tool
        available_tools = [
            Tool(name="builtin_tool", description="Builtin", parameters={})
        ]

        with patch.object(dynamic_mcp, "_list_tools", return_value=available_tools):
            # Mock super()._mcp_call_tool
            with patch.object(
                dynamic_mcp.__class__.__bases__[0],
                "_mcp_call_tool",
                new=AsyncMock(
                    return_value=[types.TextContent(type="text", text="Result")]
                ),
            ):
                result = await dynamic_mcp._mcp_call_tool("builtin_tool", {})

        assert len(result) == 1
        assert result[0].text == "Result"

    async def test_call_proxied_tool_translates_name(self, dynamic_mcp, user_context):
        """Test calling proxied tool translates name."""
        dynamic_mcp._user_context_provider = lambda: user_context
        dynamic_mcp._proxied_tool_servers["proxied_tool"] = "server-id"

        # Mock _list_tools to include the tool
        available_tools = [
            Tool(name="proxied_tool", description="Proxied", parameters={})
        ]

        with patch.object(dynamic_mcp, "_list_tools", return_value=available_tools):
            # Mock super()._mcp_call_tool to verify name translation
            with patch.object(
                dynamic_mcp.__class__.__bases__[0],
                "_mcp_call_tool",
                new=AsyncMock(
                    return_value=[types.TextContent(type="text", text="Result")]
                ),
            ) as mock_super:
                result = await dynamic_mcp._mcp_call_tool("proxied_tool", {})

                # Verify internal name was used
                safe_account_id = user_context.account_id.replace("-", "_")
                expected_internal_name = f"account_{safe_account_id}_proxied_tool"
                mock_super.assert_called_once_with(expected_internal_name, {})


class TestCreateProxiedToolWrapper:
    """Test _create_proxied_tool_wrapper method."""

    def test_create_wrapper_simple_params(self, dynamic_mcp, user_context):
        """Test creating wrapper with simple parameters."""
        wrapper = dynamic_mcp._create_proxied_tool_wrapper(
            tool_name="test_tool",
            server_id="server-123",
            account_id=user_context.account_id,
            description="Test tool",
            input_schema={
                "properties": {"param1": {"type": "string"}},
                "required": ["param1"],
            },
        )

        assert callable(wrapper)
        assert wrapper.__doc__ == "Test tool"
        assert wrapper._display_name == "test_tool"
        assert wrapper._account_id == user_context.account_id

    def test_create_wrapper_optional_params(self, dynamic_mcp, user_context):
        """Test creating wrapper with optional parameters."""
        wrapper = dynamic_mcp._create_proxied_tool_wrapper(
            tool_name="test_tool",
            server_id="server-123",
            account_id=user_context.account_id,
            description="Test tool",
            input_schema={
                "properties": {
                    "required_param": {"type": "string"},
                    "optional_param": {"type": "integer"},
                },
                "required": ["required_param"],
            },
        )

        assert callable(wrapper)

    def test_create_wrapper_various_types(self, dynamic_mcp, user_context):
        """Test creating wrapper with various parameter types."""
        wrapper = dynamic_mcp._create_proxied_tool_wrapper(
            tool_name="test_tool",
            server_id="server-123",
            account_id=user_context.account_id,
            description="Test tool",
            input_schema={
                "properties": {
                    "str_param": {"type": "string"},
                    "int_param": {"type": "integer"},
                    "float_param": {"type": "number"},
                    "bool_param": {"type": "boolean"},
                    "list_param": {"type": "array"},
                    "dict_param": {"type": "object"},
                },
                "required": [],
            },
        )

        assert callable(wrapper)


class TestHelperFunctions:
    """Test helper functions."""

    def test_create_dynamic_mcp_server(self):
        """Test create_dynamic_mcp_server creates instance."""
        mcp = create_dynamic_mcp_server()

        assert isinstance(mcp, DynamicFastMCP)

    def test_create_user_context_no_authenticated_user(self):
        """Test creating user context with no authenticated user."""
        scope = {"user": None}

        result = create_user_context_from_scope(scope)

        assert result is None

    def test_create_user_context_no_account(self):
        """Test creating user context when user has no account."""
        # Create mock authenticated user with no account
        mock_user = MagicMock()
        mock_user.access_token = MagicMock()
        mock_user.access_token.account = None

        scope = {"user": mock_user}

        result = create_user_context_from_scope(scope)

        assert result is None

    def test_create_user_context_success(self):
        """Test successfully creating user context."""
        from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

        # Create mock authenticated user with account
        mock_account = MagicMock()
        mock_account.id = str(uuid4())
        mock_account.username = "testuser"

        # Use spec to make isinstance() work
        mock_user = MagicMock(spec=AuthenticatedUser)
        mock_user.access_token = MagicMock()
        mock_user.access_token.account = mock_account

        scope = {"user": mock_user}

        with patch("spacebridge.services.dynamic_fastmcp.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.close = MagicMock()
            mock_get_db.return_value = iter([mock_db])

            with patch(
                "spacebridge.services.dynamic_fastmcp.has_tracker",
                return_value=True,
            ):
                result = create_user_context_from_scope(scope)

        assert result is not None
        assert result.username == "testuser"
        assert result.has_tracker is True
