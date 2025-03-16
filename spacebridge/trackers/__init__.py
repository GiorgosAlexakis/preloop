"""Issue tracker integrations for SpaceBridge."""

from spacebridge.trackers.base import (
    Issue,
    IssueComment,
    IssueCreate,
    IssueFilter,
    IssuePriority,
    IssueRelation,
    IssueStatus,
    IssueUpdate,
    IssueUser,
    ProjectMetadata,
    TrackerConnection,
    TrackerInterface,
)
from spacebridge.trackers.factory import TrackerFactory
from spacebridge.trackers.github import GitHubClient

__all__ = [
    "Issue",
    "IssueComment",
    "IssueCreate",
    "IssueFilter",
    "IssuePriority",
    "IssueRelation",
    "IssueStatus", 
    "IssueUpdate",
    "IssueUser",
    "ProjectMetadata",
    "TrackerConnection",
    "TrackerInterface",
    "TrackerFactory",
    "GitHubClient",
]