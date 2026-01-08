# Manual MCP Testing Scripts

This directory contains manual testing scripts for verifying MCP functionality.

## Progress Reporting Tests

### Basic Progress Test (FastMCP Docs Example)

Tests progress reporting with a minimal FastMCP server to verify the feature works independently.

**Start the test server:**
```bash
python scripts/manual_tests/test_basic_progress_server.py
```

**Run the client test:**
```bash
python scripts/manual_tests/test_basic_progress_client.py
```

Expected output: Progress handler should be called for each table backup (5 times total).

### Preloop Progress Test

Tests that progress reporting works with Preloop's stateless HTTP mode.

**Prerequisites:**
- Preloop server running on `http://localhost:8001`
- Valid API key/token

**Run the test:**
```bash
export PRELOOP_TOKEN="your-api-key-here"
python scripts/manual_tests/test_preloop_progress.py
```

Expected output: Progress handler should be called during `test_progress` tool execution.

**Note:** If progress updates are not received with `stateless_http=True`, you may need to investigate whether FastMCP's stateless mode supports SSE streaming for progress notifications. The `json_response=None` parameter should enable this, but it may require verification.

## Troubleshooting

If progress updates don't work with `stateless_http=True`:

1. Check FastMCP's documentation for stateless HTTP limitations
2. Verify that SSE (Server-Sent Events) streaming is enabled
3. Consider whether session state is required for progress notifications
4. Look for any FastMCP configuration options related to progress in stateless mode

If the issue persists, you may need to:
- Review FastMCP's implementation of stateless HTTP + progress
- Check if there's a way to maintain session state only for progress notifications
- Consider alternative approaches (e.g., polling, webhooks)
