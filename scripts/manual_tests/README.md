# Manual Test Scripts

This directory contains interactive scripts for manual testing and debugging of SpaceBridge MCP functionality. These are NOT part of the automated pytest suite.

## MCP Connection & Auth Testing

- **`test_mcp_auth.sh`** - Shell script to test MCP authentication with bearer tokens
- **`test_mcp_connection.py`** - Test basic MCP server connectivity
- **`check_client_api.py`** - Inspect FastMCP Client API signatures
- **`check_tool_config.py`** - Check tool configuration database state

## Progress Notification Testing

### Basic FastMCP Progress (Proof of Concept)
- **`test_basic_progress_server.py`** - Minimal FastMCP server with progress reporting (from docs)
- **`test_basic_progress_client.py`** - Minimal client to test basic progress notifications

### SpaceBridge Progress Testing
- **`test_spacebridge_progress.py`** - Test progress notifications with SpaceBridge's `test_progress` tool

## Approval Streaming Testing

- **`test_approval_streaming.py`** - Test approval flow with progress streaming for **builtin tools** (e.g., `estimate_compliance`)
- **`test_proxied_approval_streaming.py`** - Test approval flow with progress streaming for **proxied external MCP tools** (e.g., `calculate_fibonacci`)

## Usage

### Running Progress Tests

1. Start SpaceBridge server
2. Set your MCP access token:
   ```bash
   export SPACEBRIDGE_TOKEN='your-token-here'
   ```
3. Run the test client:
   ```bash
   python scripts/manual_tests/test_spacebridge_progress.py
   ```

### Running Approval Tests

**Prerequisites:**
1. Configure an approval policy for the tool being tested (via `/console/tools` UI)
2. Ensure notification channel is set up (Mattermost/Slack/webhook)
3. Get your MCP access token from `/console/mcp-servers`

**Test builtin tools:**
```bash
export SPACEBRIDGE_TOKEN='your-token-here'
python scripts/manual_tests/test_approval_streaming.py
```

**Test proxied tools:**
1. Start external MCP server: `python examples/example_mcp_server.py`
2. Add the server via SpaceBridge UI and scan tools
3. Configure approval policy for `calculate_fibonacci`
4. Run test:
   ```bash
   python scripts/manual_tests/test_proxied_approval_streaming.py
   ```

## Expected Output

When progress notifications work correctly, you should see output like:
```
🔔 PROGRESS HANDLER CALLED!
   progress=0.0
   total=100.0
   message=Approval request sent to mattermost (@dimo)
   → 0.0% complete

🔔 PROGRESS HANDLER CALLED!
   progress=10.0
   total=100.0
   message=Waiting for approval from @dimo (270s remaining)
   → 10.0% complete
```

## Troubleshooting

- **No progress notifications**: Ensure `json_response=None` in `dynamic_fastmcp_http.py`
- **Authentication errors**: Check token validity with `check_tool_config.py`
- **Approval not triggered**: Verify ToolConfiguration exists with `requires_approval=True`
- **External tools not visible**: Run scan endpoint for the MCP server
