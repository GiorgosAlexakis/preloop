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
from spacebridge.schemas.tracker import ProjectIdentifier, OrganizationGroup

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_WEBHOOK_EVENTS = [
    "push",
    "issues",
    "issue_comment",
    "pull_request",
    "release",
    "deployment_status",
    "commit_comment",
    "pull_request_review",
    "pull_request_review_comment",
    "discussion",
    "discussion_comment",
    # Add other relevant events as needed, e.g.:
    # "create",  # branch/tag creation
    # "delete",  # branch/tag deletion
    # "fork",
    # "member",  # collaborator added
    # "project_card",
    # "project_column",
    # "project",
    # "public",  # repo made public
    # "repository_dispatch", # for custom events
    # "star",
    # "watch", # same as star
    # "workflow_run",
    # "workflow_job",
    # "check_run",
    # "check_suite",
]


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

    async def get_organizations(self) -> List[Dict[str, Any]]:
        """Fetch organizations accessible by the authenticated user.

        Returns:
            List of dictionaries, each representing an organization.
        """
        try:
            orgs_path = "/user/orgs"
            orgs_data = await self._request("GET", orgs_path)
            orgs = [
                OrganizationGroup(
                    id=str(org["id"]),
                    name=org["login"],
                    identifier=str(org["id"]),
                    type="organization",
                    children=[],
                )
                for org in orgs_data
            ]
            return orgs
        except Exception as e:
            logger.exception("Failed to fetch organizations from GitHub")
            return []

    async def list_projects(self, org_id: int) -> List[ProjectIdentifier]:
        """Fetch projects accessible by the authenticated user.

        Returns:
            List of dictionaries, each representing a project."""
        try:
            projects_path = f"/orgs/{org_id}/repos"
            projects_data = await self._request("GET", projects_path)
            projects = [
                ProjectIdentifier(
                    id=str(p["id"]),
                    name=p["name"],
                    identifier=p["full_name"],
                    type="project",
                )
                for p in projects_data
            ]
            return projects
        except Exception as e:
            logger.exception("Failed to fetch projects from GitHub")
            return []

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

    async def create_webhook(
        self,
        owner: str,
        repo: str,
        webhook_url: str,
        secret: Optional[str] = None,
        events: Optional[List[str]] = None,
        active: bool = True,
    ) -> Dict[str, Any]:
        """Create a new webhook for a GitHub repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            webhook_url: The URL to which the payloads will be delivered.
            secret: Optional secret for securing webhooks.
            events: A list of events to subscribe to. Defaults to DEFAULT_GITHUB_WEBHOOK_EVENTS.
            active: Whether the webhook is active.

        Returns:
            The created webhook data.
        """
        if not owner or not repo:
            raise ValueError("Owner and repo must be specified to create a webhook.")

        path = f"/repos/{owner}/{repo}/hooks"
        config = {
            "url": webhook_url,
            "content_type": "json",
        }
        if secret:
            config["secret"] = secret

        payload_events = events if events else DEFAULT_GITHUB_WEBHOOK_EVENTS
        if (
            not payload_events
        ):  # Ensure there's always some event if default is also empty for some reason
            payload_events = ["push", "issues"]

        payload = {
            "name": "web",  # GitHub requires this to be "web"
            "active": active,
            "events": payload_events,
            "config": config,
        }
        logger.info(
            f"Creating webhook for {owner}/{repo} with events: {payload_events} pointing to {webhook_url}"
        )
        try:
            webhook_data = await self._request("POST", path, data=payload)
            logger.info(
                f"Successfully created webhook ID {webhook_data.get('id')} for {owner}/{repo}"
            )
            return webhook_data
        except httpx.HTTPStatusError as e:
            if (
                e.response.status_code == 422
            ):  # Unprocessable Entity - often means hook already exists
                logger.warning(
                    f"Webhook for {owner}/{repo} at {webhook_url} might already exist or config is invalid: {e.response.text}"
                )
                # Attempt to list existing webhooks to confirm
                existing_hooks = await self.list_webhooks(owner, repo)
                for hook in existing_hooks:
                    if hook.get("config", {}).get("url") == webhook_url:
                        logger.info(
                            f"Webhook for {owner}/{repo} at {webhook_url} already exists with ID {hook.get('id')}. Returning existing hook."
                        )
                        return hook
                logger.error(
                    f"Webhook creation for {owner}/{repo} failed with 422, but no existing hook found for {webhook_url}. Error: {e.response.text}"
                )
            logger.error(
                f"Failed to create webhook for {owner}/{repo}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise

    async def update_webhook(
        self,
        owner: str,
        repo: str,
        hook_id: int,
        webhook_url: Optional[str] = None,
        secret: Optional[str] = None,
        events: Optional[List[str]] = None,
        add_events: Optional[List[str]] = None,
        remove_events: Optional[List[str]] = None,
        active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update an existing webhook for a GitHub repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            hook_id: The ID of the webhook to update.
            webhook_url: New URL for the webhook.
            secret: New secret for the webhook.
            events: A list of events to replace the current subscription.
            add_events: A list of events to add to the current subscription.
            remove_events: A list of events to remove from the current subscription.
            active: New active status for the webhook.

        Returns:
            The updated webhook data.
        """
        if not owner or not repo:
            raise ValueError("Owner and repo must be specified to update a webhook.")

        path = f"/repos/{owner}/{repo}/hooks/{hook_id}"
        payload: Dict[str, Any] = {}
        config_update: Dict[str, str] = {}

        if webhook_url:
            config_update["url"] = webhook_url
        if secret:  # Note: GitHub API might require re-setting the secret if other config changes
            config_update["secret"] = secret

        if config_update:
            payload["config"] = config_update

        if (
            events is not None
        ):  # If events is provided (even empty list), it replaces existing events
            payload["events"] = (
                events if events else []
            )  # Use empty list to unsubscribe from all
        if add_events:
            payload["add_events"] = add_events
        if remove_events:
            payload["remove_events"] = remove_events

        if active is not None:
            payload["active"] = active

        if not payload:
            logger.warning(
                f"No update parameters provided for webhook ID {hook_id} on {owner}/{repo}."
            )
            # Optionally, fetch and return the current hook state or raise error
            return await self.get_webhook(owner, repo, hook_id)

        logger.info(
            f"Updating webhook ID {hook_id} for {owner}/{repo} with payload: {payload}"
        )
        try:
            updated_webhook_data = await self._request("PATCH", path, data=payload)
            logger.info(f"Successfully updated webhook ID {hook_id} for {owner}/{repo}")
            return updated_webhook_data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to update webhook ID {hook_id} for {owner}/{repo}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise

    async def list_webhooks(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """List all webhooks for a GitHub repository.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            A list of webhooks.
        """
        if not owner or not repo:
            raise ValueError("Owner and repo must be specified to list webhooks.")
        path = f"/repos/{owner}/{repo}/hooks"
        try:
            hooks = await self._request("GET", path)
            return hooks
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to list webhooks for {owner}/{repo}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise

    async def get_webhook(self, owner: str, repo: str, hook_id: int) -> Dict[str, Any]:
        """Get a specific webhook for a GitHub repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            hook_id: The ID of the webhook.

        Returns:
            The webhook data.
        """
        if not owner or not repo:
            raise ValueError("Owner and repo must be specified to get a webhook.")
        path = f"/repos/{owner}/{repo}/hooks/{hook_id}"
        try:
            hook = await self._request("GET", path)
            return hook
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to get webhook ID {hook_id} for {owner}/{repo}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise

    async def delete_webhook(self, owner: str, repo: str, hook_id: int) -> bool:
        """Delete a webhook for a GitHub repository.

        Args:
            owner: Repository owner.
            repo: Repository name.
            hook_id: The ID of the webhook to delete.

        Returns:
            True if deletion was successful, False otherwise.
        """
        if not owner or not repo:
            raise ValueError("Owner and repo must be specified to delete a webhook.")
        path = f"/repos/{owner}/{repo}/hooks/{hook_id}"
        try:
            await self._request("DELETE", path)
            logger.info(f"Successfully deleted webhook ID {hook_id} for {owner}/{repo}")
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Webhook ID {hook_id} not found for deletion on {owner}/{repo}."
                )
                return False  # Or True, depending on desired idempotency
            logger.error(
                f"Failed to delete webhook ID {hook_id} for {owner}/{repo}: {e} - {e.response.text if e.response else 'No response text'}"
            )
            raise
