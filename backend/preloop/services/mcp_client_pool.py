"""MCP Client Pool for managing connections to external MCP servers.

This module provides connection pooling and management for external MCP servers.
It maintains persistent HTTP connections and handles authentication.
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import httpx
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for communicating with an external MCP server over HTTP streaming."""

    def __init__(
        self,
        url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None,
        transport: str = "http-streaming",
    ):
        """Initialize MCP client.

        Args:
            url: Full URL of the MCP server endpoint (e.g., http://localhost:8001/mcp)
            auth_type: Type of authentication (none, bearer, api_key)
            auth_config: Authentication configuration
            transport: Transport protocol (default: http-streaming)
        """
        self.url = url.rstrip("/")
        self.auth_type = auth_type
        self.auth_config = auth_config or {}
        self.transport = transport
        self._session: Optional[ClientSession] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._connected = False

    async def connect(self):
        """Establish connection to the MCP server."""
        headers = {}

        # Add authentication headers
        if self.auth_type == "bearer" and "token" in self.auth_config:
            headers["Authorization"] = f"Bearer {self.auth_config['token']}"
        elif self.auth_type == "api_key" and "api_key" in self.auth_config:
            key_name = self.auth_config.get("key_name", "X-API-Key")
            headers[key_name] = self.auth_config["api_key"]

        # Create auth object for httpx if using bearer token
        auth = None
        if self.auth_type == "bearer" and "token" in self.auth_config:
            # Use httpx.Auth for bearer token
            class BearerAuth(httpx.Auth):
                def __init__(self, token: str):
                    self.token = token

                def auth_flow(self, request):
                    request.headers["Authorization"] = f"Bearer {self.token}"
                    yield request

            auth = BearerAuth(self.auth_config["token"])

        # Test connection with MCP SDK client
        try:
            self._exit_stack = AsyncExitStack()

            # Connect using MCP SDK's streamablehttp_client
            (
                read_stream,
                write_stream,
                get_session_id,
            ) = await self._exit_stack.enter_async_context(
                streamablehttp_client(
                    url=self.url,
                    headers=headers if not auth else {},  # Use auth param if bearer
                    timeout=30.0,
                    sse_read_timeout=60.0 * 5,  # 5 minutes for SSE
                    auth=auth,
                )
            )

            # Create client session
            # The session manages its own message loop internally via context manager
            self._session = ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
            )

            # Enter the session context (this starts the message loop)
            await self._exit_stack.enter_async_context(self._session)

            # Initialize the session
            init_result = await self._session.initialize()
            self._connected = True
            logger.info(
                f"Connected to MCP server at {self.url} "
                f"(protocol: {init_result.protocolVersion}, "
                f"server: {init_result.serverInfo.name})"
            )
        except Exception as e:
            logger.error(f"Failed to connect to MCP server at {self.url}: {e}")
            if self._exit_stack:
                try:
                    await self._exit_stack.aclose()
                except RuntimeError as cleanup_error:
                    # Ignore benign cancel scope errors during cleanup
                    if "cancel scope" not in str(cleanup_error).lower():
                        raise
                self._exit_stack = None
            raise

    async def close(self):
        """Close the connection to the MCP server."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except RuntimeError as e:
                # Ignore benign cancel scope errors during cleanup
                if "cancel scope" not in str(e).lower():
                    raise
            self._exit_stack = None
            self._session = None
            self._connected = False
            logger.info(f"Closed connection to MCP server at {self.url}")

    def is_connected(self) -> bool:
        """Check if client is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._session is not None

    async def _create_temp_session(self):
        """Create a temporary session for a single operation.

        Returns tuple of (ClientSession, streams_context, client_context) for cleanup.
        """
        # Build auth
        headers = {}
        if self.auth_type == "bearer" and "token" in self.auth_config:
            headers["Authorization"] = f"Bearer {self.auth_config['token']}"
        elif self.auth_type == "api_key" and "api_key" in self.auth_config:
            key_name = self.auth_config.get("key_name", "X-API-Key")
            headers[key_name] = self.auth_config["api_key"]

        auth = None
        if self.auth_type == "bearer" and "token" in self.auth_config:

            class BearerAuth(httpx.Auth):
                def __init__(self, token: str):
                    self.token = token

                def auth_flow(self, request):
                    request.headers["Authorization"] = f"Bearer {self.token}"
                    yield request

            auth = BearerAuth(self.auth_config["token"])

        # Create client connection (returns context manager)
        streams_context = streamablehttp_client(
            url=self.url,
            headers=headers if not auth else {},
            timeout=30.0,
            sse_read_timeout=60.0,
            auth=auth,
        )

        # Enter streams context
        read_stream, write_stream, _ = await streams_context.__aenter__()

        # Create and enter session context
        session = ClientSession(read_stream=read_stream, write_stream=write_stream)
        await session.__aenter__()
        await session.initialize()

        return session, streams_context

    async def list_tools(self) -> List[types.Tool]:
        """List available tools from the MCP server.

        Returns:
            List of available tools

        Raises:
            RuntimeError: If not connected
        """
        if not self._connected or not self._session:
            raise RuntimeError("Client not connected. Call connect() first.")

        try:
            result = await self._session.list_tools()
            return result.tools
        except Exception as e:
            logger.error(f"Error listing tools: {e}", exc_info=True)
            raise

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
        """
        if not self._connected or not self._session:
            raise RuntimeError("Client not connected. Call connect() first.")

        # Use AsyncExitStack for proper cleanup ordering
        async with AsyncExitStack() as stack:
            # Create client connection
            auth = None
            headers = {}
            if self.auth_type == "bearer" and "token" in self.auth_config:

                class BearerAuth(httpx.Auth):
                    def __init__(self, token: str):
                        self.token = token

                    def auth_flow(self, request):
                        request.headers["Authorization"] = f"Bearer {self.token}"
                        yield request

                auth = BearerAuth(self.auth_config["token"])
            elif self.auth_type == "api_key" and "api_key" in self.auth_config:
                key_name = self.auth_config.get("key_name", "X-API-Key")
                headers[key_name] = self.auth_config["api_key"]

            # Enter streams context and add to stack for cleanup
            read_stream, write_stream, _ = await stack.enter_async_context(
                streamablehttp_client(
                    url=self.url,
                    headers=headers if not auth else {},
                    timeout=30.0,
                    sse_read_timeout=60.0,
                    auth=auth,
                )
            )

            # Create and enter session context, add to stack
            session = ClientSession(read_stream=read_stream, write_stream=write_stream)
            await stack.enter_async_context(session)
            await session.initialize()

            # Execute tool call
            result = await session.call_tool(name=tool_name, arguments=arguments)

            # Convert to list and extract all data
            content_list = []
            for item in result.content:
                if hasattr(item, "text"):
                    content_list.append(types.TextContent(type="text", text=item.text))
                elif hasattr(item, "data"):
                    content_list.append(
                        types.ImageContent(
                            type="image",
                            data=item.data,
                            mimeType=getattr(item, "mimeType", "image/png"),
                        )
                    )
                elif hasattr(item, "resource"):
                    content_list.append(
                        types.EmbeddedResource(type="resource", resource=item.resource)
                    )

            return content_list
            # AsyncExitStack will handle cleanup in reverse order automatically


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
