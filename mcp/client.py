"""MCP client module for interacting with the SpaceBridge server."""

import logging
from typing import Any, Dict, List

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MCPClient:
    """MCP client for interacting with the SpaceBridge server."""

    def __init__(self, base_url: str, username: str = None, password: str = None):
        """Initialize the MCP client.

        Args:
            base_url: Base URL of the SpaceBridge server.
            username: Optional username for authentication.
            password: Optional password for authentication.
        """
        self.base_url = base_url.rstrip("/")
        self.username = username or "admin"
        self.password = password or "admin"
        self.token = None

    async def authenticate(self) -> None:
        """Authenticate with the SpaceBridge server."""
        url = f"{self.base_url}/api/v1/auth/token"
        data = {"username": self.username, "password": self.password, "scope": ""}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            result = response.json()
            self.token = result.get("access_token")

    async def list_tools(self) -> List[str]:
        """List available MCP tools.

        Returns:
            List of tool names.
        """
        url = f"{self.base_url}/mcp/tools"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_tool_metadata(self, tool_name: str) -> Dict[str, Any]:
        """Get metadata for a specific tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            Tool metadata.
        """
        url = f"{self.base_url}/mcp/tools/{tool_name}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def invoke_tool(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke an MCP tool asynchronously.

        Args:
            tool_name: Name of the tool to invoke.
            parameters: Parameters for the tool.

        Returns:
            Tool result.
        """
        url = f"{self.base_url}/mcp/invoke"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        data = {"tool_name": tool_name, "parameters": parameters}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()

    def invoke(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke an MCP tool synchronously.

        This is a convenience wrapper around invoke_tool that handles authentication
        and runs the async method in a new event loop.

        Args:
            tool_name: Name of the tool to invoke.
            parameters: Parameters for the tool.

        Returns:
            Tool result.
        """
        import asyncio

        async def _invoke():
            # Authenticate if needed
            if self.token is None:
                await self.authenticate()

            # Invoke the tool
            return await self.invoke_tool(tool_name, parameters)

        # Run in a new event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create a new event loop if there isn't one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(_invoke())
        except Exception as e:
            logger.error(f"Error invoking tool {tool_name}: {e}")
            raise
