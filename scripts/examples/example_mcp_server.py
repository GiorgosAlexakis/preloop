"""
Example MCP Server for testing external MCP server integration.

This is a simple MCP server built with FastMCP that provides a few example tools
for testing the Phase 1B external MCP server functionality in SpaceBridge.

The server supports HTTP streaming transport with bearer token authentication.

To run this server:
    python examples/example_mcp_server.py

The server will start on http://localhost:8001
"""

import logging
import os
import random
from typing import Optional

from fastmcp import Context, FastMCP

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
def send_money(recipient: str, amount: int) -> str:
    """Send a payment of the specified amount in USD to the recipient.

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


@mcp.tool()
def get_random_number(min_value: int = 1, max_value: int = 100) -> str:
    """Generate a random number between min_value and max_value.

    Args:
        min_value: Minimum value (inclusive)
        max_value: Maximum value (inclusive)

    Returns:
        A random number as a string
    """
    number = random.randint(min_value, max_value)
    return f"Random number: {number}"


@mcp.tool()
def calculate_fibonacci(n: int) -> str:
    """Calculate the nth Fibonacci number.

    Args:
        n: The position in the Fibonacci sequence (must be positive)

    Returns:
        The nth Fibonacci number
    """
    if n <= 0:
        return "Error: n must be positive"
    if n > 50:
        return "Error: n too large (max 50 to avoid overflow)"

    if n == 1 or n == 2:
        return f"Fibonacci({n}) = 1"

    a, b = 1, 1
    for _ in range(n - 2):
        a, b = b, a + b

    return f"Fibonacci({n}) = {b}"


@mcp.tool()
def reverse_text(text: str) -> str:
    """Reverse the given text.

    Args:
        text: The text to reverse

    Returns:
        The reversed text
    """
    return f"Reversed: {text[::-1]}"


@mcp.tool()
def count_words(text: str) -> str:
    """Count the number of words in the given text.

    Args:
        text: The text to analyze

    Returns:
        Word count and character count
    """
    words = len(text.split())
    chars = len(text)
    return f"Words: {words}, Characters: {chars}"


@mcp.tool()
async def slow_fibonacci(n: int, ctx: Optional[Context] = None) -> str:
    """Calculate Fibonacci number with progress updates.

    This tool demonstrates streaming progress notifications while computing.
    It sends progress updates as it calculates the Fibonacci sequence.

    Args:
        n: The position in the Fibonacci sequence (must be between 1 and 30)

    Returns:
        The nth Fibonacci number with computation details
    """
    import asyncio

    if n <= 0:
        return "Error: n must be positive"
    if n > 30:
        return "Error: n too large (max 30 for this slow version)"

    # Send initial progress
    if ctx:
        try:
            await ctx.report_progress(progress=0, total=100)
            logger.info("[slow_fibonacci] Sent progress: 0/100")
        except Exception as e:
            logger.error(f"[slow_fibonacci] Failed to send initial progress: {e}")
    else:
        logger.warning("[slow_fibonacci] No context available for progress updates")

    # Calculate with progress updates
    result_parts = []
    if n == 1 or n == 2:
        result_parts.append("F(1) = 1, F(2) = 1")
        a, b = 1, 1
    else:
        a, b = 1, 1
        result_parts.append("Starting: F(1) = 1, F(2) = 1")

        for i in range(3, n + 1):
            # Simulate slow computation
            await asyncio.sleep(0.5)

            # Calculate next Fibonacci number
            a, b = b, a + b
            result_parts.append(f"F({i}) = {b}")

            # Send progress update
            progress = int((i / n) * 100)
            if ctx:
                try:
                    await ctx.report_progress(progress=progress, total=100)
                    logger.info(
                        f"[slow_fibonacci] Sent progress: {progress}/100 (F({i}) = {b})"
                    )
                except Exception as e:
                    logger.error(f"[slow_fibonacci] Failed to send progress: {e}")

    # Send final progress
    if ctx:
        try:
            await ctx.report_progress(progress=100, total=100)
            logger.info("[slow_fibonacci] Sent final progress: 100/100")
        except Exception as e:
            logger.error(f"[slow_fibonacci] Failed to send final progress: {e}")

    computation_log = "\n".join(result_parts)
    return f"Fibonacci({n}) = {b}\n\nComputation log:\n{computation_log}"


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
    logger.info("To add this server to SpaceBridge:")
    logger.info("  1. Navigate to /console/tools in SpaceBridge UI")
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
