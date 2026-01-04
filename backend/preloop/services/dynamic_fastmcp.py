"""Dynamic FastMCP extension that provides per-user tool filtering.

This extends FastMCP to support dynamic tool lists based on authenticated user context
while keeping FastMCP's proven StreamableHTTP transport implementation.

Phase 1B: Added support for proxied tools from external MCP servers.
"""

import logging
from typing import Callable, Dict, Optional

from fastmcp import FastMCP
from fastmcp.tools import Tool

from preloop.services.dynamic_mcp_server import (
    UserContext,
    has_tracker,
    get_tracker_types,
)
from preloop.services.mcp_client_pool import get_mcp_client_pool
from preloop.services.mcp_tool_discovery import get_all_enabled_proxied_tools
from preloop.models.crud import crud_mcp_server
from preloop.models.db.session import get_db_session as get_db
from preloop.api.endpoints.tools import BUILTIN_TOOLS

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
        # Track registered proxied tools to avoid re-registration
        self._registered_proxied_tools: set = set()
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

    async def _list_tools(self, context=None) -> list[Tool]:
        """Override FastMCP's _list_tools to filter based on user context.

        This method is called by FastMCP's protocol handler to get the list
        of available tools. We filter the full tool list based on the current
        user's context.

        Phase 1B: Now includes proxied tools from external MCP servers.

        Args:
            context: MiddlewareContext (FastMCP 2.13.0+), ignored for now

        Returns:
            List of tools available to the current user
        """
        logger.info("!!! _list_tools called - ENTRY POINT !!!")
        # Get current user context
        user_context = self._get_current_user_context()
        logger.info(f"!!! Got user context: {user_context} !!!")

        if not user_context:
            logger.warning("No user context available, returning empty tool list")
            return []

        logger.info(
            f"Filtering tools for user {user_context.username}, has_tracker={user_context.has_tracker}"
        )

        # Start with empty list
        available_tools = []

        # Add built-in tools (filtered by tracker requirements metadata)
        default_tools = await super()._list_tools(context)
        # Filter out internal proxied tool names (they start with "account_")
        builtin_tools = [t for t in default_tools if not t.name.startswith("account_")]

        builtin_meta = {t["name"]: t for t in BUILTIN_TOOLS}

        filtered_tools = []
        for tool in builtin_tools:
            meta = builtin_meta.get(tool.name)
            if not meta:
                filtered_tools.append(tool)
                continue

            required_types = meta.get("required_tracker_types") or []
            requires_tracker = meta.get("requires_tracker", False)

            if requires_tracker and not user_context.has_tracker:
                logger.info(
                    f"Skipping tool '{tool.name}' (requires tracker but none configured)"
                )
                continue

            if required_types and not any(
                t in user_context.tracker_types for t in required_types
            ):
                logger.info(
                    f"Skipping tool '{tool.name}' (requires tracker types {required_types}, have {user_context.tracker_types})"
                )
                continue

            filtered_tools.append(tool)

        available_tools.extend(filtered_tools)
        logger.info(
            f"Added {len(filtered_tools)} default tools after tracker-type filtering "
            f"(filtered out {len(builtin_tools) - len(filtered_tools)} tracker-specific tools, "
            f"{len(default_tools) - len(builtin_tools)} internal names)"
        )

        # Add proxied tools from external MCP servers (Phase 1B)
        # Now with dynamic registration for streaming approval support
        try:
            db = next(get_db())
            try:
                proxied_tools_data = await get_all_enabled_proxied_tools(
                    user_context.account_id, db
                )

                # Dynamically register wrapper functions for proxied tools
                proxied_tool_map = {}  # Track original_name -> internal_name mapping

                for mcp_server, mcp_tool in proxied_tools_data:
                    # Create internal name with namespace (sanitize account_id)
                    safe_account_id = user_context.account_id.replace("-", "_")
                    internal_name = f"account_{safe_account_id}_{mcp_tool.name}"
                    proxied_tool_map[mcp_tool.name] = (
                        internal_name,
                        mcp_tool,
                        mcp_server,
                    )

                    # Only register if not already registered
                    if internal_name not in self._registered_proxied_tools:
                        logger.info(
                            f"Dynamically registering proxied tool: {mcp_tool.name} "
                            f"(internal: {internal_name})"
                        )

                        # Create wrapper function with approval and streaming
                        wrapper = self._create_proxied_tool_wrapper(
                            tool_name=mcp_tool.name,
                            server_id=str(mcp_server.id),
                            account_id=user_context.account_id,
                            description=mcp_tool.description or "",
                            input_schema=mcp_tool.input_schema,
                        )

                        # Register with FastMCP using @mcp.tool() decorator
                        self.tool()(wrapper)

                        # Track as registered
                        self._registered_proxied_tools.add(internal_name)

                    # Always track the mapping for name translation
                    self._proxied_tool_servers[mcp_tool.name] = str(mcp_server.id)

                # Now get all registered tools and map back to original names
                all_registered = await super()._list_tools(context)
                logger.info(
                    f"Total registered tools after dynamic registration: {len(all_registered)}"
                )

                for original_name, (
                    internal_name,
                    mcp_tool,
                    mcp_server,
                ) in proxied_tool_map.items():
                    # Check if this tool was registered
                    if any(t.name == internal_name for t in all_registered):
                        # Add with original name for client visibility
                        tool = Tool(
                            name=original_name,  # Client sees original name
                            description=mcp_tool.description or "",
                            parameters=mcp_tool.input_schema,
                        )
                        available_tools.append(tool)
                        logger.info(
                            f"Exposing proxied tool: {original_name} (internal: {internal_name}) mcp_server: {mcp_server}"
                        )
                    else:
                        logger.warning(
                            f"Proxied tool {internal_name} was not found in registered tools!"
                        )

                logger.info(
                    f"Added {len(proxied_tool_map)} proxied tools to available list"
                )

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error loading proxied tools: {e}", exc_info=True)
            # Continue with just default tools

        # SECURITY: Enforce flow-specific tool restrictions if present
        # This provides defense-in-depth: even if an agent is compromised,
        # it cannot call tools outside the flow's allowed list
        if user_context.allowed_flow_tools is not None:
            original_count = len(available_tools)
            available_tools = [
                tool
                for tool in available_tools
                if tool.name in user_context.allowed_flow_tools
            ]
            logger.info(
                f"Flow execution restriction: filtered {original_count} tools down to "
                f"{len(available_tools)} allowed tools for flow execution "
                f"{user_context.flow_execution_id}"
            )

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

    def _create_proxied_tool_wrapper(
        self,
        tool_name: str,
        server_id: str,
        account_id: str,
        description: str,
        input_schema: dict,
    ):
        """Factory to create wrapper functions for proxied tools with approval and streaming.

        Creates a function with explicit parameters based on the input_schema.
        FastMCP doesn't support **kwargs, so we need to build the function dynamically.

        Args:
            tool_name: Name of the tool
            server_id: MCP server ID
            account_id: Owner account ID
            description: Tool description
            input_schema: Tool input schema (JSON Schema)

        Returns:
            Async wrapper function with Context support and explicit parameters
        """
        from fastmcp import Context

        # Create internal name with namespace to avoid collisions
        # Sanitize account_id for Python identifier (replace hyphens with underscores)
        safe_account_id = account_id.replace("-", "_")
        internal_name = f"account_{safe_account_id}_{tool_name}"

        # Extract parameters from input schema
        properties = input_schema.get("properties", {})
        required_params = set(input_schema.get("required", []))

        # Build parameter list dynamically
        params = []
        param_names = []

        for param_name, param_def in properties.items():
            param_names.append(param_name)
            param_type = param_def.get("type", "string")

            # Map JSON Schema types to Python type names
            if param_type == "string":
                type_str = "str"
            elif param_type == "integer":
                type_str = "int"
            elif param_type == "number":
                type_str = "float"
            elif param_type == "boolean":
                type_str = "bool"
            elif param_type == "array":
                type_str = "list"
            elif param_type == "object":
                type_str = "dict"
            else:
                type_str = "str"  # Default to string

            # Add Optional if not required
            if param_name not in required_params:
                params.append(f"{param_name}: Optional[{type_str}] = None")
            else:
                params.append(f"{param_name}: {type_str}")

        # Add Context parameter at the end
        params.append("ctx: Optional[Context] = None")

        # Create function signature string
        params_str = ", ".join(params)

        # Create the wrapper function using exec (yes, it's safe here - we control the input)
        wrapper_code = f"""
async def {internal_name}({params_str}) -> str:
    # DEBUG: Log Context availability
    logger.info(f"[WRAPPER] {{tool_name}} called with Context: {{ctx is not None}}")
    if ctx:
        logger.info(f"[WRAPPER] Context type: {{type(ctx)}}, has report_progress: {{hasattr(ctx, 'report_progress')}}")

    # SECURITY CHECK: Verify caller owns this tool
    user_context = self._get_current_user_context()
    if not user_context or user_context.account_id != account_id:
        logger.warning(
            f"Security violation: User {{user_context.account_id if user_context else 'None'}} "
            f"attempted to call tool '{{tool_name}}' owned by {{account_id}}"
        )
        return "Access denied: Tool not available"

    # Collect all arguments
    arguments = {{}}
    for param_name in param_names:
        value = locals().get(param_name)
        if value is not None:
            arguments[param_name] = value

    # Check approval with streaming (we have Context!)
    from preloop.services.approval_helper import require_approval

    approved, error = await require_approval(
        tool_name=tool_name,
        tool_source="mcp",
        account_id=account_id,
        arguments=arguments,
        ctx=ctx,
    )

    if not approved:
        return error

    # Call external MCP server
    try:
        db = next(get_db())
        try:
            # Use CRUD layer to get MCP server
            mcp_server = crud_mcp_server.get(db, id=server_id, account_id=account_id)

            if not mcp_server:
                return f"Error: MCP server {{server_id}} not found"

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
            result = await client.call_tool(tool_name, arguments)
            logger.info(
                f"Tool {{tool_name}} executed successfully on external server"
            )

            # Convert result to string
            if isinstance(result, list):
                return "\\n".join(
                    item.text if hasattr(item, "text") else str(item)
                    for item in result
                )
            return str(result)

        finally:
            db.close()

    except Exception as e:
        logger.error(
            f"Error executing proxied tool {{tool_name}}: {{e}}", exc_info=True
        )
        return f"Error executing tool: {{str(e)}}"
"""

        # Create local namespace with required variables
        namespace = {
            "self": self,
            "account_id": account_id,
            "tool_name": tool_name,
            "server_id": server_id,
            "param_names": param_names,
            "logger": logger,
            "get_db": get_db,
            "crud_mcp_server": crud_mcp_server,
            "get_mcp_client_pool": get_mcp_client_pool,
            "Optional": Optional,
            "Context": Context,
        }

        # Execute the code to create the function
        exec(wrapper_code, namespace)
        wrapper = namespace[internal_name]

        # Set function metadata
        wrapper.__doc__ = description
        # Store original name and owner for reference
        wrapper._display_name = tool_name  # type: ignore
        wrapper._account_id = account_id  # type: ignore

        logger.info(
            f"Created wrapper function for {tool_name} with parameters: {param_names}"
        )

        return wrapper

    async def _call_tool(self, context):
        """Override tool execution for access validation and name translation.

        This is called by FastMCP's protocol handler before executing a tool.
        We check if the user has access to the requested tool, then translate
        the tool name if it's a proxied tool (client name -> internal name).

        Approval is now handled at the function level (in tool implementations)
        for both builtin and proxied tools, allowing streaming progress updates.

        Args:
            context: MiddlewareContext[CallToolRequestParams] from FastMCP 2.13.0+

        Returns:
            ToolResult from tool execution
        """
        from fastmcp.tools.tool import ToolResult
        from mcp.types import TextContent

        # Extract tool name and arguments from context
        name = context.message.name
        arguments = context.message.arguments or {}

        logger.info(f"!!! _call_tool called for tool: {name} !!!")

        # Get current user context
        user_context = self._get_current_user_context()

        if not user_context:
            logger.warning("No user context available for tool call")
            return ToolResult(
                content=[
                    TextContent(type="text", text="Error: No user context available")
                ]
            )

        # Check if user has access to this tool
        available_tools = await self._list_tools(context=None)
        if not any(tool.name == name for tool in available_tools):
            logger.warning(
                f"User {user_context.username} attempted to call "
                f"unauthorized tool: {name}"
            )
            return ToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Access denied: Tool '{name}' is not available",
                    )
                ]
            )

        # Translate tool name for proxied tools
        # Client calls "calculate_fibonacci", we translate to "account_123_calculate_fibonacci"
        if name in self._proxied_tool_servers:
            safe_account_id = user_context.account_id.replace("-", "_")
            internal_name = f"account_{safe_account_id}_{name}"
            logger.info(f"Translating proxied tool name: {name} -> {internal_name}")
            # Modify context with translated name
            context.message.name = internal_name

        else:
            # Builtin tool - call with original name
            logger.info(f"Calling builtin tool: {name}")

        # Call parent with (possibly modified) context
        return await super()._call_tool(context)


