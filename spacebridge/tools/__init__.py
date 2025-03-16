"""MCP tool implementations for SpaceBridge."""

from spacebridge.tools.base import MCPTool, MCPToolMetadata

# Import tool modules to register them
from spacebridge.tools.issue import CreateIssueTool, SearchIssuesTool
from spacebridge.tools.organization import GetOrganizationTool
from spacebridge.tools.project import TestConnectionTool
from spacebridge.tools.registry import get_tool, list_tools, register_tool

__all__ = [
    "MCPTool",
    "MCPToolMetadata",
    "get_tool",
    "list_tools",
    "register_tool",
    # Tool implementations
    "CreateIssueTool",
    "GetOrganizationTool",
    "SearchIssuesTool",
    "TestConnectionTool",
]
