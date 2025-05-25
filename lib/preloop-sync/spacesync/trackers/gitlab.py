"""
GitLab tracker implementation for SpaceSync using python-gitlab library.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import gitlab

from ..config import logger # Added logger import
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
                author_name_str = "Unknown User"
                if hasattr(note, 'author') and isinstance(note.author, dict):
                    author_id_str = str(note.author.get('id')) if note.author.get('id') else None
                    author_name_str = note.author.get('username') or note.author.get('name') or author_name_str
                
                try:
                    created_at_dt = datetime.strptime(note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                    updated_at_dt = datetime.strptime(note.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                except (ValueError, TypeError) as ve: # Added TypeError for None values
                    logger.warning(f"Could not parse datetime for note {note.id} on issue {issue_obj.iid}: {ve}. Using fallback.")
                    created_at_dt = datetime.now() # Fallback, consider if note.created_at can be None
                    if isinstance(note.created_at, str):
                        try: created_at_dt = datetime.strptime(note.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except ValueError: pass # Keep datetime.now() if parsing fails
                    updated_at_dt = created_at_dt 

                comments_data.append(
                    {
                        "id": str(note.id),
                        "body": note.body or "",
                        "author_id": author_id_str,
                        "author_name": author_name_str,
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
                     try: issue_created_at = datetime.strptime(issue_obj.created_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                     except ValueError: pass # Keep datetime.now() if parsing fails
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


if __name__ == "__main__":
    pass
