"""
GitLab tracker implementation for SpaceSync using python-gitlab library.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Literal # For Python < 3.8 compatibility with Literal
import os

import gitlab

from ..config import logger
from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from ..utils import retry
from .base import BaseTracker


class GitLabTracker(BaseTracker):
    """GitLab tracker implementation using python-gitlab."""

    def __init__(
        self, tracker_id: str, api_key: str, connection_details: Dict[str, Any]
    ):
        """
        Initialize the GitLab tracker.

        Args:
            tracker_id: ID of the tracker in the database (UUID string).
            api_key: GitLab API token.
            connection_details: Connection details including GitLab instance URL (optional).
        """
        super().__init__(tracker_id, api_key, connection_details)
        # The tracker object should be set on this instance by TrackerClient
        # but it's missing at this point

        # Use URL from connection_details if available
        gitlab_url = connection_details.get("url")

        # If there's no URL, use https://gitlab.com/
        if not gitlab_url:
            gitlab_url = "https://gitlab.com"

        # Strip '/api/v4' from the URL if present, as python-gitlab adds this automatically
        gitlab_url = gitlab_url.rstrip("/")
        if gitlab_url.endswith("/api/v4"):
            # Remove the /api/v4 suffix
            gitlab_url = gitlab_url[:-7]  # Remove last 7 characters (/api/v4)

        self.url = gitlab_url

        # Log information for debugging
        print("GitLab Tracker Debug Info:")
        print(f"  URL: {self.url}")
        print(f"  Original URL from connection_details: {gitlab_url}")
        print(
            f"  API Key (first 5 chars): {api_key[:5] if len(api_key) > 5 else '***'}"
        )
        print(f"  Tracker ID: {tracker_id}")

        try:
            print(f"  Attempting to connect to GitLab at {self.url}")
            self.gl = gitlab.Gitlab(self.url, private_token=api_key)
            # Test connection and authentication
            print("  Testing authentication...")
            self.gl.auth()
            print("  Authentication successful!")
        except gitlab.exceptions.GitlabAuthenticationError as e:
            print(f"  Authentication Error: {str(e)}")
            raise TrackerAuthenticationError(f"GitLab authentication failed: {str(e)}")
        except gitlab.exceptions.GitlabHttpError as e:
            print(f"  HTTP Error: {str(e)}")
            raise TrackerConnectionError(f"GitLab connection error: {str(e)}")

    @retry(max_attempts=3, exceptions=(TrackerConnectionError, TrackerResponseError))
    def _make_request(self, method, *args, **kwargs):
        """
        Execute a GitLab API request with error handling.

        Args:
            method: The python-gitlab method to call
            *args: Positional arguments for the method
            **kwargs: Keyword arguments for the method

        Returns:
            Result from the GitLab API call

        Raises:
            TrackerAuthenticationError: If authentication fails.
            TrackerConnectionError: If connection fails.
            TrackerResponseError: If response is invalid.
        """
        try:
            return method(*args, **kwargs)
        except gitlab.exceptions.GitlabAuthenticationError:
            raise TrackerAuthenticationError("GitLab authentication failed")
        except gitlab.exceptions.GitlabHttpError as e:
            if e.response_code == 401:
                raise TrackerAuthenticationError("GitLab authentication failed")
            else:
                raise TrackerResponseError(f"GitLab API error: {e.response_code} - {e}")
        except gitlab.exceptions.GitlabConnectionError as e:
            raise TrackerConnectionError(f"GitLab connection error: {str(e)}")
        except Exception as e:
            raise TrackerResponseError(f"GitLab API error: {str(e)}")

    def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Get organizations (groups) from GitLab.

        Returns:
            List of organization data dictionaries.
        """
        # For GitLab, organizations are groups
        groups = self._make_request(self.gl.groups.list, all=True)

        organizations = []
        for group in groups:
            organizations.append(
                {"id": str(group.id), "name": group.name, "url": group.web_url}
            )

        return organizations

    def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get projects for a group from GitLab.

        Args:
            organization_id: GitLab group ID.

        Returns:
            List of project data dictionaries.
        """
        # Get the group object first
        group = self._make_request(self.gl.groups.get, organization_id)

        # Get projects for the specified group
        projects = self._make_request(group.projects.list, all=True)

        project_list = []
        for project in projects:
            # Ensure we have the necessary attributes, especially path_with_namespace for the slug
            project_attributes = project.attributes # Use .attributes to get the raw dict
            project_list.append(
                {
                    "id": str(project_attributes.get("id")),
                    "name": project_attributes.get("name"),
                    "description": project_attributes.get("description", ""),
                    "url": project_attributes.get("web_url"),
                    "path_with_namespace": project_attributes.get("path_with_namespace"),
                    # Add metadata including timestamps
                    "meta_data": {
                        "created_at": project_attributes.get("created_at"),
                        "updated_at": project_attributes.get("last_activity_at"), # Use last_activity_at for updates
                    },
                }
            )

        return project_list

    def transform_project(
        self, proj_data: Dict[str, Any], organization_id: str
    ) -> Dict[str, Any]:
        """
        Transform GitLab project data, adding the slug.

        Args:
            proj_data: Project data from the GitLab API.
            organization_id: Database ID of the organization (UUID string).

        Returns:
            Transformed project data ready for database storage, including slug.
        """
        # Start with the base transformation
        transformed_data = super().transform_project(proj_data, organization_id)

        # Extract slug from GitLab's path_with_namespace if available
        # The raw proj_data comes from the get_projects method which uses project.attributes
        # Let's adjust get_projects to return the full object or ensure path_with_namespace is there.
        # For now, assume proj_data might contain it directly or within meta_data if get_projects is adjusted.
        # A safer approach is to modify get_projects first. Let's assume proj_data has 'path_with_namespace' for now.

        # Re-checking get_projects: It returns a dict like:
        # { 'id': ..., 'name': ..., 'description': ..., 'url': ... }
        # It DOES NOT include path_with_namespace. We need to modify get_projects first.

        # --- Let's modify get_projects first ---
        # This insert is now incorrect, need to modify get_projects instead/before this.
        # Backtracking: Modify get_projects to include 'path_with_namespace'

        # --- Corrected Plan ---
        # 1. Modify get_projects in gitlab.py to include 'path_with_namespace' in the returned dict.
        # 2. Override transform_project in gitlab.py to extract 'path_with_namespace' and add it as 'slug'.

        # --- Applying Step 1 (Modify get_projects) ---
        # This requires an apply_diff, not insert_content.

        # --- Applying Step 2 (Override transform_project) ---
        # Assuming Step 1 is done, this insert would be correct.
        gitlab_slug = proj_data.get("path_with_namespace") # Assumes get_projects was modified
        if gitlab_slug:
            transformed_data["slug"] = gitlab_slug
        else:
             # Fallback or log warning if path_with_namespace wasn't added
             logger.warning(f"Could not determine slug (path_with_namespace) for GitLab project ID {proj_data.get('id')}")


        return transformed_data

    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a project from GitLab, including their comments (notes).

        Args:
            organization_id: GitLab group ID (not used in API call but kept for interface consistency).
            project_id: GitLab project ID.
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries, each including a 'comments' list.
        """
        project = self._make_request(self.gl.projects.get, project_id)
        project_slug = project.path_with_namespace
        if not project_slug:
             logger.error(f"Could not determine path_with_namespace (slug) for GitLab project ID {project_id}")
             raise TrackerResponseError(f"Missing path_with_namespace for GitLab project ID {project_id}")

        kwargs = {"all": True, "include_metadata": True}
        if since:
            kwargs["updated_after"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        gitlab_issues = self._make_request(project.issues.list, **kwargs)

        issue_list_with_comments = []
        for issue_obj in gitlab_issues:
            try:
                notes = self._make_request(issue_obj.notes.list, all=True, sort='asc', order_by='created_at')
            except Exception as e:
                logger.error(f"Failed to fetch notes for GitLab issue {issue_obj.iid} in project {project_id}: {e}")
                notes = []

            comments_data = []
            for note in notes:
                if note.system:
                    continue

                author_id_str = None
                if hasattr(note, 'author') and isinstance(note.author, dict):
                    author_id_str = str(note.author.get('id')) if note.author.get('id') else None

                try:
                    created_at_dt = datetime.strptime(note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                    updated_at_dt = datetime.strptime(note.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                except (ValueError, TypeError) as ve: # Added TypeError for None values
                    logger.warning(f"Could not parse datetime for note {note.id} on issue {issue_obj.iid}: {ve}. Using fallback.")
                    created_at_dt = datetime.now() # Fallback, consider if note.created_at can be None
                    if isinstance(note.created_at, str):
                        try:
                            created_at_dt = datetime.strptime(note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except ValueError:
                            pass # Keep datetime.now() if parsing fails
                    updated_at_dt = created_at_dt

                comments_data.append(
                    {
                        "id": str(note.id),
                        "body": note.body or "",
                        "author_id": author_id_str,
                        "created_at": created_at_dt,
                        "updated_at": updated_at_dt,
                        "url": f"{issue_obj.web_url}#note_{note.id}"
                    }
                )

            external_id = str(issue_obj.iid)
            key = f"{project_slug}#{external_id}"

            try:
                issue_created_at = datetime.strptime(issue_obj.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                issue_updated_at = datetime.strptime(issue_obj.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ")
            except (ValueError, TypeError) as ve: # Added TypeError for None values
                 logger.warning(f"Could not parse datetime for issue {issue_obj.iid}: {ve}. Using fallback.")
                 issue_created_at = datetime.now()
                 if isinstance(issue_obj.created_at, str):
                     try:
                        issue_created_at = datetime.strptime(issue_obj.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                     except ValueError:
                        pass # Keep datetime.now() if parsing fails
                 issue_updated_at = issue_created_at

            issue_list_with_comments.append(
                {
                    "external_id": external_id,
                    "key": key,
                    "title": issue_obj.title,
                    "description": issue_obj.description or "",
                    "state": issue_obj.state,
                    "created_at": issue_created_at,
                    "updated_at": issue_updated_at,
                    "labels": issue_obj.labels if hasattr(issue_obj, "labels") else [],
                    "assignees": [assignee["username"] for assignee in issue_obj.assignees if isinstance(assignee, dict) and "username" in assignee]
                    if hasattr(issue_obj, "assignees")
                    else [],
                    "url": issue_obj.web_url,
                    "comments": comments_data,
                }
            )
        return issue_list_with_comments

    def register_webhook(self, **kwargs: Any) -> bool:
        """
        Register a webhook for the GitLab tracker, attempting group-level registration.

        This method is implemented to satisfy the BaseTracker interface. The primary
        webhook registration logic for GitLab during scans is handled in
        spacesync.scanner.core by trying register_group_webhook and then
        falling back to register_project_webhook for each project.

        Args:
            **kwargs: Keyword arguments. Expected keys for GitLab:
                      'org_identifier' (str): The GitLab group ID.
                      'webhook_url' (str): The target URL for the webhook.
                      'secret' (str): The secret token for the webhook.

        Returns:
            True if group webhook registration was successful, False otherwise (including
            if group hooks are not supported or an error occurred).
        """
        org_identifier = kwargs.pop("org_identifier", None)
        webhook_url = kwargs.pop("webhook_url", None)
        secret = kwargs.pop("secret", None)

        if not all([org_identifier, webhook_url, secret]):
            logger.error(
                "GitLabTracker.register_webhook called with missing required arguments "
                "(org_identifier, webhook_url, or secret) in kwargs."
            )
            return False

        logger.info(
            f"GitLabTracker.register_webhook called for org_identifier '{org_identifier}'. "
            f"Attempting group webhook registration via self.register_group_webhook."
        )

        # Log any remaining/unexpected kwargs
        if kwargs:
            logger.debug(f"Ignoring additional/unexpected kwargs in GitLabTracker.register_webhook: {kwargs}")

        result = self.register_group_webhook(
            org_identifier=org_identifier, webhook_url=webhook_url, secret=secret
        )

        if result is True:
            logger.info(
                f"Generic register_webhook: Successfully registered group webhook for '{org_identifier}'."
            )
            return True
        elif result == "group_hooks_not_supported":
            logger.warning(
                f"Generic register_webhook: Group hooks not supported for '{org_identifier}'. "
                f"Webhook registration via this generic method failed."
            )
            return False
        else:  # result is False (actual error)
            logger.error(
                f"Generic register_webhook: Failed to register group webhook for '{org_identifier}'."
            )
            return False
    def register_group_webhook(
        self, org_identifier: str, webhook_url: str, secret: str
    ) -> Union[bool, Literal["group_hooks_not_supported"]]:
        """
        Register a webhook for the given GitLab group.

        Args:
            org_identifier: The GitLab group ID.
            webhook_url: The target URL for the webhook.
            secret: The secret token to use for the webhook.

        Returns:
            True if registration was successful or webhook already exists.
            "group_hooks_not_supported" if the /hooks endpoint for the group returns 404.
            False for other errors.
        """
        logger.info(f"Attempting to register group webhook for GitLab group ID '{org_identifier}' pointing to {webhook_url}")

        hook_attrs = {
            "url": webhook_url,
            "token": secret,
            "issues_events": True,
            "push_events": True,
            "merge_requests_events": False,
            "repository_update_events": True,
            "enable_ssl_verification": True,
        }

        try:
            logger.info(f"GitLabTracker: Attempting self.gl.groups.get() for group webhook. org_identifier='{org_identifier}', client API URL='{self.gl.url}'")
            group = self._make_request(self.gl.groups.get, org_identifier)

            # Try to list existing hooks. A 404 here indicates group hooks are not supported.
            try:
                existing_hooks = group.hooks.list(all=True)
                for h in existing_hooks:
                    if h.url == webhook_url:
                        logger.warning(f"Group webhook for GitLab group '{org_identifier}' (URL: {webhook_url}) already exists (ID: {h.id}).")
                        return True
            except gitlab.exceptions.GitlabListError as e:
                if e.response_code == 404:
                    logger.info(f"Listing group hooks for GitLab group '{org_identifier}' failed with 404. Assuming group hooks are not supported (e.g., GitLab CE).")
                    return "group_hooks_not_supported"
                logger.error(f"Error listing group hooks for GitLab group '{org_identifier}': {e.response_code} - {e.error_message}", exc_info=True)
                return False # Other errors during list are a failure

            # If list succeeded and hook doesn't exist, try to create it.
            logger.info(f"Attempting to create group hook for GitLab group '{org_identifier}' (URL: {webhook_url}).")
            try:
                hook = group.hooks.create(hook_attrs)
                logger.info(f"Successfully created group webhook (ID: {hook.id}) for GitLab group '{org_identifier}'.")
                return True
            except gitlab.exceptions.GitlabCreateError as e:
                if e.response_code == 409: # Conflict
                    logger.warning(f"Group webhook for GitLab group '{org_identifier}' (URL: {webhook_url}) already exists (409 on create).")
                    return True
                elif e.response_code == 404: # Not Found on create
                    logger.warning(f"Creating group hook for GitLab group '{org_identifier}' failed with 404. Assuming group hooks are not supported (e.g., GitLab CE).")
                    return "group_hooks_not_supported"
                elif e.response_code == 401:
                    logger.error(f"GitLab authentication failed (401) creating group hook for '{org_identifier}'.")
                    return False
                elif e.response_code == 403:
                    logger.error(f"Permission denied (403) creating group hook for '{org_identifier}'. Check token permissions.")
                    return False
                else:
                    logger.error(f"GitLab API error {e.response_code} creating group hook for '{org_identifier}'. Response: {e.error_message}", exc_info=True)
                    return False

        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404:
                logger.error(f"GitLab group '{org_identifier}' not found when attempting to register group webhook.")
                return False # Group itself not found
            logger.error(f"Error getting GitLab group '{org_identifier}' for group webhook: {e.response_code} - {e.error_message}", exc_info=True)
            return False
        except gitlab.exceptions.GitlabAuthenticationError as e: # Should be caught by _make_request mostly
            logger.error(f"GitLab authentication error during group webhook setup for '{org_identifier}': {e}", exc_info=True)
            raise # Re-raise as this is a fundamental issue
        except Exception as e: # Catch-all for unexpected issues
            logger.error(f"Unexpected error registering group webhook for GitLab group '{org_identifier}': {e}", exc_info=True)
            return False

    def register_project_webhook(
        self, project_id_or_path: Union[int, str], webhook_url: str, secret: str
    ) -> bool:
        """
        Register a webhook for the given GitLab project.

        Args:
            project_id_or_path: The GitLab project ID (int) or path_with_namespace (str).
            webhook_url: The target URL for the webhook.
            secret: The secret token to use for the webhook.

        Returns:
            True if registration was successful or webhook already exists, False otherwise.
        """
        logger.info(f"Attempting to register project webhook for GitLab project '{project_id_or_path}' pointing to {webhook_url}")

        hook_attrs = {
            "url": webhook_url,
            "token": secret,
            "issues_events": True,
            "push_events": True,
            "merge_requests_events": False, # Keep consistent with group hook events for now
            "repository_update_events": True,
            "enable_ssl_verification": True,
            # Consider adding more project-specific events if needed:
            # "note_events": True,
            # "job_events": True,
            # "pipeline_events": True,
            # "wiki_page_events": True,
        }

        try:
            logger.info(f"GitLabTracker: Attempting self.gl.projects.get() for project webhook. project_id_or_path='{project_id_or_path}'")
            project = self._make_request(self.gl.projects.get, project_id_or_path)

            # Try to list existing hooks for the project.
            try:
                existing_hooks = project.hooks.list(all=True)
                for h in existing_hooks:
                    if h.url == webhook_url:
                        logger.warning(f"Project webhook for GitLab project '{project_id_or_path}' (URL: {webhook_url}) already exists (ID: {h.id}).")
                        return True
            except gitlab.exceptions.GitlabListError as e:
                # A 404 on listing project hooks is a genuine error if the project itself was found.
                # It means the /hooks endpoint for that specific project is not found or accessible.
                # This is different from a 404 on group.hooks.list which might mean group hooks aren't supported at all.
                logger.error(f"Error listing project hooks for GitLab project '{project_id_or_path}': {e.response_code} - {e.error_message}", exc_info=True)
                return False # Treat as a failure for this specific project's hook setup

            # If list succeeded (or didn't error out before this point) and hook doesn't exist, try to create it.
            logger.info(f"Attempting to create project hook for GitLab project '{project_id_or_path}' (URL: {webhook_url}).")
            try:
                hook = project.hooks.create(hook_attrs)
                logger.info(f"Successfully created project webhook (ID: {hook.id}) for GitLab project '{project_id_or_path}'.")
                return True
            except gitlab.exceptions.GitlabCreateError as e:
                if e.response_code == 409: # Conflict
                    logger.warning(f"Project webhook for GitLab project '{project_id_or_path}' (URL: {webhook_url}) already exists (409 on create).")
                    return True
                # A 404 on create for a project hook is a genuine "not found" for the endpoint or project, or permission issue.
                elif e.response_code == 404:
                    logger.error(f"Creating project hook for GitLab project '{project_id_or_path}' failed with 404. Project or hooks endpoint not found or no permission.")
                    return False
                elif e.response_code == 401:
                    logger.error(f"GitLab authentication failed (401) creating project hook for '{project_id_or_path}'.")
                    return False
                elif e.response_code == 403:
                    logger.error(f"Permission denied (403) creating project hook for '{project_id_or_path}'. Check token permissions.")
                    return False
                else:
                    logger.error(f"GitLab API error {e.response_code} creating project hook for '{project_id_or_path}'. Response: {e.error_message}", exc_info=True)
                    return False

        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404:
                logger.error(f"GitLab project '{project_id_or_path}' not found when attempting to register project webhook.")
            else:
                logger.error(f"Error getting GitLab project '{project_id_or_path}' for project webhook: {e.response_code} - {e.error_message}", exc_info=True)
            return False
        except gitlab.exceptions.GitlabAuthenticationError as e: # Should be caught by _make_request
            logger.error(f"GitLab authentication error during project webhook setup for '{project_id_or_path}': {e}", exc_info=True)
            raise # Re-raise
        except Exception as e: # Catch-all for unexpected issues
            logger.error(f"Unexpected error registering project webhook for GitLab project '{project_id_or_path}': {e}", exc_info=True)
            return False

    def unregister_webhook(self, **kwargs: Any) -> bool:
        """
        Unregister a specific webhook by its ID for a GitLab group or project.

        Args:
            **kwargs: Keyword arguments. Expected:
                      'org_identifier' (str, optional): GitLab group ID.
                      'project_id_or_path' (Union[int, str], optional): GitLab project ID or path.
                      'webhook_id' (int): The ID of the webhook to unregister.

        Returns:
            True if unregistration was successful or webhook was already gone, False otherwise.
        """
        org_identifier = kwargs.get("org_identifier")
        project_id_or_path = kwargs.get("project_id_or_path")
        webhook_id = kwargs.get("webhook_id")

        if not webhook_id:
            logger.error("GitLab: unregister_webhook called without 'webhook_id'.")
            return False
        if not org_identifier and not project_id_or_path:
            logger.error("GitLab: unregister_webhook called without 'org_identifier' or 'project_id_or_path'.")
            return False
        if org_identifier and project_id_or_path:
            logger.error("GitLab: unregister_webhook called with both 'org_identifier' and 'project_id_or_path'. Provide only one.")
            return False

        target_entity = None
        entity_type = ""
        entity_id_for_log = "" # For logging purposes

        try:
            if org_identifier:
                entity_type = "group"
                entity_id_for_log = str(org_identifier)
                logger.info(f"GitLab: Attempting to get group '{entity_id_for_log}' for unregistering webhook ID {webhook_id}.")
                target_entity = self._make_request(self.gl.groups.get, org_identifier)
            elif project_id_or_path:
                entity_type = "project"
                entity_id_for_log = str(project_id_or_path)
                logger.info(f"GitLab: Attempting to get project '{entity_id_for_log}' for unregistering webhook ID {webhook_id}.")
                target_entity = self._make_request(self.gl.projects.get, project_id_or_path)

            if not target_entity: # Should not happen if one of the above blocks executed
                logger.error("GitLab: Could not determine target entity for webhook unregistration.")
                return False

            # We have the entity (group or project), now try to delete the hook by its ID.
            # The python-gitlab library uses entity.hooks.delete(hook_id).
            logger.info(f"GitLab: Attempting to delete webhook ID {webhook_id} from {entity_type} '{entity_id_for_log}'.")
            try:
                hook_manager = target_entity.hooks
                self._make_request(hook_manager.delete, webhook_id)
                logger.info(
                    f"Successfully unregistered webhook {webhook_id} for GitLab {entity_type} {entity_id_for_log}."
                )
                return True
            except gitlab.exceptions.GitlabDeleteError as e:
                if e.response_code == 404:
                    logger.warning(
                        f"Webhook {webhook_id} for GitLab {entity_type} {entity_id_for_log} not found during delete. Assuming already unregistered."
                    )
                    return True # Treat as success if already gone
                logger.error(
                    f"Failed to unregister webhook {webhook_id} for GitLab {entity_type} {entity_id_for_log}: {e.response_code} - {e.error_message}",
                    exc_info=True,
                )
                return False
            except TrackerResponseError as e: # Catch errors from _make_request if delete fails for other reasons
                if "404" in str(e).lower():
                     logger.warning(
                        f"Webhook {webhook_id} for GitLab {entity_type} {entity_id_for_log} not found during delete (via TrackerResponseError). Assuming already unregistered."
                    )
                     return True
                logger.error(
                    f"TrackerResponseError while unregistering webhook {webhook_id} for GitLab {entity_type} {entity_id_for_log}: {e}",
                    exc_info=True,
                )
                return False


        except gitlab.exceptions.GitlabGetError as e: # Error getting group/project
            if e.response_code == 404:
                logger.error(f"GitLab {entity_type} {entity_id_for_log} not found when trying to unregister webhook.")
            else:
                logger.error(
                    f"Error getting GitLab {entity_type} {entity_id_for_log} for webhook unregistration: {e.response_code} - {e.error_message}",
                    exc_info=True,
                )
            return False
        except gitlab.exceptions.GitlabAuthenticationError: # Should be caught by _make_request
            logger.error(f"GitLab authentication error during webhook unregistration for {entity_id_for_log}.")
            raise # Re-raise
        except Exception as e:
            logger.error(
                f"Unexpected error unregistering webhook for GitLab {entity_type} {entity_id_for_log}: {e}",
                exc_info=True,
            )
            return False

    def unregister_all_webhooks(
        self, webhook_url_pattern: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Unregister all webhooks for relevant groups and projects, optionally matching a URL pattern.

        Args:
            webhook_url_pattern: If provided, only unregister webhooks whose URL
                                 matches this pattern. If None, attempts to unregister
                                 webhooks matching the SPACEBRIDGE_URL pattern.

        Returns:
            A dictionary summarizing the actions taken, e.g.,
            {"unregistered": count, "failed": count, "not_found": count}.
        """
        results = {"unregistered": 0, "failed": 0, "not_found": 0}

        target_pattern = webhook_url_pattern
        if target_pattern is None:
            sb_url = os.getenv("SPACEBRIDGE_URL")
            if sb_url:
                target_pattern = f"{sb_url.rstrip('/')}/api/v1/private/webhooks/"
                logger.info(f"GitLab: No specific webhook_url_pattern provided, using default pattern: {target_pattern}")
            else:
                logger.warning("GitLab: Cannot determine target webhook URL pattern: webhook_url_pattern is None and SPACEBRIDGE_URL is not set.")
                return results # Cannot proceed without a pattern

        # Phase 1: Group Webhook Unregistration
        logger.info("GitLab: Starting unregistration of group webhooks.")
        groups: List[Any] = []
        try:
            groups = self._make_request(self.gl.groups.list, all=True, owned=True)
        except TrackerAuthenticationError as e:
            logger.error(f"GitLab: Authentication error listing groups for webhook unregistration: {e}", exc_info=True)
            results["failed"] +=1
        except TrackerConnectionError as e:
            logger.error(f"GitLab: Connection error listing groups for webhook unregistration: {e}", exc_info=True)
            results["failed"] +=1
        except TrackerResponseError as e:
            logger.error(f"GitLab: Response error listing groups for webhook unregistration: {e}", exc_info=True)
            results["failed"] +=1
        except Exception as e: # Catch any other unexpected error during group listing
            logger.error(f"GitLab: Unexpected error listing groups for webhook unregistration: {e}", exc_info=True)
            results["failed"] +=1
        # If group listing fails, 'groups' list will be empty, and the loop below won't run.
        # We still proceed to project-level unregistration.

        for group_obj in groups:
            group_id = group_obj.id
            group_name = group_obj.name
            logger.debug(f"GitLab: Processing group '{group_name}' (ID: {group_id}) for webhook unregistration.")
            existing_hooks_for_group: Optional[List[Any]] = None
            try:
                existing_hooks_for_group = self._make_request(group_obj.hooks.list, all=True)

                found_matching_in_group = False
                if not existing_hooks_for_group:
                    logger.debug(f"GitLab: No webhooks found for group '{group_name}'.")
                    # If a pattern was specified, and no hooks exist at all, it's a "not_found" for this entity.
                    # However, the primary "not_found" is for when hooks exist but none match.
                    # This case is implicitly handled by found_matching_in_group remaining False.
                else:
                    for hook in existing_hooks_for_group:
                        hook_config_url = getattr(hook, 'url', None)
                        if hook_config_url and target_pattern and target_pattern in hook_config_url:
                            found_matching_in_group = True
                            logger.info(f"GitLab: Found matching group webhook ID {hook.id} (URL: {hook_config_url}) for group '{group_name}'. Attempting to unregister.")
                            try:
                                if self.unregister_webhook(org_identifier=str(group_id), webhook_id=hook.id):
                                    results["unregistered"] += 1
                                else:
                                    results["failed"] += 1
                            except Exception as unreg_e: # Catch errors from the unregister_webhook call itself
                                logger.error(f"GitLab: Error during unregister_webhook call for hook ID {hook.id} in group '{group_name}': {unreg_e}", exc_info=True)
                                results["failed"] += 1

                if not found_matching_in_group and target_pattern and existing_hooks_for_group is not None:
                     logger.debug(f"GitLab: No webhooks matching pattern '{target_pattern}' found for group '{group_name}' (hooks were listed).")
                     results["not_found"] += 1

            except TrackerResponseError as e:
                if "404" in str(e).lower():
                    logger.info(f"GitLab: Listing group hooks for group '{group_name}' (ID: {group_id}) failed with 404, likely not supported or no hooks. Skipping group hook processing for this group.")
                    # Do not increment results["failed"] for 404 on listing group hooks
                else:
                    logger.error(f"GitLab: TrackerResponseError listing hooks for group '{group_name}' (ID: {group_id}): {e}", exc_info=True)
                    results["failed"] += 1
            except TrackerConnectionError as e:
                logger.error(f"GitLab: TrackerConnectionError listing hooks for group '{group_name}' (ID: {group_id}): {e}", exc_info=True)
                results["failed"] += 1
            except TrackerAuthenticationError as e:
                logger.error(f"GitLab: TrackerAuthenticationError listing hooks for group '{group_name}' (ID: {group_id}): {e}", exc_info=True)
                results["failed"] += 1
            except Exception as e: # Catch-all for other errors during hook listing for a specific group
                logger.error(f"GitLab: Unexpected error processing group '{group_name}' (ID: {group_id}) for hook listing: {e}", exc_info=True)
                results["failed"] += 1

        # Phase 2: Project Webhook Unregistration (Independent Fallback)
        logger.info("GitLab: Starting project-level webhook unregistration.")
        all_projects: List[Any] = []
        try:
            all_projects = self._make_request(self.gl.projects.list, all=True, owned=True)
        except TrackerAuthenticationError as e:
            logger.error(f"GitLab: Authentication error listing all projects for webhook unregistration: {e}", exc_info=True)
            results["failed"] +=1
        except TrackerConnectionError as e:
            logger.error(f"GitLab: Connection error listing all projects for webhook unregistration: {e}", exc_info=True)
            results["failed"] +=1
        except TrackerResponseError as e:
            logger.error(f"GitLab: Response error listing all projects for webhook unregistration: {e}", exc_info=True)
            results["failed"] +=1
        except Exception as e: # Catch any other unexpected error during all_projects listing
            logger.error(f"GitLab: Unexpected error listing all projects for webhook unregistration: {e}", exc_info=True)
            results["failed"] +=1
        # If all_projects listing fails, 'all_projects' list will be empty, and the loop below won't run.

        for project_obj in all_projects:
            project_id = project_obj.id
            project_name = project_obj.path_with_namespace
            logger.debug(f"GitLab: Processing project '{project_name}' (ID: {project_id}) for webhook unregistration.")
            existing_hooks_for_project: Optional[List[Any]] = None
            try:
                existing_hooks_for_project = self._make_request(project_obj.hooks.list, all=True)

                found_matching_in_project = False
                if not existing_hooks_for_project:
                    logger.debug(f"GitLab: No webhooks found for project '{project_name}'.")
                else:
                    for hook in existing_hooks_for_project:
                        hook_config_url = getattr(hook, 'url', None)
                        if hook_config_url and target_pattern and target_pattern in hook_config_url:
                            found_matching_in_project = True
                            logger.info(f"GitLab: Found matching project webhook ID {hook.id} (URL: {hook_config_url}) for project '{project_name}'. Attempting to unregister.")
                            try:
                                if self.unregister_webhook(project_id_or_path=project_id, webhook_id=hook.id):
                                    results["unregistered"] += 1
                                else:
                                    results["failed"] += 1
                            except Exception as unreg_e: # Catch errors from the unregister_webhook call itself
                                logger.error(f"GitLab: Error during unregister_webhook call for hook ID {hook.id} in project '{project_name}': {unreg_e}", exc_info=True)
                                results["failed"] += 1

                if not found_matching_in_project and target_pattern and existing_hooks_for_project is not None:
                    logger.debug(f"GitLab: No webhooks matching pattern '{target_pattern}' found for project '{project_name}' (hooks were listed).")
                    results["not_found"] += 1

            except TrackerResponseError as e:
                if "404" in str(e).lower():
                    logger.info(f"GitLab: Listing project hooks for project '{project_name}' (ID: {project_id}) failed with 404. Skipping this project's hook processing.")
                    # Do not increment results["failed"] for 404 on listing project hooks
                else:
                    logger.error(f"GitLab: TrackerResponseError listing hooks for project '{project_name}' (ID: {project_id}): {e}", exc_info=True)
                    results["failed"] += 1
            except TrackerConnectionError as e:
                logger.error(f"GitLab: TrackerConnectionError listing hooks for project '{project_name}' (ID: {project_id}): {e}", exc_info=True)
                results["failed"] += 1
            except TrackerAuthenticationError as e:
                logger.error(f"GitLab: TrackerAuthenticationError listing hooks for project '{project_name}' (ID: {project_id}): {e}", exc_info=True)
                results["failed"] += 1
            except Exception as e: # Catch-all for other errors during hook listing for a specific project
                logger.error(f"GitLab: Unexpected error processing project '{project_name}' (ID: {project_id}) for hook listing: {e}", exc_info=True)
                results["failed"] += 1

        logger.info(f"GitLab: unregister_all_webhooks summary: {results}")
        return results

print("DEBUG: === Post-GitLabTracker Class Definition Diagnostics (V4) ===")
print(f"DEBUG: BaseTracker abstract methods: {getattr(BaseTracker, '__abstractmethods__', 'N/A')}")
print(f"DEBUG: GitLabTracker abstract methods: {getattr(GitLabTracker, '__abstractmethods__', 'N/A')}")
print(f"DEBUG: GitLabTracker.register_webhook method: {getattr(GitLabTracker, 'register_webhook', 'Missing')}")
print(f"DEBUG: type(GitLabTracker.register_webhook): {type(getattr(GitLabTracker, 'register_webhook', None))}")
print(f"DEBUG: Callable GitLabTracker.register_webhook? {callable(getattr(GitLabTracker, 'register_webhook', None))}")
print(f"DEBUG: GitLabTracker.unregister_webhook method: {getattr(GitLabTracker, 'unregister_webhook', 'Missing')}")
print(f"DEBUG: type(GitLabTracker.unregister_webhook): {type(getattr(GitLabTracker, 'unregister_webhook', None))}")
print(f"DEBUG: Callable GitLabTracker.unregister_webhook? {callable(getattr(GitLabTracker, 'unregister_webhook', None))}")
print(f"DEBUG: GitLabTracker.unregister_all_webhooks method: {getattr(GitLabTracker, 'unregister_all_webhooks', 'Missing')}")
print(f"DEBUG: type(GitLabTracker.unregister_all_webhooks): {type(getattr(GitLabTracker, 'unregister_all_webhooks', None))}")
print(f"DEBUG: Callable GitLabTracker.unregister_all_webhooks? {callable(getattr(GitLabTracker, 'unregister_all_webhooks', None))}")
print("DEBUG: === End Diagnostics (V4) ===")
