"""
GitLab tracker implementation for SpaceSync using python-gitlab library.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from typing_extensions import Literal  # For Python < 3.8 compatibility with Literal

import gitlab
from sqlalchemy.orm import Session

from ..config import logger
from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from ..utils import retry
from .base import BaseTracker
from spacemodels.models.project import Project
from spacemodels.models.organization import Organization
from spacemodels.models.webhook import Webhook
from spacemodels.crud import crud_webhook


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

        try:
            self.gl = gitlab.Gitlab(self.url, private_token=api_key)
            # Test connection and authentication
            self.gl.auth()
        except gitlab.exceptions.GitlabAuthenticationError as e:
            raise TrackerAuthenticationError(f"GitLab authentication failed: {str(e)}")
        except gitlab.exceptions.GitlabHttpError as e:
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
            project_attributes = (
                project.attributes
            )  # Use .attributes to get the raw dict
            project_list.append(
                {
                    "id": str(project_attributes.get("id")),
                    "name": project_attributes.get("name"),
                    "description": project_attributes.get("description", ""),
                    "url": project_attributes.get("web_url"),
                    "path_with_namespace": project_attributes.get(
                        "path_with_namespace"
                    ),
                    # Add metadata including timestamps
                    "meta_data": {
                        "created_at": project_attributes.get("created_at"),
                        "updated_at": project_attributes.get(
                            "last_activity_at"
                        ),  # Use last_activity_at for updates
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
        gitlab_slug = proj_data.get(
            "path_with_namespace"
        )  # Assumes get_projects was modified
        if gitlab_slug:
            transformed_data["slug"] = gitlab_slug
        else:
            # Fallback or log warning if path_with_namespace wasn't added
            logger.warning(
                f"Could not determine slug (path_with_namespace) for GitLab project ID {proj_data.get('id')}"
            )

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
            logger.error(
                f"Could not determine path_with_namespace (slug) for GitLab project ID {project_id}"
            )
            raise TrackerResponseError(
                f"Missing path_with_namespace for GitLab project ID {project_id}"
            )

        kwargs = {"all": True, "include_metadata": True}
        if since:
            kwargs["updated_after"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        gitlab_issues = self._make_request(project.issues.list, **kwargs)

        issue_list_with_comments = []
        for issue_obj in gitlab_issues:
            try:
                notes = self._make_request(
                    issue_obj.notes.list, all=True, sort="asc", order_by="created_at"
                )
            except Exception as e:
                logger.error(
                    f"Failed to fetch notes for GitLab issue {issue_obj.iid} in project {project_id}: {e}"
                )
                notes = []

            comments_data = []
            for note in notes:
                if note.system:
                    continue

                author_id_str = None
                if hasattr(note, "author") and isinstance(note.author, dict):
                    author_id_str = (
                        str(note.author.get("id")) if note.author.get("id") else None
                    )

                try:
                    created_at_dt = datetime.strptime(
                        note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    updated_at_dt = datetime.strptime(
                        note.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                except (ValueError, TypeError) as ve:  # Added TypeError for None values
                    logger.warning(
                        f"Could not parse datetime for note {note.id} on issue {issue_obj.iid}: {ve}. Using fallback."
                    )
                    created_at_dt = (
                        datetime.now()
                    )  # Fallback, consider if note.created_at can be None
                    if isinstance(note.created_at, str):
                        try:
                            created_at_dt = datetime.strptime(
                                note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                            )
                        except ValueError:
                            pass  # Keep datetime.now() if parsing fails
                    updated_at_dt = created_at_dt

                comments_data.append(
                    {
                        "id": str(note.id),
                        "body": note.body or "",
                        "author_id": author_id_str,
                        "created_at": created_at_dt,
                        "updated_at": updated_at_dt,
                        "url": f"{issue_obj.web_url}#note_{note.id}",
                    }
                )

            external_id = str(issue_obj.id)
            key = f"{project_slug}#{issue_obj.iid}"

            try:
                issue_created_at = datetime.strptime(
                    issue_obj.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                issue_updated_at = datetime.strptime(
                    issue_obj.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
            except (ValueError, TypeError) as ve:  # Added TypeError for None values
                logger.warning(
                    f"Could not parse datetime for issue {issue_obj.iid}: {ve}. Using fallback."
                )
                issue_created_at = datetime.now()
                if isinstance(issue_obj.created_at, str):
                    try:
                        issue_created_at = datetime.strptime(
                            issue_obj.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                        )
                    except ValueError:
                        pass  # Keep datetime.now() if parsing fails
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
                    "assignees": [
                        assignee["username"]
                        for assignee in issue_obj.assignees
                        if isinstance(assignee, dict) and "username" in assignee
                    ]
                    if hasattr(issue_obj, "assignees")
                    else [],
                    "url": issue_obj.web_url,
                    "comments": comments_data,
                }
            )
        return issue_list_with_comments

    def transform_issue(
        self, issue_data: Dict[str, Any], project: Project
    ) -> Dict[str, Any]:
        """
        Transforms GitLab issue data into a standardized format.
        """
        if "key" not in issue_data:
            issue_data["key"] = f"{project.slug}#{issue_data['iid']}"

        transformed_data = super().transform_issue(issue_data, project)
        labels = transformed_data.get("meta_data", {}).get("labels", [])
        new_labels = [
            label["title"] if isinstance(label, dict) and "title" in label else label
            for label in labels
        ]
        transformed_data["meta_data"]["labels"] = new_labels

        return transformed_data

    def transform_comment(
        self,
        comment_data: Dict[str, Any],
        issue_db_id: str,
        author_db_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transforms GitLab comment data into a standardized format.
        """
        transformed_data = super().transform_comment(
            comment_data, issue_db_id, author_db_id
        )

        # GitLab-specific transformations can be added here if needed

        return transformed_data

    def register_webhook(self, **kwargs: Any) -> bool:
        raise NotImplementedError("GitLabTracker.register_webhook is not implemented.")

    def register_group_webhook(
        self, db: Session, organization: Organization, webhook_url: str, secret: str
    ) -> Union[bool, Literal["group_hooks_not_supported"]]:
        """
        Register a webhook for the given GitLab group.

        Args:
            db: The database session.
            organization: The organization to register the webhook for.
            webhook_url: The target URL for the webhook.
            secret: The secret token to use for the webhook.

        Returns:
            True if registration was successful or webhook already exists.
            "group_hooks_not_supported" if the /hooks endpoint for the group returns 404.
            False for other errors.
        """
        logger.info(
            f"Attempting to register group webhook for GitLab group ID '{organization.identifier}' pointing to {webhook_url}"
        )

        hook_attrs = {
            "url": webhook_url,
            "token": secret,
            "issues_events": True,
            "push_events": True,
            "merge_requests_events": True,
            "note_events": True,
            "pipeline_events": True,
            "job_events": True,
            "repository_update_events": True,
            "enable_ssl_verification": True,
        }

        try:
            logger.info(
                f"GitLabTracker: Attempting self.gl.groups.get() for group webhook. org_identifier='{organization.identifier}', client API URL='{self.gl.url}'"
            )
            group = self._make_request(self.gl.groups.get, organization.identifier)

            # Try to list existing hooks. A 404 here indicates group hooks are not supported.
            try:
                existing_hooks = group.hooks.list(all=True)
                for h in existing_hooks:
                    if h.url == webhook_url:
                        logger.warning(
                            f"Group webhook for GitLab group '{organization.identifier}' (URL: {webhook_url}) already exists (ID: {h.id})."
                        )
                        return True
            except gitlab.exceptions.GitlabListError as e:
                if e.response_code == 404:
                    logger.info(
                        f"Listing group hooks for GitLab group '{organization.identifier}' failed with 404. Assuming group hooks are not supported (e.g., GitLab CE)."
                    )
                    return "group_hooks_not_supported"
                logger.error(
                    f"Error listing group hooks for GitLab group '{organization.identifier}': {e.response_code} - {e.error_message}",
                    exc_info=True,
                )
                return False  # Other errors during list are a failure

            # If list succeeded and hook doesn't exist, try to create it.
            logger.info(
                f"Attempting to create group hook for GitLab group '{organization.identifier}' (URL: {webhook_url})."
            )
            try:
                hook = group.hooks.create(hook_attrs)
                logger.info(
                    f"Successfully created group webhook (ID: {hook.id}) for GitLab group '{organization.identifier}'."
                )
                crud_webhook.create(
                    db,
                    obj_in={
                        "external_id": str(hook.id),
                        "url": webhook_url,
                        "secret": secret,
                        "tracker_id": self.tracker_id,
                        "organization_id": organization.id,
                    },
                )
                return True
            except gitlab.exceptions.GitlabCreateError as e:
                if e.response_code == 409:  # Conflict
                    logger.warning(
                        f"Group webhook for GitLab group '{organization.identifier}' (URL: {webhook_url}) already exists (409 on create)."
                    )
                    return True
                elif e.response_code == 404:  # Not Found on create
                    logger.warning(
                        f"Creating group hook for GitLab group '{organization.identifier}' failed with 404. Assuming group hooks are not supported (e.g., GitLab CE)."
                    )
                    return "group_hooks_not_supported"
                elif e.response_code == 401:
                    logger.error(
                        f"GitLab authentication failed (401) creating group hook for '{organization.identifier}'."
                    )
                    return False
                elif e.response_code == 403:
                    logger.error(
                        f"Permission denied (403) creating group hook for '{organization.identifier}'. Check token permissions."
                    )
                    return False
                else:
                    logger.error(
                        f"GitLab API error {e.response_code} creating group hook for '{organization.identifier}'. Response: {e.error_message}",
                        exc_info=True,
                    )
                    return False

        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404:
                logger.error(
                    f"GitLab group '{organization.identifier}' not found when attempting to register group webhook."
                )
                return False  # Group itself not found
            logger.error(
                f"Error getting GitLab group '{organization.identifier}' for group webhook: {e.response_code} - {e.error_message}",
                exc_info=True,
            )
            return False
        except (
            gitlab.exceptions.GitlabAuthenticationError
        ) as e:  # Should be caught by _make_request mostly
            logger.error(
                f"GitLab authentication error during group webhook setup for '{organization.identifier}': {e}",
                exc_info=True,
            )
            raise  # Re-raise as this is a fundamental issue
        except Exception as e:  # Catch-all for unexpected issues
            logger.error(
                f"Unexpected error registering group webhook for GitLab group '{organization.identifier}': {e}",
                exc_info=True,
            )
            return False

    def register_project_webhook(
        self, db: Session, project: Project, webhook_url: str, secret: str
    ) -> bool:
        """
        Register a webhook for the given GitLab project.

        Args:
            db: The database session.
            project: The project to register the webhook for.
            webhook_url: The target URL for the webhook.
            secret: The secret token to use for the webhook.

        Returns:
            True if registration was successful or webhook already exists, False otherwise.
        """
        logger.info(
            f"Attempting to register project webhook for GitLab project '{project.identifier}' pointing to {webhook_url}"
        )

        hook_attrs = {
            "url": webhook_url,
            "token": secret,
            "issues_events": True,
            "push_events": True,
            "merge_requests_events": True,
            "repository_update_events": True,
            "enable_ssl_verification": True,
            # Consider adding more project-specific events if needed:
            "note_events": True,
            "job_events": True,
            "pipeline_events": True,
            "wiki_page_events": True,
        }

        try:
            logger.info(
                f"GitLabTracker: Attempting self.gl.projects.get() for project webhook. project_id_or_path='{project.identifier}'"
            )
            gitlab_project = self._make_request(
                self.gl.projects.get, project.identifier
            )

            # Try to list existing hooks for the project.
            try:
                existing_hooks = gitlab_project.hooks.list(all=True)
                for h in existing_hooks:
                    if h.url == webhook_url:
                        logger.warning(
                            f"Project webhook for GitLab project '{project.identifier}' (URL: {webhook_url}) already exists (ID: {h.id})."
                        )
                        return True
            except gitlab.exceptions.GitlabListError as e:
                logger.error(
                    f"Error listing project hooks for GitLab project '{project.identifier}': {e.response_code} - {e.error_message}",
                    exc_info=True,
                )
                return False

            # If list succeeded and hook doesn't exist, try to create it.
            logger.info(
                f"Attempting to create project hook for GitLab project '{project.identifier}' (URL: {webhook_url})."
            )
            try:
                hook = gitlab_project.hooks.create(hook_attrs)
                crud_webhook.create(
                    db,
                    obj_in={
                        "external_id": str(hook.id),
                        "url": webhook_url,
                        "secret": secret,
                        "tracker_id": self.tracker_id,
                        "project_id": project.id,
                    },
                )
                logger.info(
                    f"Successfully registered webhook {hook.id} for project {project.identifier}."
                )
                return True
            except gitlab.exceptions.GitlabCreateError as e:
                if e.response_code == 409:  # Conflict
                    logger.warning(
                        f"Project webhook for GitLab project '{project.identifier}' (URL: {webhook_url}) already exists (409 on create)."
                    )
                    return True
                elif e.response_code == 404:
                    logger.error(
                        f"Creating project hook for GitLab project '{project.identifier}' failed with 404. Project or hooks endpoint not found or no permission."
                    )
                    return False
                elif e.response_code == 401:
                    logger.error(
                        f"GitLab authentication failed (401) creating project hook for '{project.identifier}'."
                    )
                    return False
                elif e.response_code == 403:
                    logger.error(
                        f"Permission denied (403) creating project hook for '{project.identifier}'. Check token permissions."
                    )
                    return False
                else:
                    logger.error(
                        f"GitLab API error {e.response_code} creating project hook for '{project.identifier}'. Response: {e.error_message}",
                        exc_info=True,
                    )
                    return False

        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404:
                logger.error(
                    f"GitLab project '{project.identifier}' not found when attempting to register project webhook."
                )
            else:
                logger.error(
                    f"Error getting GitLab project '{project.identifier}' for project webhook: {e.response_code} - {e.error_message}",
                    exc_info=True,
                )
            return False
        except (
            gitlab.exceptions.GitlabAuthenticationError
        ) as e:  # Should be caught by _make_request
            logger.error(
                f"GitLab authentication error during project webhook setup for '{project.identifier}': {e}",
                exc_info=True,
            )
            raise  # Re-raise
        except Exception as e:  # Catch-all for unexpected issues
            logger.error(
                f"Unexpected error registering project webhook for GitLab project '{project.identifier}': {e}",
                exc_info=True,
            )
            return False

    def unregister_webhook(self, db: Session, webhook: Webhook) -> bool:
        """
        Unregister a specific webhook by its ID for a GitLab group or project.

        Args:
            db: The database session.
            webhook: The Webhook object to unregister.

        Returns:
            True if unregistration was successful or webhook was already gone, False otherwise.
        """
        target_entity = None
        entity_type = ""
        entity_id_for_log = ""
        webhook_id = int(webhook.external_id)

        try:
            if webhook.organization_id:
                entity_type = "group"
                entity_id_for_log = str(webhook.organization.identifier)
                target_entity = self._make_request(
                    self.gl.groups.get, entity_id_for_log
                )
            elif webhook.project_id:
                entity_type = "project"
                entity_id_for_log = str(webhook.project.identifier)
                target_entity = self._make_request(
                    self.gl.projects.get, entity_id_for_log
                )
            else:
                logger.error(
                    f"Webhook {webhook.id} has no organization or project associated."
                )
                return False

            logger.info(
                f"GitLab: Attempting to delete webhook ID {webhook_id} from {entity_type} '{entity_id_for_log}'."
            )
            hook_manager = target_entity.hooks
            self._make_request(hook_manager.delete, webhook_id)
            logger.info(
                f"Successfully unregistered webhook {webhook_id} from GitLab {entity_type} {entity_id_for_log}."
            )

        except gitlab.exceptions.GitlabDeleteError as e:
            if e.response_code != 404:
                logger.error(
                    f"Failed to unregister webhook {webhook_id} for GitLab {entity_type} {entity_id_for_log}: {e.response_code} - {e.error_message}",
                    exc_info=True,
                )
                return False
            logger.warning(
                f"Webhook {webhook_id} for GitLab {entity_type} {entity_id_for_log} not found during delete. Assuming already unregistered."
            )
        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code != 404:
                logger.error(
                    f"Error getting GitLab {entity_type} {entity_id_for_log} for webhook unregistration: {e.response_code} - {e.error_message}",
                    exc_info=True,
                )
                return False
            logger.warning(
                f"GitLab {entity_type} {entity_id_for_log} not found when trying to unregister webhook. Assuming webhook is already gone."
            )
        except Exception as e:
            logger.error(
                f"Unexpected error unregistering webhook for GitLab {entity_type} {entity_id_for_log}: {e}",
                exc_info=True,
            )
            return False

        # If we reach here, the webhook is gone from GitLab (or was never there), so remove from DB
        crud_webhook.remove(db, id=webhook.id)
        logger.info(
            f"Removed webhook record {webhook.id} for {entity_type} {entity_id_for_log} from database."
        )
        return True

    def unregister_all_webhooks(self, db: Session) -> Dict[str, int]:
        """
        Unregister all webhooks for this tracker based on database records.

        Args:
            db: The database session.

        Returns:
            A dictionary summarizing the actions taken.
        """
        results = {"unregistered": 0, "failed": 0, "not_found": 0}
        logger.info(f"Unregistering all webhooks for GitLab tracker {self.tracker_id}.")
        webhooks = crud_webhook.get_by_tracker(db, tracker_id=self.tracker_id)

        if not webhooks:
            logger.info("No webhooks found in database for this tracker.")
            results["not_found"] = 1
            return results

        for webhook in webhooks:
            if self.unregister_webhook(db, webhook=webhook):
                results["unregistered"] += 1
            else:
                results["failed"] += 1

        logger.info(f"GitLab unregister_all_webhooks summary: {results}")
        return results
