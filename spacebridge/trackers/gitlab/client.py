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


class GitLabCredentials(BaseModel):
    """Credentials for GitLab API authentication."""

    token: str = Field(..., description="GitLab personal access token")
    username: Optional[str] = Field(None, description="GitLab username (optional)")


class GitLabClient(TrackerInterface):
    """GitLab API client for issue tracking."""

    def __init__(
        self, credentials: GitLabCredentials, project_id: str, timeout: int = 10
    ):
        """Initialize the GitLab client.

        Args:
            credentials: GitLab API credentials.
            project_id: GitLab project ID or path (e.g., "group/project").
            timeout: Request timeout in seconds.
        """
        self.credentials = credentials
        self.project_id = project_id
        self.timeout = timeout
        self.base_url = "https://gitlab.com/api/v4"
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
            # Get project info to test the connection
            project_path = f"/projects/{self.project_id.replace('/', '%2F')}"
            project_data = await self._request("GET", project_path)

            # Get rate limit info from headers by making a lightweight request
            rate_info_path = "/version"
            await self._request("GET", rate_info_path)

            return TrackerConnection(
                connected=True,
                message=f"Successfully connected to GitLab project: {project_data['name']}",
                rate_limit=None,  # GitLab doesn't provide comprehensive rate limit info in API
                server_info={"version": "GitLab API v4"},
            )
        except Exception as e:
            logger.exception("Failed to connect to GitLab")
            return TrackerConnection(
                connected=False,
                message=f"Failed to connect to GitLab: {str(e)}",
            )

    async def get_project_metadata(self, project_key: str) -> ProjectMetadata:
        """Get metadata about a GitLab project.

        Note: For GitLab, project_key is ignored since we already have project_id.

        Args:
            project_key: Project key (ignored for GitLab).

        Returns:
            Project metadata.
        """
        # Get project info
        project_path = f"/projects/{self.project_id.replace('/', '%2F')}"
        project_data = await self._request("GET", project_path)

        # Get labels for the project
        labels_path = f"/projects/{self.project_id.replace('/', '%2F')}/labels"
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
            project_key: Project key (ignored for GitLab).
            filter_params: Filter parameters.
            limit: Maximum number of issues to return.
            offset: Pagination offset.

        Returns:
            Tuple of (list of issues, total count).
        """
        # Build API path
        issues_path = f"/projects/{self.project_id.replace('/', '%2F')}/issues"

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
                relation = IssueRelation(
                    relation_type=link_type,
                    issue_id=str(related["id"]),
                    issue_key=f"{related['references']['full']}",
                    summary=related["title"],
                )
                relations.append(relation)

            issue.relations = relations
        except Exception as e:
            logger.warning(f"Failed to get issue links: {e}")

        return issue

    async def create_issue(self, project_key: str, issue_data: IssueCreate) -> Issue:
        """Create a new GitLab issue.

        Args:
            project_key: Project key (ignored for GitLab).
            issue_data: Issue data.

        Returns:
            Created issue.
        """
        # Build the request body
        body = {
            "title": issue_data.title,
            "description": issue_data.description or "",
        }

        # Set assignee if provided
        if issue_data.assignee:
            body["assignee_ids"] = [
                issue_data.assignee
            ]  # GitLab requires user IDs, not usernames

        # Set labels if provided
        if issue_data.labels:
            body["labels"] = ",".join(issue_data.labels)

        # Set due date if in custom fields
        if issue_data.custom_fields and "due_date" in issue_data.custom_fields:
            body["due_date"] = issue_data.custom_fields["due_date"]

        # Set milestone if in custom fields
        if issue_data.custom_fields and "milestone_id" in issue_data.custom_fields:
            body["milestone_id"] = issue_data.custom_fields["milestone_id"]

        # Create the issue
        issues_path = f"/projects/{self.project_id.replace('/', '%2F')}/issues"
        issue_data = await self._request("POST", issues_path, data=body)

        # Parse and return the issue
        return self._parse_gitlab_issue(issue_data)

    async def update_issue(self, issue_id: str, issue_data: IssueUpdate) -> Issue:
        """Update an existing GitLab issue.

        Args:
            issue_id: Issue ID or IID.
            issue_data: Updated issue data.

        Returns:
            Updated issue.
        """
        # Extract issue IID
        issue_iid = issue_id
        if "#" in issue_id:
            issue_iid = issue_id.split("#")[-1]
        if "/" in issue_iid:
            issue_iid = issue_iid.split("/")[-1]

        # Build the request body
        body = {}

        if issue_data.title is not None:
            body["title"] = issue_data.title

        if issue_data.description is not None:
            body["description"] = issue_data.description

        if issue_data.status is not None:
            # GitLab uses state_event instead of state
            if issue_data.status.lower() == "closed":
                body["state_event"] = "close"
            elif issue_data.status.lower() in ["open", "opened"]:
                body["state_event"] = "reopen"

        if issue_data.assignee is not None:
            if issue_data.assignee:
                body["assignee_ids"] = [issue_data.assignee]
            else:
                body["assignee_ids"] = []  # Unassign

        if issue_data.labels is not None:
            body["labels"] = ",".join(issue_data.labels) if issue_data.labels else ""

        # Handle custom fields
        if issue_data.custom_fields:
            if "due_date" in issue_data.custom_fields:
                body["due_date"] = issue_data.custom_fields["due_date"]

            if "milestone_id" in issue_data.custom_fields:
                body["milestone_id"] = issue_data.custom_fields["milestone_id"]

        # Update the issue
        issue_path = (
            f"/projects/{self.project_id.replace('/', '%2F')}/issues/{issue_iid}"
        )
        issue_data = await self._request("PUT", issue_path, data=body)

        # Parse and return the issue
        return self._parse_gitlab_issue(issue_data)

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
        if "/" in issue_iid:
            issue_iid = issue_iid.split("/")[-1]

        # Add the comment
        notes_path = (
            f"/projects/{self.project_id.replace('/', '%2F')}/issues/{issue_iid}/notes"
        )
        note_data = await self._request("POST", notes_path, data={"body": comment})

        # Parse and return the comment
        return IssueComment(
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

    async def add_relation(
        self, issue_id: str, related_issue_id: str, relation_type: str
    ) -> bool:
        """Add a relation between GitLab issues.

        GitLab supports issue links but doesn't have relation types.

        Args:
            issue_id: Source issue ID.
            related_issue_id: Target issue ID.
            relation_type: Relation type (ignored in GitLab).

        Returns:
            Whether the operation was successful.
        """
        # Extract issue IIDs
        issue_iid = issue_id
        if "#" in issue_id:
            issue_iid = issue_id.split("#")[-1]
        if "/" in issue_iid:
            issue_iid = issue_iid.split("/")[-1]

        related_iid = related_issue_id
        if "#" in related_issue_id:
            related_iid = related_issue_id.split("#")[-1]
        if "/" in related_iid:
            related_iid = related_iid.split("/")[-1]

        # GitLab issue links work across projects, so we need project path for target issue
        target_project_id = self.project_id  # Default to same project

        # Check if the related issue contains project info
        if "/" in related_issue_id and "#" in related_issue_id:
            parts = related_issue_id.split("#")
            target_project_id = parts[0]
            related_iid = parts[1]

        # Add the link
        link_path = (
            f"/projects/{self.project_id.replace('/', '%2F')}/issues/{issue_iid}/links"
        )
        link_data = {
            "target_project_id": target_project_id.replace("/", "%2F"),
            "target_issue_iid": related_iid,
        }

        try:
            await self._request("POST", link_path, data=link_data)
            return True
        except Exception as e:
            logger.exception(f"Failed to add issue link: {e}")
            return False
