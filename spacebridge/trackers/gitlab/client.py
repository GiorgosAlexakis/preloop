"""GitLab API client for issue tracking."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from pydantic import BaseModel, Field

from spacebridge.trackers.base import (
    Issue,
    IssueComment,
    IssueCreate,
    IssueFilter,
    IssuePriority,
    IssueRelation,
    IssueStatus,
    IssueUpdate,
    IssueUser,
    ProjectMetadata,
    TrackerConnection,
    TrackerInterface,
)

logger = logging.getLogger(__name__)

DEFAULT_GITLAB_WEBHOOK_EVENTS = [
    "push_events",
    "issues_events",
    "confidential_issues_events",
    "merge_requests_events",
    "tag_push_events",
    "note_events",  # Comments
    "job_events",
    "pipeline_events",
    "wiki_page_events",
    "releases_events",
    # "confidential_note_events"
    # "deployment_events" # This is a separate type of hook in GitLab, not a standard event.
]


class GitLabCredentials(BaseModel):
    """Credentials for GitLab API authentication."""

    token: str = Field(..., description="GitLab personal access token")
    username: Optional[str] = Field(None, description="GitLab username (optional)")


class GitLabClient(TrackerInterface):
    """GitLab API client for issue tracking."""

    def __init__(
        self,
        credentials: GitLabCredentials,
        project_id: str = None,
        timeout: int = 10,
        base_url: str = None,
    ):
        """Initialize the GitLab client.

        Args:
            credentials: GitLab API credentials.
            project_id: Optional GitLab project ID or path (e.g., "group/project").
                        If not provided, the client will operate at the global level.
            timeout: Request timeout in seconds.
            base_url: Optional custom GitLab API URL. Defaults to gitlab.com.
        """
        self.credentials = credentials
        self.project_id = project_id
        self.timeout = timeout
        self.base_url = base_url if base_url else "https://gitlab.com/api/v4"

        # Ensure the URL ends with /api/v4
        if not self.base_url.endswith("/api/v4"):
            self.base_url = f"{self.base_url.rstrip('/')}/api/v4"

        self.headers = {
            "PRIVATE-TOKEN": credentials.token,
            "User-Agent": "SpaceBridge-GitLab-Client",
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a request to the GitLab API.

        Args:
            method: HTTP method.
            path: API path.
            params: Query parameters.
            data: Request body.

        Returns:
            Response data.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data,
            )

            # Check for rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                logger.warning(
                    f"GitLab API rate limit reached. Retry after {retry_after} seconds"
                )

            # Raise for other status codes
            response.raise_for_status()

            return response.json()

    async def test_connection(self) -> TrackerConnection:
        """Test the connection to GitLab.

        Returns:
            Connection status.
        """
        try:
            # Get GitLab version info to test the API connection
            version_path = "/version"
            version_data = await self._request("GET", version_path)

            # Get user info to verify token permissions
            user_path = "/user"
            user_data = await self._request("GET", user_path)

            # If project_id is provided, check that project as well
            project_info = ""
            if self.project_id:
                try:
                    project_path = f"/projects/{self.project_id.replace('/', '%2F')}"
                    project_data = await self._request("GET", project_path)
                    project_info = f" and project: {project_data['name']}"
                except Exception as project_err:
                    logger.warning(
                        f"Connected to GitLab API but could not access project: {str(project_err)}"
                    )
                    project_info = " but could not access specified project"

            return TrackerConnection(
                connected=True,
                message=f"Successfully connected to GitLab API{project_info} as user: {user_data['username']}",
                rate_limit=None,  # GitLab doesn't provide comprehensive rate limit info in API
                server_info={
                    "version": f"GitLab {version_data.get('version', 'API v4')}"
                },
            )
        except Exception as e:
            logger.exception("Failed to connect to GitLab")
            return TrackerConnection(
                connected=False,
                message=f"Failed to connect to GitLab: {str(e)}",
            )

    async def get_project_metadata(self, project_key: str) -> ProjectMetadata:
        """Get metadata about a GitLab project.

        Note: For GitLab, if project_key is provided it will be used,
        otherwise the instance project_id will be used if available.

        Args:
            project_key: Project key (namespace/project path).

        Returns:
            Project metadata.
        """
        # Use project_key if provided, otherwise fall back to instance project_id
        actual_project_id = project_key if project_key else self.project_id

        if not actual_project_id:
            raise ValueError(
                "No project specified. Provide project_key or initialize with project_id."
            )

        # Get project info
        project_path = f"/projects/{actual_project_id.replace('/', '%2F')}"
        project_data = await self._request("GET", project_path)

        # Get labels for the project
        labels_path = f"/projects/{actual_project_id.replace('/', '%2F')}/labels"
        labels_data = await self._request("GET", labels_path)

        # GitLab has prioritized labels, map them to our priority model
        # If they don't use standard priority labels, create defaults
        priorities = [
            IssuePriority(id="critical", name="Critical", level=4),
            IssuePriority(id="high", name="High", level=3),
            IssuePriority(id="medium", name="Medium", level=2),
            IssuePriority(id="low", name="Low", level=1),
        ]

        # Check for priority labels in project labels
        for label in labels_data:
            if label["name"].lower().startswith("priority::"):
                pass  # Process if needed

        # GitLab issue states
        statuses = [
            IssueStatus(id="opened", name="Open", category="todo"),
            IssueStatus(id="closed", name="Closed", category="done"),
        ]

        return ProjectMetadata(
            key=str(project_data["id"]),
            name=project_data["name"],
            description=project_data["description"] or "",
            statuses=statuses,
            priorities=priorities,
            url=project_data["web_url"],
        )

    async def get_projects_for_group(self, group_path: str) -> List[Dict[str, Any]]:
        """Fetch projects for a specific group."""
        return await self._request("GET", f"groups/{group_path}/projects")

    async def get_groups(self) -> List[Dict[str, Any]]:
        """Fetch groups the user has access to."""
        return await self._request("GET", "groups")

    async def get_groups_and_projects(self) -> List[Dict[str, Any]]:
        """Fetch groups and projects the user has access to, structured for UI."""
        results = []
        processed_project_ids = set()

        async def _fetch_paginated(
            path: str, params: Optional[Dict[str, Any]] = None
        ) -> List[Dict[str, Any]]:
            """Helper to fetch all pages for a GitLab endpoint."""
            all_items = []
            page = 1
            if params is None:
                params = {}
            # Use a reasonable default per_page, GitLab max is 100
            params["per_page"] = params.get("per_page", 100)

            while True:
                current_params = params.copy()
                current_params["page"] = page
                logger.debug(
                    f"Fetching page {page} from {path} with params: {current_params}"
                )
                try:
                    # NOTE: Assuming self._request is available as this is now a class method
                    page_items = await self._request("GET", path, params=current_params)
                    if not page_items:
                        logger.debug(f"No more items found on page {page} for {path}.")
                        break
                    logger.debug(
                        f"Found {len(page_items)} items on page {page} for {path}."
                    )
                    all_items.extend(page_items)
                    # Check if this was the last page based on items returned vs per_page requested
                    if len(page_items) < current_params["per_page"]:
                        logger.debug(
                            f"Last page detected for {path} (returned {len(page_items)} < requested {current_params['per_page']})."
                        )
                        break
                    page += 1
                    # Safety break after a large number of pages to prevent infinite loops
                    if page > 100:  # Adjust limit as needed
                        logger.warning(
                            f"Stopping pagination for {path} after 100 pages."
                        )
                        break
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"HTTP error fetching paginated data from {path} (page {page}): {e.response.status_code} - {e.response.text}"
                    )
                    # Stop pagination on error for this path
                    break
                except Exception as e:
                    logger.exception(
                        f"Unexpected error fetching paginated data from {path} (page {page})"
                    )
                    # Stop pagination on unexpected error
                    break
            logger.debug(
                f"Finished fetching paginated data for {path}. Total items: {len(all_items)}"
            )
            return all_items

        # 1. Fetch groups the user is a member of (min_access_level=10 -> Guest access)
        logger.info("Fetching GitLab groups (min_access_level=10)...")
        groups_params = {"min_access_level": 10}
        groups = await _fetch_paginated("/groups", params=groups_params)
        logger.info(f"Found {len(groups)} groups accessible by the user.")

        # 2. Fetch projects for each group
        for group in groups:
            group_id = group["id"]
            group_name = group["name"]
            group_path = group[
                "path"
            ]  # Use 'path' as it's the unique identifier in URLs
            logger.info(
                f"Fetching projects for group: '{group_name}' (Path: {group_path}, ID: {group_id})"
            )
            # Fetch projects within the group the user can see
            group_projects_path = f"/groups/{group_id}/projects"
            # We don't need extra params here, default visibility/membership applies
            group_projects = await _fetch_paginated(group_projects_path)
            logger.info(
                f"Found {len(group_projects)} projects in group '{group_name}'."
            )

            projects_list = []
            for proj in group_projects:
                project_id = proj["id"]
                projects_list.append(
                    {
                        "id": project_id,
                        "name": proj["name"],
                        "path_with_namespace": proj["path_with_namespace"],
                        "identifier": str(
                            project_id
                        ),  # Use string ID as identifier for ProjectIdentifier
                    }
                )
                processed_project_ids.add(project_id)  # Track processed projects

            # Only add the group entry if it contains projects
            if projects_list:
                results.append(
                    {
                        "group_id": group_id,  # Keep original ID for reference if needed
                        "group_name": group_name,
                        "group_path": group_path,  # Use path for OrganizationGroup ID
                        "projects": projects_list,
                    }
                )
            else:
                logger.info(
                    f"Skipping group '{group_name}' as no accessible projects were found within it."
                )

        # 3. Fetch projects owned directly by the user (these might not be in any fetched groups)
        logger.info("Fetching user-owned GitLab projects...")
        user_projects_params = {"owned": "true"}
        user_projects = await _fetch_paginated("/projects", params=user_projects_params)
        logger.info(f"Found {len(user_projects)} directly owned projects.")

        user_specific_projects = []
        user_name = "Your Projects"  # Default name
        user_path = "user"  # Default path/ID
        try:
            # Attempt to get user info for better naming
            # NOTE: Assuming self._request is available
            user_info = await self._request("GET", "/user")
            user_name = user_info.get("name", user_name)
            # Use username as the 'path' for the user's personal namespace group
            user_path = user_info.get("username", user_path)
            logger.info(f"Using user info: Name='{user_name}', Path='{user_path}'")
        except Exception as e:
            logger.warning(
                f"Could not fetch user info to name user's project group: {e}"
            )

        for proj in user_projects:
            project_id = proj["id"]
            # Only add projects not already processed via groups
            if project_id not in processed_project_ids:
                logger.debug(
                    f"Adding user-owned project '{proj['name']}' (ID: {project_id}) not found in groups."
                )
                user_specific_projects.append(
                    {
                        "id": project_id,
                        "name": proj["name"],
                        "path_with_namespace": proj["path_with_namespace"],
                        "identifier": str(project_id),  # Use string ID as identifier
                    }
                )
            else:
                logger.debug(
                    f"Skipping user-owned project '{proj['name']}' (ID: {project_id}) as it was already processed in a group."
                )

        # Add the "User's Projects" group if it contains any projects not listed elsewhere
        if user_specific_projects:
            logger.info(
                f"Adding '{user_name}' group with {len(user_specific_projects)} projects."
            )
            results.append(
                {
                    "group_id": "user",  # Special identifier for the user's personal space
                    "group_name": user_name,
                    "group_path": user_path,  # Use username or 'user' as the ID for OrganizationGroup
                    "projects": user_specific_projects,
                }
            )

        logger.info(
            f"Finished fetching GitLab groups and projects. Returning {len(results)} group/user entries."
        )
        return results

    def _parse_gitlab_issue(self, issue_data: Dict[str, Any]) -> Issue:
        """Parse a GitLab issue into our standard format.

        Args:
            issue_data: Raw GitLab issue data.

        Returns:
            Standardized issue.
        """
        # Parse assignee
        assignee = None
        if issue_data.get("assignee"):
            assignee = IssueUser(
                id=str(issue_data["assignee"]["id"]),
                name=issue_data["assignee"]["name"],
                email=None,  # GitLab API doesn't provide email here
                avatar_url=issue_data["assignee"]["avatar_url"],
            )

        # Parse author (user who created the issue)
        reporter = IssueUser(
            id=str(issue_data["author"]["id"]),
            name=issue_data["author"]["name"],
            email=None,  # GitLab API doesn't provide email here
            avatar_url=issue_data["author"]["avatar_url"],
        )

        # Parse status
        status_id = issue_data["state"]
        status_name = "Closed" if status_id == "closed" else "Open"
        status_category = "done" if status_id == "closed" else "todo"

        status = IssueStatus(
            id=status_id,
            name=status_name,
            category=status_category,
        )

        # Parse labels
        labels = issue_data.get("labels", [])

        # Parse priority (GitLab doesn't have built-in priorities, so we use labels)
        priority = None
        priority_map = {
            "priority::critical": IssuePriority(
                id="critical", name="Critical", level=4
            ),
            "priority::high": IssuePriority(id="high", name="High", level=3),
            "priority::medium": IssuePriority(id="medium", name="Medium", level=2),
            "priority::low": IssuePriority(id="low", name="Low", level=1),
        }

        for label in labels:
            if label.lower() in priority_map:
                priority = priority_map[label.lower()]
                break

        # Handle created_at and updated_at with ISO format parsing
        created_at = datetime.fromisoformat(
            issue_data["created_at"].replace("Z", "+00:00")
        )
        updated_at = datetime.fromisoformat(
            issue_data["updated_at"].replace("Z", "+00:00")
        )

        # Handle closed_at if available
        closed_at = None
        if issue_data.get("closed_at"):
            closed_at = datetime.fromisoformat(
                issue_data["closed_at"].replace("Z", "+00:00")
            )

        # Create the issue
        return Issue(
            id=str(issue_data["id"]),
            key=f"{self.project_id}#{issue_data['iid']}",
            title=issue_data["title"],
            description=issue_data["description"] or "",
            status=status,
            priority=priority,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=closed_at,
            reporter=reporter,
            assignee=assignee,
            labels=labels,
            components=[],  # GitLab doesn't have components
            parent=None,  # Will be set separately if applicable
            relations=[],  # Will be set separately if applicable
            comments=[],  # Will be set separately if applicable
            url=issue_data["web_url"],
            api_url=issue_data["_links"]["self"],
            tracker_type="gitlab",
            project_key=self.project_id,
            custom_fields={},
        )

    async def search_issues(
        self,
        project_key: str,
        filter_params: IssueFilter,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[Issue], int]:
        """Search for issues in a GitLab project.

        Args:
            project_key: Project ID (numeric string) or URL-encoded path (e.g., group%2Fproject).
            filter_params: Filter parameters.
            limit: Maximum number of issues to return.
            offset: Pagination offset.

        Returns:
            Tuple of (list of issues, total count).
        """
        # Validate project_key (should be the numeric ID string for GitLab issues API)
        if not project_key or not project_key.isdigit():
            # Although the API might support path, using ID is more reliable here.
            # If proj.identifier isn't the numeric ID, this needs adjustment upstream.
            # Assuming proj.identifier IS the numeric ID string based on previous analysis.
            logger.error(
                f"GitLab search_issues requires a numeric project ID, but received: {project_key}"
            )
            # Raise an error or return empty? Returning empty might hide issues.
            # Let's proceed assuming it's correct for now, but add a warning.
            logger.warning(
                f"Proceeding with potentially non-numeric project_key for GitLab issue search: {project_key}"
            )
            # Fallback to self.project_id if project_key seems invalid? Or just use project_key?
            # Let's use project_key as intended by the interface contract.

        # Build API path using the provided project_key
        # URL-encode the project_key in case it's a path (though we expect ID)
        encoded_project_key = project_key.replace("/", "%2F")
        issues_path = f"/projects/{encoded_project_key}/issues"

        # Build query parameters
        params = {
            "per_page": limit,
            "page": (offset // limit) + 1,  # GitLab uses 1-based pagination
        }

        # Add search term if provided
        if filter_params.query:
            params["search"] = filter_params.query

        # Add state filter if provided
        if filter_params.status:
            # GitLab only supports 'opened' or 'closed'
            if any(s.lower() == "closed" for s in filter_params.status):
                params["state"] = "closed"
            elif any(
                s.lower() == "opened" or s.lower() == "open"
                for s in filter_params.status
            ):
                params["state"] = "opened"

        # Add label filter if provided
        if filter_params.labels:
            params["labels"] = ",".join(filter_params.labels)

        # Add assignee filter if provided
        if filter_params.assigned_to:
            params["assignee_username"] = filter_params.assigned_to

        # Add date filters if provided
        if filter_params.created_after:
            params["created_after"] = filter_params.created_after.isoformat()

        if filter_params.created_before:
            params["created_before"] = filter_params.created_before.isoformat()

        if filter_params.updated_after:
            params["updated_after"] = filter_params.updated_after.isoformat()

        if filter_params.updated_before:
            params["updated_before"] = filter_params.updated_before.isoformat()

        # Add sort parameters if provided
        if filter_params.sort_by:
            sort_map = {
                "created": "created_at",
                "updated": "updated_at",
                "priority": "priority",
            }
            params["order_by"] = sort_map.get(filter_params.sort_by, "created_at")

        if filter_params.sort_direction:
            params["sort"] = filter_params.sort_direction.lower()

        # Make the request
        issues_data = await self._request("GET", issues_path, params=params)

        # Get total count from headers (need a separate request)
        count_params = dict(params)
        count_params["per_page"] = 1
        count_params["page"] = 1

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method="GET",
                url=f"{self.base_url}{issues_path}",
                headers=self.headers,
                params=count_params,
            )

            total_count = int(response.headers.get("X-Total", 0))

        # Parse issues
        issues = []
        for issue_data in issues_data:
            issues.append(self._parse_gitlab_issue(issue_data))

        # Add comments to issues
        for issue in issues:
            issue_comments = await self._get_issue_comments(
                issue.id.split("#")[-1] if "#" in issue.id else issue.id
            )
            issue.comments = issue_comments

        return issues, total_count

    async def _get_issue_comments(self, issue_id: str) -> List[IssueComment]:
        """Get comments for a GitLab issue.

        Args:
            issue_id: Issue ID.

        Returns:
            List of comments.
        """
        # For GitLab, we need to use the issue iid, not the global id
        issue_iid = issue_id
        if "#" in issue_id:
            issue_iid = issue_id.split("#")[-1]

        # Get notes (comments)
        notes_path = (
            f"/projects/{self.project_id.replace('/', '%2F')}/issues/{issue_iid}/notes"
        )
        notes_data = await self._request("GET", notes_path)

        # Parse comments
        comments = []
        for note_data in notes_data:
            # Skip system notes
            if note_data.get("system", False):
                continue

            comment = IssueComment(
                id=str(note_data["id"]),
                body=note_data["body"],
                created_at=datetime.fromisoformat(
                    note_data["created_at"].replace("Z", "+00:00")
                ),
                updated_at=datetime.fromisoformat(
                    note_data["updated_at"].replace("Z", "+00:00")
                ),
                author=IssueUser(
                    id=str(note_data["author"]["id"]),
                    name=note_data["author"]["name"],
                    email=None,
                    avatar_url=note_data["author"]["avatar_url"],
                ),
            )
            comments.append(comment)

        return comments

    async def get_issue(self, issue_id: str) -> Issue:
        """Get a specific GitLab issue by ID.

        Args:
            issue_id: Issue ID or IID.

        Returns:
            Issue details.
        """
        # Extract issue IID from various formats
        issue_iid = issue_id
        if "#" in issue_id:
            issue_iid = issue_id.split("#")[-1]
        if "/" in issue_iid:
            issue_iid = issue_iid.split("/")[-1]

        # Get the issue
        issue_path = (
            f"/projects/{self.project_id.replace('/', '%2F')}/issues/{issue_iid}"
        )
        issue_data = await self._request("GET", issue_path)

        # Parse the issue
        issue = self._parse_gitlab_issue(issue_data)

        # Get and add comments
        issue.comments = await self._get_issue_comments(issue_iid)

        # Get and add related issues (links)
        related_path = (
            f"/projects/{self.project_id.replace('/', '%2F')}/issues/{issue_iid}/links"
        )
        try:
            related_data = await self._request("GET", related_path)
            relations = []

            for related in related_data:
                link_type = "relates_to"  # GitLab doesn't provide the type in API
                related_issue_data = related["issue"]
                relation = IssueRelation(
                    id=str(related["id"]),
                    type=link_type,
                    target_issue_id=str(related_issue_data["id"]),
                    target_issue_key=f"{self.project_id}#{related_issue_data['iid']}",
                )
                relations.append(relation)
            issue.relations = relations
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Issue links endpoint not found for issue {issue_iid}. Skipping relations."
                )
            else:
                raise

        return issue

    async def create_issue(self, project_key: str, issue_data: IssueCreate) -> Issue:
        """Create a new GitLab issue.

        Args:
            project_key: Project key (ignored).
            issue_data: Issue data.

        Returns:
            Created issue.
        """
        # Build API path
        issues_path = f"/projects/{self.project_id.replace('/', '%2F')}/issues"

        # Build request body
        body = {
            "title": issue_data.title,
            "description": issue_data.description,
        }

        # Add labels if provided
        if issue_data.labels:
            body["labels"] = ",".join(issue_data.labels)

        # Add assignee if provided (lookup user ID by username)
        if issue_data.assignee:
            user_id = await self._get_user_id_by_username(issue_data.assignee)
            if user_id:
                body["assignee_ids"] = [user_id]
            # else: User not found or error occurred, warning logged in helper

        # Add priority label if provided
        if issue_data.priority:  # Use 'priority' instead of 'priority_id'
            # Assuming priority is a string like 'high', 'medium', 'low' etc.
            # GitLab uses labels for priority, format: priority::value
            priority_label = f"priority::{issue_data.priority}"
            if "labels" in body:
                body["labels"] += f",{priority_label}"
            else:
                body["labels"] = priority_label

        # Make the request
        created_issue_data = await self._request("POST", issues_path, data=body)

        # Parse and return the created issue
        return self._parse_gitlab_issue(created_issue_data)

    async def update_issue(self, issue_id: str, issue_data: IssueUpdate) -> Issue:
        """Update an existing GitLab issue.

        Args:
            issue_id: Issue ID or IID.
            issue_data: Issue update data.

        Returns:
            Updated issue.
        """
        # Extract issue IID
        issue_iid = issue_id
        if "#" in issue_id:
            issue_iid = issue_id.split("#")[-1]

        # Build API path
        issue_path = (
            f"/projects/{self.project_id.replace('/', '%2F')}/issues/{issue_iid}"
        )

        # Build request body
        body = {}
        if issue_data.title is not None:
            body["title"] = issue_data.title
        if issue_data.description is not None:
            body["description"] = issue_data.description
        if issue_data.status is not None:
            body["state_event"] = "close" if issue_data.status == "closed" else "reopen"
        if issue_data.assignee is not None:
            body["assignee_ids"] = [int(issue_data.assignee.id)]
        if issue_data.labels is not None:
            body["labels"] = ",".join(issue_data.labels)

        # Handle priority update (add/remove priority labels)
        if issue_data.priority is not None:
            # Get current labels first
            current_issue = await self.get_issue(issue_id)
            current_labels = set(current_issue.labels)

            # Remove existing priority labels
            priority_prefixes = [
                "priority::critical",
                "priority::high",
                "priority::medium",
                "priority::low",
            ]
            labels_to_remove = {
                label for label in current_labels if label.lower() in priority_prefixes
            }
            current_labels -= labels_to_remove

            # Add new priority label if not None
            if issue_data.priority:
                new_priority_label = f"priority::{issue_data.priority}"
                current_labels.add(new_priority_label)

            body["labels"] = ",".join(list(current_labels))

        # Make the request only if there are changes
        if not body:
            return await self.get_issue(issue_id)

        updated_issue_data = await self._request("PUT", issue_path, data=body)

        # Parse and return the updated issue
        return self._parse_gitlab_issue(updated_issue_data)

    async def add_comment(self, issue_id: str, comment: str) -> IssueComment:
        """Add a comment to a GitLab issue.

        Args:
            issue_id: Issue ID or IID.
            comment: Comment text.

        Returns:
            Created comment.
        """
        # Extract issue IID
        issue_iid = issue_id
        if "#" in issue_id:
            issue_iid = issue_id.split("#")[-1]

        # Build API path
        notes_path = (
            f"/projects/{self.project_id.replace('/', '%2F')}/issues/{issue_iid}/notes"
        )

        # Build request body
        body = {"body": comment}

        # Make the request
        comment_data = await self._request("POST", notes_path, data=body)

        # Parse and return the comment
        return IssueComment(
            id=str(comment_data["id"]),
            body=comment_data["body"],
            created_at=datetime.fromisoformat(
                comment_data["created_at"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                comment_data["updated_at"].replace("Z", "+00:00")
            ),
            author=IssueUser(
                id=str(comment_data["author"]["id"]),
                name=comment_data["author"]["name"],
                email=None,
                avatar_url=comment_data["author"]["avatar_url"],
            ),
        )

    async def add_relation(
        self, issue_id: str, target_issue_id: str, relation_type: str
    ) -> None:
        """Add a relation between GitLab issues.

        Note: GitLab API for issue links might require specific permissions
              and might have limitations on relation types.

        Args:
            issue_id: Source issue ID or IID.
            target_issue_id: Target issue ID or IID.
            relation_type: Type of relation (e.g., 'relates_to', 'blocks', 'is_blocked_by').
                           GitLab API might only support 'relates_to'.
        """
        # Extract issue IIDs
        source_iid = issue_id
        if "#" in issue_id:
            source_iid = issue_id.split("#")[-1]

        target_iid = target_issue_id
        if "#" in target_issue_id:
            target_iid = target_issue_id.split("#")[-1]

        # Build API path
        link_path = (
            f"/projects/{self.project_id.replace('/', '%2F')}/issues/{source_iid}/links"
        )

        # Build request body
        # GitLab API expects the target project ID and target issue IID
        # Assuming the target issue is in the same project for simplicity
        link_data = {
            "target_project_id": self.project_id,
            "target_issue_iid": target_iid,
            # "link_type": relation_type # GitLab API might not support this directly
        }

        # Make the request
        try:
            await self._request("POST", link_path, data=link_data)
            logger.info(
                f"Successfully added relation from issue {source_iid} to {target_iid}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to add relation: {e.response.status_code} - {e.response.text}"
            )
            raise

    async def _get_user_id_by_username(self, username: str) -> Optional[int]:
        """Helper to get user ID by username."""
        try:
            users_data = await self._request(
                "GET", "/users", params={"username": username}
            )
            if users_data and len(users_data) == 1:
                return users_data[0]["id"]
            logger.warning(f"User '{username}' not found or multiple users found.")
            return None
        except Exception as e:
            logger.error(f"Error fetching user ID for '{username}': {e}")
            return None

    async def create_webhook(
        self,
        project_id: str,  # Project ID or URL-encoded path
        webhook_url: str,
        secret: Optional[str] = None,
        events: Optional[List[str]] = None,  # List of event names like "push_events"
        active: bool = True,  # GitLab hooks are active by default
    ) -> Dict[str, Any]:
        """Create a new webhook for a GitLab project.

        Args:
            project_id: The ID or URL-encoded path of the project.
            webhook_url: The URL to which the payloads will be delivered.
            secret: Optional secret token for the webhook.
            events: A list of event names (e.g., "push_events", "issues_events").
                    Defaults to DEFAULT_GITLAB_WEBHOOK_EVENTS.
            active: GitLab webhooks are implicitly active on creation. This param is for consistency.

        Returns:
            The created webhook data.
        """
        if not project_id:
            raise ValueError("Project ID must be specified to create a webhook.")

        encoded_project_id = project_id.replace("/", "%2F")
        path = f"/projects/{encoded_project_id}/hooks"

        payload: Dict[str, Any] = {
            "url": webhook_url,
            "enable_ssl_verification": True,  # Good default
        }

        if secret:
            payload["token"] = secret

        # Convert event list to GitLab's boolean flags
        target_events = events if events is not None else DEFAULT_GITLAB_WEBHOOK_EVENTS
        if not target_events:  # Ensure some events if default is empty
            target_events = ["push_events", "issues_events"]

        for (
            event_name
        ) in DEFAULT_GITLAB_WEBHOOK_EVENTS:  # Iterate through all possible known events
            payload[event_name] = event_name in target_events

        # Ensure at least one event is true if target_events was specified but empty
        # or if default was empty. GitLab requires at least one event type.
        if not any(
            payload.get(ev_name)
            for ev_name in DEFAULT_GITLAB_WEBHOOK_EVENTS
            if isinstance(payload.get(ev_name), bool)
        ):
            payload["push_events"] = (
                True  # Default to push_events if nothing else is set
            )

        logger.info(
            f"Creating GitLab webhook for project {project_id} with payload: {payload}"
        )
        try:
            webhook_data = await self._request("POST", path, data=payload)
            logger.info(
                f"Successfully created GitLab webhook ID {webhook_data.get('id')} for project {project_id}"
            )
            return webhook_data
        except httpx.HTTPStatusError as e:
            # GitLab returns 400 if hook already exists for URL, but message is not specific.
            # It might also return 422 for other validation issues.
            if e.response.status_code == 400 or e.response.status_code == 422:
                logger.warning(
                    f"GitLab webhook for project {project_id} at {webhook_url} might already exist or config is invalid: {e.response.text}"
                )
                # Attempt to list existing webhooks to confirm
                try:
                    existing_hooks = await self.list_webhooks(project_id)
                    for hook in existing_hooks:
                        if hook.get("url") == webhook_url:
                            logger.info(
                                f"GitLab webhook for project {project_id} at {webhook_url} already exists with ID {hook.get('id')}. Returning existing hook."
                            )
                            return hook
                except Exception as list_err:
                    logger.error(
                        f"Could not list existing webhooks for {project_id} while handling creation error: {list_err}"
                    )
                logger.error(
                    f"Webhook creation for {project_id} failed with {e.response.status_code}, but no existing hook found for {webhook_url} or failed to list. Error: {e.response.text}"
                )
            logger.error(
                f"Failed to create GitLab webhook for project {project_id}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise

    async def update_webhook(
        self,
        project_id: str,
        hook_id: int,
        webhook_url: Optional[str] = None,
        secret: Optional[str] = None,
        events: Optional[List[str]] = None,  # Full list of event names to set
        active: Optional[
            bool
        ] = None,  # GitLab hooks are active/inactive via PUT, not a separate flag in payload
    ) -> Dict[str, Any]:
        """Update an existing webhook for a GitLab project.

        Args:
            project_id: The ID or URL-encoded path of the project.
            hook_id: The ID of the webhook to update.
            webhook_url: New URL for the webhook.
            secret: New secret token for the webhook.
            events: A list of event names to replace the current subscription.
                    If None, event subscriptions are not changed.
                    If an empty list, all event subscriptions are disabled (if API allows).
            active: GitLab doesn't have a direct 'active' flag in PUT.
                    It's implied by the hook existing. Deletion removes it.
                    This parameter is kept for interface consistency but might not directly map.

        Returns:
            The updated webhook data.
        """
        if not project_id:
            raise ValueError("Project ID must be specified to update a webhook.")

        encoded_project_id = project_id.replace("/", "%2F")
        path = f"/projects/{encoded_project_id}/hooks/{hook_id}"

        payload: Dict[str, Any] = {}
        if webhook_url is not None:
            payload["url"] = webhook_url
        if secret is not None:  # Can be set to empty string to remove
            payload["token"] = secret

        if events is not None:  # If events is provided, update event flags
            # Set all known events to false first, then true for those in the list
            for event_name in DEFAULT_GITLAB_WEBHOOK_EVENTS:
                payload[event_name] = event_name in events
            # Ensure at least one event is true if 'events' was an empty list,
            # as GitLab might require at least one event.
            if not events and not any(
                payload.get(ev_name)
                for ev_name in DEFAULT_GITLAB_WEBHOOK_EVENTS
                if isinstance(payload.get(ev_name), bool)
            ):
                # If user explicitly wants to disable all, this might be an issue with GitLab.
                # For now, let's assume if 'events' is empty, they mean to disable what they can.
                # If GitLab errors, this logic might need adjustment or clarification.
                logger.warning(
                    f"Attempting to set an empty event list for GitLab webhook {hook_id} on project {project_id}. This might be rejected by GitLab if no events are true."
                )

        if not payload:
            logger.warning(
                f"No update parameters provided for GitLab webhook ID {hook_id} on project {project_id}."
            )
            return await self.get_webhook(project_id, hook_id)

        logger.info(
            f"Updating GitLab webhook ID {hook_id} for project {project_id} with payload: {payload}"
        )
        try:
            updated_webhook_data = await self._request("PUT", path, data=payload)
            logger.info(
                f"Successfully updated GitLab webhook ID {hook_id} for project {project_id}"
            )
            return updated_webhook_data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to update GitLab webhook ID {hook_id} for project {project_id}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise

    async def list_webhooks(self, project_id: str) -> List[Dict[str, Any]]:
        """List all webhooks for a GitLab project.

        Args:
            project_id: The ID or URL-encoded path of the project.

        Returns:
            A list of webhooks.
        """
        if not project_id:
            raise ValueError("Project ID must be specified to list webhooks.")
        encoded_project_id = project_id.replace("/", "%2F")
        path = f"/projects/{encoded_project_id}/hooks"
        try:
            hooks = await self._request("GET", path)
            return hooks
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to list GitLab webhooks for project {project_id}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise

    async def get_webhook(self, project_id: str, hook_id: int) -> Dict[str, Any]:
        """Get a specific webhook for a GitLab project.

        Args:
            project_id: The ID or URL-encoded path of the project.
            hook_id: The ID of the webhook.

        Returns:
            The webhook data.
        """
        if not project_id:
            raise ValueError("Project ID must be specified to get a webhook.")
        encoded_project_id = project_id.replace("/", "%2F")
        path = f"/projects/{encoded_project_id}/hooks/{hook_id}"
        try:
            hook = await self._request("GET", path)
            return hook
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to get GitLab webhook ID {hook_id} for project {project_id}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise

    async def delete_webhook(self, project_id: str, hook_id: int) -> bool:
        """Delete a webhook for a GitLab project.

        Args:
            project_id: The ID or URL-encoded path of the project.
            hook_id: The ID of the webhook to delete.

        Returns:
            True if deletion was successful (status 204).
        """
        if not project_id:
            raise ValueError("Project ID must be specified to delete a webhook.")
        encoded_project_id = project_id.replace("/", "%2F")
        path = f"/projects/{encoded_project_id}/hooks/{hook_id}"
        try:
            # GitLab DELETE returns 204 No Content on success
            url = f"{self.base_url}{path}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method="DELETE",
                    url=url,
                    headers=self.headers,
                )
            response.raise_for_status()  # Will raise for 4xx/5xx
            logger.info(
                f"Successfully deleted GitLab webhook ID {hook_id} for project {project_id}"
            )
            return True  # Status 204 implies success
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"GitLab webhook ID {hook_id} not found for deletion on project {project_id}."
                )
                return False  # Or True for idempotency, but False indicates it wasn't there to delete
            logger.error(
                f"Failed to delete GitLab webhook ID {hook_id} for project {project_id}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise
