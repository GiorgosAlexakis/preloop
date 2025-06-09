"""
Jira tracker implementation for SpaceSync.
"""

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

import requests

from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from ..utils import retry
from .base import BaseTracker

logger = logging.getLogger(__name__)

class JiraTracker(BaseTracker):
    """Jira tracker implementation."""

    def __init__(
        self, tracker_id: str, api_key: str, connection_details: Dict[str, Any]
    ):
        """
        Initialize the Jira tracker.

        Args:
            tracker_id: ID of the tracker in the database (UUID string).
            api_key: Jira API token (or password for Basic Auth).
            connection_details: Connection details including:
                - jira_url: URL of the Jira instance
                - username: Jira username for authentication
                - url: Alternative field for Jira URL (for compatibility)
        """
        super().__init__(tracker_id, api_key, connection_details)

        # Check for Jira URL in either jira_url or url field
        jira_url = connection_details.get("jira_url")
        if not jira_url:
            jira_url = connection_details.get("url")

        if not jira_url:
            raise ValueError(
                "Jira URL is required in connection_details (either 'jira_url' or 'url')"
            )

        if "username" not in connection_details:
            raise ValueError("Jira username is required in connection_details")

        self.jira_url = jira_url.rstrip("/")
        self.username = connection_details["username"]

        # Basic authentication header
        auth_str = f"{self.username}:{api_key}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }

    @retry(max_attempts=3, exceptions=(TrackerConnectionError, TrackerResponseError))
    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Make a request to the Jira API.

        Args:
            endpoint: API endpoint to request.
            params: Query parameters.

        Returns:
            JSON response data.

        Raises:
            TrackerAuthenticationError: If authentication fails.
            TrackerConnectionError: If connection fails.
            TrackerResponseError: If response is invalid.
        """
        try:
            url = f"{self.jira_url}/rest/api/2/{endpoint.lstrip('/')}"
            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 401:
                raise TrackerAuthenticationError("Jira authentication failed")
            elif response.status_code >= 400:
                raise TrackerResponseError(
                    f"Jira API error: {response.status_code} - {response.text}"
                )

            return response.json()
        except requests.RequestException as e:
            raise TrackerConnectionError(f"Jira connection error: {str(e)}")

    def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Get organizations from Jira.

        In Jira, there's no direct concept of "organizations" like in GitHub/GitLab.
        Instead, we return a single organization representing the Jira instance.

        Returns:
            List containing a single organization data dictionary.
        """
        # Extract domain name from Jira URL for the organization name
        import re

        domain_match = re.search(r"https?://([^/]+)", self.jira_url)
        org_name = domain_match.group(1) if domain_match else "Jira Instance"

        return [{"id": org_name, "name": org_name, "url": self.jira_url}]

    def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get projects from Jira.

        Args:
            organization_id: Not used for Jira, but kept for interface consistency.

        Returns:
            List of project data dictionaries.
        """
        # Get all accessible projects
        projects_data = self._make_request("project")

        projects = []
        for project in projects_data:
            projects.append(
                {
                    "id": project["key"],
                    "name": project["name"],
                    "description": project.get("description", ""),
                    "url": f"{self.jira_url}/projects/{project['key']}",
                }
            )

        return projects

    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a project from Jira, including their comments.

        Args:
            organization_id: Not used for Jira, but kept for interface consistency.
            project_id: Jira project key.
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries, each including a 'comments' list.
        """
        jql = f"project = {project_id}"
        if since:
            jql += f" AND updated >= '{since.strftime('%Y-%m-%d %H:%M')}'"

        params = {
            "jql": jql,
            "maxResults": 100,
            "fields": "id,key,summary,description,status,created,updated,labels,assignee,issuetype,comment",
        }

        try:
            issues_response = self._make_request("search", params)
        except TrackerResponseError as e:
            logger.error(f"Failed to get Jira issues for project {project_id}: {e}")
            return []

        processed_issues = []
        for issue_data in issues_response.get("issues", []):
            try:
                created_dt = datetime.strptime(
                    issue_data["fields"]["created"], "%Y-%m-%dT%H:%M:%S.%f%z"
                ).replace(tzinfo=None)
                updated_dt = datetime.strptime(
                    issue_data["fields"]["updated"], "%Y-%m-%dT%H:%M:%S.%f%z"
                ).replace(tzinfo=None)
            except (ValueError, TypeError) as ve:
                logger.warning(f"Could not parse datetime for Jira issue {issue_data.get('key')}: {ve}. Using fallback.")
                created_dt = datetime.now()
                if isinstance(issue_data["fields"].get("created"), str):
                    try:
                        created_dt = datetime.strptime(issue_data["fields"]["created"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                    except ValueError:
                        pass
                updated_dt = created_dt

            assignee_list = []
            if issue_data["fields"].get("assignee"):
                assignee_list = [issue_data["fields"]["assignee"].get("displayName", issue_data["fields"]["assignee"].get("name"))]

            # Process comments
            comments_transformed = []
            if issue_data["fields"].get("comment") and issue_data["fields"]["comment"].get("comments"):
                raw_comments = issue_data["fields"]["comment"]["comments"]
                for comment_item in raw_comments:
                    try:
                        comment_created_dt = datetime.strptime(comment_item["created"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                        comment_updated_dt = datetime.strptime(comment_item["updated"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                    except (ValueError, TypeError) as ve:
                        logger.warning(f"Could not parse datetime for Jira comment {comment_item.get('id')} on issue {issue_data.get('key')}: {ve}. Using fallback.")
                        comment_created_dt = datetime.now()
                        if isinstance(comment_item.get("created"), str):
                            try:
                                comment_created_dt = datetime.strptime(comment_item["created"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                            except ValueError:
                                pass
                        comment_updated_dt = comment_created_dt

                    author = comment_item.get("author", {})
                    author_id = author.get("accountId") or author.get("key") or author.get("name")

                    comments_transformed.append({
                        "id": str(comment_item["id"]),
                        "body": comment_item.get("body", "") or "",
                        "author_id": str(author_id) if author_id else None,
                        "created_at": comment_created_dt,
                        "updated_at": comment_updated_dt,
                        "url": f"{self.jira_url}/browse/{issue_data['key']}?focusedCommentId={comment_item['id']}#comment-{comment_item['id']}"
                    })

            # Jira API might return None for description, ensure it's a string
            description_text = issue_data["fields"].get("description", "")
            if description_text is None:
                description_text = ""

            processed_issues.append(
                {
                    "id": issue_data["id"],  # Add this line for consistency with BaseTracker
                    "external_id": issue_data["id"],
                    "key": issue_data["key"],
                    "title": issue_data["fields"]["summary"],
                    "description": description_text,
                    "state": issue_data["fields"]["status"]["name"].lower(),
                    "created_at": created_dt,
                    "updated_at": updated_dt,
                    "labels": issue_data["fields"].get("labels", []),
                    "assignees": assignee_list,
                    "url": f"{self.jira_url}/browse/{issue_data['key']}",
                    "comments": comments_transformed,
                }
            )
        return processed_issues

    def transform_project(
        self, proj_data: Dict[str, Any], organization_id: str
    ) -> Dict[str, Any]:
        """
        Transform Jira project data, setting the slug to the project identifier (key).

        Args:
            proj_data: Project data from the Jira tracker.
            organization_id: Database ID of the organization (UUID string).

        Returns:
            Transformed project data ready for database storage.
        """
        # Get the base transformation from the parent class
        transformed_data = super().transform_project(proj_data, organization_id)

        # Set the slug to be the project identifier (which is the Jira project key)
        if "identifier" in transformed_data:
            transformed_data["slug"] = transformed_data["identifier"]

        return transformed_data
