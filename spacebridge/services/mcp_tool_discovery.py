"""MCP Tool Discovery Service.

This module provides functionality to discover and cache tools from external MCP servers.
"""

import logging
from datetime import datetime
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from spacebridge.services.mcp_client_pool import get_mcp_client_pool
from spacemodels.models.mcp_server import MCPServer
from spacemodels.models.mcp_tool import MCPTool

logger = logging.getLogger(__name__)


async def scan_mcp_server_tools(mcp_server_id: UUID, db: Session) -> List[MCPTool]:
    """Scan an MCP server and cache its available tools.

    Args:
        mcp_server_id: ID of the MCP server to scan
        db: Database session

    Returns:
        List of discovered tools

    Raises:
        ValueError: If server not found
        Exception: If scan fails
    """
    # Get MCP server from database
    mcp_server = db.query(MCPServer).filter(MCPServer.id == mcp_server_id).first()
    if not mcp_server:
        raise ValueError(f"MCP server not found: {mcp_server_id}")

    logger.info(f"Scanning MCP server: {mcp_server.name} ({mcp_server.url})")

    try:
        # Get client from pool
        client_pool = get_mcp_client_pool()
        client = await client_pool.get_client(
            server_id=str(mcp_server_id),
            url=mcp_server.url,
            auth_type=mcp_server.auth_type,
            auth_config=mcp_server.auth_config,
            transport=mcp_server.transport,
        )

        # List tools from the server
        discovered_tools = await client.list_tools()
        logger.info(
            f"Discovered {len(discovered_tools)} tools from server {mcp_server.name}"
        )

        # Get existing tools for this server
        existing_tools = (
            db.query(MCPTool).filter(MCPTool.mcp_server_id == mcp_server_id).all()
        )
        existing_tool_names = {tool.name for tool in existing_tools}

        # Track new and updated tools
        new_tools = []
        updated_count = 0

        discovered_at = datetime.utcnow().isoformat()

        for tool in discovered_tools:
            if tool.name in existing_tool_names:
                # Update existing tool
                existing_tool = next(t for t in existing_tools if t.name == tool.name)
                existing_tool.description = tool.description
                existing_tool.input_schema = tool.inputSchema
                existing_tool.discovered_at = discovered_at
                updated_count += 1
            else:
                # Create new tool
                new_tool = MCPTool(
                    mcp_server_id=mcp_server_id,
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.inputSchema,
                    discovered_at=discovered_at,
                )
                db.add(new_tool)
                new_tools.append(new_tool)

        # Update server scan timestamp and status
        mcp_server.last_scan_at = discovered_at
        mcp_server.status = "active"
        mcp_server.last_error = None

        # Commit all changes
        db.commit()

        logger.info(
            f"Scan complete for {mcp_server.name}: "
            f"{len(new_tools)} new tools, {updated_count} updated tools"
        )

        # Return all tools for this server
        all_tools = (
            db.query(MCPTool).filter(MCPTool.mcp_server_id == mcp_server_id).all()
        )
        return all_tools

    except Exception as e:
        # Update server with error status
        mcp_server.status = "error"
        mcp_server.last_error = str(e)
        db.commit()

        logger.error(f"Failed to scan MCP server {mcp_server.name}: {e}", exc_info=True)
        raise


async def get_cached_tools_for_server(
    mcp_server_id: UUID, db: Session
) -> List[MCPTool]:
    """Get cached tools for an MCP server without scanning.

    Args:
        mcp_server_id: ID of the MCP server
        db: Database session

    Returns:
        List of cached tools
    """
    tools = db.query(MCPTool).filter(MCPTool.mcp_server_id == mcp_server_id).all()
    return tools


async def get_all_enabled_proxied_tools(
    account_id: str, db: Session
) -> List[tuple[MCPServer, MCPTool]]:
    """Get all enabled proxied tools for an account.

    Args:
        account_id: Account ID
        db: Database session

    Returns:
        List of (MCPServer, MCPTool) tuples for enabled servers
    """
    # Get all active MCP servers for this account
    mcp_servers = (
        db.query(MCPServer)
        .filter(MCPServer.account_id == account_id, MCPServer.status == "active")
        .all()
    )

    # Get all tools for these servers
    proxied_tools = []
    for server in mcp_servers:
        tools = db.query(MCPTool).filter(MCPTool.mcp_server_id == server.id).all()
        for tool in tools:
            proxied_tools.append((server, tool))

    return proxied_tools
