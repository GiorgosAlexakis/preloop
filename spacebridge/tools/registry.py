"""Registry for MCP tools in SpaceBridge."""

import importlib
import logging
import pkgutil
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
        return sorted(list(self._tools.keys()))

    def discover_tools(self, package_name: str = "spacebridge.tools") -> None:
        """Discover and register tools from a package.

        This method will recursively import all modules in the package and register
        any tool classes that use the @register_tool decorator.

        Args:
            package_name: The name of the package to discover tools in.
        """
        try:
            package = importlib.import_module(package_name)
            for _, name, is_pkg in pkgutil.iter_modules(package.__path__, f"{package_name}."):
                try:
                    # Import the module or package
                    importlib.import_module(name)
                    
                    # If it's a package, recursively discover tools in it
                    if is_pkg and not name.endswith("__pycache__"):
                        self.discover_tools(name)
                except Exception as e:
                    logger.error(f"Error importing module {name}: {e}")
            
            logger.info(f"Discovered {len(self._tools)} tools")
        except Exception as e:
            logger.error(f"Error discovering tools in {package_name}: {e}")


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


def discover_tools(package_name: str = "spacebridge.tools") -> None:
    """Discover and register tools from a package.

    This method will recursively import all modules in the package and register
    any tool classes that use the @register_tool decorator.

    Args:
        package_name: The name of the package to discover tools in.
    """
    registry.discover_tools(package_name)