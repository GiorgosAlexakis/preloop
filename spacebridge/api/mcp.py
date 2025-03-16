"""Model Context Protocol implementation for SpaceBridge."""

import logging
from typing import Any, Dict, List, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from spacebridge.tools.registry import discover_tools, get_tool, list_tools

logger = logging.getLogger(__name__)

router = APIRouter()


class MCPToolRequest(BaseModel):
    """Request model for invoking an MCP tool."""

    tool_name: str = Field(..., description="Name of the tool to invoke")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters for the tool"
    )


class MCPToolMetadataResponse(BaseModel):
    """Response model for MCP tool metadata."""

    name: str = Field(..., description="Name of the tool")
    description: str = Field(..., description="Description of the tool")
    required_parameters: List[str] = Field(
        ..., description="Required parameters for the tool"
    )
    optional_parameters: Dict[str, Any] = Field(
        ..., description="Optional parameters with default values"
    )


class MCPToolResponse(BaseModel):
    """Response model for MCP tool invocation results."""

    tool_name: str = Field(..., description="Name of the tool that was invoked")
    result: Any = Field(..., description="Tool execution result")


@router.on_event("startup")
async def startup_event():
    """Initialize the MCP router on startup."""
    # Discover all available tools
    discover_tools()
    logger.info(f"Discovered {len(list_tools())} MCP tools")


@router.post("/invoke", response_model=MCPToolResponse)
async def invoke_tool(request: MCPToolRequest, req: Request) -> Dict[str, Any]:
    """Invoke an MCP tool with the given parameters.

    Args:
        request: The tool invocation request.
        req: The FastAPI request object.

    Returns:
        The tool execution result.

    Raises:
        HTTPException: If the tool is not found or if the invocation fails.
    """
    logger.info(f"Invoking tool: {request.tool_name}")

    # Get the tool class from the registry
    tool_class = get_tool(request.tool_name)
    if not tool_class:
        logger.error(f"Tool not found: {request.tool_name}")
        raise HTTPException(
            status_code=404, detail=f"Tool '{request.tool_name}' not found"
        )

    try:
        # Create an instance of the tool
        tool = tool_class()

        # Log the parameters (excluding sensitive data)
        safe_params = {
            k: v
            for k, v in request.parameters.items()
            if not k.lower() in ["password", "token", "secret", "key", "credential"]
        }
        logger.debug(f"Tool parameters: {safe_params}")

        # Execute the tool with the parameters
        result = tool.execute(request.parameters)

        # Return the result
        return {"tool_name": request.tool_name, "result": result}
    except ValueError as e:
        # Parameter validation error
        logger.warning(f"Parameter validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Other errors
        logger.exception(f"Error executing tool '{request.tool_name}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error executing tool '{request.tool_name}': {str(e)}",
        )


@router.get("/tools", response_model=List[str])
async def list_available_tools() -> List[str]:
    """List all available MCP tools.

    Returns:
        A list of available tool names.
    """
    return list_tools()


@router.get("/tools/{tool_name}", response_model=MCPToolMetadataResponse)
async def get_tool_metadata(tool_name: str) -> Dict[str, Any]:
    """Get metadata for a specific MCP tool.

    Args:
        tool_name: The name of the tool to get metadata for.

    Returns:
        The tool metadata.

    Raises:
        HTTPException: If the tool is not found.
    """
    tool_class = get_tool(tool_name)
    if not tool_class:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    metadata = tool_class.metadata()
    return {
        "name": metadata.name,
        "description": metadata.description,
        "required_parameters": sorted(list(metadata.required_parameters)),
        "optional_parameters": metadata.optional_parameters,
    }


# Define the router to be included in the main app
mcp_router = router
