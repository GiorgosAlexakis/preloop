"""API endpoints for SpaceBridge."""

# Removed potentially problematic self-import:
# from spacebridge.api.endpoints import comments, health, issues, organizations, projects

# Define __all__ to explicitly list all endpoint modules in this package
__all__ = [
    "comments",
    "health",
    "issues",
    "issue_compliance",
    "mcp_servers",
    "organizations",
    "projects",
    "search",  # Added new search endpoint
    "trackers",
    "version",
]
