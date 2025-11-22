"""Factory for creating tracker clients."""

import logging
from typing import Any, Dict, Optional

from .base import BaseTracker
from .github import GitHubTracker
from .gitlab import GitLabTracker
from .jira import JiraTracker

logger = logging.getLogger(__name__)


async def create_tracker_client(
    tracker_type: str,
    tracker_id: str,
    api_key: str,
    connection_details: Dict[str, Any],
) -> Optional[BaseTracker]:
    """Create a tracker client.

    Args:
        tracker_type: Type of tracker ("github", "jira", "gitlab").
        tracker_id: ID of the tracker in the database (UUID string).
        api_key: API key or token for the tracker.
        connection_details: Connection details for the tracker.

    Returns:
        A tracker client or None if the tracker type is not supported.
    """
    try:
        if tracker_type == "github":
            return GitHubTracker(tracker_id, api_key, connection_details)
        elif tracker_type == "gitlab":
            return GitLabTracker(tracker_id, api_key, connection_details)
        elif tracker_type == "jira":
            return JiraTracker(tracker_id, api_key, connection_details)
        else:
            logger.warning(f"Unsupported tracker type: {tracker_type}")
            return None
    except Exception as e:
        logger.exception(f"Failed to create tracker client: {e}")
        return None
