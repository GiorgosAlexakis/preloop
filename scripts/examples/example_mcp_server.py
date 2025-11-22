"""
Example MCP Server for testing external MCP server integration.

This is a simple MCP server built with FastMCP that provides a few example tools
for testing the Phase 1B external MCP server functionality in Preloop AI.

The server supports HTTP streaming transport with bearer token authentication.

To run this server:
    python examples/example_mcp_server.py

The server will start on http://localhost:8001
"""

import logging
import os

from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get bearer token from environment
BEARER_TOKEN = os.getenv("BEARER_TOKEN", "test-token-12345")

# Create FastMCP server instance
# Note: Authentication/middleware is not supported in current FastMCP API
# The server will be publicly accessible - secure with network policies if needed
mcp = FastMCP("Example MCP Server")


@mcp.tool()
def pay(recipient: str, amount: int) -> str:
    """Pay the recipient the specified amount in USD.

    Args:
        recipient: The recipient of the payment
        amount: The amount to pay

    Returns:
        A message indicating the success of the payment
    """
    return f"Payment of ${amount} to {recipient} completed successfully"


@mcp.tool()
def rollback_deployment(env: str = "production") -> str:
    """Rollback the deployment to the previous version."""
    return f"Deployment of {env} environment rolled back successfully"


if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("Starting Example MCP Server on http://localhost:8001")
    logger.info("=" * 70)
    logger.info("")
    logger.info("⚠️  WARNING: No authentication configured (FastMCP limitation)")
    logger.info("   Secure with network policies or firewall rules if needed")
    logger.info("")
    logger.info("Available tools:")
    logger.info("  - get_random_number: Generate a random number")
    logger.info("  - get_current_time: Get current timestamp")
    logger.info("  - calculate_fibonacci: Calculate Fibonacci numbers")
    logger.info("  - reverse_text: Reverse any text")
    logger.info("  - count_words: Count words in text")
    logger.info("  - process_items: Process items with percentage progress (STREAMING)")
    logger.info(
        "  - slow_fibonacci: Calculate Fibonacci with detailed progress (STREAMING)"
    )
    logger.info("")
    logger.info("To add this server to Preloop AI:")
    logger.info("  1. Navigate to /console/tools in Preloop AI UI")
    logger.info("  2. Click 'Add MCP Server'")
    logger.info("  3. Enter:")
    logger.info("     - Name: Example MCP Server")
    logger.info("     - URL: http://host.docker.internal:8001")
    logger.info("            (or http://localhost:8001 if running locally)")
    logger.info("     - Transport: http-streaming")
    logger.info("     - Auth Type: none")
    logger.info("     - Status: active")
    logger.info("  4. Click 'Add' and then 'Scan' to discover tools")
    logger.info("")
    logger.info("=" * 70)

    # Run with FastMCP's built-in server using streamable HTTP transport
    # This creates a FastAPI app internally with the correct MCP protocol handlers
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001,
    )
