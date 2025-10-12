"""Direct HTTP transport for MCP with per-request user context injection.

This module implements a simple, direct HTTP transport for the MCP protocol
that bypasses StreamableHTTPSessionManager's complex session handling and
gives us full control over request context injection.
"""

import logging
from typing import Optional

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from spacebridge.api.auth import get_current_active_user
from spacebridge.services.dynamic_mcp_server import (
    DynamicMCPServer,
    UserContext,
    has_tracker,
    initialize_dynamic_mcp_server,
)
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.account import Account

logger = logging.getLogger(__name__)

# Global server instance
_mcp_server_instance: Optional[DynamicMCPServer] = None


def get_mcp_server() -> DynamicMCPServer:
    """Get or create the MCP server instance."""
    global _mcp_server_instance
    if _mcp_server_instance is None:
        _mcp_server_instance = initialize_dynamic_mcp_server()
        logger.info("DynamicMCPServer initialized for direct HTTP transport")
    return _mcp_server_instance


async def handle_mcp_request(
    request: Request,
    current_user: Account = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Handle MCP protocol requests with direct user context injection.

    This endpoint directly handles MCP JSON-RPC messages and injects user
    context before calling handlers. This gives us full control over the
    request context without relying on StreamableHTTPSessionManager.

    Args:
        request: FastAPI request
        current_user: Authenticated user from JWT/API key
        db: Database session

    Returns:
        JSON response with MCP protocol data
    """
    # Get the MCP server
    server = get_mcp_server()

    # Build user context
    user_has_tracker = has_tracker(current_user, db)

    user_context = UserContext(
        user_id=str(current_user.id),
        account_id=str(current_user.id),
        username=current_user.username,
        has_tracker=user_has_tracker,
        enabled_default_tools=[],  # Empty = all tools
        enabled_proxied_tools=[],
    )

    logger.info(
        f"Processing MCP request for {current_user.username}, "
        f"has_tracker={user_has_tracker}"
    )

    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse request body: {e}")
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error: Invalid JSON",
                },
            },
        )

    method = body.get("method")
    request_id = body.get("id", 1)

    logger.info(f"MCP method: {method}")

    # Handle initialize
    if method == "initialize":
        logger.info(f"Handling initialize for user {current_user.username}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": "spacebridge-mcp",
                        "version": "1.0.0",
                    },
                },
            }
        )

    # Handle notifications/initialized
    if method == "notifications/initialized":
        logger.info(
            f"Handling notifications/initialized for user {current_user.username}"
        )
        return JSONResponse(status_code=204, content=None)

    # Handle tools/list
    if method == "tools/list":
        logger.info(f"Handling tools/list for user {current_user.username}")

        try:
            # Get tools for user directly (no request context needed)
            tools = server._get_tools_for_user(user_context)

            # Convert to MCP format
            tools_list = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }
                for tool in tools
            ]

            logger.info(
                f"Returning {len(tools_list)} tools for user {current_user.username}"
            )
            for tool in tools:
                logger.info(f"  - {tool.name}")

            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools_list},
                }
            )

        except Exception as e:
            logger.error(f"Error handling tools/list: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": f"Internal error: {str(e)}",
                    },
                },
            )

    # Handle tools/call
    elif method == "tools/call":
        logger.info(f"Handling tools/call for user {current_user.username}")

        params = body.get("params", {})
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if not tool_name:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "Missing tool name in params",
                    },
                },
            )

        try:
            # Check access
            available_tools = server._get_tools_for_user(user_context)
            if not any(tool.name == tool_name for tool in available_tools):
                logger.warning(
                    f"User {current_user.username} attempted to call "
                    f"unauthorized tool: {tool_name}"
                )
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": f"Access denied: Tool '{tool_name}' is not available",
                        },
                    }
                )

            # Execute tool
            handler = server._tool_handlers.get(tool_name)
            if not handler:
                logger.error(f"No handler found for tool: {tool_name}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": f"Handler not found for tool '{tool_name}'",
                        },
                    },
                )

            logger.info(
                f"Executing tool {tool_name} for user {current_user.username} "
                f"with args: {tool_args}"
            )

            # Call handler
            result = await handler(**tool_args)

            # Convert result to MCP format
            result_text = (
                result.model_dump_json()
                if hasattr(result, "model_dump_json")
                else str(result)
            )

            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text,
                            }
                        ]
                    },
                }
            )

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": f"Error executing tool: {str(e)}",
                    },
                },
            )

    else:
        logger.warning(f"Unsupported method: {method}")
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            },
        )
