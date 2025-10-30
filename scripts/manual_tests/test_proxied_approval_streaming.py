"""Test approval streaming with proxied external MCP tools.

This client connects to SpaceBridge and calls a proxied tool (from example_mcp_server.py)
that requires approval, displaying progress notifications during the approval wait period.
"""

import asyncio
import os
from datetime import datetime

from fastmcp.client import Client, StreamableHttpTransport


async def progress_handler(
    progress: float, total: float | None, message: str | None
) -> None:
    """Handle progress notifications from the server."""
    import sys

    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    # ALWAYS print to show handler was called
    print("\n🔔 PROGRESS HANDLER CALLED!", file=sys.stderr, flush=True)
    print(
        f"   progress={progress}, total={total}, message={message}",
        file=sys.stderr,
        flush=True,
    )

    if total is not None:
        percentage = (progress / total) * 100
        bar_length = 40
        filled = int(bar_length * progress / total)
        bar = "█" * filled + "░" * (bar_length - filled)
        status = message or ""
        print(
            f"[{timestamp}] {bar} {percentage:5.1f}% ({progress}/{total}) {status}",
            flush=True,
        )
    else:
        # Indeterminate progress
        print(f"[{timestamp}] Progress: {progress} {message or ''}", flush=True)


async def main():
    """Test approval streaming with proxied tools."""
    print("\n" + "=" * 80)
    print("SpaceBridge Approval Streaming Test - PROXIED TOOLS")
    print("=" * 80)
    print()

    # Get configuration from environment or use defaults
    server_url = os.getenv("SPACEBRIDGE_URL", "http://localhost:8000/mcp/v1")
    bearer_token = os.getenv("SPACEBRIDGE_TOKEN")

    if not bearer_token:
        print("ERROR: SPACEBRIDGE_TOKEN environment variable not set!")
        print(
            "Usage: SPACEBRIDGE_TOKEN=your-token python test_proxied_approval_streaming.py"
        )
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
        print("✓ Connected successfully!")
        print()

        # List available tools
        print("Listing available tools...")
        tools = await client.list_tools()
        print(f"Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.name}")
        print()

        # Check if calculate_fibonacci is available
        if not any(tool.name == "calculate_fibonacci" for tool in tools):
            print("❌ ERROR: calculate_fibonacci tool not found!")
            print()
            print("Please ensure:")
            print("  1. example_mcp_server.py is running on http://localhost:8001")
            print("  2. The external MCP server is added to your SpaceBridge account")
            print("  3. The tools have been scanned and are active")
            print()
            return

        # Test proxied tool with approval
        tool_name = "calculate_fibonacci"
        arguments = {
            "n": 10,
        }

        print("=" * 80)
        print(f"Calling PROXIED tool: {tool_name}")
        print(f"Arguments: {arguments}")
        print("=" * 80)
        print()
        print("⏳ Waiting for approval... (watch for progress updates below)")
        print()

        try:
            result = await client.call_tool(
                tool_name, arguments, progress_handler=progress_handler
            )
            print()
            print("-" * 80)
            print("RESULT:")
            print(result)
            print("-" * 80)
        except Exception as e:
            print()
            print(f"ERROR: {e}")
            import traceback

            traceback.print_exc()

    print()
    print("=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    print()
    print("SETUP INSTRUCTIONS:")
    print("=" * 80)
    print("1. Make sure example_mcp_server.py is running:")
    print("   python examples/example_mcp_server.py")
    print()
    print("2. Add the external MCP server to SpaceBridge:")
    print("   - Go to SpaceBridge UI: /console/tools")
    print("   - Click 'Add MCP Server'")
    print("   - Enter:")
    print("     * Name: Example MCP Server")
    print("     * URL: http://localhost:8001")
    print("     * Transport: http-streaming")
    print("     * Auth Type: none")
    print("   - Click 'Add' and then 'Scan' to discover tools")
    print()
    print("3. Configure an approval policy for calculate_fibonacci:")
    print("   - Go to SpaceBridge UI: /console/tools")
    print("   - Find 'calculate_fibonacci' tool (from External MCP server)")
    print("   - Enable 'Requires Approval'")
    print("   - Configure approval policy (Slack/Mattermost/webhook)")
    print()
    print("4. Get your MCP access token:")
    print("   - Go to: /console/mcp-servers")
    print("   - Create or view an MCP access token")
    print()
    print("5. Run this script with your token:")
    print("   export SPACEBRIDGE_TOKEN='your-token-here'")
    print("   python test_proxied_approval_streaming.py")
    print("=" * 80)
    print()

    # Check if token is set
    if os.getenv("SPACEBRIDGE_TOKEN"):
        asyncio.run(main())
    else:
        print(
            "⚠️  SPACEBRIDGE_TOKEN not set. Please follow the setup instructions above."
        )
