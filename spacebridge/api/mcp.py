"""Model Context Protocol implementation for SpaceBridge."""

import logging
from typing import Any, Dict, List, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from spacebridge.tools.registry import get_tool, list_tools

logger = logging.getLogger(__name__)

router = APIRouter()


class MCPToolRequest(BaseModel):
    """Request model for invoking an MCP tool."""

    tool_name: str = Field(..., description="Name of the tool to invoke")
    parameters: Dict[str, Any] = Field({}, description="Parameters for the tool")


class MCPToolResponse(BaseModel):
    """Response model for MCP tool invocation results."""

    tool_name: str = Field(..., description="Name of the tool that was invoked")
    result: Any = Field(..., description="Tool execution result")


@router.post("/invoke", response_model=MCPToolResponse)
async def invoke_tool(request: MCPToolRequest) -> Dict[str, Any]:
    """Invoke an MCP tool with the given parameters.

    Args:
        request: The tool invocation request.

    Returns:
        The tool execution result.

    Raises:
        HTTPException: If the tool is not found or if the invocation fails.
    """
    tool_class = get_tool(request.tool_name)
    if not tool_class:
        raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")

    try:
        # Create an instance of the tool
        tool = tool_class()
        
        # Execute the tool with the parameters
        result = tool.execute(request.parameters)
        
        # Return the result
        return {
            "tool_name": request.tool_name,
            "result": result
        }
    except Exception as e:
        logger.exception(f"Error executing tool '{request.tool_name}': {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error executing tool '{request.tool_name}': {str(e)}"
        )


@router.get("/tools", response_model=List[str])
async def list_available_tools() -> List[str]:
    """List all available MCP tools.

    Returns:
        A list of available tool names.
    """
    return list_tools()


# Define the router to be included in the main app
mcp_router = router