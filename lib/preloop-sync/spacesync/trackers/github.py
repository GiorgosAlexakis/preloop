"""
GitHub tracker implementation for SpaceSync.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import os

import requests

from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from ..utils import retry
from .base import BaseTracker
from ..config import logger
from spacemodels.models.project import Project
from spacemodels.crud import crud_webhook
from spacemodels.db.session import get_db_session

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
                    "id": org["id"],
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

    def transform_issue(
        self, issue_data: Dict[str, Any], project: Project
    ) -> Dict[str, Any]:
        """
        Transforms GitHub issue data into a standardized format.
        """
        if "key" not in issue_data:
            issue_data["key"] = f"{project.slug}#{issue_data['number']}"

        transformed_data = super().transform_issue(issue_data, project)

        # GitHub-specific transformations can be added here if needed

        return transformed_data

    def transform_comment(
        self, comment_data: Dict[str, Any], issue_db_id: str, author_db_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transforms GitHub comment data into a standardized format.
        """
        transformed_data = super().transform_comment(comment_data, issue_db_id, author_db_id)

        # GitHub-specific transformations can be added here if needed

        return transformed_data

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
        db = get_db_session()
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

            if response.status_code == 201 or response.status_code == 200:
                crud_webhook.create(
                    db,
                    obj_in={
                        "organization_id": org_id,
                        "external_id": webhook_id,
                        "url": url_with_secret_and_project,
                        "secret": secret,
                        "events": actual_events,
                    },
                )
                logger.info(f"Successfully registered webhook {webhook_id} for project {project_key}.")
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

    def unregister_webhook(
        self,
        org_identifier: str,
        webhook_id: Optional[int] = None,
        webhook_url: Optional[str] = None,
    ) -> bool:
        """
        Unregister a webhook for the given GitHub organization.
        Can unregister by specific webhook ID or by matching a webhook URL.

        Args:
            org_identifier: The GitHub organization login name.
            webhook_id: The ID of the webhook to remove.
            webhook_url: The target URL of the webhook to remove (used if webhook_id is None).

        Returns:
            True if unregistration was successful or webhook didn't exist/was already unregistered, False otherwise.
        """
        if not org_identifier or org_identifier == "personal":
            logger.info(
                f"Skipping webhook unregistration for org '{org_identifier}'. GitHub webhooks are managed per-repository for personal accounts or org_identifier is missing."
            )
            return True # No action to take, consider it success for this context

        if not webhook_id and not webhook_url:
            logger.error(
                f"Cannot unregister webhook for org '{org_identifier}': either webhook_id or webhook_url must be provided."
            )
            return False

        base_hooks_endpoint = f"orgs/{org_identifier}/hooks"
        hook_to_delete_id = webhook_id

        try:
            if not hook_to_delete_id and webhook_url:
                # Need to list hooks to find the ID by URL
                list_url = f"{self.API_BASE_URL}/{base_hooks_endpoint.lstrip('/')}"
                list_response = requests.get(
                    list_url, headers=self.headers, params={"per_page": 100}
                )

                if list_response.status_code != 200:
                    logger.error(
                        f"Failed to list webhooks for GitHub org '{org_identifier}' to find URL '{webhook_url}': {list_response.status_code} - {list_response.text}"
                    )
                    return False

                hooks = list_response.json()
                for hook in hooks:
                    if hook.get("config", {}).get("url") == webhook_url:
                        hook_to_delete_id = hook["id"]
                        break

                if not hook_to_delete_id:
                    logger.warning(
                        f"Webhook for GitHub org '{org_identifier}' with URL '{webhook_url}' not found. Assuming already unregistered."
                    )
                    return True # Not found is a form of success for unregistration

            if not hook_to_delete_id: # Should only happen if only webhook_id was None and URL wasn't found
                logger.warning(
                    f"No webhook ID provided or found for GitHub org '{org_identifier}' with URL '{webhook_url}'. Cannot unregister."
                )
                return True # Or False if strict "must find then delete" is required. True aligns with "not found is success".

            # Proceed to delete the hook by its ID
            delete_endpoint = f"{base_hooks_endpoint}/{hook_to_delete_id}"
            delete_url = f"{self.API_BASE_URL}/{delete_endpoint.lstrip('/')}"
            delete_response = requests.delete(delete_url, headers=self.headers)

            if delete_response.status_code == 204:
                logger.info(
                    f"Successfully unregistered webhook {hook_to_delete_id} for GitHub org '{org_identifier}'."
                )
                return True
            elif delete_response.status_code == 404: # Not found during delete attempt
                logger.warning(
                    f"Webhook {hook_to_delete_id} for GitHub org '{org_identifier}' not found during delete attempt. Assuming already unregistered."
                )
                return True
            else:
                logger.error(
                    f"Failed to unregister webhook {hook_to_delete_id} for GitHub org '{org_identifier}': {delete_response.status_code} - {delete_response.text}"
                )
                return False

        except requests.RequestException as e:
            logger.error(
                f"GitHub connection error while unregistering webhook for org '{org_identifier}': {e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error unregistering webhook for GitHub org '{org_identifier}': {e}",
                exc_info=True,
            )
            return False

    def unregister_all_webhooks(
        self, webhook_url_pattern: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Unregister all webhooks for all relevant organizations, optionally matching a URL pattern.
        For GitHub, this targets organization-level webhooks.

        Args:
            webhook_url_pattern: If provided, only unregister webhooks whose URL
                                 matches this pattern. If None, attempts to unregister
                                 webhooks matching the SPACEBRIDGE_URL pattern.

        Returns:
            A dictionary summarizing the actions taken, e.g.,
            {"unregistered": count, "failed": count, "not_found": count}.
        """
        results = {"unregistered": 0, "failed": 0, "not_found": 0}

        # Determine the target URL pattern
        target_pattern = webhook_url_pattern
        if target_pattern is None:
            # Fallback to SPACEBRIDGE_URL if available and pattern is not given
            # Ensure SPACEBRIDGE_URL is correctly imported or accessed from config
            # from ..config import SPACEBRIDGE_URL # or os.getenv
            sb_url = os.getenv("SPACEBRIDGE_URL")
            if sb_url:
                target_pattern = f"{sb_url.rstrip('/')}/api/v1/private/webhooks/"
                logger.info(f"No specific webhook_url_pattern provided, using default pattern: {target_pattern}")
            else:
                logger.warning("Cannot determine target webhook URL pattern: webhook_url_pattern is None and SPACEBRIDGE_URL is not set.")
                # Depending on desired behavior, could return early or try to delete all webhooks (risky)
                # For safety, let's not delete all if no pattern can be determined.
                return results


        try:
            organizations = self.get_organizations()
        except (TrackerAuthenticationError, TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Failed to get organizations for GitHub tracker {self.tracker_id}: {e}")
            return results # Cannot proceed

        for org_data in organizations:
            org_identifier = org_data.get("id")
            if not org_identifier or org_identifier == "personal":
                logger.debug(f"Skipping webhook operations for org '{org_identifier}' (personal or invalid).")
                continue

            logger.info(f"Processing webhooks for GitHub organization: {org_identifier}")
            hooks_endpoint = f"orgs/{org_identifier}/hooks"
            list_url = f"{self.API_BASE_URL}/{hooks_endpoint.lstrip('/')}"

            try:
                list_response = requests.get(
                    list_url, headers=self.headers, params={"per_page": 100}
                )
                if list_response.status_code != 200:
                    logger.error(
                        f"Failed to list webhooks for GitHub org '{org_identifier}': {list_response.status_code} - {list_response.text}"
                    )
                    results["failed"] += 1 # Count failure at org level if list fails
                    continue

                hooks = list_response.json()
                if not hooks:
                    logger.info(f"No webhooks found for GitHub org '{org_identifier}'.")
                    results["not_found"] += 1 # Or just continue, depends on how "not_found" is defined
                    continue

                hooks_to_delete_ids = []
                for hook in hooks:
                    hook_config_url = hook.get("config", {}).get("url")
                    if hook_config_url:
                        if target_pattern and target_pattern in hook_config_url:
                            hooks_to_delete_ids.append(hook["id"])
                        elif not target_pattern:
                            # This case should ideally be handled by the check above for sb_url
                            # If target_pattern is None here, it means SPACEBRIDGE_URL was also not found.
                            # Avoid deleting all hooks if no pattern.
                            logger.debug(f"Skipping hook {hook['id']} for org {org_identifier} as no target_pattern is defined.")
                            pass


                if not hooks_to_delete_ids:
                    logger.info(f"No webhooks matching pattern '{target_pattern}' found for GitHub org '{org_identifier}'.")
                    # This could be counted as "not_found" for webhooks matching the pattern
                    # For simplicity, let's assume if none match, it's not an error but nothing to do.
                    # results["not_found"] += 1 # if we consider "no matching hooks" as "not_found"
                    continue

                for hook_id in hooks_to_delete_ids:
                    if self.unregister_webhook(org_identifier=org_identifier, webhook_id=hook_id):
                        results["unregistered"] += 1
                    else:
                        # unregister_webhook already logs errors, so just count failure
                        results["failed"] += 1

            except requests.RequestException as e:
                logger.error(f"Connection error processing webhooks for org '{org_identifier}': {e}", exc_info=True)
                results["failed"] += 1 # Count as failed for this org
            except Exception as e:
                logger.error(f"Unexpected error processing webhooks for org '{org_identifier}': {e}", exc_info=True)
                results["failed"] += 1 # Count as failed for this org

        logger.info(f"GitHub unregister_all_webhooks summary: {results}")
        return results
