"""API endpoints for SpaceBridge."""

# Removed potentially problematic self-import:
# from spacebridge.api.endpoints import comments, health, issues, organizations, projects

# Define __all__ to explicitly list all endpoint modules in this package
__all__ = [
    "account",
    "approval_requests",
    "comments",
    "features",
    "health",
    "invitations",
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
    "teams",
    "tools",
    "trackers",
    "users",
    "version",
    "webhooks",
    "flows",
    "ai_models",
    "billing",
    "websockets",
]
