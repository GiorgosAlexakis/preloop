"""Integration test for consecutive proxied tool calls.

This test ensures that proxied tools can be called multiple times consecutively
without resource cleanup issues (regression test for Issue #3).
"""

import asyncio
import os
import pytest

from fastmcp.client import Client, StreamableHttpTransport


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1",
)
async def test_consecutive_proxied_tool_calls():
    """Test that proxied tools can be called multiple times without failures.

    This is a regression test for the issue where the second invocation of a
    proxied tool would fail due to improper async context cleanup.

    Prerequisites:
    - Preloop server running on http://localhost:8001
    - External MCP server with a test tool registered
    - PRELOOP_TOKEN environment variable set
    - TEST_MCP_TOOL environment variable set (name of tool to test)
    """
    # Get configuration from environment
    token = os.getenv("PRELOOP_TOKEN")
    test_tool = os.getenv("TEST_MCP_TOOL", "get_random_number")

    if not token:
        pytest.skip("PRELOOP_TOKEN not set")

    # Connect to Preloop
    transport = StreamableHttpTransport(
        url="http://localhost:8001/mcp/v1",
        headers={"Authorization": f"Bearer {token}"},
    )

    async with Client(transport=transport) as client:
        # List available tools
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]

        # Check if test tool is available
        if test_tool not in tool_names:
            pytest.skip(
                f"Test tool '{test_tool}' not found in available tools: {tool_names}"
            )

        # Call the proxied tool 3 times consecutively
        results = []
        for i in range(3):
            print(f"\n=== Consecutive call #{i + 1} ===")

            # Call the tool
            result = await client.call_tool(
                test_tool,
                arguments={},  # Adjust based on your test tool's schema
            )

            # Verify we got a result
            assert result is not None, f"Call #{i + 1} returned None"
            assert result.data is not None, f"Call #{i + 1} returned no data"

            results.append(result.data)
            print(
                f"✓ Call #{i + 1} succeeded: {result.data[:100] if len(str(result.data)) > 100 else result.data}"
            )

        # Verify all calls succeeded
        assert len(results) == 3, "Not all calls completed"
        print("\n✅ All consecutive calls succeeded!")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS=1",
)
async def test_concurrent_proxied_tool_calls():
    """Test that multiple proxied tool calls can run concurrently.

    This verifies that the AsyncExitStack cleanup doesn't interfere with
    concurrent operations.
    """
    token = os.getenv("PRELOOP_TOKEN")
    test_tool = os.getenv("TEST_MCP_TOOL", "get_random_number")

    if not token:
        pytest.skip("PRELOOP_TOKEN not set")

    # Connect to Preloop
    transport = StreamableHttpTransport(
        url="http://localhost:8001/mcp/v1",
        headers={"Authorization": f"Bearer {token}"},
    )

    async with Client(transport=transport) as client:
        # List available tools
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]

        if test_tool not in tool_names:
            pytest.skip(f"Test tool '{test_tool}' not found")

        # Launch 5 concurrent calls
        print("\n=== Launching 5 concurrent calls ===")

        async def call_tool(call_id: int):
            print(f"  Starting call #{call_id}")
            result = await client.call_tool(test_tool, arguments={})
            print(f"  ✓ Call #{call_id} completed")
            return result

        # Run all calls concurrently
        results = await asyncio.gather(
            *[call_tool(i) for i in range(1, 6)], return_exceptions=True
        )

        # Check for failures
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(failures) == 0, f"Some concurrent calls failed: {failures}"

        # Verify all succeeded
        assert len(results) == 5, "Not all concurrent calls completed"
        print("\n✅ All concurrent calls succeeded!")


if __name__ == "__main__":
    """Run tests manually for debugging."""
    print("Running consecutive proxied tool call tests...")
    print("Make sure to set:")
    print("  - PRELOOP_TOKEN=your-token")
    print("  - TEST_MCP_TOOL=tool-name (optional, defaults to get_random_number)")
    print("  - RUN_INTEGRATION_TESTS=1")
    print()

    asyncio.run(test_consecutive_proxied_tool_calls())
    asyncio.run(test_concurrent_proxied_tool_calls())
