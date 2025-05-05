"""
GitHub tracker implementation for SpaceSync.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from ..utils import retry
from .base import BaseTracker
from ..config import logger

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
        organizations = []

        # Get user data and organization data in parallel
        # This single request gets the authenticated user info
        user_data = self._make_request("user")

        # Create a virtual "Personal" organization for consistency with GitLab
        organizations.append(
            {
                "id": "personal",  # Use "personal" as a special ID for personal repositories
                "name": f"{user_data['login']}",
                "url": user_data["html_url"],
            }
        )

        # Get all organizations at once - this gives us enough info without individual calls
        # GitHub API already returns detailed organization info with this call
        orgs_data = self._make_request("user/orgs", {"per_page": 100})

        # Process each organization without making additional API calls
        for org in orgs_data:
            organizations.append(
                {
                    "id": org["login"],
                    "name": org["login"],  # Use login name as display name
                    "url": org["url"]
                    .replace("api.github.com", "github.com")
                    .replace("/orgs/", "/"),
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
        # Set up parameters for the API request with proper pagination and sorting
        params = {"per_page": 100, "sort": "updated", "direction": "desc"}

        # For GitHub, projects are repositories
        if organization_id == "personal":
            # Get user's repositories
            repos_data = self._make_request("user/repos", params)
        else:
            # Get organization's repositories
            repos_data = self._make_request(f"orgs/{organization_id}/repos", params)

        # Process repository data
        projects = []
        for repo in repos_data:
            projects.append(
                {
                    "id": str(repo["id"]),
                    "name": repo["name"],
                    "description": repo["description"] or "",
                    "url": repo["html_url"],
                    # Add additional metadata that might be useful for filtering and display
                    "meta_data": {
                        "full_name": repo["full_name"],
                        "default_branch": repo["default_branch"],
                        "language": repo.get("language"),
                        "created_at": repo["created_at"],
                        "updated_at": repo["pushed_at"],  # Use pushed_at for last activity
                        "stars": repo["stargazers_count"],
                    },
                }
            )

        return projects

    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a repository from GitHub, optionally filtering by update time.

        Args:
            organization_id: GitHub organization login name or "personal" for user repos.
            project_id: GitHub repository ID.
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries.
        """

        # If project_id looks like a full repo name (contains a slash), use it directly
        if "/" in project_id:
            repo_name = project_id
        else:
            # Make one API call to get the repository details
            repo_details = self._make_request(f"repositories/{project_id}")
            repo_name = repo_details["full_name"]

        # Query parameters for the issues API
        params = {"state": "all", "per_page": 100, "sort": "updated", "direction": "desc"}
        if since:
            # GitHub API expects ISO8601 format string for 'since'
            params["since"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.debug(f"GitHub get_issues: Filtering issues updated since {params['since']}")


        # Use the repo_name to directly access the issues
        issues_endpoint = f"repos/{repo_name}/issues"
        issues_data = self._make_request(issues_endpoint, params)

        # Process issues as before, filtering out PRs
        issues = []
        for issue in issues_data:
            # Skip pull requests
            if "pull_request" in issue:
                continue

            issue_number = issue["number"]
            issues.append(
                {
                    "external_id": str(issue_number),  # Use GitHub issue number
                    "key": f"{repo_name}#{issue_number}",  # Construct key as repo#number
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
