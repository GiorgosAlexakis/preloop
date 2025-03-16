#!/usr/bin/env python
"""MCP client for testing the SpaceBridge server."""

import argparse
import json
import logging
import sys
from typing import Any, Dict, List, Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MCPClient:
    """MCP client for interacting with the SpaceBridge server."""

    def __init__(self, base_url: str, username: str, password: str):
        """Initialize the MCP client.

        Args:
            base_url: Base URL of the SpaceBridge server.
            username: Username for authentication.
            password: Password for authentication.
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
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
        headers = {"Authorization": f"Bearer {self.token}"}

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
        headers = {"Authorization": f"Bearer {self.token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def invoke_tool(
        self, tool_name: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke an MCP tool.

        Args:
            tool_name: Name of the tool to invoke.
            parameters: Parameters for the tool.

        Returns:
            Tool result.
        """
        url = f"{self.base_url}/mcp/invoke"
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {"tool_name": tool_name, "parameters": parameters}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()


async def main() -> None:
    """Run the MCP client."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="MCP client for SpaceBridge")
    parser.add_argument(
        "--url", default="http://localhost:8000", help="SpaceBridge server URL"
    )
    parser.add_argument(
        "--username", default="admin", help="Username for authentication"
    )
    parser.add_argument(
        "--password", default="admin", help="Password for authentication"
    )
    parser.add_argument(
        "command", choices=["list", "metadata", "invoke"], help="Command to run"
    )
    parser.add_argument("--tool", help="Tool name for metadata or invoke commands")
    parser.add_argument("--params", help="Tool parameters for invoke command (JSON)")
    args = parser.parse_args()

    # Create client
    client = MCPClient(args.url, args.username, args.password)

    try:
        # Authenticate
        await client.authenticate()
        logger.info("Successfully authenticated")

        # Run command
        if args.command == "list":
            # List tools
            tools = await client.list_tools()
            print("Available tools:")
            for tool in tools:
                print(f"- {tool}")

        elif args.command == "metadata":
            # Get tool metadata
            if not args.tool:
                logger.error("Tool name is required for metadata command")
                sys.exit(1)

            metadata = await client.get_tool_metadata(args.tool)
            print(f"Metadata for {args.tool}:")
            print(f"Description: {metadata['description']}")
            print("Required parameters:")
            for param in metadata["required_parameters"]:
                print(f"- {param}")
            print("Optional parameters:")
            for param, default in metadata["optional_parameters"].items():
                print(f"- {param} (default: {default})")

        elif args.command == "invoke":
            # Invoke tool
            if not args.tool:
                logger.error("Tool name is required for invoke command")
                sys.exit(1)

            # Parse parameters
            parameters = {}
            if args.params:
                try:
                    parameters = json.loads(args.params)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON for parameters")
                    sys.exit(1)

            # Invoke tool
            result = await client.invoke_tool(args.tool, parameters)
            print("Tool result:")
            print(json.dumps(result, indent=2))

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code} {e.response.text}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
