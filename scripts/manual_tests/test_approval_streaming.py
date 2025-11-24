"""Test approval streaming with Preloop AI MCP server.

This client connects to Preloop AI and calls a tool that requires approval,
displaying progress notifications during the approval wait period.
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
    """Test approval streaming."""
    print("\n" + "=" * 80)
    print("Preloop AI Approval Streaming Test")
    print("=" * 80)
    print()

    # Get configuration from environment or use defaults
    server_url = os.getenv("PRELOOP_URL", "http://localhost:8000/mcp/v1")
    bearer_token = os.getenv("PRELOOP_TOKEN")

    if not bearer_token:
        print("ERROR: PRELOOP_TOKEN environment variable not set!")
        print("Usage: PRELOOP_TOKEN=your-token python test_approval_streaming.py")
        return

    print(f"Connecting to Preloop AI: {server_url}")
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

        # Test tool with approval
        tool_name = "estimate_compliance"
        arguments = {
            "issues": ["SB-123"],  # Dummy issue for testing
            "compliance_metric": "DoR",
        }

        print("=" * 80)
        print(f"Calling tool: {tool_name}")
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
    print("1. Configure an approval policy for estimate_compliance:")
    print("   - Go to Preloop AI UI: /console/tools")
    print("   - Find 'estimate_compliance' tool")
    print("   - Enable 'Requires Approval'")
    print("   - Configure approval policy (Slack/Mattermost/webhook)")
    print()
    print("2. Get your MCP access token:")
    print("   - Go to: /console/mcp-servers")
    print("   - Create or view an MCP access token")
    print()
    print("3. Run this script with your token:")
    print("   export PRELOOP_TOKEN='your-token-here'")
    print("   python test_approval_streaming.py")
    print("=" * 80)
    print()

    # Check if token is set
    if os.getenv("PRELOOP_TOKEN"):
        asyncio.run(main())
    else:
        print(
            "⚠️  PRELOOP_TOKEN not set. Please follow the setup instructions above."
        )
