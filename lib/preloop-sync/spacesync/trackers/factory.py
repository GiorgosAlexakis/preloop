"""
Tracker factory for SpaceSync.
"""

from typing import Dict, Any

from spacemodels.models import Tracker
from ..exceptions import ConfigurationError
from .base import BaseTracker
from .github import GitHubTracker
from .gitlab import GitLabTracker
from .jira import JiraTracker


class TrackerFactory:
    """Factory class for creating tracker instances."""

    @staticmethod
    def create_tracker(tracker: Tracker) -> BaseTracker:
        """
        Create a tracker instance based on the tracker type.

        Args:
            tracker: Tracker object from the database.

        Returns:
            BaseTracker: An instance of the appropriate tracker subclass.

        Raises:
            ConfigurationError: If the tracker type is not supported.
        """
        tracker_type = tracker.tracker_type.lower()
        
        if tracker_type == "github":
            return GitHubTracker(
                tracker_id=tracker.id,
                api_key=tracker.api_key,
                connection_details=tracker.connection_details
            )
        elif tracker_type == "gitlab":
            return GitLabTracker(
                tracker_id=tracker.id,
                api_key=tracker.api_key,
                connection_details=tracker.connection_details
            )
        elif tracker_type == "jira":
            return JiraTracker(
                tracker_id=tracker.id,
                api_key=tracker.api_key,
                connection_details=tracker.connection_details
            )
        else:
            raise ConfigurationError(f"Unsupported tracker type: {tracker_type}")

    @classmethod
    def create_trackers_for_account(cls, trackers: list[Tracker]) -> Dict[int, BaseTracker]:
        """
        Create tracker instances for all trackers associated with an account.

        Args:
            trackers: List of Tracker objects from the database.

        Returns:
            Dict mapping tracker IDs to tracker instances.
        """
        tracker_instances = {}
        
        for tracker in trackers:
            tracker_instances[tracker.id] = cls.create_tracker(tracker)
            
        return tracker_instances
