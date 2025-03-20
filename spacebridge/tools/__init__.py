"""MCP tool implementations for SpaceBridge."""

from spacebridge.tools.base import MCPToolContext


__all__ = [
    "MCPToolContext",
]

# Discover and register tools
import pkgutil
import importlib

# Importing the tool modules will register them via the decorator
for _, name, is_pkg in pkgutil.iter_modules(__path__, f"{__name__}."):
    importlib.import_module(name)
