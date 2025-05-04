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
        Get issues for a repository from GitHub, including their comments,
        optionally filtering by update time.

        Args:
            organization_id: GitHub organization login name or "personal" for user repos.
            project_id: GitHub repository ID or full name (e.g., 'owner/repo').
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries, each including a 'comments' list.
        """

        if "/" in project_id:
            repo_name = project_id
        else:
            try:
                repo_details = self._make_request(f"repositories/{project_id}")
                repo_name = repo_details["full_name"]
            except TrackerResponseError as e:
                logger.error(f"Failed to get repository details for project_id {project_id}: {e}")
                return [] # Cannot proceed without repo_name

        params = {"state": "all", "per_page": 100, "sort": "updated", "direction": "desc"}
        if since:
            params["since"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.debug(f"GitHub get_issues: Filtering issues updated since {params['since']}")

        issues_endpoint = f"repos/{repo_name}/issues"
        try:
            raw_issues_data = self._make_request(issues_endpoint, params)
        except TrackerResponseError as e:
            logger.error(f"Failed to get issues for repo {repo_name}: {e}")
            return []

        processed_issues = []
        for issue_data in raw_issues_data:
            if "pull_request" in issue_data: # Skip pull requests
                continue

            issue_number = issue_data["number"]

            # Fetch comments for the issue
            comments_data_transformed = []
            comments_endpoint = f"repos/{repo_name}/issues/{issue_number}/comments"
            try:
                # GitHub API for comments might not support 'since' for individual issue comments list
                # It's usually for the main issues list. We fetch all comments for an issue.
                raw_comments_data = self._make_request(comments_endpoint, params={"per_page": 100})
                for comment_item in raw_comments_data:
                    try:
                        created_at_dt = datetime.strptime(comment_item["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                        updated_at_dt = datetime.strptime(comment_item["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
                    except (ValueError, TypeError) as ve:
                        logger.warning(f"Could not parse datetime for comment {comment_item.get('id')} on issue {issue_number}: {ve}. Using fallback.")
                        created_at_dt = datetime.now()
                        if isinstance(comment_item.get("created_at"), str):
                            try:
                                created_at_dt = datetime.strptime(comment_item["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                            except ValueError:
                                pass
                        updated_at_dt = created_at_dt

                    comments_data_transformed.append(
                        {
                            "id": str(comment_item["id"]),
                            "body": comment_item.get("body", "") or "", # Ensure body is not None
                            "author_id": str(comment_item["user"]["id"]) if comment_item.get("user") and comment_item["user"].get("id") else None,
                            "created_at": created_at_dt,
                            "updated_at": updated_at_dt,
                            "url": comment_item.get("html_url", ""),
                        }
                    )
            except TrackerResponseError as e:
                logger.error(f"Failed to get comments for issue {repo_name}#{issue_number}: {e}")
            # Continue processing the issue even if comments fail

            try:
                issue_created_at = datetime.strptime(issue_data["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                issue_updated_at = datetime.strptime(issue_data["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, TypeError) as ve:
                logger.warning(f"Could not parse datetime for issue {issue_number}: {ve}. Using fallback.")
                issue_created_at = datetime.now()
                if isinstance(issue_data.get("created_at"), str):
                    try:
                        issue_created_at = datetime.strptime(issue_data["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        pass
                issue_updated_at = issue_created_at

            processed_issues.append(
                {
                    "external_id": str(issue_data["id"]),
                    "key": f"{repo_name}#{issue_number}",
                    "title": issue_data["title"],
                    "description": issue_data.get("body", "") or "", # Ensure body is not None
                    "state": issue_data["state"],
                    "created_at": issue_created_at,
                    "updated_at": issue_updated_at,
                    "labels": [label["name"] for label in issue_data.get("labels", []) if isinstance(label, dict) and "name" in label],
                    "assignees": [assignee["login"] for assignee in issue_data.get("assignees", []) if isinstance(assignee, dict) and "login" in assignee],
                    "url": issue_data.get("html_url", ""),
                    "comments": comments_data_transformed,
                }
            )
        return processed_issues

    def register_webhook(
        self, org_identifier: str, webhook_url: str, secret: str
    ) -> bool:
        """
        Register a webhook for the given GitHub organization.

        Args:
            org_identifier: The GitHub organization login name.
            webhook_url: The target URL for the webhook.
            secret: The secret to use for the webhook.

        Returns:
            True if registration was successful or webhook already exists, False otherwise.
        """
        # GitHub doesn't support organization-level webhooks for personal accounts via this API
        if org_identifier == "personal":
            logger.info(f"Skipping webhook registration for personal account '{self.connection_details.get('login', 'N/A')}'. GitHub personal webhooks are managed per-repository.")
            # Consider this 'successful' in the sense that there's nothing to do here.
            # Alternatively, could return False if strict registration is required.
            return True

        endpoint = f"orgs/{org_identifier}/hooks"
        payload = {
            "name": "web",
            "active": True,
            "events": [
                "issues",       # Issue opened, edited, closed, reopened, assigned, etc.
                "project",      # Project created, updated, deleted
                "repository",   # Repository created, deleted, archived, unarchived
                "push"          # Git push to a repository
                # Add more events as needed, e.g., 'pull_request', 'release', 'member'
            ],
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0", # Recommended to verify SSL
            },
        }

        try:
            url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
            response = requests.post(url, headers=self.headers, json=payload)

            if response.status_code == 201:
                logger.info(f"Successfully created webhook for GitHub org '{org_identifier}' pointing to {webhook_url}")
                return True
            elif response.status_code == 401:
                logger.error(f"GitHub authentication failed while trying to register webhook for org '{org_identifier}'.")
                # Raise specific error? Or just log and return False? Let's log and return False for now.
                return False
            elif response.status_code == 403:
                 logger.error(f"Permission denied: Unable to register webhook for GitHub org '{org_identifier}'. Check token permissions (needs admin:org_hook).")
                 return False
            elif response.status_code == 404:
                 logger.error(f"GitHub organization '{org_identifier}' not found while trying to register webhook.")
                 return False
            elif response.status_code == 422:
                # Check if it's because the hook already exists
                response_data = response.json()
                if "errors" in response_data and any("Hook already exists" in e.get("message", "") for e in response_data["errors"]):
                    logger.warning(f"Webhook for GitHub org '{org_identifier}' pointing to {webhook_url} already exists.")
                    # Consider this a success as the desired state is achieved
                    return True
                else:
                    logger.error(f"Failed to register webhook for GitHub org '{org_identifier}' (Unprocessable Entity - check config/permissions): {response.text}")
                    return False
            else:
                # General API error
                logger.error(f"GitHub API error registering webhook for org '{org_identifier}': {response.status_code} - {response.text}")
                return False

        except requests.RequestException as e:
            logger.error(f"GitHub connection error while registering webhook for org '{org_identifier}': {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error registering webhook for GitHub org '{org_identifier}': {e}", exc_info=True)
            return False
