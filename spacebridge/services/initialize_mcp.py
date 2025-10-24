"""Initialize and configure the DynamicFastMCP server with all default tools."""

import logging
from typing import Optional

from fastmcp import Context

from spacebridge.services.approval_helper import require_approval
from spacebridge.services.dynamic_fastmcp import (
    DynamicFastMCP,
    create_dynamic_mcp_server,
)

logger = logging.getLogger(__name__)


class CancelScopeErrorFilter(logging.Filter):
    """Filter out benign cancel scope errors from nested MCP sessions.

    When proxying tools to external MCP servers, we create nested MCP sessions
    (SpaceBridge as server, MCPClient as client). This causes harmless cancel
    scope cleanup errors that don't affect functionality. This filter suppresses
    those specific errors to avoid log spam.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress the log record, True to keep it."""
        # Filter out the specific cancel scope error from session cleanup
        if record.levelname == "ERROR" and "crashed" in record.getMessage():
            # Check if this is the benign cancel scope error
            if hasattr(record, "exc_info") and record.exc_info:
                # The exception might be an ExceptionGroup, need to check recursively
                exc = record.exc_info[1]
                if self._contains_cancel_scope_error(exc):
                    return False  # Suppress this specific error
        return True  # Keep all other log records

    def _contains_cancel_scope_error(self, exc: BaseException) -> bool:
        """Check if exception or its nested exceptions contain cancel scope error."""
        # Check the exception message
        exc_str = str(exc)
        if "Attempted to exit a cancel scope" in exc_str:
            return True

        # Check if it's an ExceptionGroup and recurse into sub-exceptions
        if hasattr(exc, "exceptions"):
            for sub_exc in exc.exceptions:
                if self._contains_cancel_scope_error(sub_exc):
                    return True

        # Check __cause__ and __context__
        if exc.__cause__ and self._contains_cancel_scope_error(exc.__cause__):
            return True
        if exc.__context__ and self._contains_cancel_scope_error(exc.__context__):
            return True

        return False


