"""Test MCP client connection to example server."""

import asyncio
import logging

from preloop_ai.services.mcp_client_pool import MCPClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_connection():
    """Test connecting to the example MCP server."""
    client = MCPClient(
        url="http://localhost:8001/mcp",
        auth_type="none",
        auth_config=None,
        transport="http-streaming",
    )

    try:
        logger.info("Attempting to connect to MCP server...")
        await asyncio.wait_for(client.connect(), timeout=10.0)
        logger.info("✓ Connected successfully!")

        logger.info("Listing tools...")
        tools = await asyncio.wait_for(client.list_tools(), timeout=10.0)
        logger.info(f"✓ Found {len(tools)} tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")

        logger.info("Testing tool call...")
        result = await asyncio.wait_for(
            client.call_tool("get_random_number", {"min_value": 1, "max_value": 10}),
            timeout=10.0,
        )
        logger.info(f"✓ Tool call result: {result}")

    except asyncio.TimeoutError as e:
        logger.error(f"✗ Timeout: {e}")
        import traceback

        traceback.print_exc()
    except Exception as e:
        logger.error(f"✗ Error: {e}", exc_info=True)
    finally:
        await client.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    asyncio.run(test_connection())
