# SpaceBridge-MCP

## Overview

SpaceBridge-MCP is a companion project to SpaceBridge, designed to bridge the gap between Model Context Protocol (MCP) clients like Claude Code and the SpaceBridge REST API. It implements an MCP server using the stdio transport, which is compatible with most MCP client tools.

## Architecture

```
┌────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│                │     │                  │     │                  │     │                 │
│  MCP Clients   ├─────┤  SpaceBridge     ├─────┤  SpaceBridge     ├─────┤  Issue Trackers │
│  (Claude Code) │     │  MCP Server      │     │  REST API        │     │  (Jira/GitHub/  │
│                │     │                  │     │                  │     │   GitLab/etc)   │
└────────────────┘     └──────────────────┘     └──────────────────┘     └─────────────────┘
```

SpaceBridge-MCP acts as a bridge between MCP clients and the SpaceBridge REST API. When an MCP client invokes a tool, SpaceBridge-MCP:

1. Receives the tool invocation via stdio
2. Validates the parameters
3. Translates the request to an HTTP call to the SpaceBridge REST API
4. Returns the result back to the MCP client

## Implementation Guidelines

The SpaceBridge-MCP project should be implemented as follows:

1. **Base Structure**
   - Create a Python package with MCP server implementation
   - Use the official MCP SDK with stdio transport
   - Implement a clean architecture with separation of concerns

2. **Core Components**
   - MCP server with stdio transport
   - HTTP client for communicating with SpaceBridge REST API
   - Function-based tool registration with decorators
   - Parameter validation and transformation
   - Error handling and reporting

3. **Configuration**
   - Environment variables for API URL, credentials, etc.
   - Optional configuration file support
   - Command-line arguments for overriding defaults

4. **Tools Implementation**
   - Implement the same set of tools available in SpaceBridge
   - Each tool should translate MCP calls to REST API calls
   - Maintain consistent parameter naming and validation
   - Handle errors gracefully with meaningful messages

## Example Tool Implementation

```python
from mcp.server import ToolContext, register_tool
import httpx
import os
from typing import Dict, Any

API_URL = os.getenv("SPACEBRIDGE_URL", "http://localhost:8000/api/v1")
API_KEY = os.getenv("SPACEBRIDGE_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

@register_tool(
    name="get_organization",
    description="Retrieves organization details and configuration"
)
async def get_organization(organization_id: str, ctx: ToolContext = None) -> Dict[str, Any]:
    """Get organization details from SpaceBridge.

    Args:
        organization_id: Organization ID or identifier
        ctx: MCP context for progress reporting

    Returns:
        Organization details
    """
    # Report progress if context is available
    if ctx:
        await ctx.report_progress("Fetching organization details...")

    # Make the API call to SpaceBridge
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_URL}/organizations/{organization_id}",
            headers=HEADERS,
            timeout=30.0
        )

        # Handle errors
        if response.status_code != 200:
            error_message = f"Error fetching organization: {response.text}"
            if ctx:
                await ctx.report_error(error_message)
            raise Exception(error_message)

        # Return the result
        return response.json()
```

## Setup for MCP Clients

MCP clients like Claude Code can be configured to use SpaceBridge-MCP as follows:

```bash
# Install SpaceBridge-MCP
pip install SpaceBridge-MCP

# Configure Claude Code to use SpaceBridge-MCP
claude mcp add SpaceBridge-MCP "python -m SpaceBridge-MCP.server"

# Set environment variables for SpaceBridge-MCP
export SPACEBRIDGE_URL="http://localhost:8000/api/v1"
export SPACEBRIDGE_API_KEY="your-api-key"

# List available tools in Claude Code
claude tools list

# Use SpaceBridge tools via Claude
claude "Search for issues related to authentication in the Astrobot project"
```

## Next Steps

1. Create a new repository for SpaceBridge-MCP
2. Implement the base MCP server with stdio transport
3. Create HTTP client for communicating with SpaceBridge
4. Implement all tools defined in the SpaceBridge API
5. Add tests and documentation
6. Publish to PyPI for easy installation
