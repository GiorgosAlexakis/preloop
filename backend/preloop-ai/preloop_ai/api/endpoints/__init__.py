"""API endpoints for Preloop AI."""

# Removed potentially problematic self-import:
# from preloop_ai.api.endpoints import comments, health, issues, organizations, projects

# Define __all__ to explicitly list all endpoint modules in this package
__all__ = [
    "account",
    "approval_requests",
    "comments",
    "features",
    "health",
    "impersonation",
    "issues",
    "issue_compliance",
    "issue_dependencies",
    "issue_duplicates",
    "mcp_servers",
    "notification_preferences",
    "organizations",
    "projects",
    "public_approval",
    "roles",
    "search",
    "tools",
    "trackers",
    "version",
    "webhooks",
    "flows",
    "ai_models",
    "websockets",
]
