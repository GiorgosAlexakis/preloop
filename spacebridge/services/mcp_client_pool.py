"""MCP Client Pool for managing connections to external MCP servers.

This module provides connection pooling and management for external MCP servers.
It maintains persistent HTTP connections and handles authentication.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from mcp import types

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for communicating with an external MCP server over HTTP."""

    def __init__(
        self,
        url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None,
        transport: str = "http-streaming",
    ):
        """Initialize MCP client.

        Args:
            url: Base URL of the MCP server
            auth_type: Type of authentication (none, bearer, api_key)
            auth_config: Authentication configuration
            transport: Transport protocol (default: http-streaming)
        """
        self.url = url.rstrip("/")
        self.auth_type = auth_type
        self.auth_config = auth_config or {}
        self.transport = transport
        self._client: Optional[httpx.AsyncClient] = None
        self._connected = False

    async def connect(self):
        """Establish connection to the MCP server."""
        headers = {"Content-Type": "application/json"}

        # Add authentication headers
        if self.auth_type == "bearer" and "token" in self.auth_config:
            headers["Authorization"] = f"Bearer {self.auth_config['token']}"
        elif self.auth_type == "api_key" and "api_key" in self.auth_config:
            key_name = self.auth_config.get("key_name", "X-API-Key")
            headers[key_name] = self.auth_config["api_key"]

        self._client = httpx.AsyncClient(
            base_url=self.url,
            headers=headers,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        # Test connection with initialize request
        try:
            response = await self._client.post(
                "/v1",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "spacebridge-mcp-proxy",
                            "version": "1.0.0",
                        },
                    },
                },
            )
            response.raise_for_status()
            self._connected = True
            logger.info(f"Connected to MCP server at {self.url}")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server at {self.url}: {e}")
            raise

    async def close(self):
        """Close the connection to the MCP server."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._connected = False
            logger.info(f"Closed connection to MCP server at {self.url}")

    def is_connected(self) -> bool:
        """Check if client is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    async def list_tools(self) -> List[types.Tool]:
        """List available tools from the MCP server.

        Returns:
            List of available tools

        Raises:
            RuntimeError: If not connected
            httpx.HTTPError: If request fails
        """
        if not self._connected or not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        response = await self._client.post(
            "/v1",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise RuntimeError(f"MCP server error: {data['error']}")

        tools = []
        for tool_data in data.get("result", {}).get("tools", []):
            tool = types.Tool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                inputSchema=tool_data.get("inputSchema", {}),
            )
            tools.append(tool)

        return tools

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> List[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If not connected
            httpx.HTTPError: If request fails
        """
        if not self._connected or not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        response = await self._client.post(
            "/v1",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            return [types.TextContent(type="text", text=f"Error: {error_msg}")]

        # Parse result content
        result_content = []
        for content_item in data.get("result", {}).get("content", []):
            if content_item.get("type") == "text":
                result_content.append(
                    types.TextContent(type="text", text=content_item.get("text", ""))
                )
            elif content_item.get("type") == "image":
                result_content.append(
                    types.ImageContent(
                        type="image",
                        data=content_item.get("data", ""),
                        mimeType=content_item.get("mimeType", "image/png"),
                    )
                )
            elif content_item.get("type") == "resource":
                result_content.append(
                    types.EmbeddedResource(
                        type="resource",
                        resource=content_item.get("resource", {}),
                    )
                )

        return result_content


class MCPClientPool:
    """Pool of MCP clients for external servers.

    Maintains persistent connections to user-configured external MCP servers
    and provides connection pooling and lifecycle management.
    """

    def __init__(self):
        """Initialize the client pool."""
        self._clients: Dict[str, MCPClient] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        logger.info("MCPClientPool initialized")

    def _get_lock(self, server_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific server.

        Args:
            server_id: ID of the MCP server

        Returns:
            Lock for the server
        """
        if server_id not in self._locks:
            self._locks[server_id] = asyncio.Lock()
        return self._locks[server_id]

    async def get_client(
        self,
        server_id: str,
        url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None,
        transport: str = "http-streaming",
    ) -> MCPClient:
        """Get or create an MCP client for a server.

        Args:
            server_id: Unique ID of the MCP server
            url: Base URL of the MCP server
            auth_type: Authentication type
            auth_config: Authentication configuration
            transport: Transport protocol

        Returns:
            Connected MCP client

        Raises:
            Exception: If connection fails
        """
        # Check if client already exists
        if server_id in self._clients:
            client = self._clients[server_id]
            if client.is_connected():
                return client
            else:
                # Client exists but not connected, remove it
                logger.warning(
                    f"Existing client for {server_id} not connected, recreating"
                )
                await self.close_client(server_id)

        # Create new client with lock
        lock = self._get_lock(server_id)
        async with lock:
            # Double-check after acquiring lock
            if server_id in self._clients and self._clients[server_id].is_connected():
                return self._clients[server_id]

            # Create and connect new client
            client = MCPClient(
                url=url,
                auth_type=auth_type,
                auth_config=auth_config,
                transport=transport,
            )
            await client.connect()
            self._clients[server_id] = client
            logger.info(f"Created new MCP client for server {server_id}")

        return client

    async def close_client(self, server_id: str):
        """Close and remove a client from the pool.

        Args:
            server_id: ID of the MCP server
        """
        if server_id in self._clients:
            async with self._get_lock(server_id):
                if server_id in self._clients:
                    await self._clients[server_id].close()
                    del self._clients[server_id]
                    logger.info(f"Closed and removed client for server {server_id}")

    async def close_all(self):
        """Close all clients in the pool."""
        async with self._global_lock:
            for server_id in list(self._clients.keys()):
                await self.close_client(server_id)
            logger.info("Closed all MCP clients")

    def get_active_servers(self) -> List[str]:
        """Get list of server IDs with active connections.

        Returns:
            List of server IDs
        """
        return [
            server_id
            for server_id, client in self._clients.items()
            if client.is_connected()
        ]


# Global client pool instance
_client_pool: Optional[MCPClientPool] = None


def get_mcp_client_pool() -> MCPClientPool:
    """Get the global MCP client pool instance.

    Returns:
        Global MCPClientPool instance
    """
    global _client_pool
    if _client_pool is None:
        _client_pool = MCPClientPool()
    return _client_pool
