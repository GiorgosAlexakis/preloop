"""GitHub API client for issue tracking."""

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
    IssueStatus,
    IssueUpdate,
    IssueUser,
    ProjectMetadata,
    TrackerConnection,
    TrackerInterface,
)

logger = logging.getLogger(__name__)


class GitHubCredentials(BaseModel):
    """Credentials for GitHub API authentication."""

    token: str = Field(..., description="GitHub API token")
    username: Optional[str] = Field(None, description="GitHub username (optional)")


class GitHubClient(TrackerInterface):
    """GitHub API client for issue tracking."""

    def __init__(
        self,
        credentials: GitHubCredentials,
        owner: str = None,
        repo: str = None,
        timeout: int = 10,
    ):
        """Initialize the GitHub client.

        Args:
            credentials: GitHub API credentials.
            owner: Repository owner/organization (optional).
            repo: Repository name (optional).
            timeout: Request timeout in seconds.
        """
        self.credentials = credentials
        self.owner = owner
        self.repo = repo
        self.timeout = timeout
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {credentials.token}",
            "User-Agent": "SpaceBridge-GitHub-Client",
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the GitHub API.

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
            if (
                response.status_code == 403
                and "X-RateLimit-Remaining" in response.headers
            ):
                remaining = response.headers.get("X-RateLimit-Remaining", "0")
                if remaining == "0":
                    reset_time = response.headers.get("X-RateLimit-Reset", "0")
                    logger.warning(
                        f"GitHub API rate limit reached. Resets at timestamp {reset_time}"
                    )

            # Raise for other status codes
            response.raise_for_status()

            return response.json()

    async def test_connection(self) -> TrackerConnection:
        """Test the connection to GitHub.

        Returns:
            Connection status.
        """
        try:
            # Get repository info to test the connection
            if self.repo:
                repo_path = f"/repos/{self.owner}/{self.repo}"
                repo_data = await self._request("GET", repo_path)
            else:
                user_path = "/user/repos"
                repo_data = await self._request("GET", user_path)

            # Get rate limit info
            rate_limit_data = await self._request("GET", "/rate_limit")

            return TrackerConnection(
                connected=True,
                message=f"Successfully connected to GitHub repository: {repo_data['full_name'] if self.repo else 'User Repositories'}",
                rate_limit=rate_limit_data["resources"],
                server_info={"version": "GitHub API v3"},
            )
        except Exception as e:
            logger.exception("Failed to connect to GitHub")
            return TrackerConnection(
                connected=False,
                message=f"Failed to connect to GitHub: {str(e)}",
            )

    async def get_repositories_grouped_by_owner(self) -> List[Dict[str, Any]]:
        """Fetch repositories accessible by the authenticated user, grouped by owner.

        Returns:
            List of dictionaries, each representing an owner and their repositories.
        """
        all_repos = []
        page = 1
        per_page = 100
        path = "/user/repos"

        while True:
            params = {
                "type": "all",
                "per_page": per_page,
                "page": page,
            }
            try:
                logger.debug(f"Fetching page {page} of user repositories from GitHub.")
                repos_page = await self._request("GET", path, params=params)
                if not repos_page:
                    logger.debug(
                        "No more repositories found, breaking pagination loop."
                    )
                    break
                all_repos.extend(repos_page)
                if len(repos_page) < per_page:
                    logger.debug("Last page of repositories reached.")
                    break
                page += 1
            except httpx.HTTPStatusError as e:
                logger.error(f"Error fetching user repositories from GitHub: {e}")
                # If it's a 404 or similar, maybe the user has no repos? Break gracefully.
                if e.response.status_code in [404, 403, 401]:
                    logger.warning(
                        f"Received {e.response.status_code} fetching repos, stopping."
                    )
                    break
                raise  # Re-raise other errors
            except Exception as e:
                logger.exception("Unexpected error fetching user repositories.")
                raise

        logger.info(f"Fetched a total of {len(all_repos)} repositories.")

        grouped_repos: Dict[str, Dict[str, Any]] = {}
        for repo in all_repos:
            owner_login = repo["owner"]["login"]
            owner_id = repo["owner"]["id"]
            owner_type = repo["owner"]["type"]  # "User" or "Organization"

            if owner_login not in grouped_repos:
                grouped_repos[owner_login] = {
                    "owner_login": owner_login,
                    "owner_id": owner_id,
                    "owner_type": owner_type,
                    "repositories": [],
                }

            repo_info = {
                "id": repo["id"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "identifier": repo["full_name"],  # Use full_name as identifier
                "description": repo.get("description"),
                "url": repo.get("html_url"),
                "is_private": repo.get("private", False),
                "updated_at": repo.get("updated_at"),
            }
            grouped_repos[owner_login]["repositories"].append(repo_info)

        # Sort repositories within each group by name
        for owner_data in grouped_repos.values():
            owner_data["repositories"].sort(key=lambda r: r["name"].lower())

        # Sort groups by owner login name
        result = sorted(grouped_repos.values(), key=lambda g: g["owner_login"].lower())
        logger.debug(f"Grouped repositories into {len(result)} owners.")

        return result

    async def get_project_metadata(self, project_key: str) -> ProjectMetadata:
        """Get metadata about a GitHub repository.

        Note: For GitHub, project_key is ignored since we already have owner/repo.

        Args:
            project_key: Project key (ignored for GitHub).

        Returns:
            Project metadata.
        """
        # Get repository info
        if self.repo:
            repo_path = f"/repos/{self.owner}/{self.repo}"
            repo_data = await self._request("GET", repo_path)
        else:
            user_path = "/user/repos"
            repo_data = await self._request("GET", user_path)
            repo_data = repo_data[0]

        # Get labels for the repository
        if self.repo:
            labels_path = f"/repos/{self.owner}/{self.repo}/labels"
            labels_data = await self._request("GET", labels_path)
        else:
            labels_path = (
                f"/repos/{repo_data['owner']['login']}/{repo_data['name']}/labels"
            )
            labels_data = await self._request("GET", labels_path)

        # GitHub doesn't have built-in priorities, so we simulate them
        priorities = [
            IssuePriority(id="high", name="High", level=3),
            IssuePriority(id="medium", name="Medium", level=2),
            IssuePriority(id="low", name="Low", level=1),
        ]

        # GitHub has fixed statuses for issues
        statuses = [
            IssueStatus(id="open", name="Open", category="todo"),
            IssueStatus(id="closed", name="Closed", category="done"),
        ]

        return ProjectMetadata(
            key=f"{self.owner}/{self.repo}" if self.repo else repo_data["full_name"],
            name=repo_data["name"],
            description=repo_data["description"],
            statuses=statuses,
            priorities=priorities,
            url=repo_data["html_url"],
        )

    def _parse_github_issue(self, issue_data: Dict[str, Any]) -> Issue:
        """Parse a GitHub issue into our standard format.

        Args:
            issue_data: Raw GitHub issue data.

        Returns:
            Standardized issue.
        """
        # Parse assignee
        assignee = None
        if issue_data.get("assignee"):
            assignee = IssueUser(
                id=str(issue_data["assignee"]["id"]),
                name=issue_data["assignee"]["login"],
                email=None,  # GitHub API doesn't provide email in this context
                avatar_url=issue_data["assignee"]["avatar_url"],
            )

        # Parse reporter (user who created the issue)
        reporter = IssueUser(
            id=str(issue_data["user"]["id"]),
            name=issue_data["user"]["login"],
            email=None,  # GitHub API doesn't provide email in this context
            avatar_url=issue_data["user"]["avatar_url"],
        )

        # Parse status
        status_id = "closed" if issue_data["state"] == "closed" else "open"
        status_name = "Closed" if issue_data["state"] == "closed" else "Open"
        status_category = "done" if issue_data["state"] == "closed" else "todo"

        status = IssueStatus(
            id=status_id,
            name=status_name,
            category=status_category,
        )

        # Parse labels
        labels = [label["name"] for label in issue_data.get("labels", [])]

        # Parse priority (GitHub doesn't have built-in priorities, so we use labels)
        priority = None
        priority_map = {
            "priority:high": IssuePriority(id="high", name="High", level=3),
            "priority:medium": IssuePriority(id="medium", name="Medium", level=2),
            "priority:low": IssuePriority(id="low", name="Low", level=1),
        }

        for label in labels:
            if label in priority_map:
                priority = priority_map[label]
                break

        # Create the issue
        return Issue(
            id=str(issue_data["id"]),
            key=f"{self.owner}/{self.repo}#{issue_data['number']}"
            if self.repo
            else f"{issue_data['repository_url'].split('/')[-2]}/{issue_data['repository_url'].split('/')[-1]}#{issue_data['number']}",
            title=issue_data["title"],
            description=issue_data["body"],
            status=status,
            priority=priority,
            created_at=datetime.fromisoformat(
                issue_data["created_at"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                issue_data["updated_at"].replace("Z", "+00:00")
            ),
            resolved_at=(
                datetime.fromisoformat(issue_data["closed_at"].replace("Z", "+00:00"))
                if issue_data.get("closed_at")
                else None
            ),
            reporter=reporter,
            assignee=assignee,
            labels=labels,
            components=[],  # GitHub doesn't have components
            parent=None,  # Will be set separately if applicable
            relations=[],  # Will be set separately if applicable
            comments=[],  # Will be set separately if applicable
            url=issue_data["html_url"],
            api_url=issue_data["url"],
            tracker_type="github",
            project_key=f"{self.owner}/{self.repo}"
            if self.repo
            else issue_data["repository_url"].split("/")[-2],
            custom_fields={},
        )

    async def search_issues(
        self,
        project_key: str,
        filter_params: IssueFilter,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[Issue], int]:
        """Search for issues in a GitHub repository.

        Args:
            project_key: Project key (ignored for GitHub).
            filter_params: Filter parameters.
            limit: Maximum number of issues to return.
            offset: Pagination offset.

        Returns:
            Tuple of (list of issues, total count).
        """
        # Build the search query
        query_parts = []

        if self.repo:
            query_parts.append(f"repo:{self.owner}/{self.repo}")
        else:
            query_parts.append(f"user:{self.owner}")

        if filter_params.query:
            query_parts.append(filter_params.query)

        if filter_params.status:
            for status in filter_params.status:
                if status.lower() == "open" or status.lower() == "closed":
                    query_parts.append(f"is:{status.lower()}")

        if filter_params.labels:
            for label in filter_params.labels:
                query_parts.append(f'label:"{label}"')

        if filter_params.created_after:
            date_str = filter_params.created_after.strftime("%Y-%m-%d")
            query_parts.append(f"created:>={date_str}")

        if filter_params.created_before:
            date_str = filter_params.created_before.strftime("%Y-%m-%d")
            query_parts.append(f"created:<={date_str}")

        if filter_params.updated_after:
            date_str = filter_params.updated_after.strftime("%Y-%m-%d")
            query_parts.append(f"updated:>={date_str}")

        if filter_params.updated_before:
            date_str = filter_params.updated_before.strftime("%Y-%m-%d")
            query_parts.append(f"updated:<={date_str}")

        if filter_params.assigned_to:
            query_parts.append(f"assignee:{filter_params.assigned_to}")

        if filter_params.reported_by:
            query_parts.append(f"author:{filter_params.reported_by}")

        # Build the final query
        query = " ".join(query_parts)

        # Determine sort options
        sort_field = "updated"
        if filter_params.sort_by:
            if filter_params.sort_by in ["created", "updated", "comments"]:
                sort_field = filter_params.sort_by

        sort_direction = "desc"
        if filter_params.sort_direction and filter_params.sort_direction.lower() in [
            "asc",
            "desc",
        ]:
            sort_direction = filter_params.sort_direction.lower()

        # Calculate page number (GitHub uses 1-based pagination)
        page = (offset // limit) + 1

        # Make the search request
        search_path = "/search/issues"
        params = {
            "q": query,
            "sort": sort_field,
            "order": sort_direction,
            "per_page": limit,
            "page": page,
        }

        search_data = await self._request("GET", search_path, params=params)

        # Parse the issues
        issues = []
        for issue_data in search_data["items"]:
            issues.append(self._parse_github_issue(issue_data))

        return issues, search_data["total_count"]

    async def get_issue(self, issue_id: str) -> Issue:
        """Get a specific GitHub issue by ID.

        For GitHub, issue_id should be the issue number (not the internal ID).

        Args:
            issue_id: Issue number in the repository.

        Returns:
            Issue details.
        """
        # Issue ID might be in various formats, so we extract just the number
        issue_number = issue_id
        if "/" in issue_id:
            parts = issue_id.split("/")
            issue_number = parts[-1]
        if "#" in issue_number:
            issue_number = issue_number.split("#")[-1]

        # Get the issue
        if self.repo:
            issue_path = f"/repos/{self.owner}/{self.repo}/issues/{issue_number}"
            issue_data = await self._request("GET", issue_path)
        else:
            issues_path = f"/search/issues?q=repo:{self.owner}+#{issue_number}"
            issues_data = await self._request("GET", issues_path)
            issue_data = issues_data["items"][0]

        # Get comments
        if self.repo:
            comments_path = (
                f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments"
            )
            comments_data = await self._request("GET", comments_path)
        else:
            comments_path = f"/repos/{issue_data['repository_url'].split('/')[-2]}/{issue_data['repository_url'].split('/')[-1]}/issues/{issue_number}/comments"
            comments_data = await self._request("GET", comments_path)

        # Parse the issue
        issue = self._parse_github_issue(issue_data)

        # Parse and add comments
        comments = []
        for comment_data in comments_data:
            comment = IssueComment(
                id=str(comment_data["id"]),
                body=comment_data["body"],
                created_at=datetime.fromisoformat(
                    comment_data["created_at"].replace("Z", "+00:00")
                ),
                updated_at=datetime.fromisoformat(
                    comment_data["updated_at"].replace("Z", "+00:00")
                ),
                author=IssueUser(
                    id=str(comment_data["user"]["id"]),
                    name=comment_data["user"]["login"],
                    email=None,
                    avatar_url=comment_data["user"]["avatar_url"],
                ),
            )
            comments.append(comment)

        issue.comments = comments

        return issue

    async def create_issue(self, project_key: str, issue_data: IssueCreate) -> Issue:
        """Create a new GitHub issue.

        Args:
            project_key: Project key (ignored for GitHub).
            issue_data: Issue data.

        Returns:
            Created issue.
        """
        # Build the request body
        body = {
            "title": issue_data.title,
            "body": issue_data.description or "",
        }

        # Set assignee if provided
        if issue_data.assignee:
            body["assignee"] = issue_data.assignee

        # Set labels if provided
        if issue_data.labels:
            body["labels"] = issue_data.labels

        # Create the issue
        if self.repo:
            issues_path = f"/repos/{self.owner}/{self.repo}/issues"
            issue_data = await self._request("POST", issues_path, data=body)
        else:
            issues_path = f"/repos/{self.owner}/{issue_data.repository}/issues"
            issue_data = await self._request("POST", issues_path, data=body)

        # Parse and return the issue
        return self._parse_github_issue(issue_data)

    async def update_issue(self, issue_id: str, issue_data: IssueUpdate) -> Issue:
        """Update an existing GitHub issue.

        Args:
            issue_id: Issue number in the repository.
            issue_data: Updated issue data.

        Returns:
            Updated issue.
        """
        # Issue ID might be in various formats, so we extract just the number
        issue_number = issue_id
        if "/" in issue_id:
            parts = issue_id.split("/")
            issue_number = parts[-1]
        if "#" in issue_number:
            issue_number = issue_number.split("#")[-1]

        # Build the request body
        body = {}

        if issue_data.title is not None:
            body["title"] = issue_data.title

        if issue_data.description is not None:
            body["body"] = issue_data.description

        if issue_data.status is not None:
            body["state"] = issue_data.status.lower()

        if issue_data.assignee is not None:
            body["assignee"] = issue_data.assignee

        if issue_data.labels is not None:
            body["labels"] = issue_data.labels

        # Update the issue
        if self.repo:
            issue_path = f"/repos/{self.owner}/{self.repo}/issues/{issue_number}"
            issue_data = await self._request("PATCH", issue_path, data=body)
        else:
            issues_path = (
                f"/repos/{self.owner}/{issue_data.repository}/issues/{issue_number}"
            )
            issue_data = await self._request("PATCH", issues_path, data=body)

        # Parse and return the issue
        return self._parse_github_issue(issue_data)

    async def add_comment(self, issue_id: str, comment: str) -> IssueComment:
        """Add a comment to a GitHub issue.

        Args:
            issue_id: Issue number in the repository.
            comment: Comment text.

        Returns:
            Created comment.
        """
        # Issue ID might be in various formats, so we extract just the number
        issue_number = issue_id
        if "/" in issue_id:
            parts = issue_id.split("/")
            issue_number = parts[-1]
        if "#" in issue_number:
            issue_number = issue_number.split("#")[-1]

        # Build the request body
        body = {
            "body": comment,
        }

        # Add the comment
        if self.repo:
            comments_path = (
                f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments"
            )
            comment_data = await self._request("POST", comments_path, data=body)
        else:
            comments_path = f"/repos/{self.owner}/{issue_data.repository}/issues/{issue_number}/comments"
            comment_data = await self._request("POST", comments_path, data=body)

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
                id=str(comment_data["user"]["id"]),
                name=comment_data["user"]["login"],
                email=None,
                avatar_url=comment_data["user"]["avatar_url"],
            ),
        )

    async def add_relation(
        self, issue_id: str, related_issue_id: str, relation_type: str
    ) -> bool:
        """Add a relation between GitHub issues.

        Since GitHub doesn't have a built-in way to relate issues beyond
        mentioning them in comments or body, this method adds a comment
        to the issue referencing the related issue.

        Args:
            issue_id: Source issue number.
            related_issue_id: Target issue number.
            relation_type: Relation type.

        Returns:
            Whether the operation was successful.
        """
        # Issue IDs might be in various formats, so we extract just the numbers
        issue_number = issue_id
        if "/" in issue_id:
            parts = issue_id.split("/")
            issue_number = parts[-1]
        if "#" in issue_number:
            issue_number = issue_number.split("#")[-1]

        related_issue_number = related_issue_id
        if "/" in related_issue_id:
            parts = related_issue_id.split("/")
            related_issue_number = parts[-1]
        if "#" in related_issue_number:
            related_issue_number = related_issue_number.split("#")[-1]

        # Format the relation as a comment
        comment = f"This issue {relation_type} #{related_issue_number}"

        # Add the comment
        try:
            await self.add_comment(issue_number, comment)
            return True
        except Exception as e:
            logger.exception(f"Failed to add relation: {e}")
            return False
