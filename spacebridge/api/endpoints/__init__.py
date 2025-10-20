"""API endpoints for SpaceBridge."""

# Removed potentially problematic self-import:
# from spacebridge.api.endpoints import comments, health, issues, organizations, projects

# Define __all__ to explicitly list all endpoint modules in this package
__all__ = [
    "approval_requests",
    "comments",
    "health",
    "issues",
    "issue_compliance",
    "issue_dependencies",
    "issue_duplicates",
    "mcp_servers",
    "organizations",
    "projects",
    "public_approval",
    "search",
    "tools",
    "trackers",
    "version",
    "webhooks",
    "flows",
    "ai_models",
    "billing",
    "websockets",
]
