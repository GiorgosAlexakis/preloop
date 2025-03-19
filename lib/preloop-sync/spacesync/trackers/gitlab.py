"""
GitLab tracker implementation for SpaceSync using python-gitlab library.
"""

import gitlab
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..exceptions import TrackerAuthenticationError, TrackerConnectionError, TrackerResponseError
from ..utils import retry
from .base import BaseTracker


class GitLabTracker(BaseTracker):
    """GitLab tracker implementation using python-gitlab."""

    def __init__(self, tracker_id: int, api_key: str, connection_details: Dict[str, Any]):
        """
        Initialize the GitLab tracker.

        Args:
            tracker_id: ID of the tracker in the database.
            api_key: GitLab API token.
            connection_details: Connection details including GitLab instance URL (optional).
        """
        super().__init__(tracker_id, api_key, connection_details)
        
        gitlab_url = connection_details['gitlab_url'].rstrip('/')
            
        try:
            self.gl = gitlab.Gitlab(gitlab_url, private_token=api_key)
            # Test connection and authentication
            self.gl.auth()
        except gitlab.exceptions.GitlabAuthenticationError:
            raise TrackerAuthenticationError("GitLab authentication failed")
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
            organizations.append({
                "id": str(group.id),
                "name": group.name,
                "url": group.web_url
            })
            
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
            project_list.append({
                "id": str(project.id),
                "name": project.name,
                "description": project.description or "",
                "url": project.web_url
            })
            
        return project_list

    def get_issues(
        self, organization_id: str, project_id: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a project from GitLab.

        Args:
            organization_id: GitLab group ID (not used in API call but kept for interface consistency).
            project_id: GitLab project ID.
            since: Only return issues updated since this datetime.

        Returns:
            List of issue data dictionaries.
        """
        # Get the project object
        project = self._make_request(self.gl.projects.get, project_id)
        
        # Prepare query parameters
        kwargs = {'all': True}
        if since:
            kwargs['updated_after'] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Get issues for the project    
        issues = self._make_request(project.issues.list, **kwargs)
        
        issue_list = []
        for issue in issues:
            issue_list.append({
                "id": str(issue.iid),  # Use iid which is project-specific ID
                "title": issue.title,
                "description": issue.description or "",
                "state": issue.state,
                "created_at": datetime.strptime(issue.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"),
                "updated_at": datetime.strptime(issue.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"),
                "labels": issue.labels if hasattr(issue, 'labels') else [],
                "assignees": [assignee['username'] for assignee in issue.assignees] if hasattr(issue, 'assignees') else [],
                "url": issue.web_url
            })
            
        return issue_list