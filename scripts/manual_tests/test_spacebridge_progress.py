"""Test progress reporting with Preloop MCP server.

This tests that progress updates work correctly with stateless_http=True.
"""

import asyncio
import os

from fastmcp.client import Client, StreamableHttpTransport


async def my_progress_handler(
    progress: float, total: float | None, message: str | None
) -> None:
    """Progress handler to verify progress updates are received."""
    print("\n🔔 PROGRESS HANDLER CALLED!", flush=True)
    print(f"   progress={progress}", flush=True)
    print(f"   total={total}", flush=True)
    print(f"   message={message}", flush=True)

    if total is not None:
        percentage = (progress / total) * 100
        print(f"   → {percentage:.1f}% complete", flush=True)


async def main():
    """Test progress reporting with Preloop server."""
    print("\n" + "=" * 70)
    print("Testing Progress Reporting with Preloop (stateless_http=True)")
    print("=" * 70)
    print()

    # Get auth token from environment
    token = os.getenv("PRELOOP_TOKEN")
    if not token:
        print("❌ Error: PRELOOP_TOKEN environment variable not set")
        print("   Please set it with: export PRELOOP_TOKEN='your-api-key'")
        return

    # Connect to Preloop server
    transport = StreamableHttpTransport(
        url="http://localhost:8001/mcp/v1",
        headers={"Authorization": f"Bearer {token}"},
    )

    async with Client(transport=transport) as client:
        print("✓ Connected to Preloop server")
        print()

        # List tools
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")
        print()

        # Find test_progress tool
        if not any(t.name == "test_progress" for t in tools):
            print("❌ Error: test_progress tool not found")
            print("   Make sure the Preloop server has test_progress tool registered")
            return

        # Call test_progress with progress handler
        print("Calling test_progress with progress handler...")
        print("-" * 70)

        result = await client.call_tool(
            "test_progress",
            arguments={"count": 5, "items": ["item1", "item2", "item3"]},
            progress_handler=my_progress_handler,
        )

        print("-" * 70)
        print(f"\n✓ Result: {result.data}")
        print()

    print("=" * 70)
    print("✅ Progress test completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
