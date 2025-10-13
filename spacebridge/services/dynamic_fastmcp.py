"""Dynamic FastMCP extension that provides per-user tool filtering.

This extends FastMCP to support dynamic tool lists based on authenticated user context
while keeping FastMCP's proven StreamableHTTP transport implementation.

Phase 1B: Added support for proxied tools from external MCP servers.
"""

import logging
from typing import Callable, Dict, Optional

from fastmcp import FastMCP
from fastmcp.tools import Tool
from mcp import types

from spacebridge.services.dynamic_mcp_server import UserContext, has_tracker
from spacebridge.services.mcp_client_pool import get_mcp_client_pool
from spacebridge.services.mcp_tool_discovery import get_all_enabled_proxied_tools
from spacemodels.db.session import get_db_session as get_db

logger = logging.getLogger(__name__)


class DynamicFastMCP(FastMCP):
    """FastMCP extension with per-user dynamic tool filtering.

    This subclass overrides FastMCP's tool listing and execution to provide
    per-request filtering based on authenticated user context. It keeps all
    of FastMCP's StreamableHTTP transport functionality while adding dynamic
    tool visibility.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user_context_provider: Optional[Callable[[], Optional[UserContext]]] = (
            None
        )
        # Track proxied tool -> server mapping for routing
        self._proxied_tool_servers: Dict[str, str] = {}
        logger.info("DynamicFastMCP initialized")

    def set_user_context_provider(self, provider: Callable[[], Optional[UserContext]]):
        """Set a function that provides current user context.

        This function will be called during tool listing and execution to get
        the current authenticated user's context.

        Args:
            provider: Function that returns UserContext or None
        """
        self._user_context_provider = provider
        logger.info("User context provider registered")

    async def _list_tools(self) -> list[Tool]:
        """Override FastMCP's _list_tools to filter based on user context.

        This method is called by FastMCP's protocol handler to get the list
        of available tools. We filter the full tool list based on the current
        user's context.

        Phase 1B: Now includes proxied tools from external MCP servers.

        Returns:
            List of tools available to the current user
        """
        # Get current user context
        user_context = self._get_current_user_context()

        if not user_context:
            logger.warning("No user context available, returning empty tool list")
            return []

        logger.info(
            f"Filtering tools for user {user_context.username}, has_tracker={user_context.has_tracker}"
        )

        # Start with empty list
        available_tools = []

        # Add default tools if user has tracker
        if user_context.has_tracker:
            default_tools = await super()._list_tools()
            available_tools.extend(default_tools)
            logger.info(f"Added {len(default_tools)} default tools")

        # Add proxied tools from external MCP servers (Phase 1B)
        try:
            db = next(get_db())
            try:
                proxied_tools_data = await get_all_enabled_proxied_tools(
                    user_context.account_id, db
                )

                # Clear previous proxied tool mappings
                # (only keep mappings for current user's tools)
                self._proxied_tool_servers.clear()

                # Convert MCPTool records to FastMCP Tool objects
                for mcp_server, mcp_tool in proxied_tools_data:
                    # Create Tool object from cached schema
                    tool = Tool(
                        name=mcp_tool.name,
                        description=mcp_tool.description or "",
                        parameters=mcp_tool.input_schema,
                    )
                    available_tools.append(tool)

                    # Track which server this tool belongs to
                    self._proxied_tool_servers[mcp_tool.name] = str(mcp_server.id)

                logger.info(f"Added {len(proxied_tools_data)} proxied tools")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error loading proxied tools: {e}", exc_info=True)
            # Continue with just default tools

        logger.info(
            f"Returning {len(available_tools)} total tools for user {user_context.username}"
        )
        for tool in available_tools:
            logger.info(f"  - {tool.name}")

        return available_tools

    def _get_current_user_context(self) -> Optional[UserContext]:
        """Get the current user context for this request.

        This calls the user context provider function that was registered
        via set_user_context_provider().

        Returns:
            UserContext if available, None otherwise
        """
        if not self._user_context_provider:
            logger.warning("No user context provider registered")
            return None

        try:
            context = self._user_context_provider()
            if context:
                logger.debug(f"Got user context: {context.username}")
            else:
                logger.warning("User context provider returned None")
            return context
        except Exception as e:
            logger.error(f"Error getting user context: {e}", exc_info=True)
            return None

    async def _mcp_call_tool(
        self, name: str, arguments: dict | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Override tool execution to check user access and route appropriately.

        This is called by FastMCP's protocol handler before executing a tool.
        We check if the user has access to the requested tool, then route
        to either default tool handlers or external MCP servers.

        Phase 1B: Added routing to external MCP servers for proxied tools.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result or access denied error
        """
        # Get current user context
        user_context = self._get_current_user_context()

        if not user_context:
            logger.warning("No user context available for tool call")
            return [
                types.TextContent(type="text", text="Error: No user context available")
            ]

        # Check if user has access to this tool
        available_tools = await self._list_tools()
        if not any(tool.name == name for tool in available_tools):
            logger.warning(
                f"User {user_context.username} attempted to call "
                f"unauthorized tool: {name}"
            )
            return [
                types.TextContent(
                    type="text", text=f"Access denied: Tool '{name}' is not available"
                )
            ]

        # Check if this is a proxied tool (Phase 1B)
        if name in self._proxied_tool_servers:
            # Route to external MCP server
            server_id = self._proxied_tool_servers[name]
            logger.info(
                f"Routing tool {name} to external MCP server {server_id} "
                f"for user {user_context.username}"
            )

            try:
                # Get server configuration from database
                db = next(get_db())
                try:
                    from spacemodels.models.mcp_server import MCPServer

                    mcp_server = (
                        db.query(MCPServer).filter(MCPServer.id == server_id).first()
                    )

                    if not mcp_server:
                        return [
                            types.TextContent(
                                type="text",
                                text=f"Error: MCP server {server_id} not found",
                            )
                        ]

                    # Get client from pool
                    client_pool = get_mcp_client_pool()
                    client = await client_pool.get_client(
                        server_id=server_id,
                        url=mcp_server.url,
                        auth_type=mcp_server.auth_type,
                        auth_config=mcp_server.auth_config,
                        transport=mcp_server.transport,
                    )

                    # Call tool on external server
                    result = await client.call_tool(name, arguments or {})
                    logger.info(f"Tool {name} executed successfully on external server")
                    return result

                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Error executing proxied tool {name}: {e}", exc_info=True)
                return [
                    types.TextContent(
                        type="text", text=f"Error executing tool: {str(e)}"
                    )
                ]

        # Default tool - call parent implementation
        logger.info(f"Executing default tool {name} for user {user_context.username}")
        return await super()._mcp_call_tool(name, arguments)


