# SpaceBridge Examples

This directory contains example code for working with SpaceBridge.

## Example MCP Server

`example_mcp_server.py` is a simple MCP server built with FastMCP that provides several example tools for testing external MCP server integration (Phase 1B).

### Available Tools

- **get_random_number**: Generate a random number within a range
- **get_current_time**: Get the current timestamp
- **calculate_fibonacci**: Calculate Fibonacci numbers
- **reverse_text**: Reverse any text string
- **count_words**: Count words and characters in text

### Running the Server

```bash
# Install FastMCP if not already installed
pip install fastmcp

# Run the server
python examples/example_mcp_server.py
```

The server will start on `http://localhost:8001` and be ready to accept connections.

### Adding to SpaceBridge

1. Start the example MCP server:
   ```bash
   python examples/example_mcp_server.py
   ```

2. Navigate to `/console/tools` in the SpaceBridge UI
3. Click "Add MCP Server"
4. Enter the following:
   - **Name**: Example MCP Server
   - **URL**: `http://host.docker.internal:8001` (if running SpaceBridge in Docker) or `http://localhost:8001` (if running locally)
   - **Transport**: http-streaming
   - **Auth Type**: none
   - **Status**: active
5. Click "Add"
6. Click "Scan" to discover the available tools
7. Enable/disable tools as needed in the Tools view

**Note**: This example server runs without authentication for simplicity. Phase 1B supports HTTP streaming transport with optional bearer token authentication.

### Testing Tool Execution

Once added and scanned, the example tools will appear in your SpaceBridge tools list and can be called via:

- The SpaceBridge MCP server at `/mcp/v1`
- MCP clients like Claude Code configured to use SpaceBridge as their MCP server
- The SpaceBridge UI (if tool execution UI is implemented)

### Tool Proxying Flow

When you call a proxied tool:
1. MCP client → SpaceBridge MCP endpoint (`/mcp/v1`)
2. SpaceBridge authenticates request and checks tool access
3. SpaceBridge proxies the tool call to this example server
4. Example server executes the tool
5. Result flows back: Example server → SpaceBridge → MCP client
