"""
GitHub tracker implementation for SpaceSync.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from ..config import logger
from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from ..utils import retry
from .base import BaseTracker


class GitHubTracker(BaseTracker):
    """GitHub tracker implementation."""

    API_BASE_URL = "https://api.github.com"

    def __init__(
        self, tracker_id: str, api_key: str, connection_details: Dict[str, Any]
    ):
        """
        Initialize the GitHub tracker.

        Args:
            tracker_id: ID of the tracker in the database (UUID string).
            api_key: GitHub API token.
            connection_details: Connection details including repository information.
        """
        super().__init__(tracker_id, api_key, connection_details)
        self.headers = {
            "Authorization": f"token {api_key}",
            "Accept": "application/vnd.github.v3+json",
        }

    @retry(max_attempts=3, exceptions=(TrackerConnectionError, TrackerResponseError))
    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Make a request to the GitHub API.

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
            url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 401:
                raise TrackerAuthenticationError("GitHub authentication failed")
            elif response.status_code >= 400:
                raise TrackerResponseError(
                    f"GitHub API error: {response.status_code} - {response.text}"
                )

            return response.json()
        except requests.RequestException as e:
            raise TrackerConnectionError(f"GitHub connection error: {str(e)}")

    def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Get organizations from GitHub.

        Returns:
            List of organization data dictionaries.
        """
        # First, add a "Personal" organization for the user's repositories
        # Get authenticated user info
        user_data = self._make_request("user")

        organizations = [
            {
                "id": "personal",  # Use "personal" as a special ID for personal repositories
                "name": f"{user_data['login']}'s Repositories",
                "url": user_data["html_url"],
            }
        ]

        # Then get the user's organizations
        orgs_data = self._make_request("user/orgs")

        for org in orgs_data:
            # Get detailed information for each organization
            org_detail = self._make_request(f"orgs/{org['login']}")
            organizations.append(
                {
                    "id": org_detail["login"],
                    "name": org_detail["name"] or org_detail["login"],
                    "url": org_detail["html_url"],
                }
            )

        return organizations

    def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get repositories (projects) for an organization from GitHub.

        Args:
            organization_id: GitHub organization login name or "personal" for user repos.

        Returns:
            List of project data dictionaries.
        """
        # For GitHub, projects are repositories
        if organization_id == "personal":
            # Get user's repositories
            repos_data = self._make_request("user/repos", {"per_page": 100})
        else:
            # Get organization's repositories
            repos_data = self._make_request(
                f"orgs/{organization_id}/repos", {"per_page": 100}
            )

        projects = []
        for repo in repos_data:
            projects.append(
                {
                    "id": str(repo["id"]),
                    "name": repo["name"],
                    "description": repo["description"] or "",
                    "url": repo["html_url"],
                }
            )

        return projects

    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a repository from GitHub.

        Args:
            organization_id: GitHub organization login name or "personal" for user repos.
            project_id: GitHub repository ID.
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries.
        """
        # First, we need to get the repo full name (owner/repo) using the repo ID
        repo_name = None

        if organization_id == "personal":
            # Search user's repos
            repos_data = self._make_request("user/repos", {"per_page": 100})
        else:
            # Search organization's repos
            repos_data = self._make_request(
                f"orgs/{organization_id}/repos", {"per_page": 100}
            )

        for repo in repos_data:
            if str(repo["id"]) == project_id:
                repo_name = repo["full_name"]  # This includes the owner/repo format
                break

        if not repo_name:
            logger.warning(
                f"Repository with ID {project_id} not found in organization {organization_id}"
            )
            return []

        # Query parameters for the issues API
        params = {"state": "all", "per_page": 100}
        # Removing these lines below correctly gets the issues, otherwise, no issues are received
        # if since:
        #     params["since"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Make the request
        issues_endpoint = f"repos/{repo_name}/issues"
        issues_data = self._make_request(issues_endpoint, params)

        # Process issues as before, filtering out PRs
        issues = []
        for issue in issues_data:
            # Skip pull requests
            if "pull_request" in issue:
                continue

            issues.append(
                {
                    "id": str(issue["number"]),
                    "title": issue["title"],
                    "description": issue["body"] or "",
                    "state": issue["state"],
                    "created_at": datetime.strptime(
                        issue["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "updated_at": datetime.strptime(
                        issue["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "labels": [label["name"] for label in issue.get("labels", [])],
                    "assignees": [
                        assignee["login"] for assignee in issue.get("assignees", [])
                    ],
                    "url": issue["html_url"],
                }
            )

        return issues
