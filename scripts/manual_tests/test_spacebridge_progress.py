"""Test progress reporting with SpaceBridge DynamicFastMCP server."""

import asyncio
import os

from fastmcp.client import Client, StreamableHttpTransport


async def progress_handler(
    progress: float, total: float | None, message: str | None
) -> None:
    """Progress handler to verify notifications are received."""
    print("\n🔔 PROGRESS HANDLER CALLED!", flush=True)
    print(f"   progress={progress}", flush=True)
    print(f"   total={total}", flush=True)
    print(f"   message={message}", flush=True)

    if total is not None:
        percentage = (progress / total) * 100
        print(f"   → {percentage:.1f}% complete", flush=True)


async def main():
    """Test progress reporting with SpaceBridge."""
    print("\n" + "=" * 70)
    print("Testing Progress Reporting with SpaceBridge DynamicFastMCP")
    print("=" * 70)
    print()

    # Get configuration from environment or use defaults
    server_url = os.getenv("SPACEBRIDGE_URL", "http://localhost:8000/mcp/v1")
    bearer_token = os.getenv("SPACEBRIDGE_TOKEN")

    if not bearer_token:
        print("ERROR: SPACEBRIDGE_TOKEN environment variable not set!")
        print("Usage: SPACEBRIDGE_TOKEN=your-token python test_spacebridge_progress.py")
        return

    print(f"Connecting to SpaceBridge: {server_url}")
    print(f"Using bearer token: {bearer_token[:20]}...")
    print()

    # Create transport with authentication
    transport = StreamableHttpTransport(
        url=server_url,
        headers={"Authorization": f"Bearer {bearer_token}"},
    )

    async with Client(transport=transport) as client:
        print("✓ Connected to SpaceBridge!")
        print()

        # List tools
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")
        print()

        # Call test_progress tool with progress handler
        print("Calling test_progress with progress handler...")
        print("-" * 70)

        result = await client.call_tool(
            "test_progress", arguments={"count": 5}, progress_handler=progress_handler
        )

        print("-" * 70)
        print(f"\nResult: {result.data}")
        print()

    print("=" * 70)
    print("Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    # Check if token is set
    if os.getenv("SPACEBRIDGE_TOKEN"):
        asyncio.run(main())
    else:
        print("⚠️  SPACEBRIDGE_TOKEN not set.")
        print("Usage: SPACEBRIDGE_TOKEN=your-token python test_spacebridge_progress.py")
