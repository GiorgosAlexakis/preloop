"""
Jira tracker implementation for SpaceSync.
"""

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import urllib.parse

import requests
from jira import JIRA, JIRAError # type: ignore
from sqlalchemy.orm import Session

from spacemodels.crud import crud_webhook
from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from ..utils import retry
from .base import BaseTracker

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
        self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None
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
                    "id": project["key"],
                    "name": project["name"],
                    "description": project.get("description", ""),
                    "url": f"{self.jira_url}/projects/{project['key']}",
                }
            )
        return projects

    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get issues for a project from Jira, including their comments."""
        jql = f"project = {project_id}"
        if since:
            jql += f" AND updated >= '{since.strftime('%Y-%m-%d %H:%M')}'"

        params = {
            "jql": jql,
            "maxResults": 100,
            "fields": "id,key,summary,description,status,created,updated,labels,assignee,issuetype,comment",
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

            assignee_list = [
                issue_data["fields"]["assignee"]["displayName"]
            ] if issue_data["fields"].get("assignee") else []

            comments_transformed = []
            if issue_data["fields"].get("comment", {}).get("comments"):
                for comment_item in issue_data["fields"]["comment"]["comments"]:
                    try:
                        comment_created_dt = datetime.strptime(comment_item["created"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                        comment_updated_dt = datetime.strptime(comment_item["updated"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                    except (ValueError, TypeError):
                        comment_created_dt = datetime.now()
                        comment_updated_dt = comment_created_dt

                    author = comment_item.get("author", {})
                    author_id = author.get("accountId") or author.get("key") or author.get("name")

                    comments_transformed.append({
                        "id": str(comment_item["id"]),
                        "body": comment_item.get("body", ""),
                        "author_id": str(author_id) if author_id else None,
                        "created_at": comment_created_dt,
                        "updated_at": comment_updated_dt,
                        "url": f"{self.jira_url}/browse/{issue_data['key']}?focusedCommentId={comment_item['id']}#comment-{comment_item['id']}"
                    })

            description_text = issue_data["fields"].get("description") or ""

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
                }
            )
        return processed_issues

    def transform_issue(self, issue_data: Dict[str, Any], project: "Project") -> Dict[str, Any]:
        """Transforms Jira issue data into a standardized format."""
        transformed_data = super().transform_issue(issue_data, project)
        if "external_id" not in transformed_data:
            transformed_data["external_id"] = issue_data.get("id")
        return transformed_data

    def _handle_jira_error(self, e: JIRAError, context: str) -> None:
        """Helper to map JIRAError to tracker exceptions."""
        logger.error(f"{context} (JIRAError): {e.status_code} - {e.text}")
        if e.status_code == 401:
            raise TrackerAuthenticationError(f"{context}: Jira authentication failed: {e.text}")
        elif e.status_code == 403:
            raise TrackerAuthenticationError(f"{context}: Jira permission denied: {e.text}")
        elif e.status_code == 404:
            raise TrackerResponseError(f"{context}: Jira resource not found: {e.text}")
        else:
            raise TrackerResponseError(f"{context}: Jira API error {e.status_code}: {e.text}")

    def register_webhook(
        self,
        db: Session,
        project_id: str,
        project_key: str,
        webhook_url: str,
        secret: str,
        events: Optional[List[str]] = None,
    ) -> bool:
        """Register a webhook for the Jira project, tracking it in the database."""
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot register webhook.")
            return False

        existing_webhook = crud_webhook.get_by_project_id(db, project_id=project_id)
        if existing_webhook:
            logger.info(f"Webhook for project {project_key} already registered in database. Skipping.")
            return True

        actual_events = events or DEFAULT_JIRA_WEBHOOK_EVENTS
        webhook_name = f"SpaceBridge Sync for {project_key}"

        parsed_url = urllib.parse.urlparse(webhook_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        query_params['secret'] = [secret]
        query_params['project_key'] = [project_key]
        new_query_string = urllib.parse.urlencode(query_params, doseq=True)
        url_with_secret_and_project = parsed_url._replace(query=new_query_string).geturl()

        jql_filter = f"project = {project_key.upper()}"

        try:
            logger.info(f"Registering webhook for project {project_key} in Jira.")
            response = self.jira_client._session.post(
                f"{self.jira_url}/rest/webhooks/1.0/webhook",
                json={
                    "name": webhook_name,
                    "url": url_with_secret_and_project,
                    "events": actual_events,
                    "jqlFilter": jql_filter,
                    "excludeIssueDetails": False,
                },
            )
            response.raise_for_status()
            webhook_data = response.json()
            webhook_id = str(webhook_data.get("id"))

            crud_webhook.create(
                db,
                obj_in={
                    "project_id": project_id,
                    "external_id": webhook_id,
                    "url": url_with_secret_and_project,
                    "secret": secret,
                    "events": actual_events,
                },
            )
            logger.info(f"Successfully registered webhook {webhook_id} for project {project_key}.")
            return True
        except JIRAError as e:
            if e.status_code == 400 and "webhook with same name and url already exists" in e.text.lower():
                logger.warning(f"Webhook for project {project_key} already exists in Jira. Assuming it's ours.")
                return True
            self._handle_jira_error(e, f"registering webhook for project {project_key}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error registering webhook for {project_key}: {e}", exc_info=True)
            raise TrackerConnectionError(f"Unexpected error registering webhook for {project_key}: {str(e)}")

    def unregister_webhook(self, db: Session, project_id: str) -> bool:
        """Unregister a webhook for a project using the database record."""
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot unregister webhook.")
            return False

        webhook = crud_webhook.get_by_project_id(db, project_id=project_id)
        if not webhook:
            logger.warning(f"No webhook found in database for project ID {project_id}. Cannot unregister.")
            return True

        try:
            logger.info(f"Attempting to unregister webhook with external ID {webhook.external_id}.")
            self.jira_client._session.delete(
                f"{self.jira_url}/rest/webhooks/1.0/webhook/{webhook.external_id}"
            )
            logger.info(f"Successfully unregistered webhook {webhook.external_id} from Jira.")
        except JIRAError as e:
            if e.status_code != 404:
                self._handle_jira_error(e, f"unregistering webhook {webhook.external_id}")
                return False
            logger.warning(f"Webhook {webhook.external_id} not found in Jira. Assuming already deleted.")

        crud_webhook.remove(db, id=webhook.id)
        logger.info(f"Removed webhook record for project {project_id} from database.")
        return True

    def unregister_all_webhooks(self, db: Session, organization_id: str) -> None:
        """Unregister all webhooks for all projects in an organization."""
        from spacemodels.crud import crud_project
        projects = crud_project.get_for_organization(db, organization_id=organization_id)

        if not projects:
            logger.info(f"No projects found for organization {organization_id}. No webhooks to unregister.")
            return

        logger.info(f"Starting unregistration of all webhooks for organization {organization_id}...")
        for proj in projects:
            try:
                logger.info(f"Unregistering webhook for project: {proj.name} ({proj.identifier})")
                self.unregister_webhook(db, project_id=proj.id)
            except Exception as e:
                logger.error(f"Failed to unregister webhook for project {proj.identifier}: {e}", exc_info=True)
        logger.info(f"Finished unregistering webhooks for organization {organization_id}.")