def create_dynamic_mcp_server() -> DynamicFastMCP:
    """Create a DynamicFastMCP server instance.

    Returns:
        Configured DynamicFastMCP instance
    """
    mcp = DynamicFastMCP("spacebridge-mcp")
    logger.info("Created DynamicFastMCP server")
    return mcp


def create_user_context_from_scope(scope: dict) -> Optional[UserContext]:
    """Extract user context from ASGI scope.

    This is called by middleware to build UserContext from the authenticated
    user information stored in the ASGI scope.

    Args:
        scope: ASGI scope dict with user authentication info

    Returns:
        UserContext if user is authenticated, None otherwise
    """
    from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

    auth_user = scope.get("user")

    if not isinstance(auth_user, AuthenticatedUser):
        logger.warning("No authenticated user in scope")
        return None

    account = getattr(auth_user.access_token, "account", None)

    if not account:
        logger.warning("No account cached in access token")
        return None

    # Check tracker status
    db = next(get_db())
    try:
        user_has_tracker = has_tracker(account, db)

        user_context = UserContext(
            user_id=str(account.id),
            account_id=str(account.id),
            username=account.username,
            has_tracker=user_has_tracker,
            enabled_default_tools=[],  # Empty = all tools
            enabled_proxied_tools=[],
        )

        logger.info(
            f"Created user context for {account.username}, "
            f"has_tracker={user_has_tracker}"
        )

        return user_context
    finally:
        db.close()