def create_dynamic_mcp_server() -> DynamicFastMCP:
    """Create a DynamicFastMCP server instance.

    Returns:
        Configured DynamicFastMCP instance
    """
    mcp = DynamicFastMCP("preloop-mcp")
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

    user = getattr(auth_user.access_token, "user", None)

    if not user:
        logger.warning("No user cached in access token")
        return None

    # Extract API key if available (for flow execution context)
    api_key = getattr(auth_user.access_token, "api_key", None)

    # Check tracker status
    db = next(get_db())
    try:
        # Get user's account for tracker check
        # Handle detached instance by catching the error and querying directly
        from sqlalchemy.orm.exc import DetachedInstanceError
        from preloop.models.crud import crud_account

        try:
            account = user.account if hasattr(user, "account") else None
        except DetachedInstanceError:
            account = None

        if not account:
            # Fallback: query account if relationship not loaded or detached
            account = crud_account.get(db, id=user.account_id)

        user_has_tracker = has_tracker(account, db) if account else False
        user_tracker_types = get_tracker_types(account, db) if account else []

        # Extract flow execution context from API key if present
        flow_execution_id = None
        allowed_flow_tools = None
        if api_key and api_key.context_data:
            flow_execution_id = api_key.context_data.get("flow_execution_id")
            # Combine allowed_mcp_tools with tool names from allowed_mcp_servers
            allowed_mcp_tools = api_key.context_data.get("allowed_mcp_tools")
            if allowed_mcp_tools is not None:
                # Extract tool names from the allowed_mcp_tools list
                # This could be a list of strings or a list of dicts with "name" or "tool_name" key
                allowed_flow_tools = []
                for tool in allowed_mcp_tools:
                    if isinstance(tool, str):
                        allowed_flow_tools.append(tool)
                    elif isinstance(tool, dict):
                        # Support both "tool_name" (from DB schema) and "name" (legacy)
                        tool_name = tool.get("tool_name") or tool.get("name")
                        if tool_name:
                            allowed_flow_tools.append(tool_name)

                logger.info(
                    f"Flow execution context: execution_id={flow_execution_id}, "
                    f"allowed_tools={allowed_flow_tools}"
                )

        user_context = UserContext(
            user_id=str(user.id),
            account_id=str(user.account_id),
            username=user.username,
            has_tracker=user_has_tracker,
            enabled_default_tools=[],  # Empty = all tools
            enabled_proxied_tools=[],
            tracker_types=user_tracker_types,
            flow_execution_id=flow_execution_id,
            allowed_flow_tools=allowed_flow_tools,
        )

        logger.info(
            f"Created user context for {user.username} "
            f"(account: {user.account_id}), has_tracker={user_has_tracker}, "
            f"tracker_types={user_tracker_types}, "
            f"flow_execution_id={flow_execution_id}"
        )

        return user_context
    finally:
        db.close()
