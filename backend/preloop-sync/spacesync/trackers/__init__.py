"""
Tracker abstraction layer for SpaceSync.
"""

from .base import BaseTracker
from .factory import create_tracker_client
from .github import GitHubTracker
from .gitlab import GitLabTracker
from .jira import JiraTracker

__all__ = [
    "BaseTracker",
    "create_tracker_client",
    "GitHubTracker",
    "GitLabTracker",
    "JiraTracker",
]
