"""
Direct MCP client for integration testing.

This module provides a fast, reliable way to test MCP endpoints without
spawning Claude CLI processes. Uses the Python MCP client library to
connect directly to Preloop's MCP HTTP endpoint.
"""

import asyncio
from typing import Any, Dict, List, Optional

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class MCPTestClient:
    """Test client for MCP endpoints."""

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize MCP test client.

        Args:
            base_url: Preloop base URL (e.g., https://test.preloop.ai)
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.mcp_url = f"{self.base_url}/mcp/v1"
        self.api_key = api_key
        self.session = None
        self.stream_context = None

    async def __aenter__(self):
        """Async context manager entry."""
        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Create the streamable HTTP connection
        self.stream_context = streamablehttp_client(url=self.mcp_url, headers=headers)
        streams = await self.stream_context.__aenter__()
        read_stream, write_stream, _ = streams

        # Create session and enter its context
        session = ClientSession(read_stream, write_stream)
        self.session = await session.__aenter__()

        # Initialize the MCP session
        await self.session.initialize()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Exit session context first
        if self.session:
            await self.session.__aexit__(exc_type, exc_val, exc_tb)
            self.session = None

        # Then exit stream context
        if self.stream_context:
            await self.stream_context.__aexit__(exc_type, exc_val, exc_tb)
            self.stream_context = None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call an MCP tool.

        Args:
            tool_name: Name of the tool (e.g., "create_issue", "search")
            arguments: Tool arguments as a dictionary

        Returns:
            Tool response
        """
        if not self.session:
            raise RuntimeError("Client not connected. Call connect() first.")

        result = await self.session.call_tool(tool_name, arguments)
        return result

    async def create_issue(
        self,
        project: str,
        title: str,
        description: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create an issue via MCP.

        Args:
            project: Project identifier (e.g., "owner/repo" for GitHub)
            title: Issue title
            description: Issue description
            status: Optional issue status
            priority: Optional issue priority
            assignee: Optional assignee
            labels: Optional list of labels

        Returns:
            Created issue data
        """
        arguments = {
            "project": project,
            "title": title,
            "description": description,
        }
        if status:
            arguments["status"] = status
        if priority:
            arguments["priority"] = priority
        if assignee:
            arguments["assignee"] = assignee
        if labels:
            arguments["labels"] = labels

        return await self.call_tool("create_issue", arguments)

    async def get_issue(self, issue: str) -> Dict[str, Any]:
        """
        Get issue details via MCP.

        Args:
            issue: Issue identifier (e.g., "owner/repo#123")

        Returns:
            Issue data
        """
        return await self.call_tool("get_issue", {"issue": issue})

    async def update_issue(
        self,
        issue: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Update an issue via MCP.

        Args:
            issue: Issue identifier (e.g., "owner/repo#123")
            title: Optional new title
            description: Optional new description
            status: Optional new status
            priority: Optional new priority
            assignee: Optional new assignee
            labels: Optional new labels

        Returns:
            Updated issue data
        """
        arguments = {"issue": issue}
        if title:
            arguments["title"] = title
        if description:
            arguments["description"] = description
        if status:
            arguments["status"] = status
        if priority:
            arguments["priority"] = priority
        if assignee:
            arguments["assignee"] = assignee
        if labels:
            arguments["labels"] = labels

        return await self.call_tool("update_issue", arguments)

    async def search(
        self,
        query: str,
        project: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Search for issues via MCP.

        Args:
            query: Search query
            project: Optional project filter
            limit: Maximum number of results

        Returns:
            Search results
        """
        arguments = {"query": query, "limit": limit}
        if project:
            arguments["project"] = project

        return await self.call_tool("search", arguments)


def run_async_test(coro):
    """
    Helper to run async test code synchronously.

    Args:
        coro: Coroutine to run

    Returns:
        Coroutine result
    """
    return asyncio.run(coro)
