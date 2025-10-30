"""Minimal FastMCP client with progress handler from docs."""

import asyncio

from fastmcp.client import Client, StreamableHttpTransport


async def my_progress_handler(
    progress: float, total: float | None, message: str | None
) -> None:
    """Progress handler from FastMCP docs."""
    print("\n🔔 PROGRESS HANDLER CALLED!", flush=True)
    print(f"   progress={progress}", flush=True)
    print(f"   total={total}", flush=True)
    print(f"   message={message}", flush=True)

    if total is not None:
        percentage = (progress / total) * 100
        print(f"   → {percentage:.1f}% complete", flush=True)


async def main():
    """Test basic progress reporting."""
    print("\n" + "=" * 70)
    print("Testing Basic Progress Reporting (FastMCP Docs Example)")
    print("=" * 70)
    print()

    # Connect to test server
    transport = StreamableHttpTransport(url="http://localhost:8002/mcp")

    async with Client(transport=transport) as client:
        print("✓ Connected to test server")
        print()

        # List tools
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")
        print()

        # Call tool with progress handler
        print("Calling backup_database with progress handler...")
        print("-" * 70)

        result = await client.call_tool(
            "backup_database", arguments={}, progress_handler=my_progress_handler
        )

        print("-" * 70)
        print(f"\nResult: {result.data}")
        print()

    print("=" * 70)
    print("Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
