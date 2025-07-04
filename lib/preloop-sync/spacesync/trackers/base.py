"""
Base tracker interface for SpaceSync.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

# Import the configurable max length from the Issue model
from spacemodels.models.issue import DESCRIPTION_MAX_LENGTH
from spacemodels.models.project import Project

logger = logging.getLogger(__name__)


class BaseTracker(ABC):
    """Base class for all tracker implementations."""

    def __init__(
        self, tracker_id: str, api_key: str, connection_details: Dict[str, Any]
    ):
        """
        Initialize the tracker.

        Args:
            tracker_id: ID of the tracker in the database (UUID string).
            api_key: API key or token for the tracker.
            connection_details: Connection details for the tracker.
        """
        self.tracker_id = tracker_id
        self.api_key = api_key
        self.connection_details = connection_details

    @abstractmethod
    def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Get organizations from the tracker.

        Returns:
            List of organization data dictionaries.
            Each dictionary should contain at least:
            - id: External ID of the organization
            - name: Name of the organization
            - url: URL to the organization (optional)
        """
        pass

    @abstractmethod
    def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get projects for an organization from the tracker.

        Args:
            organization_id: External ID of the organization.

        Returns:
            List of project data dictionaries.
            Each dictionary should contain at least:
            - id: External ID of the project
            - name: Name of the project
            - description: Description of the project (optional)
            - url: URL to the project (optional)
        """
        pass

    @abstractmethod
    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a project from the tracker.

        Args:
            organization_id: External ID of the organization.
            project_id: External ID of the project.
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries.
            Each dictionary should contain at least:
            - id: External ID of the issue
            - title: Title of the issue
            - description: Description/body of the issue
            - state: State of the issue (open, closed, etc.)
            - created_at: Creation datetime
            - updated_at: Last update datetime
            - labels: List of label strings (optional)
            - assignees: List of assignee names (optional)
            - url: URL to the issue (optional)
            - comments: List of comment data dictionaries.
                Each comment dict should contain at least:
                - id: External ID of the comment
                - body: Text content of the comment
                - author_id: External ID of the author (if available, from tracker)
                - created_at: Creation datetime of the comment
                - updated_at: Last update datetime of the comment
        """
        pass

    def transform_organization(self, org_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform organization data to a format that can be stored in the database.

        Args:
            org_data: Organization data from the tracker.

        Returns:
            Transformed organization data ready for database storage.
        """
        return {
            "identifier": org_data["id"],
            "name": org_data["name"],
            "tracker_id": self.tracker_id,
        }

    def transform_project(
        self, proj_data: Dict[str, Any], organization_id: str
    ) -> Dict[str, Any]:
        """
        Transform project data to a format that can be stored in the database.

        Args:
            proj_data: Project data from the tracker.
            organization_id: Database ID of the organization (UUID string).

        Returns:
            Transformed project data ready for database storage.
        """
        return {
            "organization_id": organization_id,
            "identifier": proj_data["id"],
            "name": proj_data["name"],
            "description": proj_data.get("description", ""),
            "meta_data": {
                "url": proj_data.get("url", ""),
                "external_id": proj_data.get("id", ""),
                "source": "spacesync",
            },
        }

    def transform_issue(
        self, issue_data: Dict[str, Any], project: Project
    ) -> Dict[str, Any]:
        """
        Transform issue data to a format that can be stored in the database.
        It should also include transformed comment data under the 'comments' key.

        Args:
            issue_data: Issue data from the tracker.
            project: The Project object from the database.

        Returns:
            Transformed issue data ready for database storage, including comments.
        """
        # Get issue status from data or default to "open"
        status = issue_data.get("state", "open")
        # Map common status values to standardized ones
        if status.lower() in ["closed", "done", "completed", "fixed"]:
            status = "closed"
        elif status.lower() in ["open", "new", "todo", "to do"]:
            status = "open"
        # Add more mappings as needed

        # Get issue type or default to "task"
        issue_type = issue_data.get("type", "task")
        # Map common types to standardized ones
        if issue_type.lower() in ["bug", "defect", "error"]:
            issue_type = "bug"
        elif issue_type.lower() in ["feature", "enhancement", "improvement"]:
            issue_type = "feature"

        # Convert datetime objects to ISO format strings for JSON serialization
        last_updated = issue_data.get("updated_at")
        if isinstance(last_updated, datetime):
            last_updated = last_updated.isoformat()

        created_at = issue_data.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        # Get description and truncate if necessary to avoid DB errors
        description = issue_data.get("description", "")
        original_length = len(description) if description else 0

        if description and len(description) > DESCRIPTION_MAX_LENGTH:
            # Truncate to the max length, with an indicator
            description = (
                description[: DESCRIPTION_MAX_LENGTH - 25] + "... [content truncated]"
            )
            logger.info(
                f"Truncated issue description from {original_length} to {len(description)} characters. "
                f"Set ISSUE_DESCRIPTION_MAX_LENGTH env var to increase (current: {DESCRIPTION_MAX_LENGTH})"
            )

        issue_url = issue_data.get("url", "")

        transformed = {
            "project_id": project.id,
            "external_id": issue_data.get("id", issue_data.get("external_id")),
            "key": issue_data.get("key"),
            "title": issue_data["title"],
            "description": description,
            "status": status,
            "issue_type": issue_type,
            "priority": issue_data.get("priority", None),
            "updated_at": issue_data.get("updated_at"),
            "last_updated_external": issue_data.get(
                "updated_at"
            ),
            "external_url": issue_url,
            "last_synced": datetime.now(),
            "meta_data": {
                "labels": issue_data.get("labels", []),
                "assignees": issue_data.get("assignees", []),
                "url": issue_url,
                "external_url": issue_url,
                "external_created_at": created_at,
                "external_updated_at": last_updated,
                "source": "spacesync",
            },
            "tracker_id": self.tracker_id,
            "comments": issue_data.get("comments", []),
        }

        return transformed

    def transform_comment(
        self, comment_data: Dict[str, Any], issue_db_id: str, author_db_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transform comment data to a format that can be stored in the database.

        Args:
            comment_data: Comment data from the tracker.
            issue_db_id: Database ID of the parent issue.
            author_db_id: Database ID of the comment author (if known/created).

        Returns:
            Transformed comment data ready for database storage.
        """
        external_id = str(comment_data.get("id"))
        return {
            "issue_id": issue_db_id,
            "external_id": external_id,
            "author_id": None,
            "body": comment_data.get("body", ""),
            "type": "issue",
            "meta_data": {
                "comment_id": external_id,
                "external_author_id": str(comment_data.get("author_id")) if comment_data.get("author_id") else None,
                "url": comment_data.get("url"),
                "source": "spacesync",
            },
            "updated_at": comment_data.get("updated_at"),
            "created_at": comment_data.get("created_at"),
        }

    @abstractmethod
    def register_webhook(self, **kwargs: Any) -> bool:
        """
        Register a webhook for the tracker.
        Specific arguments will depend on the tracker type.

        Args:
            **kwargs: Arbitrary keyword arguments specific to the tracker implementation.
                      For example, for GitHub/GitLab, it might be `org_identifier`, `webhook_url`, `secret`.
                      For Jira, it might be `project_key`, `webhook_url`, `secret`, `events`.

        Returns:
            True if registration was successful or webhook already exists, False otherwise.
        """
        pass

    @abstractmethod
    def unregister_webhook(self, **kwargs: Any) -> bool:
        """
        Unregister a webhook for the tracker.
        Specific arguments will depend on the tracker type.

        Args:
            **kwargs: Arbitrary keyword arguments specific to the tracker implementation.
                      For example, for Jira, it might be `project_key`, and either `webhook_url` or `webhook_id`.

        Returns:
            True if unregistration was successful, False otherwise.
        """
        pass

        @abstractmethod
        def unregister_all_webhooks(self, webhook_url_pattern: Optional[str] = None) -> Dict[str, int]:
            """
            Unregister all webhooks, optionally matching a URL pattern.

            This method should iterate through all relevant scopes (e.g., organizations,
            projects, groups) for the tracker and attempt to unregister webhooks.

            Args:
                webhook_url_pattern: If provided, only unregister webhooks whose URL
                                     matches this pattern. Otherwise, the tracker might
                                     try to identify and remove all webhooks it
                                     previously registered (e.g., by a known description
                                     or a URL pattern based on SPACEBRIDGE_URL).

            Returns:
                A dictionary summarizing the actions taken, e.g.,
                {"unregistered": count, "failed": count, "not_found": count}.
            """
            pass


    if __name__ == "__main__":
        pass
