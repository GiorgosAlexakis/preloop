"""Base classes for MCP tools in SpaceBridge."""

from typing import Any, Dict, Set, Type, TypeVar, Optional

from mcp.server.fastmcp import Context
from mcp.types import TextContent, ImageContent, EmbeddedResource
from pydantic import BaseModel, Field

# Some tools might still need these during migration
from pydantic import create_model

# Redefine types for back-compatibility during migration
MCPToolContext = Context

# TypeVar for tool implementations
T = TypeVar("T", bound="BaseModel")


class MCPToolMetadata(BaseModel):
    """Metadata about an MCP tool (for backward compatibility)."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    required_parameters: Set[str] = Field(
        default_factory=set, description="Required parameters for the tool"
    )
    optional_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Optional parameters with default values"
    )


class ToolResult(BaseModel):
    """Base class for tool results."""

    pass
