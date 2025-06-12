"""
Jira tracker implementation for SpaceSync.
"""

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import urllib.parse
import os # Added for SPACEBRIDGE_URL

import requests
from jira import JIRA, JIRAError # type: ignore

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

        # Check for Jira URL in either jira_url or url field
        jira_url = connection_details.get("jira_url")
        if not jira_url:
            jira_url = connection_details.get("url")

        if not jira_url:
            raise ValueError(
                "Jira URL is required in connection_details (either 'jira_url' or 'url')"
            )

        if "username" not in connection_details:
            raise ValueError("Jira username is required in connection_details")

        self.jira_url = jira_url.rstrip("/")
        self.username = connection_details["username"]

        # Basic authentication header for requests library
        auth_str = f"{self.username}:{api_key}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }

        # Initialize python-jira client
        self.jira_client: Optional[JIRA] = None
        if self.jira_url and self.username and api_key:
            try:
                self.jira_client = JIRA(
                    server=self.jira_url,
                    basic_auth=(self.username, api_key),
                    timeout=20,  # seconds
                    max_retries=3,
                )
                # Optionally, test connection, e.g., by fetching server info or user details
                # self.jira_client.server_info()
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
        """
        Make a request to the Jira API using the requests library.

        Args:
            endpoint: API endpoint to request.
            params: Query parameters.

        Returns:
            JSON response data or None for success with no content.

        Raises:
            TrackerAuthenticationError: If authentication fails.
            TrackerConnectionError: If connection fails.
            TrackerResponseError: If response is invalid.
        """
        try:
            url = f"{self.jira_url}/rest/api/2/{endpoint.lstrip('/')}"
            response = requests.request(
                method.upper(), url, headers=self.headers, params=params, json=json_data
            )

            if response.status_code == 401:
                raise TrackerAuthenticationError("Jira authentication failed")

            # Handle successful responses
            if 200 <= response.status_code < 300:
                if response.status_code == 204:  # No Content
                    return None
                if response.content:
                    try:
                        return response.json()
                    except ValueError: # Not JSON
                        return response.text # Return text if not json
                return None # Success but no content and not 204 explicitly

            # Handle error responses
            raise TrackerResponseError(
                f"Jira API error: {response.status_code} - {response.text}"
            )
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

        return [{"id": org_name, "name": org_name, "url": self.jira_url}]

    def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get projects from Jira.

        Args:
            organization_id: Not used for Jira, but kept for interface consistency.

        Returns:
            List of project data dictionaries.
        """
        # Get all accessible projects
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
        """
        Get issues for a project from Jira, including their comments.

        Args:
            organization_id: Not used for Jira, but kept for interface consistency.
            project_id: Jira project key.
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries, each including a 'comments' list.
        """
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
            except (ValueError, TypeError) as ve:
                logger.warning(f"Could not parse datetime for Jira issue {issue_data.get('key')}: {ve}. Using fallback.")
                created_dt = datetime.now()
                if isinstance(issue_data["fields"].get("created"), str):
                    try:
                        created_dt = datetime.strptime(issue_data["fields"]["created"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                    except ValueError:
                        pass
                updated_dt = created_dt

            assignee_list = []
            if issue_data["fields"].get("assignee"):
                assignee_list = [issue_data["fields"]["assignee"].get("displayName", issue_data["fields"]["assignee"].get("name"))]

            # Process comments
            comments_transformed = []
            if issue_data["fields"].get("comment") and issue_data["fields"]["comment"].get("comments"):
                raw_comments = issue_data["fields"]["comment"]["comments"]
                for comment_item in raw_comments:
                    try:
                        comment_created_dt = datetime.strptime(comment_item["created"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                        comment_updated_dt = datetime.strptime(comment_item["updated"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                    except (ValueError, TypeError) as ve:
                        logger.warning(f"Could not parse datetime for Jira comment {comment_item.get('id')} on issue {issue_data.get('key')}: {ve}. Using fallback.")
                        comment_created_dt = datetime.now()
                        if isinstance(comment_item.get("created"), str):
                            try:
                                comment_created_dt = datetime.strptime(comment_item["created"], "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                            except ValueError:
                                pass
                        comment_updated_dt = comment_created_dt

                    author = comment_item.get("author", {})
                    author_id = author.get("accountId") or author.get("key") or author.get("name")

                    comments_transformed.append({
                        "id": str(comment_item["id"]),
                        "body": comment_item.get("body", "") or "",
                        "author_id": str(author_id) if author_id else None,
                        "created_at": comment_created_dt,
                        "updated_at": comment_updated_dt,
                        "url": f"{self.jira_url}/browse/{issue_data['key']}?focusedCommentId={comment_item['id']}#comment-{comment_item['id']}"
                    })

            # Jira API might return None for description, ensure it's a string
            description_text = issue_data["fields"].get("description", "")
            if description_text is None:
                description_text = ""

            processed_issues.append(
                {
                    "id": issue_data["id"],  # Add this line for consistency with BaseTracker
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

    def transform_project(
        self, proj_data: Dict[str, Any], organization_id: str
    ) -> Dict[str, Any]:
        """
        Transform Jira project data, setting the slug to the project identifier (key).

        Args:
            proj_data: Project data from the Jira tracker.
            organization_id: Database ID of the organization (UUID string).

        Returns:
            Transformed project data ready for database storage.
        """
        # Get the base transformation from the parent class
        transformed_data = super().transform_project(proj_data, organization_id)

        # Set the slug to be the project identifier (which is the Jira project key)
        if "identifier" in transformed_data:
            transformed_data["slug"] = transformed_data["identifier"]

        return transformed_data

    def transform_issue(
        self, issue_data: Dict[str, Any], project: "Project"
    ) -> Dict[str, Any]:
        """
        Transforms Jira issue data into a standardized format.
        """
        if "key" not in issue_data:
            issue_data["key"] = issue_data["key"]

        transformed_data = super().transform_issue(issue_data, project)

        # Jira-specific transformations can be added here if needed

        return transformed_data

    def transform_comment(
        self, comment_data: Dict[str, Any], issue_db_id: str, author_db_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transforms Jira comment data into a standardized format.
        """
        transformed_data = super().transform_comment(comment_data, issue_db_id, author_db_id)

        # Jira-specific transformations can be added here if needed

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
        else: # Other client/server errors
            raise TrackerResponseError(f"{context}: Jira API error {e.status_code}: {e.text}")


    def register_webhook(
        self,
        project_key: str,
        webhook_url: str,
        secret: str,
        events: Optional[List[str]] = None,
    ) -> bool:
        """
        Register a webhook for the Jira project.

        Args:
            project_key: Jira project key.
            webhook_url: The base URL for the webhook. The secret will be appended.
            secret: Secret for webhook verification (appended to URL).
            events: List of Jira events to subscribe to. Uses defaults if None.

        Returns:
            True on successful registration or if a similar webhook already exists, False otherwise.
        """
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot register webhook.")
            return False

        actual_events = events or DEFAULT_JIRA_WEBHOOK_EVENTS
        webhook_name = f"SpaceBridge Sync for {project_key}"

        # Append secret to webhook URL
        parsed_url = urllib.parse.urlparse(webhook_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        query_params['secret'] = [secret] # parse_qs returns list values
        # Ensure project_key is also in the callback URL for SpaceBridge to identify the project
        query_params['project_key'] = [project_key]

        new_query_string = urllib.parse.urlencode(query_params, doseq=True)
        url_with_secret_and_project = parsed_url._replace(query=new_query_string).geturl()

        jql_filter = f"project = {project_key.upper()}" # JQL project keys are often uppercase

        try:
            existing_webhooks = self.jira_client.webhooks()
            for wh in existing_webhooks:
                # Normalize URLs for comparison if needed, though exact match is safer here
                wh_url_parsed = urllib.parse.urlparse(wh.url)
                wh_query_params = urllib.parse.parse_qs(wh_url_parsed.query)

                # Check if the core URL matches (ignoring our specific query params for a moment)
                core_wh_url = wh_url_parsed._replace(query='').geturl()
                core_target_url = parsed_url._replace(query='').geturl()

                if core_wh_url == core_target_url and \
                   wh_query_params.get('project_key') == [project_key] and \
                   set(wh.events) == set(actual_events) and \
                   wh.jqlFilter == jql_filter:

                    # Now check if the secret also matches, if our secret param exists
                    if wh_query_params.get('secret') == [secret]:
                        logger.warning(
                            f"Webhook for project {project_key} with URL {url_with_secret_and_project} "
                            f"and events {actual_events} already exists (ID: {wh.id})."
                        )
                        return True
                    else:
                        # Same core webhook but different secret. This might be an issue.
                        # For now, we'll treat it as "not our webhook" and try to register ours.
                        # Alternatively, one might want to delete the old one and register new.
                        logger.info(
                            f"Webhook for project {project_key} with URL {core_target_url} exists (ID: {wh.id}), "
                            f"but with a different secret or configuration. Will attempt to register new one."
                        )

            logger.info(
                f"Registering webhook for project {project_key}: Name='{webhook_name}', "
                f"URL='{url_with_secret_and_project}', JQL='{jql_filter}', Events='{actual_events}'"
            )
            self.jira_client.add_webhook(
                name=webhook_name,
                url=url_with_secret_and_project,
                jqlFilter=jql_filter,
                events=actual_events,
                excludeIssueDetails=False, # Typically false to get full data
            )
            logger.info(f"Successfully registered webhook for project {project_key}.")
            return True
        except JIRAError as e:
            self._handle_jira_error(e, f"registering webhook for project {project_key}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error registering webhook for {project_key}: {e}", exc_info=True)
            raise TrackerConnectionError(f"Unexpected error registering webhook for {project_key}: {str(e)}")


    def unregister_webhook(
        self,
        project_key: str, # Used to confirm scope when deleting by URL
        webhook_url: Optional[str] = None,
        webhook_id: Optional[int] = None,
    ) -> bool:
        """
        Unregister a webhook for the Jira project.

        Args:
            project_key: Jira project key, used to verify scope if deleting by URL.
            webhook_url: The base URL of the webhook to delete. Secret will be appended for matching.
                         If provided, all webhooks matching this URL for the project are deleted.
            webhook_id: The specific ID of the webhook to delete.

        Returns:
            True on successful unregistration, False otherwise.
        """
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot unregister webhook.")
            return False

        if not webhook_id and not webhook_url:
            logger.error("Either webhook_id or webhook_url must be provided to unregister.")
            return False

        try:
            if webhook_id:
                logger.info(f"Attempting to unregister webhook with ID {webhook_id} for project {project_key}.")
                self.jira_client.delete_webhook(webhook_id)
                logger.info(f"Successfully unregistered webhook ID {webhook_id}.")
                return True

            if webhook_url:
                logger.info(f"Attempting to unregister webhooks for project {project_key} matching base URL pattern similar to {webhook_url}.")
                all_webhooks = self.jira_client.webhooks()
                deleted_count = 0
                found_potential_matches = False
                jql_filter_to_match = f"project = {project_key.upper()}"

                for wh in all_webhooks:
                    wh_url_parsed = urllib.parse.urlparse(wh.url)
                    wh_query_params = urllib.parse.parse_qs(wh_url_parsed.query)
                    core_wh_url = wh_url_parsed._replace(query='').geturl()

                    if core_wh_url.rstrip('/') == webhook_url.rstrip('/') and \
                       wh.jqlFilter == jql_filter_to_match and \
                       'secret' in wh_query_params and \
                       wh_query_params.get('project_key') == [project_key]:
                        found_potential_matches = True
                        logger.info(f"Found matching webhook ID {wh.id} (URL: {wh.url}, JQL: {wh.jqlFilter}) for project {project_key} and base URL {webhook_url}. Attempting to delete.")
                        try:
                            self.jira_client.delete_webhook(wh.id)
                            logger.info(f"Successfully deleted webhook ID {wh.id}.")
                            deleted_count += 1
                        except JIRAError as e_delete:
                            logger.error(f"Failed to delete webhook ID {wh.id} for project {project_key}: {e_delete.status_code} - {e_delete.text}")
                            # Continue to try deleting other matches

                if not found_potential_matches:
                    logger.warning(f"No webhooks found for project {project_key} matching the URL pattern of {webhook_url} and associated JQL filter.")
                    return True

                if deleted_count > 0:
                    logger.info(f"Successfully deleted {deleted_count} webhooks for project {project_key} matching URL {webhook_url}.")
                    return True
                else:
                    logger.error(f"Found matching webhooks for project {project_key} and URL {webhook_url}, but failed to delete any.")
                    return False
            # Fallback if neither webhook_id nor webhook_url was effectively processed
            # This should ideally be caught by the initial check `if not webhook_id and not webhook_url:`
            # but as a safeguard for logical flow:
            return False

        except JIRAError as e:
            if webhook_id and e.status_code == 404: # Specific check for delete_webhook by ID
                logger.warning(f"Webhook ID {webhook_id} not found during delete attempt. Assuming already unregistered.")
                return True
            self._handle_jira_error(e, f"unregistering webhook for project {project_key}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error unregistering webhook for {project_key}: {e}", exc_info=True)
            return False

    def unregister_all_webhooks(
        self, webhook_url_pattern: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Unregister all webhooks for all relevant projects, optionally matching a URL pattern.

        Args:
            webhook_url_pattern: If provided, only unregister webhooks whose URL's base
                                 matches this pattern. If None, attempts to unregister
                                 webhooks matching the SPACEBRIDGE_URL pattern.
                                 The matching also considers JQL filter for project scope
                                 and presence of 'secret' and 'project_key' query params.

        Returns:
            A dictionary summarizing the actions taken, e.g.,
            {"unregistered": count, "failed": count, "not_found": count}.
        """
        results = {"unregistered": 0, "failed": 0, "not_found": 0}
        if not self.jira_client:
            logger.error("Jira client not initialized. Cannot unregister all webhooks.")
            return results

        target_base_url_pattern = webhook_url_pattern
        if target_base_url_pattern is None:
            sb_url = os.getenv("SPACEBRIDGE_URL")
            if sb_url:
                target_base_url_pattern = f"{sb_url.rstrip('/')}/api/v1/private/webhooks/"
                logger.info(f"Jira: No specific webhook_url_pattern provided, using default base pattern: {target_base_url_pattern}")
            else:
                logger.warning("Jira: Cannot determine target webhook URL pattern: webhook_url_pattern is None and SPACEBRIDGE_URL is not set.")
                return results

        try:
            jira_projects_raw = self._make_request("GET", "project")
            if not jira_projects_raw:
                logger.info("Jira: No projects found to process for unregister_all_webhooks.")
                return results
        except (TrackerAuthenticationError, TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Jira: Failed to list projects: {e}")
            return results

        for proj_data in jira_projects_raw:
            project_key = proj_data.get("key")
            project_name = proj_data.get("name")
            if not project_key:
                logger.warning(f"Jira: Skipping project with no key: {proj_data}")
                continue

            logger.debug(f"Jira: Processing project '{project_name}' (Key: {project_key}) for webhook unregistration.")

            project_jql_filter = f"project = {project_key.upper()}"
            webhooks_for_project_found_this_iteration = 0 # Tracks if any hook matched criteria for this project

            try:
                all_global_webhooks = self.jira_client.webhooks()
                if not all_global_webhooks:
                    logger.debug(f"Jira: No global webhooks found on the instance. Skipping project {project_key} for webhook checks.")
                    # No need to increment not_found here, as it's about *matching* hooks for *this* project
                    # The check below will handle if no matching hooks are found for this project.
                    # continue # This would skip the not_found logic below

                project_specific_hooks_to_delete_ids = []
                for wh in all_global_webhooks: # Iterate even if empty, loop won't run
                    wh_url_parsed = urllib.parse.urlparse(wh.url)
                    wh_query_params = urllib.parse.parse_qs(wh_url_parsed.query)
                    core_wh_url = wh_url_parsed._replace(query='').geturl().rstrip('/')

                    if wh.jqlFilter != project_jql_filter:
                        continue

                    if target_base_url_pattern and not core_wh_url.startswith(target_base_url_pattern.rstrip('/')):
                        continue

                    if 'secret' not in wh_query_params or wh_query_params.get('project_key') != [project_key]:
                        continue

                    project_specific_hooks_to_delete_ids.append(wh.id)
                    webhooks_for_project_found_this_iteration += 1

                if not project_specific_hooks_to_delete_ids:
                    logger.debug(f"Jira: No webhooks matching pattern and criteria for project '{project_key}'.")
                    if webhooks_for_project_found_this_iteration == 0:
                        results["not_found"] += 1
                else:
                    for hook_id_to_delete in project_specific_hooks_to_delete_ids:
                        logger.info(f"Jira: Attempting to delete webhook ID {hook_id_to_delete} for project '{project_key}'.")
                        try:
                            self.jira_client.delete_webhook(hook_id_to_delete)
                            logger.info(f"Jira: Successfully deleted webhook ID {hook_id_to_delete} for project '{project_key}'.")
                            results["unregistered"] += 1
                        except JIRAError as e_delete:
                            if e_delete.status_code == 404:
                                logger.warning(f"Jira: Webhook ID {hook_id_to_delete} for project '{project_key}' not found during delete (already gone).")
                                results["unregistered"] += 1
                            else:
                                logger.error(f"Jira: Failed to delete webhook ID {hook_id_to_delete} for project '{project_key}': {e_delete.status_code} - {e_delete.text}")
                                results["failed"] += 1

            except JIRAError as e_list:
                self._handle_jira_error(e_list, f"listing global webhooks during unregister_all_webhooks for project {project_key}")
                results["failed"] += 1
            except Exception as e_proj:
                logger.error(f"Jira: Unexpected error processing project '{project_key}' for unregister_all_webhooks: {e_proj}", exc_info=True)
                results["failed"] += 1

        logger.info(f"Jira unregister_all_webhooks summary: {results}")
        return results

# Example usage (for testing, not part of the class):
# if __name__ == "__main__":
#     # Mock or set up connection details and API key
#     # jira_tracker = JiraTracker(tracker_id="test-jira", api_key="...", connection_details={...})
#     # jira_tracker.unregister_all_webhooks()
#     pass
