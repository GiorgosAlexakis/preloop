"""
GitHub tracker implementation for SpaceSync.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from spacemodels.models.organization import Organization
from spacemodels.models.webhook import Webhook
from spacebridge.schemas.tracker_models import (
    Issue,
    IssueComment,
    IssueCreate,
    IssueFilter,
    IssueUpdate,
    ProjectMetadata,
    TrackerConnection,
    IssueUser,
)

from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from .base import BaseTracker
from .utils import (
    async_retry,
    GITHUB_DEFAULT_PAGE_SIZE,
    HTTP_STATUS_OK,
    HTTP_STATUS_CREATED,
    HTTP_STATUS_NO_CONTENT,
    HTTP_STATUS_UNAUTHORIZED,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_UNPROCESSABLE_ENTITY,
)
from ..config import logger
from spacemodels.models.project import Project
from spacemodels.crud import crud_organization, crud_project, crud_webhook


class GitHubTracker(BaseTracker):
    """GitHub tracker implementation."""

    API_BASE_URL = "https://api.github.com"

    def __init__(
        self, tracker_id: str, api_key: str, connection_details: Dict[str, Any]
    ):
        """
        Initialize the GitHub tracker.
        """
        super().__init__(tracker_id, api_key, connection_details)
        self.headers = {
            "Authorization": f"token {api_key}",
            "Accept": "application/vnd.github.v3+json",
        }

    @async_retry()
    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Make a request to the GitHub API, handling pagination.
        """
        if params is None:
            params = {}
        params.setdefault("per_page", GITHUB_DEFAULT_PAGE_SIZE)
        results = []
        url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient() as client:
            while url:
                try:
                    response = await client.get(
                        url, headers=self.headers, params=params
                    )
                    params = None

                    if response.status_code == HTTP_STATUS_UNAUTHORIZED:
                        raise TrackerAuthenticationError("GitHub authentication failed")
                    elif response.status_code >= 400:
                        raise TrackerResponseError(
                            f"GitHub API error: {response.status_code} - {response.text}"
                        )

                    data = response.json()
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        return data

                    if "next" in response.links:
                        url = response.links["next"]["url"]
                    else:
                        url = None
                except httpx.RequestError as e:
                    raise TrackerConnectionError(f"GitHub connection error: {str(e)}")
        return results

    @async_retry()
    async def _make_request_delete(self, endpoint: str) -> bool:
        """
        Make a DELETE request to the GitHub API.
        """
        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
                response = await client.delete(url, headers=self.headers)

                if response.status_code == HTTP_STATUS_UNAUTHORIZED:
                    raise TrackerAuthenticationError("GitHub authentication failed")
                elif response.status_code == HTTP_STATUS_NOT_FOUND:
                    logger.warning(
                        f"Resource not found during DELETE request to {endpoint}"
                    )
                    return True
                elif response.status_code >= 400:
                    raise TrackerResponseError(
                        f"GitHub API error: {response.status_code} - {response.text}"
                    )

                return response.status_code == HTTP_STATUS_NO_CONTENT
            except httpx.RequestError as e:
                raise TrackerConnectionError(f"GitHub connection error: {str(e)}")

    async def _parse_dependencies(
        self, content: str, current_repo: str
    ) -> List[Dict[str, str]]:
        """Parse dependencies from text content (issue body, comments)."""
        dependencies = []
        import re

        # Regex to find keywords like 'closes', 'fixes', 'relates to', etc.,
        # followed by an issue reference.
        # It supports cross-repo references like 'owner/repo#123'.
        pattern = re.compile(
            r"(closes|fixes|resolves|relates to|blocked by|blocks)\s+((?:[a-zA-Z0-9-]+\/[a-zA-Z0-9_.-]+)?#\d+)",
            re.IGNORECASE,
        )

        for match in pattern.finditer(content):
            relationship_type = match.group(1).lower()
            target_issue_ref = match.group(2)

            # Normalize relationship type for consistency
            if relationship_type in ["closes", "fixes", "resolves"]:
                relationship_type = "closes"
            elif relationship_type == "relates to":
                relationship_type = "related"
            elif relationship_type == "blocked by":
                relationship_type = "is blocked by"

            # Construct the full key for the target issue
            if "#" in target_issue_ref and "/" not in target_issue_ref:
                # It's a short reference like '#123', so it's in the same repo.
                target_key = f"{current_repo}{target_issue_ref}"
            else:
                # It's a full reference like 'owner/repo#123'.
                target_key = target_issue_ref

            dependencies.append(
                {
                    "target_key": target_key,
                    "type": relationship_type,
                }
            )

        return dependencies

    async def test_connection(self) -> TrackerConnection:
        """Test the connection to the tracker."""
        try:
            await self._make_request("user")
            return TrackerConnection(connected=True, message="Connection successful")
        except (
            TrackerAuthenticationError,
            TrackerConnectionError,
            TrackerResponseError,
        ) as e:
            return TrackerConnection(connected=False, message=str(e))

    async def get_project_metadata(self, project_key: str) -> ProjectMetadata:
        """Get metadata about a project."""
        raise NotImplementedError

    async def search_issues(
        self,
        project_key: str,
        filter_params: IssueFilter,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[Issue], int]:
        """Search for issues in a project."""
        raise NotImplementedError

    async def get_issue(self, issue_id: str) -> Issue:
        """Get a specific issue by ID."""
        raise NotImplementedError

    async def create_issue(self, project_key: str, issue_data: IssueCreate) -> Issue:
        """Create a new issue."""
        raise NotImplementedError

    async def update_issue(self, issue_id: str, issue_data: IssueUpdate) -> Issue:
        """Update an existing issue."""
        raise NotImplementedError

    async def add_comment(self, issue_id: str, comment: str) -> IssueComment:
        """Add a comment to an issue."""
        raise NotImplementedError

    async def add_relation(
        self, issue_id: str, related_issue_id: str, relation_type: str
    ) -> bool:
        """Add a relation between issues."""
        raise NotImplementedError

    async def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Get organizations from GitHub.
        """
        organizations = []
        user_data = await self._make_request("user")
        organizations.append(
            {
                "id": "personal",
                "name": f"{user_data['login']}",
                "url": user_data["html_url"],
            }
        )
        orgs_data = await self._make_request(
            "user/orgs", {"per_page": GITHUB_DEFAULT_PAGE_SIZE}
        )
        for org in orgs_data:
            organizations.append(
                {
                    "id": str(org["id"]),
                    "name": org["login"],
                    "url": org["url"]
                    .replace("api.github.com", "github.com")
                    .replace("/orgs/", "/"),
                }
            )
        return organizations

    async def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get repositories (projects) for an organization from GitHub.
        """
        params = {
            "per_page": GITHUB_DEFAULT_PAGE_SIZE,
            "sort": "updated",
            "direction": "desc",
        }
        if organization_id == "personal":
            repos_data = await self._make_request("user/repos", params)
        else:
            repos_data = await self._make_request(
                f"orgs/{organization_id}/repos", params
            )
        projects = []
        for repo in repos_data:
            projects.append(
                {
                    "id": str(repo["id"]),
                    "identifier": str(repo["id"]),
                    "name": repo["name"],
                    "description": repo["description"] or "",
                    "url": repo["html_url"],
                    "meta_data": {
                        "full_name": repo["full_name"],
                        "default_branch": repo["default_branch"],
                        "language": repo.get("language"),
                        "created_at": repo["created_at"],
                        "updated_at": repo["pushed_at"],
                        "stars": repo["stargazers_count"],
                    },
                }
            )
        return projects

    async def get_issues(
        self,
        organization_id: str,
        project_id: str,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a repository from GitHub.
        """
        if "/" in project_id:
            repo_name = project_id
        else:
            try:
                repo_details = await self._make_request(f"repositories/{project_id}")
                repo_name = repo_details["full_name"]
            except TrackerResponseError as e:
                logger.error(
                    f"Failed to get repository details for project_id {project_id}: {e}"
                )
                return []

        params = {
            "state": "all",
            "per_page": GITHUB_DEFAULT_PAGE_SIZE,
            "sort": "updated",
            "direction": "desc",
        }
        if since:
            params["since"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        issues_endpoint = f"repos/{repo_name}/issues"
        try:
            raw_issues_data = await self._make_request(issues_endpoint, params)
        except TrackerResponseError as e:
            logger.error(f"Failed to get issues for repo {repo_name}: {e}")
            return []

        processed_issues = []
        for issue_data in raw_issues_data:
            if "pull_request" in issue_data:
                continue

            issue_number = issue_data["number"]
            comments_data_transformed = []
            comments_endpoint = f"repos/{repo_name}/issues/{issue_number}/comments"
            try:
                raw_comments_data = await self._make_request(
                    comments_endpoint, params={"per_page": GITHUB_DEFAULT_PAGE_SIZE}
                )
                if isinstance(raw_comments_data, dict):
                    raw_comments_data = [raw_comments_data]
                for comment_item in raw_comments_data:
                    comment_created_at = datetime.strptime(
                        comment_item["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                    )
                    comment_updated_at = datetime.strptime(
                        comment_item["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
                    )

                    comments_data_transformed.append(
                        IssueComment(
                            id=str(comment_item["id"]),
                            body=comment_item.get("body", "") or "",
                            author=IssueUser(
                                id=str(comment_item["user"]["id"]),
                                name=comment_item["user"]["login"],
                                avatar_url=comment_item["user"]["avatar_url"],
                            ),
                            created_at=comment_created_at,
                            updated_at=comment_updated_at,
                            url=comment_item.get("html_url"),
                        )
                    )
            except TrackerResponseError as e:
                logger.error(
                    f"Failed to get comments for issue {repo_name}#{issue_number}: {e}"
                )

            issue_data["comments"] = comments_data_transformed

            # Parse dependencies from issue body and comments
            dependencies = []
            if issue_data.get("body"):
                dependencies.extend(
                    await self._parse_dependencies(issue_data["body"], repo_name)
                )
            for comment in comments_data_transformed:
                if comment.body:
                    dependencies.extend(
                        await self._parse_dependencies(comment.body, repo_name)
                    )
            issue_data["dependencies"] = dependencies

            processed_issues.append(issue_data)
        return processed_issues

    async def register_webhook(
        self, db: Session, organization: Organization, webhook_url: str, secret: str
    ) -> bool:
        """
        Register a webhook for the given GitHub organization.
        """
        org_identifier = organization.identifier
        if org_identifier == "personal":
            logger.info(
                f"Skipping webhook registration for personal account '{self.connection_details.get('login', 'N/A')}'."
            )
            return True

        endpoint = f"orgs/{org_identifier}/hooks"
        events = [
            "issues",
            "project",
            "repository",
            "push",
        ]
        payload = {
            "name": "web",
            "active": True,
            "events": events,
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
                response = await client.post(url, headers=self.headers, json=payload)

            if response.status_code in [HTTP_STATUS_OK, HTTP_STATUS_CREATED]:
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
            elif response.status_code == HTTP_STATUS_UNAUTHORIZED:
                logger.error(
                    f"GitHub authentication failed while trying to register webhook for org '{org_identifier}'."
                )
                return False
            elif response.status_code == 403:
                logger.error(
                    f"Permission denied: Unable to register webhook for GitHub org '{org_identifier}'. Check token permissions (needs admin:org_hook)."
                )
                return False
            elif response.status_code == HTTP_STATUS_NOT_FOUND:
                logger.error(
                    f"GitHub organization '{org_identifier}' not found while trying to register webhook."
                )
                return False
            elif response.status_code == HTTP_STATUS_UNPROCESSABLE_ENTITY:
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

        except httpx.RequestError as e:
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

    async def unregister_webhook(self, db: Session, webhook: Webhook) -> bool:
        """
        Unregister a webhook for the given GitHub organization.

        Args:
            db: The database session.
            webhook: The webhook to unregister.

        Returns:
            True if unregistration was successful, False otherwise.
        """
        org_identifier = None
        if webhook.organization:
            org_identifier = webhook.organization.identifier
        elif webhook.project:
            org_identifier = webhook.project.organization.identifier
        webhook_id = webhook.external_id

        if not org_identifier or org_identifier == "personal":
            logger.info(f"Skipping webhook unregistration for org '{org_identifier}'.")
            return True

        if webhook.project:
            repo_full_name = webhook.project.slug
            endpoint = f"repos/{repo_full_name}/hooks/{webhook_id}"
        else:
            endpoint = f"orgs/{org_identifier}/hooks/{webhook_id}"
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
                response = await client.delete(url, headers=self.headers)

            if response.status_code == HTTP_STATUS_NO_CONTENT:
                logger.info(
                    f"Successfully unregistered webhook {webhook_id} for GitHub org '{org_identifier}'."
                )
                crud_webhook.remove(db, id=webhook.id)
                return True
            elif response.status_code == HTTP_STATUS_NOT_FOUND:
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
        except httpx.RequestError as e:
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

    async def unregister_all_webhooks(
        self, db: Session, webhook_url_pattern: Optional[str] = None
    ) -> Dict[str, int]:
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
            organizations = crud_organization.get_multi(db, tracker_id=self.tracker_id)
            organization_ids = [org.id for org in organizations]
            project_ids = []
            for org_id in organization_ids:
                projects = crud_project.get_for_organization(db, organization_id=org_id)
                project_ids.extend([proj.id for proj in projects])

            webhooks_to_delete = (
                db.query(Webhook)
                .filter(
                    (Webhook.organization_id.in_(organization_ids))
                    | (Webhook.project_id.in_(project_ids))
                )
                .all()
            )

            if not webhooks_to_delete:
                logger.info("No webhooks found in the database for this tracker.")
                return results

            for webhook in webhooks_to_delete:
                if await self.unregister_webhook(db=db, webhook=webhook):
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

    async def cleanup_stale_webhooks(
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
            await self._cleanup_project_webhooks(spacebridge_url, results)
        else:
            await self._cleanup_organization_webhooks(spacebridge_url, results)

        logger.info(f"Webhook cleanup summary: {results}")
        return results

    async def _cleanup_organization_webhooks(
        self, spacebridge_url: str, results: dict
    ) -> None:
        """Helper to clean up organization-level webhooks."""
        try:
            organizations = await self.get_organizations()
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Failed to retrieve organizations: {e}")
            return

        for org in organizations:
            org_login = org.get("name")
            if not org_login or org.get("id") == "personal":
                continue

            logger.info(f"Checking webhooks for organization: {org_login}")
            try:
                hooks = await self._make_request(f"orgs/{org_login}/hooks")
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(f"Failed to list webhooks for {org_login}: {e}")
                results["failed"] += 1
                continue

            for hook in hooks:
                await self._process_hook(
                    hook, spacebridge_url, results, f"orgs/{org_login}/hooks"
                )

    async def _cleanup_project_webhooks(
        self, spacebridge_url: str, results: dict
    ) -> None:
        """Helper to clean up repository-level webhooks."""
        try:
            organizations = await self.get_organizations()
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Failed to retrieve organizations: {e}")
            return

        for org in organizations:
            org_id = org.get("id")
            if not org_id:
                continue

            try:
                projects = await self.get_projects(org_id)
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(
                    f"Failed to retrieve projects for org {org.get('name')}: {e}"
                )
                continue

            for repo in projects:
                repo_full_name = repo.get("meta_data", {}).get("full_name")
                if not repo_full_name:
                    continue

                logger.info(f"Checking webhooks for repository: {repo_full_name}")
                try:
                    hooks = await self._make_request(f"repos/{repo_full_name}/hooks")
                except (TrackerConnectionError, TrackerResponseError) as e:
                    logger.error(f"Failed to list webhooks for {repo_full_name}: {e}")
                    results["failed"] += 1
                    continue

                for hook in hooks:
                    await self._process_hook(
                        hook, spacebridge_url, results, f"repos/{repo_full_name}/hooks"
                    )

    async def _process_hook(
        self, hook: dict, spacebridge_url: str, results: dict, base_endpoint: str
    ) -> None:
        """Processes a single webhook for cleanup."""
        hook_id = hook.get("id")
        hook_config = hook.get("config", {})
        hook_url = hook_config.get("url")

        if not all([hook_id, hook_url]):
            return

        if not hook_url.startswith(spacebridge_url):
            logger.info(
                f"Found stale webhook {hook_id} in {base_endpoint} pointing to {hook_url}. Deleting..."
            )
            try:
                delete_endpoint = f"{base_endpoint}/{hook_id}"
                if await self._make_request_delete(delete_endpoint):
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

    async def is_webhook_registered(self, webhook: "Webhook") -> bool:
        """
        Check if a webhook is registered in the tracker.

        Args:
            webhook: The webhook to check.

        Returns:
            Whether the webhook is registered.
        """
        if not webhook.external_id:
            return False

        if not webhook.project:
            return False
        repo_full_name = webhook.project.slug
        endpoint = f"repos/{repo_full_name}/hooks/{webhook.external_id}"
        try:
            await self._make_request(endpoint)
            return True
        except TrackerResponseError as e:
            if "Not Found" in str(e):
                return False
            raise

    async def get_webhooks(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get all webhooks for a specific organization's repositories.
        """
        all_webhooks = []
        repos = await self.get_projects(organization_id)
        for repo in repos:
            repo_full_name = repo["meta_data"]["full_name"]
            try:
                repo_webhooks = await self._make_request(
                    f"repos/{repo_full_name}/hooks",
                    params={"per_page": GITHUB_DEFAULT_PAGE_SIZE},
                )
                all_webhooks.extend(repo_webhooks)
            except TrackerResponseError as e:
                logger.error(f"Failed to get webhooks for repo {repo_full_name}: {e}")
        return all_webhooks

    async def delete_webhook(self, webhook: Dict[str, Any]) -> bool:
        """
        Delete a webhook from the tracker.

        Args:
            webhook: The webhook to delete.

        Returns:
            Whether the webhook was deleted successfully.
        """
        webhook_id = webhook.get("id")
        if not webhook_id:
            return False

        # The webhook response doesn't contain the org identifier, so we have to parse it from the url
        url = webhook.get("url")
        if not url:
            return False

        org_identifier = url.split("/")[-2]
        endpoint = f"orgs/{org_identifier}/hooks/{webhook_id}"
        try:
            return await self._make_request_delete(endpoint)
        except TrackerResponseError as e:
            logger.error(f"Failed to delete webhook {webhook_id}: {e}")
            return False

    async def is_webhook_registered_for_project(
        self, project: "Project", webhook_url: str
    ) -> bool:
        """
        Check if a webhook is registered for a project.

        Args:
            project: The project to check.
            webhook_url: The URL of the webhook.

        Returns:
            Whether the webhook is registered.
        """
        endpoint = f"repos/{project.slug}/hooks"
        try:
            hooks = await self._make_request(endpoint)
            for hook in hooks:
                if hook.get("config", {}).get("url") == webhook_url:
                    return True
            return False
        except TrackerResponseError:
            return False

    def transform_organization(self, org_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transforms a GitHub organization into the common format."""
        return {
            "identifier": str(org_data["id"]),
            "name": org_data["name"],
            "url": org_data.get("url"),
            "meta_data": {"source": "github"},
        }

    def transform_project(
        self, proj_data: Dict[str, Any], organization_id: str
    ) -> Dict[str, Any]:
        """Transforms a GitHub repository into the common format."""
        return {
            "identifier": str(proj_data["id"]),
            "name": proj_data["name"],
            "description": proj_data.get("description"),
            "url": proj_data.get("url"),
            "organization_id": organization_id,
            "meta_data": proj_data.get("meta_data"),
        }

    def transform_issue(
        self, issue_data: Dict[str, Any], project: "Project"
    ) -> Dict[str, Any]:
        """Transforms a GitHub issue into the common format."""
        return {
            "external_id": str(issue_data["id"]),
            "key": f"{project.slug}#{issue_data['number']}",
            "title": issue_data["title"],
            "description": issue_data.get("body"),
            "status": issue_data["state"],
            "created_at": datetime.strptime(
                issue_data["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ),
            "updated_at": datetime.strptime(
                issue_data["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
            ),
            "project_id": project.id,
            "comments": issue_data.get("comments", []),
        }

    def transform_comment(
        self, comment_data: Dict[str, Any], issue_id: str
    ) -> Dict[str, Any]:
        """Transforms a GitHub comment into the common format."""
        return {
            "external_id": str(comment_data["id"]),
            "body": comment_data.get("body"),
            "created_at": datetime.strptime(
                comment_data["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ),
            "updated_at": datetime.strptime(
                comment_data["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
            ),
            "issue_id": issue_id,
        }

    async def is_webhook_registered_for_organization(
        self, organization: "Organization", webhook_url: str
    ) -> bool:
        """
        Check if a webhook is registered for an organization.

        Args:
            organization: The organization to check.
            webhook_url: The URL of the webhook.

        Returns:
            Whether the webhook is registered.
        """
        endpoint = f"orgs/{organization.identifier}/hooks"
        try:
            hooks = await self._make_request(endpoint)
            for hook in hooks:
                if hook.get("config", {}).get("url") == webhook_url:
                    return True
            return False
        except TrackerResponseError:
            return False
