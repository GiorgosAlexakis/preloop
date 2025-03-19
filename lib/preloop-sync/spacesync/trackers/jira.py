"""
Jira tracker implementation for SpaceSync.
"""

import base64
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..config import logger
from ..exceptions import TrackerAuthenticationError, TrackerConnectionError, TrackerResponseError
from ..utils import retry
from .base import BaseTracker


class JiraTracker(BaseTracker):
    """Jira tracker implementation."""

    def __init__(self, tracker_id: int, api_key: str, connection_details: Dict[str, Any]):
        """
        Initialize the Jira tracker.

        Args:
            tracker_id: ID of the tracker in the database.
            api_key: Jira API token (or password for Basic Auth).
            connection_details: Connection details including:
                - jira_url: URL of the Jira instance
                - username: Jira username for authentication
        """
        super().__init__(tracker_id, api_key, connection_details)
        
        if "jira_url" not in connection_details:
            raise ValueError("Jira URL is required in connection_details")
        if "username" not in connection_details:
            raise ValueError("Jira username is required in connection_details")
            
        self.jira_url = connection_details["jira_url"].rstrip("/")
        self.username = connection_details["username"]
        
        # Basic authentication header
        auth_str = f"{self.username}:{api_key}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json"
        }

    @retry(max_attempts=3, exceptions=(TrackerConnectionError, TrackerResponseError))
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
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
        
        return [{
            "id": org_name,
            "name": org_name,
            "url": self.jira_url
        }]

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
            projects.append({
                "id": project["key"],
                "name": project["name"],
                "description": project.get("description", ""),
                "url": f"{self.jira_url}/projects/{project['key']}"
            })
            
        return projects

    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a project from Jira.

        Args:
            organization_id: Not used for Jira, but kept for interface consistency.
            project_id: Jira project key.
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries.
        """
        # Build JQL query
        jql = f"project = {project_id}"
        if since:
            jql += f" AND updated >= '{since.strftime('%Y-%m-%d %H:%M')}'"
            
        # Query parameters for the issues API
        params = {
            "jql": jql,
            "maxResults": 100,
            "fields": "summary,description,status,created,updated,labels,assignee,issuetype"
        }
            
        issues_data = self._make_request("search", params)
        
        issues = []
        for issue in issues_data.get("issues", []):
            # Parse datetime strings
            created = datetime.strptime(
                issue["fields"]["created"], "%Y-%m-%dT%H:%M:%S.%f%z"
            ).replace(tzinfo=None)
            updated = datetime.strptime(
                issue["fields"]["updated"], "%Y-%m-%dT%H:%M:%S.%f%z"
            ).replace(tzinfo=None)
            
            # Get assignee if available
            assignee = []
            if issue["fields"].get("assignee"):
                assignee = [issue["fields"]["assignee"]["displayName"]]
                
            issues.append({
                "id": issue["key"],
                "title": issue["fields"]["summary"],
                "description": issue["fields"].get("description", ""),
                "state": issue["fields"]["status"]["name"].lower(),
                "created_at": created,
                "updated_at": updated,
                "labels": issue["fields"].get("labels", []),
                "assignees": assignee,
                "url": f"{self.jira_url}/browse/{issue['key']}"
            })
            
        return issues
