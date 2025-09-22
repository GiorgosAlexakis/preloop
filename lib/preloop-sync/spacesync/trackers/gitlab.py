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
from spacemodels.crud import crud_webhook, crud_project, crud_organization


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

    @retry(max_attempts=2, exceptions=(TrackerConnectionError, TrackerResponseError))
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
            result = method(*args, **kwargs)
            return result
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

                author = None
                if hasattr(note, "author") and isinstance(note.author, dict):
                    author = note.author.get("username")

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
                        "author": author,
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

            # Fetch issue links for dependencies
            try:
                issue_links = self._make_request(issue_obj.links.list)
            except Exception as e:
                logger.error(
                    f"Failed to fetch links for GitLab issue {issue_obj.iid} in project {project_id}: {e}"
                )
                issue_links = []

            issue_dependencies = self._parse_dependencies(issue_links)

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
                    "dependencies": issue_dependencies,
                }
            )
        return issue_list_with_comments

    def _parse_dependencies(self, issue_links: List[Any]) -> List[Dict[str, str]]:
        """Parse issue links from GitLab API response."""
        dependencies = []
        for link in issue_links:
            try:
                # This is inefficient, as it makes an API call per link.
                # A future optimization could be to cache project slugs.
                target_project = self._make_request(
                    self.gl.projects.get, link.project_id
                )
                target_key = f"{target_project.path_with_namespace}#{link.iid}"

                # Normalize link_type: 'relates_to' -> 'relates to'
                relationship_type = link.link_type.replace("_", " ")

                dependencies.append(
                    {
                        "target_key": target_key,
                        "type": relationship_type,
                    }
                )
            except Exception as e:
                logger.error(
                    f"Could not process GitLab issue link for target iid {link.iid}: {e}"
                )
                continue
        return dependencies

    def transform_issue(
        self, issue_data: Dict[str, Any], project: Project
    ) -> Dict[str, Any]:
        """
        Transforms GitLab issue data into a standardized format.
        """
        if "key" not in issue_data:
            issue_data["key"] = f"{project.slug}#{issue_data['iid']}"
        if issue_data["state"] in ["closed", "done", "completed", "fixed"]:
            issue_data["state"] = "closed"
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
                        "events": "all",
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
            else:
                logger.error(
                    f"Error getting GitLab group '{organization.identifier}' for group webhook: {e.response_code} - {e.error_message}",
                    exc_info=True,
                )
                return False
        except (
            gitlab.exceptions.GitlabAuthenticationError
        ) as e:  # Should be caught by _make_request
            logger.error(
                f"GitLab authentication error during group webhook setup for '{organization.identifier}': {e}",
                exc_info=True,
            )
            raise  # Re-raise
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
            f"Attempting to register project webhook for GitLab project ID '{project.identifier}' pointing to {webhook_url}"
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
                f"GitLabTracker: Attempting self.gl.projects.get() for project webhook. proj_identifier='{project.identifier}', client API URL='{self.gl.url}'"
            )
            gitlab_project = self._make_request(
                self.gl.projects.get, project.identifier
            )

            # Check for existing hooks
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

            # If hook doesn't exist, create it
            logger.info(
                f"Attempting to create project hook for GitLab project '{project.identifier}' (URL: {webhook_url})."
            )
            try:
                hook = gitlab_project.hooks.create(hook_attrs)
                logger.info(
                    f"Successfully created project webhook (ID: {hook.id}) for GitLab project '{project.identifier}'."
                )
                crud_webhook.create(
                    db,
                    obj_in={
                        "external_id": str(hook.id),
                        "url": webhook_url,
                        "secret": secret,
                        "events": "all",
                        "project_id": project.id,
                    },
                )
                return True
            except gitlab.exceptions.GitlabCreateError as e:
                if e.response_code == 409:  # Conflict
                    logger.warning(
                        f"Project webhook for GitLab project '{project.identifier}' (URL: {webhook_url}) already exists (409 on create)."
                    )
                    return True
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
        webhook_id = webhook.external_id

        try:
            if webhook.organization:
                entity_type = "group"
                entity_id_for_log = str(webhook.organization.identifier)
                target_entity = self._make_request(
                    self.gl.groups.get, entity_id_for_log
                )
            elif webhook.project:
                entity_type = "project"
                entity_id_for_log = str(webhook.project.identifier)
                target_entity = self._make_request(
                    self.gl.projects.get, entity_id_for_log
                )
            else:
                logger.error(
                    f"Webhook {webhook.id} has no organization or project associated."
                )
                crud_webhook.remove(db, id=webhook.id)
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
            crud_webhook.remove(db, id=webhook.id)
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
            crud_webhook.remove(db, id=webhook.id)
        except Exception as e:
            logger.error(
                f"Unexpected error unregistering webhook for GitLab {entity_type} {entity_id_for_log}: {e}",
                exc_info=True,
            )
            crud_webhook.remove(db, id=webhook.id)
            return False

        # If we reach here, the webhook is gone from GitLab (or was never there), so remove from DB
        crud_webhook.remove(db, id=webhook.id)
        logger.info(
            f"Removed webhook record {webhook.id} for {entity_type} {entity_id_for_log} from database."
        )
        return True

    def unregister_all_webhooks(self, db: Session) -> Dict[str, int]:
        """
        Unregister all webhooks for all organizations and projects managed by this tracker instance.
        """
        results = {"unregistered": 0, "failed": 0, "not_found": 0}
        logger.info(f"Unregistering all webhooks for GitLab tracker {self.tracker_id}.")
        orgs = crud_organization.get_for_tracker(db, tracker_id=self.tracker_id)
        for org in orgs:
            self.unregister_all_webhooks_for_organization(db, org, results)
        if results["unregistered"] > 0:
            logger.info(
                f"Unregistered {results['unregistered']} webhooks for GitLab tracker {self.tracker_id}."
            )
        else:
            projects = crud_project.get_for_tracker(db, tracker_id=self.tracker_id)
            for project in projects:
                self.unregister_all_webhooks_for_project(db, project, results)
            if results["unregistered"] > 0:
                logger.info(
                    f"Unregistered {results['unregistered']} webhooks for GitLab tracker {self.tracker_id}."
                )
            else:
                logger.info(f"No webhooks found for GitLab tracker {self.tracker_id}.")

        logger.info(f"GitLab unregister_all_webhooks summary: {results}")
        return results

    def unregister_all_webhooks_for_organization(
        self, db: Session, organization: Organization, results: Dict[str, int]
    ):
        results = {"unregistered": 0, "failed": 0, "not_found": 0}
        webhooks = crud_webhook.get_all_by_organization(
            db, organization_id=organization.id
        )
        for webhook in webhooks:
            if self.unregister_webhook(db, webhook):
                results["unregistered"] += 1
            else:
                results["failed"] += 1
        return results

    def unregister_all_webhooks_for_project(
        self, db: Session, project: Project, results: Dict[str, int]
    ):
        results = {"unregistered": 0, "failed": 0, "not_found": 0}
        webhooks = crud_webhook.get_all_by_project(db, project_id=project.id)
        for webhook in webhooks:
            if self.unregister_webhook(db, webhook):
                results["unregistered"] += 1
            else:
                results["failed"] += 1
        return results

    def cleanup_stale_webhooks(self, spacebridge_url: str) -> dict:
        """
        Cleans up stale webhooks from GitLab, for both groups and projects.

        Args:
            spacebridge_url: The base URL of the SpaceBridge instance.

        Returns:
            A dictionary summarizing the actions taken, e.g., `{"unregistered": count, "failed": count}`.
        """
        results = {"unregistered": 0, "failed": 0}
        try:
            groups = self._make_request(self.gl.groups.list, all=True)
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Failed to retrieve groups for stale webhook cleanup: {e}")
            return results

        for group in groups:
            try:
                hooks = self._make_request(group.hooks.list, all=True)
                for hook in hooks:
                    if not hook.url.startswith(spacebridge_url):
                        try:
                            self._make_request(hook.delete)
                            results["unregistered"] += 1
                        except (
                            TrackerConnectionError,
                            TrackerResponseError,
                        ) as delete_error:
                            logger.error(
                                f"Failed to delete stale group webhook {hook.id} for group {group.id}: {delete_error}"
                            )
                            results["failed"] += 1
            except (TrackerConnectionError, TrackerResponseError) as list_error:
                logger.error(f"Failed to list hooks for group {group.id}: {list_error}")
                results["failed"] += 1

        try:
            projects = self._make_request(self.gl.projects.list, all=True)
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Failed to retrieve projects for stale webhook cleanup: {e}")
            return results

        for project in projects:
            try:
                hooks = self._make_request(project.hooks.list, all=True)
                for hook in hooks:
                    if not hook.url.startswith(spacebridge_url):
                        try:
                            self._make_request(hook.delete)
                            results["unregistered"] += 1
                        except (
                            TrackerConnectionError,
                            TrackerResponseError,
                        ) as delete_error:
                            logger.error(
                                f"Failed to delete stale project webhook {hook.id} for project {project.id}: {delete_error}"
                            )
                            results["failed"] += 1
            except (TrackerConnectionError, TrackerResponseError) as list_error:
                logger.error(
                    f"Failed to list hooks for project {project.id}: {list_error}"
                )
                results["failed"] += 1

        return results

    def is_webhook_registered(self, webhook: "Webhook") -> bool:
        """
        Check if a webhook is registered in the tracker.

        Args:
            webhook: The webhook to check.

        Returns:
            Whether the webhook is registered.
        """
        if not webhook.external_id:
            return False

        if webhook.project:
            try:
                project = self._make_request(
                    self.gl.projects.get, webhook.project.identifier
                )
                self._make_request(project.hooks.get, webhook.external_id)
                return True
            except (TrackerResponseError, gitlab.exceptions.GitlabGetError) as e:
                if hasattr(e, "response_code") and e.response_code == 404:
                    return False
                raise
        elif webhook.organization:
            try:
                group = self._make_request(
                    self.gl.groups.get, webhook.organization.identifier
                )
                self._make_request(group.hooks.get, webhook.external_id)
                return True
            except (TrackerResponseError, gitlab.exceptions.GitlabGetError) as e:
                if hasattr(e, "response_code") and e.response_code == 404:
                    return False
                raise
        return False

    def get_webhooks(self, organization_id: str) -> List[Dict[str, Any]]:
        """Get all webhooks for a specific group and its projects."""
        all_webhooks = []
        try:
            group = self._make_request(self.gl.groups.get, organization_id)
            group_hooks = self._make_request(group.hooks.list, all=True)
            all_webhooks.extend([h.attributes for h in group_hooks])
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(
                f"Failed to retrieve group hooks for group {organization_id}: {e}"
            )

        projects = self.get_projects(organization_id)
        for proj in projects:
            proj_identifier = proj["id"]
            try:
                project = self._make_request(self.gl.projects.get, proj_identifier)
                project_hooks = self._make_request(project.hooks.list, all=True)
                all_webhooks.extend([h.attributes for h in project_hooks])
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(
                    f"Failed to retrieve project hooks for project {proj_identifier}: {e}"
                )
        return all_webhooks

    def delete_webhook(self, webhook: Dict[str, Any]) -> bool:
        """
        Delete a webhook by its ID.
        """
        webhook_id = webhook.get("id")
        if not webhook_id:
            return False

        # Determine if it's a group or project hook
        if "project_id" in webhook:
            try:
                project = self._make_request(
                    self.gl.projects.get, webhook["project_id"]
                )
                self._make_request(project.hooks.delete, webhook_id)
                return True
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(f"Failed to delete project webhook {webhook_id}: {e}")
                return False
        elif "group_id" in webhook:
            try:
                org = self._make_request(self.gl.groups.get, webhook["group_id"])
                org_identifier = org["id"]
                group = self._make_request(self.gl.groups.get, org_identifier)
                self._make_request(group.hooks.delete, webhook_id)
                return True
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(f"Failed to delete group webhook {webhook_id}: {e}")
                return False
        return False

    def is_webhook_registered_for_project(
        self, project: "Project", webhook_url: str
    ) -> bool:
        """
        Check if a webhook is registered for a specific project.
        """
        try:
            gitlab_project = self._make_request(
                self.gl.projects.get, project.identifier
            )
            hooks = self._make_request(gitlab_project.hooks.list, all=True)
            return any(h.url == webhook_url for h in hooks)
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(
                f"Failed to check webhooks for project {project.identifier}: {e}"
            )
            return False

    def is_webhook_registered_for_organization(
        self, organization: "Organization", webhook_url: str
    ) -> bool:
        """
        Check if a webhook is registered for a specific organization (group).
        """
        try:
            group = self._make_request(self.gl.groups.get, organization.identifier)
            hooks = self._make_request(group.hooks.list, all=True)
            return any(h.url == webhook_url for h in hooks)
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(
                f"Failed to check webhooks for organization {organization.identifier}: {e}"
            )
            return False

    def get_issue(
        self, organization_id: str, project_id: str, issue_id: str
    ) -> Dict[str, Any]:
        """
        Get a single issue from GitLab.

        Args:
            organization_id: GitLab group ID.
            project_id: GitLab project ID.
            issue_id: GitLab issue IID.

        Returns:
            A dictionary containing the issue data.
        """
        try:
            project = self._make_request(self.gl.projects.get, project_id)
            issue = self._make_request(project.issues.get, issue_id)
        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404:
                raise TrackerResponseError(
                    f"Issue {issue_id} not found in project {project_id}"
                )
            raise

        project_slug = project.path_with_namespace
        key = f"{project_slug}#{issue.iid}"

        comments_data = []
        try:
            notes = self._make_request(
                issue.notes.list, all=True, sort="asc", order_by="created_at"
            )
            for note in notes:
                if note.system:
                    continue

                author = None
                if hasattr(note, "author") and isinstance(note.author, dict):
                    author = note.author.get("username")

                try:
                    created_at_dt = datetime.strptime(
                        note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    updated_at_dt = datetime.strptime(
                        note.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                except (ValueError, TypeError):
                    created_at_dt = datetime.now()
                    if isinstance(note.created_at, str):
                        try:
                            created_at_dt = datetime.strptime(
                                note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                            )
                        except ValueError:
                            pass
                    updated_at_dt = created_at_dt

                comments_data.append(
                    {
                        "id": str(note.id),
                        "body": note.body or "",
                        "author": author,
                        "created_at": created_at_dt,
                        "updated_at": updated_at_dt,
                        "url": f"{issue.web_url}#note_{note.id}",
                    }
                )
        except Exception as e:
            logger.error(f"Failed to fetch notes for issue {issue.iid}: {e}")

        try:
            issue_created_at = datetime.strptime(
                issue.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            issue_updated_at = datetime.strptime(
                issue.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"
            )
        except (ValueError, TypeError):
            issue_created_at = datetime.now()
            if isinstance(issue.created_at, str):
                try:
                    issue_created_at = datetime.strptime(
                        issue.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                except ValueError:
                    pass
            issue_updated_at = issue_created_at

        return {
            "external_id": str(issue.id),
            "key": key,
            "title": issue.title,
            "description": issue.description or "",
            "state": issue.state,
            "created_at": issue_created_at,
            "updated_at": issue_updated_at,
            "labels": issue.labels,
            "assignees": [
                assignee["username"]
                for assignee in issue.assignees
                if isinstance(assignee, dict) and "username" in assignee
            ],
            "url": issue.web_url,
            "comments": comments_data,
        }
