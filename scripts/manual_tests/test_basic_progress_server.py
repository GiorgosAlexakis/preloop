"""Minimal FastMCP server with progress reporting from docs."""

import asyncio
from typing import Optional

from fastmcp import Context, FastMCP

mcp = FastMCP("progress-test-server")


@mcp.tool()
async def backup_database(ctx: Optional[Context] = None) -> str:
    """Backup database with progress reporting (from FastMCP docs)."""
    tables = ["users", "orders", "products", "inventory", "logs"]

    for i, table in enumerate(tables):
        # Simulate work
        await asyncio.sleep(1)

        # Report progress
        if ctx:
            await ctx.info(f"Backing up table: {table}")
            await ctx.report_progress(progress=i + 1, total=len(tables))

    return f"Successfully backed up {len(tables)} tables"


if __name__ == "__main__":
    print("=" * 70)
    print("Starting minimal progress test server on http://localhost:8002")
    print("=" * 70)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8002)
