"""
GitHub tracker implementation for SpaceSync.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from spacemodels.crud import crud_webhook
from spacemodels.models.organization import Organization
from spacemodels.models.webhook import Webhook

from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from ..utils import retry
from .base import BaseTracker
from ..config import logger
from spacemodels.models.project import Project
from spacemodels.crud import crud_organization, crud_project


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

    @retry(max_attempts=2, exceptions=(TrackerConnectionError, TrackerResponseError))
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

    @retry(max_attempts=1, exceptions=(TrackerConnectionError, TrackerResponseError))
    def _make_request_delete(self, endpoint: str) -> bool:
        """
        Make a DELETE request to the GitHub API.

        Args:
            endpoint: API endpoint to request.

        Returns:
            True if successful, False otherwise.

        Raises:
            TrackerAuthenticationError: If authentication fails.
            TrackerConnectionError: If connection fails.
            TrackerResponseError: If response is invalid.
        """
        try:
            url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
            response = requests.delete(url, headers=self.headers)

            if response.status_code == 401:
                raise TrackerAuthenticationError("GitHub authentication failed")
            elif response.status_code == 404:
                logger.warning(
                    f"Resource not found during DELETE request to {endpoint}"
                )
                return True  # Treat not found as a success for cleanup
            elif response.status_code >= 400:
                raise TrackerResponseError(
                    f"GitHub API error: {response.status_code} - {response.text}"
                )

            return response.status_code == 204
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
                        "updated_at": repo[
                            "pushed_at"
                        ],  # Use pushed_at for last activity
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
                logger.error(
                    f"Failed to get repository details for project_id {project_id}: {e}"
                )
                return []  # Cannot proceed without repo_name

        params = {
            "state": "all",
            "per_page": 100,
            "sort": "updated",
            "direction": "desc",
        }
        if since:
            params["since"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.debug(
                f"GitHub get_issues: Filtering issues updated since {params['since']}"
            )

        issues_endpoint = f"repos/{repo_name}/issues"
        try:
            raw_issues_data = self._make_request(issues_endpoint, params)
        except TrackerResponseError as e:
            logger.error(f"Failed to get issues for repo {repo_name}: {e}")
            return []

        processed_issues = []
        for issue_data in raw_issues_data:
            if "pull_request" in issue_data:  # Skip pull requests
                continue

            issue_number = issue_data["number"]

            # Fetch comments for the issue
            comments_data_transformed = []
            comments_endpoint = f"repos/{repo_name}/issues/{issue_number}/comments"
            try:
                # GitHub API for comments might not support 'since' for individual issue comments list
                # It's usually for the main issues list. We fetch all comments for an issue.
                raw_comments_data = self._make_request(
                    comments_endpoint, params={"per_page": 100}
                )
                for comment_item in raw_comments_data:
                    try:
                        created_at_dt = datetime.strptime(
                            comment_item["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                        )
                        updated_at_dt = datetime.strptime(
                            comment_item["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
                        )
                    except (ValueError, TypeError) as ve:
                        logger.warning(
                            f"Could not parse datetime for comment {comment_item.get('id')} on issue {issue_number}: {ve}. Using fallback."
                        )
                        created_at_dt = datetime.now()
                        if isinstance(comment_item.get("created_at"), str):
                            try:
                                created_at_dt = datetime.strptime(
                                    comment_item["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                                )
                            except ValueError:
                                pass
                        updated_at_dt = created_at_dt

                    comments_data_transformed.append(
                        {
                            "id": str(comment_item["id"]),
                            "body": comment_item.get("body", "")
                            or "",  # Ensure body is not None
                            "author_id": str(comment_item["user"]["id"])
                            if comment_item.get("user")
                            and comment_item["user"].get("id")
                            else None,
                            "created_at": created_at_dt,
                            "updated_at": updated_at_dt,
                            "url": comment_item.get("html_url", ""),
                        }
                    )
            except TrackerResponseError as e:
                logger.error(
                    f"Failed to get comments for issue {repo_name}#{issue_number}: {e}"
                )
            # Continue processing the issue even if comments fail

            try:
                issue_created_at = datetime.strptime(
                    issue_data["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                )
                issue_updated_at = datetime.strptime(
                    issue_data["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
                )
            except (ValueError, TypeError) as ve:
                logger.warning(
                    f"Could not parse datetime for issue {issue_number}: {ve}. Using fallback."
                )
                issue_created_at = datetime.now()
                if isinstance(issue_data.get("created_at"), str):
                    try:
                        issue_created_at = datetime.strptime(
                            issue_data["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                        )
                    except ValueError:
                        pass
                issue_updated_at = issue_created_at

            processed_issues.append(
                {
                    "external_id": str(issue_data["id"]),
                    "key": f"{repo_name}#{issue_number}",
                    "title": issue_data["title"],
                    "description": issue_data.get("body", "")
                    or "",  # Ensure body is not None
                    "state": issue_data["state"],
                    "created_at": issue_created_at,
                    "updated_at": issue_updated_at,
                    "labels": [
                        label["name"]
                        for label in issue_data.get("labels", [])
                        if isinstance(label, dict) and "name" in label
                    ],
                    "assignees": [
                        assignee["login"]
                        for assignee in issue_data.get("assignees", [])
                        if isinstance(assignee, dict) and "login" in assignee
                    ],
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
        self,
        comment_data: Dict[str, Any],
        issue_db_id: str,
        author_db_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transforms GitHub comment data into a standardized format.
        """
        transformed_data = super().transform_comment(
            comment_data, issue_db_id, author_db_id
        )

        # GitHub-specific transformations can be added here if needed

        return transformed_data

    def register_webhook(
        self, db: Session, organization: Organization, webhook_url: str, secret: str
    ) -> bool:
        """
        Register a webhook for the given GitHub organization.

        Args:
            db: The database session.
            organization: The organization to register the webhook for.
            webhook_url: The target URL for the webhook.
            secret: The secret to use for the webhook.

        Returns:
            True if registration was successful or webhook already exists, False otherwise.
        """
        org_identifier = organization.identifier
        # GitHub doesn't support organization-level webhooks for personal accounts via this API
        if org_identifier == "personal":
            logger.info(
                f"Skipping webhook registration for personal account '{self.connection_details.get('login', 'N/A')}'. GitHub personal webhooks are managed per-repository."
            )
            # Consider this 'successful' in the sense that there's nothing to do here.
            # Alternatively, could return False if strict registration is required.
            return True

        endpoint = f"orgs/{org_identifier}/hooks"
        events = [
            "issues",  # Issue opened, edited, closed, reopened, assigned, etc.
            "project",  # Project created, updated, deleted
            "repository",  # Repository created, deleted, archived, unarchived
            "push",  # Git push to a repository
            # Add more events as needed, e.g., 'pull_request', 'release', 'member'
        ]
        payload = {
            "name": "web",
            "active": True,
            "events": events,
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",  # Recommended to verify SSL
            },
        }

        try:
            url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
            response = requests.post(url, headers=self.headers, json=payload)

            if response.status_code in [200, 201]:
                response_data = response.json()
                webhook_id = response_data.get("id")
                if not webhook_id:
                    logger.error(
                        f"Successfully registered webhook for org '{org_identifier}' but could not get webhook ID from response."
                    )
                    return False

                crud_webhook.create(
                    db,
                    obj_in={
                        "organization_id": organization.id,
                        "external_id": str(webhook_id),
                        "url": webhook_url,
                        "secret": secret,
                        "events": events,
                    },
                )
                logger.info(
                    f"Successfully registered and stored webhook {webhook_id} for GitHub org '{org_identifier}'"
                )
                return True
            elif response.status_code == 401:
                logger.error(
                    f"GitHub authentication failed while trying to register webhook for org '{org_identifier}'."
                )
                return False
            elif response.status_code == 403:
                logger.error(
                    f"Permission denied: Unable to register webhook for GitHub org '{org_identifier}'. Check token permissions (needs admin:org_hook)."
                )
                return False
            elif response.status_code == 404:
                logger.error(
                    f"GitHub organization '{org_identifier}' not found while trying to register webhook."
                )
                return False
            elif response.status_code == 422:
                response_data = response.json()
                if "errors" in response_data and any(
                    "Hook already exists" in e.get("message", "")
                    for e in response_data["errors"]
                ):
                    logger.warning(
                        f"Webhook for GitHub org '{org_identifier}' pointing to {webhook_url} already exists."
                    )
                    return True
                else:
                    logger.error(
                        f"Failed to register webhook for GitHub org '{org_identifier}' (Unprocessable Entity - check config/permissions): {response.text}"
                    )
                    return False
            else:
                logger.error(
                    f"GitHub API error registering webhook for org '{org_identifier}': {response.status_code} - {response.text}"
                )
                return False

        except requests.RequestException as e:
            logger.error(
                f"GitHub connection error while registering webhook for org '{org_identifier}': {e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error registering webhook for GitHub org '{org_identifier}': {e}",
                exc_info=True,
            )
            return False

    def unregister_webhook(self, db: Session, webhook: Webhook) -> bool:
        """
        Unregister a webhook for the given GitHub organization.

        Args:
            db: The database session.
            webhook: The webhook to unregister.

        Returns:
            True if unregistration was successful, False otherwise.
        """
        org_identifier = webhook.organization.identifier
        webhook_id = webhook.external_id

        if not org_identifier or org_identifier == "personal":
            logger.info(f"Skipping webhook unregistration for org '{org_identifier}'.")
            return True

        endpoint = f"orgs/{org_identifier}/hooks/{webhook_id}"
        try:
            url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
            response = requests.delete(url, headers=self.headers)

            if response.status_code == 204:
                logger.info(
                    f"Successfully unregistered webhook {webhook_id} for GitHub org '{org_identifier}'."
                )
                crud_webhook.remove(db, id=webhook.id)
                return True
            elif response.status_code == 404:
                logger.warning(
                    f"Webhook {webhook_id} for GitHub org '{org_identifier}' not found during delete attempt. Assuming already unregistered."
                )
                crud_webhook.remove(db, id=webhook.id)
                return True
            else:
                logger.error(
                    f"Failed to unregister webhook {webhook_id} for GitHub org '{org_identifier}': {response.status_code} - {response.text}"
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

    def unregister_all_webhooks(self, db: Session):
        """
        Unregister all webhooks for all organizations managed by this tracker instance.
        Args:
            db: The database session.
        """
        results = {"unregistered": 0, "failed": 0, "not_found": 0}
        logger.info(
            f"Starting to unregister all webhooks for tracker {self.tracker_id}."
        )
        try:
            webhooks_to_delete = (
                db.query(Webhook)
                .join(Organization)
                .filter(Organization.tracker_id == self.tracker_id)
                .all()
            ) + (
                db.query(Webhook)
                .join(Project)
                .join(Organization)
                .filter(Organization.tracker_id == self.tracker_id)
                .all()
            )

            if not webhooks_to_delete:
                logger.info("No webhooks found in the database for this tracker.")
                return results

            for webhook in webhooks_to_delete:
                if webhook.organization_id:
                    organization = crud_organization.get(db, id=webhook.organization_id)
                    logger.info(
                        f"Attempting to unregister webhook {webhook.external_id} for org '{organization.identifier}'..."
                    )
                else:
                    project = crud_project.get(db, id=webhook.project_id)
                    logger.info(
                        f"Attempting to unregister webhook {webhook.external_id} for project '{project.name}'..."
                    )
                if self.unregister_webhook(db=db, webhook=webhook):
                    results["unregistered"] += 1
                else:
                    results["failed"] += 1

        except Exception as e:
            logger.error(
                f"An unexpected error occurred during webhook unregistration for tracker {self.tracker_id}: {e}",
                exc_info=True,
            )
            results["failed"] += 1
        logger.info(
            f"Finished unregistering all webhooks for tracker {self.tracker_id}."
        )
        logger.info(f"GitHub unregister_all_webhooks summary: {results}")
        return results

    def cleanup_stale_webhooks(
        self, spacebridge_url: str, cleanup_projects: bool = False
    ) -> dict:
        """
        Deletes stale webhooks pointing to the given SpaceBridge URL.

        By default, this method cleans up organization-level webhooks.
        If `cleanup_projects` is True, it cleans up repository-level webhooks instead.

        Args:
            spacebridge_url: The base URL of the SpaceBridge instance.
            cleanup_projects: If True, clean up repository-level webhooks. Defaults to False.

        Returns:
            A dictionary summarizing the actions taken, e.g., `{"unregistered": count, "failed": count}`.
        """
        results = {"unregistered": 0, "failed": 0}
        logger.info(
            f"Starting cleanup of stale webhooks for URL: {spacebridge_url} (cleanup_projects={cleanup_projects})"
        )

        if cleanup_projects:
            self._cleanup_project_webhooks(spacebridge_url, results)
        else:
            self._cleanup_organization_webhooks(spacebridge_url, results)

        logger.info(f"Webhook cleanup summary: {results}")
        return results

    def _cleanup_organization_webhooks(
        self, spacebridge_url: str, results: dict
    ) -> None:
        """Helper to clean up organization-level webhooks."""
        try:
            organizations = self.get_organizations()
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Failed to retrieve organizations: {e}")
            return

        for org in organizations:
            org_login = org.get("name")
            if not org_login or org.get("id") == "personal":
                continue

            logger.info(f"Checking webhooks for organization: {org_login}")
            try:
                hooks = self._make_request(f"orgs/{org_login}/hooks")
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(f"Failed to list webhooks for {org_login}: {e}")
                results["failed"] += 1
                continue

            for hook in hooks:
                self._process_hook(
                    hook, spacebridge_url, results, f"orgs/{org_login}/hooks"
                )

    def _cleanup_project_webhooks(self, spacebridge_url: str, results: dict) -> None:
        """Helper to clean up repository-level webhooks."""
        try:
            repos = self._make_request("user/repos", {"per_page": 100})
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Failed to retrieve repositories: {e}")
            return

        for repo in repos:
            repo_full_name = repo.get("full_name")
            if not repo_full_name:
                continue

            logger.info(f"Checking webhooks for repository: {repo_full_name}")
            try:
                hooks = self._make_request(f"repos/{repo_full_name}/hooks")
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(f"Failed to list webhooks for {repo_full_name}: {e}")
                results["failed"] += 1
                continue

            for hook in hooks:
                self._process_hook(
                    hook, spacebridge_url, results, f"repos/{repo_full_name}/hooks"
                )

    def _process_hook(
        self, hook: dict, spacebridge_url: str, results: dict, base_endpoint: str
    ) -> None:
        """Processes a single webhook for cleanup."""
        hook_id = hook.get("id")
        hook_config = hook.get("config", {})
        hook_url = hook_config.get("url")

        if not all([hook_id, hook_url]):
            return

        if hook_url.startswith(spacebridge_url):
            logger.info(
                f"Found stale webhook {hook_id} in {base_endpoint} pointing to {hook_url}. Deleting..."
            )
            try:
                delete_endpoint = f"{base_endpoint}/{hook_id}"
                if self._make_request_delete(delete_endpoint):
                    logger.info(
                        f"Successfully deleted webhook {hook_id} from {base_endpoint}."
                    )
                    results["unregistered"] += 1
                else:
                    logger.error(
                        f"Failed to delete webhook {hook_id} from {base_endpoint}."
                    )
                    results["failed"] += 1
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(
                    f"An error occurred while deleting webhook {hook_id} from {base_endpoint}: {e}"
                )
                results["failed"] += 1
