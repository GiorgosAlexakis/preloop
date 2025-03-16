"""Registry for MCP tools in SpaceBridge."""

import logging
from typing import Any, Dict, List, Optional, Set, Type

from spacebridge.tools.base import MCPTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for MCP tools.

    This is a singleton class that maintains a registry of all available MCP tools.
    """

    _instance = None
    _tools: Dict[str, Type[MCPTool]] = {}

    def __new__(cls):
        """Create a new instance of the registry or return the existing one."""
        if cls._instance is None:
            cls._instance = super(ToolRegistry, cls).__new__(cls)
        return cls._instance

    def register(self, tool_class: Type[MCPTool]) -> None:
        """Register a tool class.

        Args:
            tool_class: The tool class to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        tool_name = tool_class.metadata().name
        if tool_name in self._tools:
            raise ValueError(f"Tool '{tool_name}' is already registered")

        self._tools[tool_name] = tool_class
        logger.info(f"Registered tool: {tool_name}")

    def get_tool(self, name: str) -> Optional[Type[MCPTool]]:
        """Get a tool class by name.

        Args:
            name: The name of the tool to get.

        Returns:
            The tool class if found, None otherwise.
        """
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tools.

        Returns:
            A list of tool names.
        """
        return list(self._tools.keys())


# Create a singleton registry
registry = ToolRegistry()


def register_tool(tool_class: Type[MCPTool]) -> Type[MCPTool]:
    """Decorator to register a tool class.

    Args:
        tool_class: The tool class to register.

    Returns:
        The tool class.
    """
    registry.register(tool_class)
    return tool_class


def get_tool(name: str) -> Optional[Type[MCPTool]]:
    """Get a tool class by name.

    Args:
        name: The name of the tool to get.

    Returns:
        The tool class if found, None otherwise.
    """
    return registry.get_tool(name)


def list_tools() -> List[str]:
    """List all registered tools.

    Returns:
        A list of tool names.
    """
    return registry.list_tools()
