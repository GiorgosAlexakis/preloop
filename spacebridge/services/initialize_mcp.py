"""Initialize and configure the DynamicFastMCP server with all default tools."""

import logging

from spacebridge.services.dynamic_fastmcp import (
    DynamicFastMCP,
    create_dynamic_mcp_server,
)

logger = logging.getLogger(__name__)


def initialize_mcp_with_tools() -> DynamicFastMCP:
    """Initialize DynamicFastMCP and register all default tools.

    This function creates a DynamicFastMCP instance and registers all 6 default
    tools from the current MCP implementation.

    Returns:
        Configured DynamicFastMCP instance
    """
    # Create server
    mcp = create_dynamic_mcp_server()

    # Import the MCP router functions (existing tool implementations)
    from spacebridge.api.endpoints import mcp as mcp_router

    # Register Tool 1: get_issue
    @mcp.tool()
    async def get_issue(issue: str) -> str:
        """Get detailed information about an issue by its identifier (URL, key, or ID)."""
        result = await mcp_router.get_issue(issue)
        return result.model_dump_json()

    # Register Tool 2: create_issue
    @mcp.tool()
    async def create_issue(
        project: str,
        title: str,
        description: str,
        labels: list[str] | None = None,
        assignee: str | None = None,
        priority: str | None = None,
        status: str | None = None,
    ) -> str:
        """Create a new issue in a project."""
        result = await mcp_router.create_issue(
            project=project,
            title=title,
            description=description,
            labels=labels,
            assignee=assignee,
            priority=priority,
            status=status,
        )
        return result.model_dump_json()

    # Register Tool 3: update_issue
    @mcp.tool()
    async def update_issue(
        issue: str,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
    ) -> str:
        """Update an existing issue."""
        result = await mcp_router.update_issue(
            issue=issue,
            title=title,
            description=description,
            status=status,
            priority=priority,
            assignee=assignee,
            labels=labels,
        )
        return result.model_dump_json()

    # Register Tool 4: search
    @mcp.tool()
    async def search(
        query: str,
        project: str | None = None,
        limit: int = 10,
    ) -> str:
        """Search for issues and comments using similarity or fulltext search."""
        result = await mcp_router.search(
            query=query,
            project=project,
            limit=limit,
        )
        return result.model_dump_json()

    # Register Tool 5: estimate_compliance
    @mcp.tool()
    async def estimate_compliance(
        issues: list[str],
        compliance_metric: str = "DoR",
    ) -> str:
        """Estimate compliance for a list of issues provided as URLs or issue keys."""
        result = await mcp_router.estimate_compliance(
            issues=issues,
            compliance_metric=compliance_metric,
        )
        return result.model_dump_json()

    # Register Tool 6: improve_compliance
    @mcp.tool()
    async def improve_compliance(
        issues: list[str],
        compliance_metric: str = "DoR",
    ) -> str:
        """Get suggestions to improve compliance for a list of issues."""
        result = await mcp_router.improve_compliance(
            issues=issues,
            compliance_metric=compliance_metric,
        )
        return result.model_dump_json()

    logger.info("All 6 default tools registered with DynamicFastMCP")

    return mcp
