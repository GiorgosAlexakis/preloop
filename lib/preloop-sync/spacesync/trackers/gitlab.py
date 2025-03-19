"""
GitLab tracker implementation for SpaceSync.
"""

import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..config import logger
from ..exceptions import TrackerAuthenticationError, TrackerConnectionError, TrackerResponseError
from ..utils import retry
from .base import BaseTracker


class GitLabTracker(BaseTracker):
    """GitLab tracker implementation."""

    API_BASE_URL = "https://gitlab.com/api/v4"

    def __init__(self, tracker_id: int, api_key: str, connection_details: Dict[str, Any]):
        """
        Initialize the GitLab tracker.

        Args:
            tracker_id: ID of the tracker in the database.
            api_key: GitLab API token.
            connection_details: Connection details including GitLab instance URL (optional).
        """
        super().__init__(tracker_id, api_key, connection_details)
        
        # Allow custom GitLab instance URL
        if "gitlab_url" in connection_details:
            self.api_base_url = f"{connection_details['gitlab_url'].rstrip('/')}/api/v4"
        else:
            self.api_base_url = self.API_BASE_URL
            
        self.headers = {"Private-Token": api_key}

    @retry(max_attempts=3, exceptions=(TrackerConnectionError, TrackerResponseError))
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Make a request to the GitLab API.

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
            url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 401:
                raise TrackerAuthenticationError("GitLab authentication failed")
            elif response.status_code >= 400:
                raise TrackerResponseError(
                    f"GitLab API error: {response.status_code} - {response.text}"
                )
                
            return response.json()
        except requests.RequestException as e:
            raise TrackerConnectionError(f"GitLab connection error: {str(e)}")

    def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Get organizations (groups) from GitLab.

        Returns:
            List of organization data dictionaries.
        """
        # For GitLab, organizations are groups
        groups_data = self._make_request("groups", {"per_page": 100})
        
        organizations = []
        for group in groups_data:
            organizations.append({
                "id": str(group["id"]),
                "name": group["name"],
                "url": group["web_url"]
            })
            
        return organizations

    def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get projects for a group from GitLab.

        Args:
            organization_id: GitLab group ID.

        Returns:
            List of project data dictionaries.
        """
        # Get projects for the specified group
        projects_data = self._make_request(f"groups/{organization_id}/projects", {"per_page": 100})
        
        projects = []
        for project in projects_data:
            projects.append({
                "id": str(project["id"]),
                "name": project["name"],
                "description": project["description"] or "",
                "url": project["web_url"]
            })
            
        return projects

    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a project from GitLab.

        Args:
            organization_id: GitLab group ID (not used in API call but kept for interface consistency).
            project_id: GitLab project ID.
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries.
        """
        # Query parameters for the issues API
        params = {"scope": "all", "per_page": 100}
        if since:
            params["updated_after"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            
        issues_data = self._make_request(f"projects/{project_id}/issues", params)
        
        issues = []
        for issue in issues_data:
            issues.append({
                "id": str(issue["iid"]),  # Use iid which is project-specific ID
                "title": issue["title"],
                "description": issue["description"] or "",
                "state": issue["state"],
                "created_at": datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ"),
                "updated_at": datetime.strptime(issue["updated_at"], "%Y-%m-%dT%H:%M:%S.%fZ"),
                "labels": issue.get("labels", []),
                "assignees": [assignee["username"] for assignee in issue.get("assignees", [])],
                "url": issue["web_url"]
            })
            
        return issues
