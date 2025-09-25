"""
Jira tracker implementation for SpaceSync.
"""

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import logging
import urllib.parse
import requests

import httpx
from jira import JIRA, JIRAError
from sqlalchemy.orm import Session

from spacemodels.crud import crud_webhook, crud_organization, crud_project
from spacebridge.schemas.tracker_models import (
    Issue,
    IssueComment,
    IssueCreate,
    IssueFilter,
    IssueUpdate,
    ProjectMetadata,
    TrackerConnection,
    IssueStatus,
    IssueUser,
)

from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from .base import BaseTracker
from spacemodels.models.project import Project
from spacemodels.models.webhook import Webhook
from spacemodels.models.organization import Organization


logger = logging.getLogger(__name__)

DEFAULT_JIRA_WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "comment_created",
]


class JiraTracker(BaseTracker):
    """Jira tracker implementation."""

    def __init__(
        self, tracker_id: str, api_key: str, connection_details: Dict[str, Any]
    ):
        """
        Initialize the Jira tracker.
        """
        super().__init__(tracker_id, api_key, connection_details)

        jira_url = connection_details.get("jira_url") or connection_details.get("url")
        if not jira_url:
            raise ValueError("Jira URL is required in connection_details")

        if "username" not in connection_details:
            raise ValueError("Jira username is required in connection_details")

        self.jira_url = jira_url.rstrip("/")
        self.username = connection_details["username"]

        auth_str = f"{self.username}:{api_key}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }

        self.jira_client: Optional[JIRA] = None
        if self.jira_url and self.username and api_key:
            try:
                self.jira_client = JIRA(
                    server=self.jira_url,
                    basic_auth=(self.username, api_key),
                    timeout=20,
                    max_retries=3,
                )
            except JIRAError as e:
                if e.status_code == 401:
                    raise TrackerAuthenticationError(
                        f"Jira client authentication failed: {e.text}"
                    )
                else:
                    raise TrackerConnectionError(
                        f"Jira client connection/setup failed: {e.text}"
                    )
            except Exception as e:
                raise TrackerConnectionError(
                    f"Unexpected error initializing Jira client: {str(e)}"
                )

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a request to the Jira API using httpx."""
        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.jira_url}/rest/api/2/{endpoint.lstrip('/')}"
                response = await client.request(
                    method.upper(),
                    url,
                    headers=self.headers,
                    params=params,
                    json=json_data,
                )

                if response.status_code == 401:
                    raise TrackerAuthenticationError("Jira authentication failed")

                if 200 <= response.status_code < 300:
                    if response.status_code == 204:
                        return None
                    if response.content:
                        try:
                            return response.json()
                        except ValueError:
                            return response.text
                    return None

                raise TrackerResponseError(
                    f"Jira API error: {response.status_code} - {response.text}"
                )
            except httpx.RequestError as e:
                raise TrackerConnectionError(f"Jira connection error: {str(e)}")

    async def test_connection(self) -> TrackerConnection:
        """Test the connection to the tracker."""
        try:
            await self._make_request("GET", "myself")
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
        """Get organizations from Jira."""
        import re

        domain_match = re.search(r"https?://([^/]+)", self.jira_url)
        org_name = domain_match.group(1) if domain_match else "Jira Instance"
        return [{"id": org_name, "name": org_name, "url": self.jira_url}]

    async def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """Get projects from Jira."""
        projects_data = await self._make_request("GET", "project")
        projects = []
        for project in projects_data:
            projects.append(
                {
                    "id": project["id"],
                    "identifier": project["key"],
                    "name": project["name"],
                    "description": project.get("description", ""),
                    "url": f"{self.jira_url}/projects/{project['key']}",
                }
            )
        return projects

    async def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Issue]:
        """Get issues for a project from Jira."""
        jql = f"project = {project_id}"
        if since:
            jql += f" AND updated >= '{since.strftime('%Y-%m-%d %H:%M')}'"

        params = {
            "jql": jql,
            "maxResults": 100,
            "fields": "id,key,summary,description,status,created,updated,labels,assignee,issuetype,comment,issuelinks",
        }

        try:
            issues_response = await self._make_request("GET", "search", params=params)
        except TrackerResponseError as e:
            logger.error(f"Failed to get Jira issues for project {project_id}: {e}")
            return []

        processed_issues = []
        for issue_data in issues_response.get("issues", []):
            comments_transformed = []
            if issue_data["fields"].get("comment", {}).get("comments"):
                for comment_item in issue_data["fields"]["comment"]["comments"]:
                    comments_transformed.append(
                        IssueComment(
                            id=str(comment_item["id"]),
                            body=comment_item.get("body", ""),
                            author=IssueUser(
                                id=comment_item["author"]["key"],
                                name=comment_item["author"]["displayName"],
                                avatar_url=comment_item["author"]["avatarUrls"][
                                    "48x48"
                                ],
                            ),
                            created_at=datetime.strptime(
                                comment_item["created"], "%Y-%m-%dT%H:%M:%S.%f%z"
                            ).replace(tzinfo=None),
                            updated_at=datetime.strptime(
                                comment_item["updated"], "%Y-%m-%dT%H:%M:%S.%f%z"
                            ).replace(tzinfo=None),
                        )
                    )

            processed_issues.append(
                Issue(
                    id=issue_data["id"],
                    key=issue_data["key"],
                    title=issue_data["fields"]["summary"],
                    description=issue_data["fields"].get("description") or "",
                    status=IssueStatus(
                        id=issue_data["fields"]["status"]["id"],
                        name=issue_data["fields"]["status"]["name"],
                        category=issue_data["fields"]["status"]["statusCategory"][
                            "key"
                        ],
                    ),
                    created_at=datetime.strptime(
                        issue_data["fields"]["created"], "%Y-%m-%dT%H:%M:%S.%f%z"
                    ).replace(tzinfo=None),
                    updated_at=datetime.strptime(
                        issue_data["fields"]["updated"], "%Y-%m-%dT%H:%M:%S.%f%z"
                    ).replace(tzinfo=None),
                    labels=issue_data["fields"].get("labels", []),
                    assignee=IssueUser(
                        id=issue_data["fields"]["assignee"]["key"],
                        name=issue_data["fields"]["assignee"]["displayName"],
                        avatar_url=issue_data["fields"]["assignee"]["avatarUrls"][
                            "48x48"
                        ],
                    )
                    if issue_data["fields"].get("assignee")
                    else None,
                    url=f"{self.jira_url}/browse/{issue_data['key']}",
                    comments=comments_transformed,
                    tracker_type="jira",
                    project_key=project_id,
                )
            )
        return processed_issues

    async def register_webhook(
        self,
        db: Session,
        project: Project,
        webhook_url: str,
        secret: str,
        events: Optional[List[str]] = None,
    ) -> bool:
        """Register a webhook for the Jira project."""
        if not self.jira_client:
            return False

        existing_webhook = crud_webhook.get_by_project_id(db, project_id=project.id)
        if existing_webhook:
            return True

        actual_events = events or DEFAULT_JIRA_WEBHOOK_EVENTS
        webhook_name = f"SpaceBridge Sync for {project.identifier}"

        parsed_url = urllib.parse.urlparse(webhook_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        query_params["project_key"] = [project.identifier]
        new_query_string = urllib.parse.urlencode(query_params, doseq=True)
        url_with_secret_and_project = parsed_url._replace(
            query=new_query_string
        ).geturl()

        jql_filter = f"project = {project.identifier.upper()}"

        try:
            logger.info(
                f"Registering webhook for project {project.identifier} in Jira."
            )
            response = self.jira_client._session.post(
                f"{self.jira_url}/rest/webhooks/1.0/webhook",
                json={
                    "name": webhook_name,
                    "url": url_with_secret_and_project,
                    "events": actual_events,
                    "jqlFilter": jql_filter,
                    "excludeIssueDetails": False,
                    "secret": secret,
                },
            )
            response.raise_for_status()
            webhook_data = response.json()
            webhook_id = str(webhook_data.get("id"))

            crud_webhook.create(
                db,
                obj_in={
                    "project_id": project.id,
                    "external_id": webhook_id,
                    "url": url_with_secret_and_project,
                    "secret": secret,
                    "events": actual_events,
                },
            )
            logger.info(
                f"Successfully registered webhook {webhook_id} for project {project.identifier}."
            )
            return True
        except JIRAError as e:
            if (
                e.status_code == 400
                and "webhook with same name and url already exists" in e.text.lower()
            ):
                logger.warning(
                    f"Webhook for project {project.identifier} already exists in Jira. Assuming it's ours."
                )
                return True
            self._handle_jira_error(
                e, f"registering webhook for project {project.identifier}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error registering webhook for {project.identifier}: {e}",
                exc_info=True,
            )
            raise TrackerConnectionError(
                f"Unexpected error registering webhook for {project.identifier}: {str(e)}"
            )

    async def unregister_webhook(self, db: Session, webhook: Webhook) -> bool:
        """Unregister a webhook for a project using the database record."""
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot unregister webhook.")
            return False

        try:
            logger.info(
                f"Attempting to unregister webhook with external ID {webhook.external_id}."
            )
            self.jira_client._session.delete(
                f"{self.jira_url}/rest/webhooks/1.0/webhook/{webhook.external_id}"
            )
            logger.info(
                f"Successfully unregistered webhook {webhook.external_id} from Jira."
            )
        except JIRAError as e:
            if e.status_code == 404:
                logger.warning(
                    f"Webhook {webhook.external_id} not found in Jira. Assuming already deleted."
                )
            else:
                self._handle_jira_error(
                    e, f"unregistering webhook {webhook.external_id}"
                )
                return False

        crud_webhook.remove(db, id=webhook.id)
        logger.info(
            f"Removed webhook record for project_id {webhook.project_id} from database."
        )
        return True
        return True

    async def unregister_all_webhooks(self, db: Session) -> None:
        """Unregister all webhooks for all projects in an organization."""
        results = {"unregistered": 0, "failed": 0, "not_found": 0}
        logger.info(f"Unregistering all webhooks for Jira tracker {self.tracker_id}.")

        organization_id = crud_organization.get_for_tracker(
            db, tracker_id=self.tracker_id
        )[0].id
        projects = crud_project.get_for_organization(
            db, organization_id=organization_id
        )

        if not projects:
            logger.info(
                f"No projects found for organization {organization_id}. No webhooks to unregister."
            )
            return results

        logger.info(
            f"Starting unregistration of all webhooks for organization {organization_id}..."
        )
        for proj in projects:
            try:
                webhook = crud_webhook.get_by_project_id(db, project_id=proj.id)
                if not webhook:
                    logger.warning(
                        f"No webhook found for project {proj.name} ({proj.identifier}). Skipping."
                    )
                    continue
                logger.info(
                    f"Unregistering webhook for project: {proj.name} ({proj.identifier})"
                )
                if self.unregister_webhook(db, webhook=webhook):
                    results["unregistered"] += 1
                else:
                    results["not_found"] += 1
            except Exception as e:
                logger.error(
                    f"Failed to unregister webhook for project {proj.identifier}: {e}",
                    exc_info=True,
                )
                results["failed"] += 1
        logger.info(
            f"Finished unregistering webhooks for organization {organization_id}."
        )
        logger.info(f"Jira unregister_all_webhooks summary: {results}")
        return results

    async def cleanup_stale_webhooks(self, spacebridge_url: str) -> Dict[str, int]:
        """
        Deletes all webhooks from Jira that are associated with a given SpaceBridge URL.

        This method is useful for cleaning up stale webhooks that may be left over from
        previous or defunct instances of SpaceBridge.

        Args:
            spacebridge_url: The base URL of the SpaceBridge instance whose webhooks should be removed.

        Returns:
            A dictionary with counts of unregistered and failed deletions.
            Example: {"unregistered": 5, "failed": 1}
        """
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot clean up webhooks.")
            return {"unregistered": 0, "failed": 0}

        logger.info(f"Starting cleanup of stale webhooks for URL: {spacebridge_url}")
        results = {"unregistered": 0, "failed": 0}

        try:
            response = self.jira_client._session.get(
                f"{self.jira_url}/rest/webhooks/1.0/webhook"
            )
            response.raise_for_status()
            all_webhooks = response.json()
        except (JIRAError, requests.RequestException) as e:
            text = getattr(e, "text", str(e))
            logger.error(f"Failed to retrieve webhooks from Jira: {text}")
            if isinstance(e, JIRAError):
                self._handle_jira_error(e, "retrieving webhooks for cleanup")
            results["failed"] = 1
            return results

        stale_webhooks = [
            hook
            for hook in all_webhooks
            if hook.get("url", "").startswith(spacebridge_url)
        ]

        if not stale_webhooks:
            logger.info("No stale webhooks found.")
            return results

        logger.info(f"Found {len(stale_webhooks)} stale webhooks to delete.")

        for webhook in stale_webhooks:
            try:
                webhook_id = webhook["id"]
                url = f"{self.jira_url}/rest/webhooks/1.0/webhook/{webhook_id}"
                response = self.jira_client._session.delete(url)
                response.raise_for_status()
                logger.info(f"Successfully deleted stale webhook ID: {webhook_id}")
                results["unregistered"] += 1
            except (JIRAError, requests.RequestException) as e:
                text = getattr(e, "text", str(e))
                logger.error(
                    f"Failed to delete stale webhook ID {webhook.get('id', 'N/A')}: {text}"
                )
                results["failed"] += 1
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred while deleting webhook ID {webhook.get('id', 'N/A')}: {e}",
                    exc_info=True,
                )
                results["failed"] += 1

        logger.info(
            f"Webhook cleanup summary: {results['unregistered']} unregistered, {results['failed']} failed."
        )
        return results

    async def is_webhook_registered(self, webhook: "Webhook") -> bool:
        """
        Check if a webhook is registered in the tracker.

        Args:
            webhook: The webhook to check.

        Returns:
            Whether the webhook is registered.
        """
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot check webhook.")
            return False

        if not webhook.external_id:
            return False

        try:
            all_webhooks = self.get_webhooks()
            for wh in all_webhooks:
                if str(wh.get("id")) == webhook.external_id:
                    return True
            return False
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(
                f"Failed to check webhook {webhook.external_id} due to API error: {e}"
            )
            return False

    async def get_webhooks(self) -> List[Dict[str, Any]]:
        """
        Get all webhooks for the tracker.

        Returns:
            A list of webhooks.
        """
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot get webhooks.")
            return []

        try:
            response = self.jira_client._session.get(
                f"{self.jira_url}/rest/webhooks/1.0/webhook"
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise TrackerConnectionError(
                f"Jira connection error while getting webhooks: {str(e)}"
            )
        except JIRAError as e:
            self._handle_jira_error(e, "getting webhooks")
            return []

    async def delete_webhook(self, webhook: Dict[str, Any]) -> bool:
        """
        Delete a webhook from the tracker.

        Args:
            webhook: The webhook to delete.

        Returns:
            Whether the webhook was deleted successfully.
        """
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot delete webhook.")
            return False

        webhook_id = webhook.get("id")
        if not webhook_id:
            return False

        try:
            self._make_request("DELETE", f"/rest/webhooks/1.0/webhook/{webhook_id}")
            return True
        except TrackerResponseError as e:
            if "404" in str(e):
                logger.warning(
                    f"Webhook {webhook_id} not found in Jira, considering it deleted."
                )
                return True
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
        if not self.jira_client:
            return False

        try:
            hooks = self.get_webhooks()
            for hook in hooks:
                if hook.get("url") == webhook_url:
                    # Check if the hook is for the correct project
                    jql = hook.get("jqlFilter", "")
                    if f"project = {project.identifier.upper()}" in jql:
                        return True
            return False
        except (TrackerConnectionError, TrackerResponseError):
            return False

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
        # Jira webhooks are not registered at the organization level, but at the project level.
        # This method will return False to indicate that organization-level webhooks are not supported.
        return False
