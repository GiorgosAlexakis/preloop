"""
GitLab tracker implementation for SpaceSync using python-gitlab library.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Tuple
from typing_extensions import Literal

import asyncio
import gitlab
from sqlalchemy.orm import Session

from ..config import logger
from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from .base import BaseTracker
from .utils import (
    is_not_found_error,
    is_authentication_error,
    is_conflict_error,
    async_retry,
    HTTP_STATUS_UNAUTHORIZED,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_CONFLICT,
)
from spacemodels.models.project import Project
from spacemodels.models.organization import Organization
from spacemodels.models.webhook import Webhook
from spacemodels.crud import crud_webhook
from spacebridge.schemas.tracker_models import (
    Issue,
    IssueComment,
    IssueCreate,
    IssueFilter,
    IssueUpdate,
    IssueUser,
    ProjectMetadata,
    TrackerConnection,
)


class GitLabTracker(BaseTracker):
    """GitLab tracker implementation using python-gitlab."""

    def __init__(
        self, tracker_id: str, api_key: str, connection_details: Dict[str, Any]
    ):
        """
        Initialize the GitLab tracker.
        """
        super().__init__(tracker_id, api_key, connection_details)
        gitlab_url = connection_details.get("url")
        if not gitlab_url:
            gitlab_url = "https://gitlab.com"
        gitlab_url = gitlab_url.rstrip("/")
        if gitlab_url.endswith("/api/v4"):
            gitlab_url = gitlab_url[:-7]
        self.url = gitlab_url
        try:
            self.gl = gitlab.Gitlab(self.url, private_token=api_key)
            self.gl.auth()
        except gitlab.exceptions.GitlabAuthenticationError as e:
            raise TrackerAuthenticationError(f"GitLab authentication failed: {str(e)}")
        except gitlab.exceptions.GitlabHttpError as e:
            raise TrackerConnectionError(f"GitLab connection error: {str(e)}")

    @async_retry()
    async def _make_request(self, method, *args, **kwargs):
        """
        Execute a GitLab API request with error handling in a separate thread.
        """
        try:
            # Run the synchronous method in a thread pool
            result = await asyncio.to_thread(method, *args, **kwargs)
            return result
        except gitlab.exceptions.GitlabAuthenticationError as e:
            raise TrackerAuthenticationError(f"GitLab authentication failed: {e}")
        except gitlab.exceptions.GitlabHttpError as e:
            if e.response_code == HTTP_STATUS_UNAUTHORIZED:
                raise TrackerAuthenticationError(f"GitLab authentication failed: {e}")
            else:
                raise TrackerResponseError(f"GitLab API error: {e.response_code} - {e}")
        except gitlab.exceptions.GitlabConnectionError as e:
            raise TrackerConnectionError(f"GitLab connection error: {e}")
        except Exception as e:
            # Catching potential exceptions from to_thread if the callable fails
            logger.error(
                f"An unexpected error occurred in GitLab request: {e}", exc_info=True
            )
            raise TrackerResponseError(f"GitLab API error: {e}")

    async def _make_request_no_retry(self, method, *args, **kwargs):
        """
        Execute a GitLab API request without retry logic.
        Used for operations where we want to immediately handle specific errors like 404.
        """
        try:
            # Run the synchronous method in a thread pool
            result = await asyncio.to_thread(method, *args, **kwargs)
            return result
        except gitlab.exceptions.GitlabAuthenticationError as e:
            raise TrackerAuthenticationError(f"GitLab authentication failed: {e}")
        except gitlab.exceptions.GitlabHttpError as e:
            if e.response_code == HTTP_STATUS_UNAUTHORIZED:
                raise TrackerAuthenticationError(f"GitLab authentication failed: {e}")
            else:
                raise TrackerResponseError(f"GitLab API error: {e.response_code} - {e}")
        except gitlab.exceptions.GitlabConnectionError as e:
            raise TrackerConnectionError(f"GitLab connection error: {e}")
        except Exception as e:
            # Catching potential exceptions from to_thread if the callable fails
            logger.error(
                f"An unexpected error occurred in GitLab request: {e}", exc_info=True
            )
            raise TrackerResponseError(f"GitLab API error: {e}")

    async def _parse_dependencies(self, issue_links: List[Any]) -> List[Dict[str, str]]:
        """Parse issue links from GitLab API response."""
        dependencies = []
        for link in issue_links:
            try:
                # This is inefficient, as it makes an API call per link.
                # A future optimization could be to cache project slugs.
                target_project = await self._make_request(
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

    async def test_connection(self) -> TrackerConnection:
        """Test the connection to the tracker."""
        try:
            await self._make_request(self.gl.version)
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
        Get organizations (groups) from GitLab.
        """
        groups = await self._make_request(self.gl.groups.list, all=True)
        organizations = []
        for group in groups:
            organizations.append(
                {"id": str(group.id), "name": group.name, "url": group.web_url}
            )
        return organizations

    async def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get projects for a group from GitLab.
        """
        group = await self._make_request(self.gl.groups.get, organization_id)
        projects = await self._make_request(group.projects.list, all=True)
        project_list = []
        for project in projects:
            project_attributes = project.attributes
            project_list.append(
                {
                    "id": str(project_attributes.get("id")),
                    "identifier": str(project_attributes.get("id")),
                    "name": project_attributes.get("name"),
                    "description": project_attributes.get("description", ""),
                    "url": project_attributes.get("web_url"),
                    "path_with_namespace": project_attributes.get(
                        "path_with_namespace"
                    ),
                    "meta_data": {
                        "created_at": project_attributes.get("created_at"),
                        "updated_at": project_attributes.get("last_activity_at"),
                    },
                }
            )
        return project_list

    async def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a project from GitLab.
        """
        project = await self._make_request(self.gl.projects.get, project_id)
        project_slug = project.path_with_namespace
        if not project_slug:
            raise TrackerResponseError(
                f"Missing path_with_namespace for GitLab project ID {project_id}"
            )

        kwargs = {"all": True, "include_metadata": True}
        if since:
            kwargs["updated_after"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        gitlab_issues = await self._make_request(project.issues.list, **kwargs)

        issue_list_with_comments = []
        for issue_obj in gitlab_issues:
            try:
                notes = await self._make_request(
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
                author_data = None
                if hasattr(note, "author") and isinstance(note.author, dict):
                    author_data = {
                        "id": str(note.author.get("id")),
                        "name": note.author.get("username"),
                        "avatar_url": note.author.get("avatar_url"),
                    }
                comments_data.append(
                    {
                        "id": str(note.id),
                        "body": note.body or "",
                        "author": author_data,
                        "created_at": datetime.strptime(
                            note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                        ),
                        "updated_at": datetime.strptime(
                            note.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                        ),
                        "url": f"{issue_obj.web_url}#note_{note.id}",
                    }
                )

            issue_data = issue_obj.attributes
            issue_data["comments"] = comments_data

            # Parse dependencies from issue links if available
            dependencies = []
            if hasattr(issue_obj, "links") and issue_obj.links:
                # issue_obj.links is a ProjectIssueLinkManager, need to call list() to get actual links
                try:
                    links_list = await self._make_request(
                        issue_obj.links.list, all=True
                    )
                    dependencies = await self._parse_dependencies(links_list)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse dependencies for issue {issue_obj.iid}: {e}"
                    )
                    dependencies = []
            issue_data["dependencies"] = dependencies

            issue_list_with_comments.append(issue_data)
        return issue_list_with_comments

    async def register_project_webhook(
        self, db: Session, project: Project, webhook_url: str, secret: str
    ) -> bool:
        """
        Register a webhook for the given GitLab project.
        """
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
            gitlab_project = await self._make_request(
                self.gl.projects.get, project.identifier
            )
            existing_hooks = await self._make_request(
                gitlab_project.hooks.list, all=True
            )
            for h in existing_hooks:
                if h.url == webhook_url:
                    return True

            hook = await self._make_request(gitlab_project.hooks.create, hook_attrs)
            crud_webhook.create(
                db,
                obj_in={
                    "external_id": str(hook.id),
                    "url": webhook_url,
                    "secret": secret,
                    "project_id": project.id,
                    "events": [
                        "issues",
                        "push",
                        "merge_requests",
                        "notes",
                        "pipeline",
                        "job",
                        "repository_update",
                    ],
                },
            )
            return True
        except TrackerResponseError as e:
            if str(HTTP_STATUS_CONFLICT) in str(e):  # Conflict
                logger.warning(
                    f"Project webhook for GitLab project '{project.identifier}' (URL: {webhook_url}) already exists ({HTTP_STATUS_CONFLICT} Conflict)."
                )
                return True
            logger.error(
                f"Failed to create project webhook for GitLab project '{project.identifier}': {e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during project webhook registration for GitLab project '{project.identifier}': {e}",
                exc_info=True,
            )
            return False

    async def register_group_webhook(
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
                f"GitLabTracker: Attempting self.gl.groups.get() for group webhook. org_identifier='{organization.identifier}', client API URL='{self.url}'"
            )
            group = await self._make_request(
                self.gl.groups.get, organization.identifier
            )

            # Try to list existing hooks. A 404 here indicates group hooks are not supported.
            try:
                existing_hooks = await self._make_request_no_retry(
                    group.hooks.list, all=True
                )
                for h in existing_hooks:
                    if h.url == webhook_url:
                        logger.warning(
                            f"Group webhook for GitLab group '{organization.identifier}' (URL: {webhook_url}) already exists (ID: {h.id})."
                        )
                        return True
            except Exception as e:
                # Check if this is a 404 error indicating group hooks not supported
                if is_not_found_error(e):
                    logger.info(
                        f"Listing group hooks for GitLab group '{organization.identifier}' failed with 404. Assuming group hooks are not supported (e.g., GitLab CE)."
                    )
                    return "group_hooks_not_supported"
                logger.error(
                    f"Error listing group hooks for GitLab group '{organization.identifier}': {e}",
                    exc_info=True,
                )
                return False  # Other errors during list are a failure

            # If list succeeded and hook doesn't exist, try to create it.
            logger.info(
                f"Attempting to create group hook for GitLab group '{organization.identifier}' (URL: {webhook_url})."
            )
            try:
                hook = await self._make_request_no_retry(group.hooks.create, hook_attrs)
                logger.info(
                    f"Successfully created group webhook (ID: {hook.id}) for GitLab group '{organization.identifier}'."
                )
                crud_webhook.create(
                    db,
                    obj_in={
                        "external_id": str(hook.id),
                        "url": webhook_url,
                        "secret": secret,
                        "organization_id": organization.id,
                        "events": [
                            "issues",
                            "push",
                            "merge_requests",
                            "notes",
                            "pipeline",
                            "job",
                            "repository_update",
                        ],
                    },
                )
                return True
            except Exception as e:
                # Check for various error conditions
                if is_conflict_error(e):  # Conflict
                    logger.warning(
                        f"Group webhook for GitLab group '{organization.identifier}' (URL: {webhook_url}) already exists (409 on create)."
                    )
                    return True
                elif is_not_found_error(e):  # Not Found on create
                    logger.warning(
                        f"Creating group hook for GitLab group '{organization.identifier}' failed with 404. Assuming group hooks are not supported (e.g., GitLab CE)."
                    )
                    return "group_hooks_not_supported"
                elif is_authentication_error(e):
                    logger.error(
                        f"GitLab authentication failed (401) creating group hook for '{organization.identifier}'."
                    )
                    raise TrackerAuthenticationError("GitLab authentication failed")
                else:
                    logger.error(
                        f"Failed to create group webhook for GitLab group '{organization.identifier}': {e}",
                        exc_info=True,
                    )
                    return False

        except TrackerAuthenticationError:
            raise
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during group webhook registration for GitLab group '{organization.identifier}': {e}",
                exc_info=True,
            )
            return False

    async def register_webhook(self, **kwargs: Any) -> bool:
        """Register a webhook for the tracker."""
        raise NotImplementedError

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook."""
        raise NotImplementedError

    async def get_webhooks(self, organization_id: str) -> List[Dict[str, Any]]:
        """Get webhooks for an organization."""
        raise NotImplementedError

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

        if webhook.project:
            try:
                project = await self._make_request(
                    self.gl.projects.get, webhook.project.identifier
                )
                await self._make_request(project.hooks.get, webhook.external_id)
                return True
            except (TrackerResponseError, gitlab.exceptions.GitlabGetError) as e:
                if "404" in str(e):
                    return False
                logger.error(
                    f"Failed to check project webhook {webhook.external_id}: {e}"
                )
                return False
        elif webhook.organization:
            try:
                group = await self._make_request(
                    self.gl.groups.get, webhook.organization.identifier
                )
                await self._make_request(group.hooks.get, webhook.external_id)
                return True
            except (TrackerResponseError, gitlab.exceptions.GitlabGetError) as e:
                if "404" in str(e):
                    return False
                logger.error(
                    f"Failed to check group webhook {webhook.external_id}: {e}"
                )
                return False
        return False

    async def unregister_all_webhooks(
        self, db: Session, webhook_url_pattern: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Unregister all webhooks, optionally matching a URL pattern.

        This method iterates through all relevant scopes (organizations and projects)
        for the tracker and attempts to unregister webhooks.

        Args:
            db: Database session to use for operations.
            webhook_url_pattern: If provided, only unregister webhooks whose URL
                                 matches this pattern. Otherwise, removes all webhooks
                                 associated with this tracker.

        Returns:
            A dictionary summarizing the actions taken:
            {"unregistered": count, "failed": count, "not_found": count}.
        """
        results = {"unregistered": 0, "failed": 0, "not_found": 0}
        logger.info(f"Unregistering all webhooks for GitLab tracker {self.tracker_id}.")

        # Get all organizations for this tracker from SpaceModels
        from spacemodels.crud import crud_organization, crud_project

        orgs = crud_organization.get_for_tracker(db, tracker_id=self.tracker_id)
        for org in orgs:
            await self._unregister_all_webhooks_for_organization(db, org, results)

        if results["unregistered"] == 0:
            # If no organization webhooks, try project webhooks
            projects = crud_project.get_for_tracker(db, tracker_id=self.tracker_id)
            for project in projects:
                await self._unregister_all_webhooks_for_project(db, project, results)

        if results["unregistered"] > 0:
            logger.info(
                f"Unregistered {results['unregistered']} webhooks for GitLab tracker {self.tracker_id}."
            )
        else:
            logger.info(f"No webhooks found for GitLab tracker {self.tracker_id}.")

        logger.info(f"GitLab unregister_all_webhooks summary: {results}")
        return results

    async def _unregister_all_webhooks_for_organization(
        self, db: Session, organization: Organization, results: Dict[str, int]
    ):
        """Unregister all webhooks for a specific organization."""
        webhooks = crud_webhook.get_all_by_organization(
            db, organization_id=organization.id
        )
        for webhook in webhooks:
            if await self.unregister_webhook(db, webhook):
                results["unregistered"] += 1
            else:
                results["failed"] += 1

    async def _unregister_all_webhooks_for_project(
        self, db: Session, project: Project, results: Dict[str, int]
    ):
        """Unregister all webhooks for a specific project."""
        webhooks = crud_webhook.get_all_by_project(db, project_id=project.id)
        for webhook in webhooks:
            if await self.unregister_webhook(db, webhook):
                results["unregistered"] += 1
            else:
                results["failed"] += 1

    async def unregister_webhook(self, db: Session, webhook: Webhook) -> bool:
        """Unregister a webhook."""
        try:
            if webhook.project:
                project = await self._make_request(
                    self.gl.projects.get, webhook.project.identifier
                )
                await self._make_request(project.hooks.delete, webhook.external_id)
            elif webhook.organization:
                group = await self._make_request(
                    self.gl.groups.get, webhook.organization.identifier
                )
                await self._make_request(group.hooks.delete, webhook.external_id)
            else:
                return False

            crud_webhook.remove(db, id=webhook.id)
            return True
        except Exception:
            return False

    async def is_webhook_registered_for_project(
        self, project: "Project", webhook_url: str
    ) -> bool:
        """
        Check if a webhook is registered for a specific project.
        """
        try:
            gitlab_project = await self._make_request(
                self.gl.projects.get, project.identifier
            )
            hooks = await self._make_request(gitlab_project.hooks.list, all=True)
            return any(h.url == webhook_url for h in hooks)
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(
                f"Failed to check webhooks for project {project.identifier}: {e}"
            )
            return False

    async def is_webhook_registered_for_organization(
        self, organization: "Organization", webhook_url: str
    ) -> bool:
        """
        Check if a webhook is registered for a specific organization (group).
        """
        try:
            group = await self._make_request(
                self.gl.groups.get, organization.identifier
            )
            hooks = await self._make_request(group.hooks.list, all=True)
            return any(h.url == webhook_url for h in hooks)
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(
                f"Failed to check webhooks for organization {organization.identifier}: {e}"
            )
            return False

    async def get_issue(self, issue_id: str) -> Dict[str, Any]:
        """
        Get a single issue from GitLab.

        Args:
            issue_id: GitLab issue IID.

        Returns:
            A dictionary containing the issue data.
        """
        project_id = self.connection_details.get("project_id")
        if not project_id:
            raise TrackerResponseError("Project ID not found in connection details")

        try:
            project = await self._make_request(self.gl.projects.get, project_id)
            issue = await self._make_request(project.issues.get, issue_id)
        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == HTTP_STATUS_NOT_FOUND:
                raise TrackerResponseError(
                    f"Issue {issue_id} not found in project {project_id}"
                )
            raise

        project_slug = project.path_with_namespace
        key = f"{project_slug}#{issue.iid}"

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
        }

    async def get_comments(self, issue_id: str) -> List[IssueComment]:
        """Get comments for an issue."""
        project_id = self.connection_details.get("project_id")
        if not project_id:
            raise TrackerResponseError("Project ID not found in connection details")

        try:
            project = await self._make_request(self.gl.projects.get, project_id)
            issue = await self._make_request(project.issues.get, issue_id)
        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == HTTP_STATUS_NOT_FOUND:
                raise TrackerResponseError(
                    f"Issue {issue_id} not found in project {project_id}"
                )
            raise

        comments_data = []
        try:
            notes = await self._make_request(
                issue.notes.list, all=True, sort="asc", order_by="created_at"
            )
            for note in notes:
                if note.system:
                    continue

                author_data = None
                if hasattr(note, "author") and isinstance(note.author, dict):
                    author_data = IssueUser(
                        id=str(note.author.get("id")),
                        name=note.author.get("username"),
                        avatar_url=note.author.get("avatar_url"),
                    )

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
                    IssueComment(
                        id=str(note.id),
                        body=note.body or "",
                        author=author_data,
                        created_at=created_at_dt,
                        updated_at=updated_at_dt,
                        url=f"{issue.web_url}#note_{note.id}",
                    )
                )
        except Exception as e:
            logger.error(f"Failed to fetch notes for issue {issue_id}: {e}")

        return comments_data
