"""
Jira tracker implementation for SpaceSync.
"""

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import urllib.parse

import requests
from jira import JIRA, JIRAError  # type: ignore
from sqlalchemy.orm import Session

from spacemodels.crud import crud_webhook
from spacemodels.models.issue import DESCRIPTION_MAX_LENGTH

from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from ..utils import retry
from .base import BaseTracker
from spacemodels.models.project import Project
from spacemodels.models.webhook import Webhook
from spacemodels.models.organization import Organization
from spacemodels.crud import crud_project, crud_organization


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

        Args:
            tracker_id: ID of the tracker in the database (UUID string).
            api_key: Jira API token (or password for Basic Auth).
            connection_details: Connection details including:
                - jira_url: URL of the Jira instance
                - username: Jira username for authentication
                - url: Alternative field for Jira URL (for compatibility)
        """
        super().__init__(tracker_id, api_key, connection_details)

        jira_url = connection_details.get("jira_url") or connection_details.get("url")
        if not jira_url:
            raise ValueError(
                "Jira URL is required in connection_details (either 'jira_url' or 'url')"
            )

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
                logger.error(
                    f"Failed to initialize Jira client (JIRAError): {e.status_code} - {e.text}"
                )
                if e.status_code == 401:
                    raise TrackerAuthenticationError(
                        f"Jira client authentication failed: {e.text}"
                    )
                else:
                    raise TrackerConnectionError(
                        f"Jira client connection/setup failed: {e.text}"
                    )
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred during Jira client initialization: {e}"
                )
                raise TrackerConnectionError(
                    f"Unexpected error initializing Jira client: {str(e)}"
                )
        else:
            logger.warning(
                "Jira client could not be initialized due to missing credentials/URL."
            )

    @retry(max_attempts=3, exceptions=(TrackerConnectionError, TrackerResponseError))
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a request to the Jira API using the requests library."""
        try:
            url = f"{self.jira_url}/rest/api/2/{endpoint.lstrip('/')}"
            response = requests.request(
                method.upper(), url, headers=self.headers, params=params, json=json_data
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
        except requests.RequestException as e:
            raise TrackerConnectionError(f"Jira connection error: {str(e)}")

    def get_organizations(self) -> List[Dict[str, Any]]:
        """Get organizations from Jira."""
        import re

        domain_match = re.search(r"https?://([^/]+)", self.jira_url)
        org_name = domain_match.group(1) if domain_match else "Jira Instance"
        return [{"id": org_name, "name": org_name, "url": self.jira_url}]

    def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """Get projects from Jira."""
        projects_data = self._make_request("GET", "project")
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

    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get issues for a project from Jira, including their comments and dependencies."""
        jql = f"project = {project_id}"
        if since:
            jql += f" AND updated >= '{since.strftime('%Y-%m-%d %H:%M')}'"

        params = {
            "jql": jql,
            "maxResults": 100,
            "fields": "id,key,summary,description,status,created,updated,labels,assignee,issuetype,comment,issuelinks",
        }

        try:
            issues_response = self._make_request("GET", "search", params=params)
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
            except (ValueError, TypeError):
                created_dt = datetime.now()
                updated_dt = created_dt

            assignee_list = (
                [issue_data["fields"]["assignee"]["displayName"]]
                if issue_data["fields"].get("assignee")
                else []
            )

            comments_transformed = []
            if issue_data["fields"].get("comment", {}).get("comments"):
                for comment_item in issue_data["fields"]["comment"]["comments"]:
                    try:
                        comment_created_dt = datetime.strptime(
                            comment_item["created"], "%Y-%m-%dT%H:%M:%S.%f%z"
                        ).replace(tzinfo=None)
                        comment_updated_dt = datetime.strptime(
                            comment_item["updated"], "%Y-%m-%dT%H:%M:%S.%f%z"
                        ).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        comment_created_dt = datetime.now()
                        comment_updated_dt = comment_created_dt

                    author = comment_item.get("author", {})
                    author_name = (
                        author.get("name")
                        or author.get("displayName")
                        or author.get("key")
                        or author.get("accountId")
                    )

                    comments_transformed.append(
                        {
                            "id": str(comment_item["id"]),
                            "body": comment_item.get("body", ""),
                            "author": author_name,
                            "created_at": comment_created_dt,
                            "updated_at": comment_updated_dt,
                            "url": f"{self.jira_url}/browse/{issue_data['key']}?focusedCommentId={comment_item['id']}#comment-{comment_item['id']}",
                        }
                    )

            description_text = issue_data["fields"].get("description") or ""
            dependencies = self._parse_dependencies(issue_data)

            processed_issues.append(
                {
                    "id": issue_data["id"],
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
                    "dependencies": dependencies,
                }
            )
        return processed_issues

    def _parse_dependencies(self, issue_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Parse issue links from Jira issue data."""
        dependencies = []
        for link in issue_data.get("fields", {}).get("issuelinks", []):
            link_type = link.get("type", {})
            if "outwardIssue" in link:
                target_issue = link["outwardIssue"]
                relationship_type = link_type.get("outward", "relates to")
            elif "inwardIssue" in link:
                target_issue = link["inwardIssue"]
                relationship_type = link_type.get("inward", "relates to")
            else:
                continue

            dependencies.append(
                {
                    "target_key": target_issue["key"],
                    "type": relationship_type,
                }
            )
        return dependencies

    def transform_issue(
        self, issue_data: Dict[str, Any], project: Project
    ) -> Dict[str, Any]:
        """Transforms Jira issue data into a standardized format."""
        # Get issue status from data or default to "open"
        status = issue_data.get("state", "open")

        # Map common status values to standardized ones
        if status.lower() in ["closed", "done", "completed", "fixed"]:
            status = "closed"
        elif status.lower() in ["open", "new", "todo", "to do"]:
            status = "open"

        # Convert datetime objects to ISO format strings for JSON serialization
        last_updated = issue_data.get("updated_at")
        if isinstance(last_updated, datetime):
            last_updated = last_updated.isoformat()

        created_at = issue_data.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        # Get description and truncate if necessary to avoid DB errors
        description = issue_data.get("description", "")
        original_length = len(description) if description else 0

        if description and len(description) > DESCRIPTION_MAX_LENGTH:
            # Truncate to the max length, with an indicator
            description = (
                description[: DESCRIPTION_MAX_LENGTH - 25] + "... [content truncated]"
            )
            logger.info(
                f"Truncated issue description from {original_length} to {len(description)} characters. "
                f"Set ISSUE_DESCRIPTION_MAX_LENGTH env var to increase (current: {DESCRIPTION_MAX_LENGTH})"
            )

        issue_url = issue_data.get("url", "")

        transformed_data = {
            "project_id": project.id,
            "external_id": issue_data.get("id", issue_data.get("external_id")),
            "key": issue_data.get("key"),
            "title": issue_data.get("title"),
            "description": description,
            "status": status,
            "priority": issue_data.get("priority", None),
            "external_url": issue_url,
            "updated_at": last_updated,
            "last_synced": datetime.now(),
            "meta_data": {
                "labels": issue_data.get("labels", []),
                "assignees": issue_data.get("assignees", []),
                "url": issue_url,
                "external_url": issue_url,
                "source": "spacesync",
            },
            "tracker_id": self.tracker_id,
            "comments": issue_data.get("comments", []),
            "dependencies": issue_data.get("dependencies", []),
        }

        return transformed_data

    def transform_issue_webhook(
        self, issue_data: Dict[str, Any], project: "Project"
    ) -> Dict[str, Any]:
        """Transforms Jira issue data into a standardized format."""
        # Get issue status from data or default to "open"
        status = issue_data["fields"].get("status", {}).get("name")
        # Map common status values to standardized ones
        if status.lower() in ["closed", "done", "completed", "fixed"]:
            status = "closed"
        elif status.lower() in ["open", "new", "todo", "to do"]:
            status = "open"
        # Add more mappings as needed

        # Get issue type or default to "task"
        issue_type = issue_data["fields"].get("issuetype", {}).get("name")
        # Map common types to standardized ones
        if issue_type.lower() in ["bug", "defect", "error"]:
            issue_type = "bug"
        elif issue_type.lower() in ["feature", "enhancement", "improvement"]:
            issue_type = "feature"

        # Convert datetime objects to ISO format strings for JSON serialization
        last_updated = issue_data["fields"].get("updated")
        if isinstance(last_updated, datetime):
            last_updated = last_updated.isoformat()

        created_at = issue_data["fields"].get("created")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        # Get description and truncate if necessary to avoid DB errors
        description = issue_data["fields"].get("description", "")
        original_length = len(description) if description else 0

        if description and len(description) > DESCRIPTION_MAX_LENGTH:
            # Truncate to the max length, with an indicator
            description = (
                description[: DESCRIPTION_MAX_LENGTH - 25] + "... [content truncated]"
            )
            logger.info(
                f"Truncated issue description from {original_length} to {len(description)} characters. "
                f"Set ISSUE_DESCRIPTION_MAX_LENGTH env var to increase (current: {DESCRIPTION_MAX_LENGTH})"
            )

        issue_url = issue_data.get("url", "")

        transformed_data = {
            "project_id": project.id,
            "external_id": issue_data.get("id", issue_data.get("external_id")),
            "key": issue_data.get("key"),
            "title": issue_data["fields"]["summary"],
            "description": description,
            "status": status,
            "issue_type": issue_type,
            "priority": issue_data.get("priority", None),
            "updated_at": last_updated,
            "last_updated_external": last_updated,
            "last_synced": datetime.now(),
            "meta_data": {
                "labels": issue_data["fields"].get("labels", []),
                "assignees": issue_data["fields"]
                .get("assignee", {})
                .get("displayName", []),
                "url": issue_url,
                "external_url": issue_url,
                "external_created_at": created_at,
                "external_updated_at": last_updated,
                "source": "spacesync",
            },
            "tracker_id": self.tracker_id,
            "comments": issue_data.get("comments", []),
            "dependencies": issue_data.get("dependencies", []),
        }

        if "external_id" not in transformed_data:
            transformed_data["external_id"] = issue_data.get("id")
        return transformed_data

    def _handle_jira_error(self, e: JIRAError, context: str) -> None:
        """Helper to map JIRAError to tracker exceptions."""
        logger.error(f"{context} (JIRAError): {e.status_code} - {e.text}")
        if e.status_code == 401:
            raise TrackerAuthenticationError(
                f"{context}: Jira authentication failed: {e.text}"
            )
        elif e.status_code == 403:
            raise TrackerAuthenticationError(
                f"{context}: Jira permission denied: {e.text}"
            )
        elif e.status_code == 404:
            raise TrackerResponseError(f"{context}: Jira resource not found: {e.text}")
        else:
            raise TrackerResponseError(
                f"{context}: Jira API error {e.status_code}: {e.text}"
            )

    def register_project_webhook(
        self, db: Session, project: Project, webhook_url: str, secret: str
    ) -> bool:
        """
        Register a webhook for the given Jira project.
        """
        logger.info(
            f"Attempting to register project webhook for Jira project '{project.identifier}' pointing to {webhook_url}"
        )
        hook_attrs = {
            "url": webhook_url,
            "token": secret,
            "events": ["issue_created", "issue_updated", "issue_deleted"],
        }
        try:
            self.jira_client.webhooks.create(
                project_id=project.external_id, **hook_attrs
            )
            logger.info(
                f"Successfully registered project webhook for Jira project '{project.identifier}'"
            )
            return True
        except JIRAError as e:
            logger.error(
                f"Failed to register project webhook for Jira project '{project.identifier}': {e.text}"
            )
            return False

    def register_webhook(
        self,
        db: Session,
        project: Project,
        webhook_url: str,
        secret: str,
        events: Optional[List[str]] = None,
    ) -> bool:
        """Register a webhook for the Jira project, tracking it in the database."""
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot register webhook.")
            return False

        existing_webhook = crud_webhook.get_by_project_id(db, project_id=project.id)
        if existing_webhook:
            logger.info(
                f"Webhook for project {project.identifier} already registered in database. Skipping."
            )
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

    def unregister_webhook(self, db: Session, webhook: Webhook) -> bool:
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

    def unregister_all_webhooks(self, db: Session) -> None:
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

    def cleanup_stale_webhooks(self, spacebridge_url: str) -> Dict[str, int]:
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

    def is_webhook_registered(self, webhook: "Webhook") -> bool:
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

    def get_webhooks(self) -> List[Dict[str, Any]]:
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

    def delete_webhook(self, webhook: Dict[str, Any]) -> bool:
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

    def is_webhook_registered_for_project(
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

    def is_webhook_registered_for_organization(
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