def initialize_mcp_with_tools() -> DynamicFastMCP:
    """Initialize DynamicFastMCP and register all default tools.

    This function creates a DynamicFastMCP instance and registers all 6 default
    tools from the current MCP implementation.

    Returns:
        Configured DynamicFastMCP instance
    """
    # Install filter to suppress benign cancel scope errors from nested MCP sessions
    mcp_manager_logger = logging.getLogger("mcp.server.streamable_http_manager")
    cancel_scope_filter = CancelScopeErrorFilter()
    mcp_manager_logger.addFilter(cancel_scope_filter)
    logger.info("Installed cancel scope error filter for nested MCP session cleanup")

    # Create server
    mcp = create_dynamic_mcp_server()

    # Import the MCP router functions (existing tool implementations)
    from spacebridge.api.endpoints import mcp as mcp_router

    # Register Tool 1: get_issue
    @mcp.tool()
    async def get_issue(issue: str, ctx: Optional[Context] = None) -> str:
        """Get detailed information about an issue by its identifier (URL, key, or ID)."""
        # Get user context for approval checking
        from spacebridge.services.dynamic_fastmcp_http import get_current_user_context

        user_context = get_current_user_context()

        if not user_context:
            return "Error: No user context available"

        # Check approval with streaming
        approved, error = await require_approval(
            tool_name="get_issue",
            tool_source="builtin",
            account_id=user_context.account_id,
            arguments={"issue": issue},
            ctx=ctx,
        )

        if not approved:
            return error

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
        ctx: Optional[Context] = None,
    ) -> str:
        """Create a new issue in a project."""
        # Get user context for approval checking
        from spacebridge.services.dynamic_fastmcp_http import get_current_user_context

        user_context = get_current_user_context()

        if not user_context:
            return "Error: No user context available"

        # Check approval with streaming
        approved, error = await require_approval(
            tool_name="create_issue",
            tool_source="builtin",
            account_id=user_context.account_id,
            arguments={
                "project": project,
                "title": title,
                "description": description,
                "labels": labels,
                "assignee": assignee,
                "priority": priority,
                "status": status,
            },
            ctx=ctx,
        )

        if not approved:
            return error

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
        ctx: Optional[Context] = None,
    ) -> str:
        """Update an existing issue."""
        # Get user context for approval checking
        from spacebridge.services.dynamic_fastmcp_http import get_current_user_context

        user_context = get_current_user_context()

        if not user_context:
            return "Error: No user context available"

        # Check approval with streaming
        approved, error = await require_approval(
            tool_name="update_issue",
            tool_source="builtin",
            account_id=user_context.account_id,
            arguments={
                "issue": issue,
                "title": title,
                "description": description,
                "status": status,
                "priority": priority,
                "assignee": assignee,
                "labels": labels,
            },
            ctx=ctx,
        )

        if not approved:
            return error

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
        ctx: Optional[Context] = None,
    ) -> str:
        """Search for issues and comments using similarity or fulltext search."""
        # Get user context for approval checking
        from spacebridge.services.dynamic_fastmcp_http import get_current_user_context

        user_context = get_current_user_context()

        if not user_context:
            return "Error: No user context available"

        # Check approval with streaming
        approved, error = await require_approval(
            tool_name="search",
            tool_source="builtin",
            account_id=user_context.account_id,
            arguments={"query": query, "project": project, "limit": limit},
            ctx=ctx,
        )

        if not approved:
            return error

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
        ctx: Optional[Context] = None,
    ) -> str:
        """Estimate compliance for a list of issues provided as URLs or issue keys."""
        # Get user context for approval checking
        from spacebridge.services.dynamic_fastmcp_http import get_current_user_context

        user_context = get_current_user_context()

        if not user_context:
            return "Error: No user context available"

        # Debug: Check if Context is being passed
        logger.info(f"estimate_compliance called with Context: {ctx is not None}")
        if ctx:
            logger.info(f"Context type: {type(ctx)}")
            logger.info(
                f"Context has report_progress: {hasattr(ctx, 'report_progress')}"
            )

        # Check approval with streaming
        approved, error = await require_approval(
            tool_name="estimate_compliance",
            tool_source="builtin",
            account_id=user_context.account_id,
            arguments={"issues": issues, "compliance_metric": compliance_metric},
            ctx=ctx,
        )

        if not approved:
            return error

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
        ctx: Optional[Context] = None,
    ) -> str:
        """Get suggestions to improve compliance for a list of issues."""
        # Get user context for approval checking
        from spacebridge.services.dynamic_fastmcp_http import get_current_user_context

        user_context = get_current_user_context()

        if not user_context:
            return "Error: No user context available"

        # Check approval with streaming
        approved, error = await require_approval(
            tool_name="improve_compliance",
            tool_source="builtin",
            account_id=user_context.account_id,
            arguments={"issues": issues, "compliance_metric": compliance_metric},
            ctx=ctx,
        )

        if not approved:
            return error

        result = await mcp_router.improve_compliance(
            issues=issues,
            compliance_metric=compliance_metric,
        )
        return result.model_dump_json()

    # Register TEST TOOL: test_progress (simple progress without approval)
    @mcp.tool()
    async def test_progress(count: int = 5, ctx: Optional[Context] = None) -> str:
        """Test tool to verify progress reporting works in DynamicFastMCP."""
        import asyncio

        logger.info(f"🔧 test_progress called with Context: {ctx is not None}")

        if not ctx:
            logger.warning("❌ No Context available in test_progress!")
            return "No Context available - progress reporting not possible"

        logger.info(f"✅ Context available: {type(ctx)}")
        logger.info(f"   Has report_progress: {hasattr(ctx, 'report_progress')}")

        items = []
        for i in range(count):
            await asyncio.sleep(0.5)
            items.append(f"item_{i + 1}")

            # Report progress
            try:
                logger.info(f"   Calling ctx.report_progress({i + 1}, {count})...")
                await ctx.report_progress(
                    progress=i + 1,
                    total=count,
                    message=f"Processing item {i + 1}/{count}",
                )
                logger.info(f"   ✅ Progress reported: {i + 1}/{count}")
            except Exception as e:
                logger.error(f"   ❌ Failed to report progress: {e}", exc_info=True)

        return f"Processed {count} items: {', '.join(items)}"

    logger.info("All 6 default tools + test_progress registered with DynamicFastMCP")

    return mcp
