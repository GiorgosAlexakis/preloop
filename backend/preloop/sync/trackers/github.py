"""
GitHub tracker implementation for preloop.sync.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from preloop.models.models.organization import Organization
from preloop.models.models.webhook import Webhook
from preloop.schemas.tracker_models import (
    Issue,
    IssueComment,
    IssueCreate,
    IssueFilter,
    IssuePriority,
    IssueStatus,
    IssueUpdate,
    ProjectMetadata,
    TrackerConnection,
    IssueUser,
)

from ..exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)
from .base import BaseTracker
from .utils import (
    async_retry,
    GITHUB_DEFAULT_PAGE_SIZE,
    HTTP_STATUS_OK,
    HTTP_STATUS_CREATED,
    HTTP_STATUS_NO_CONTENT,
    HTTP_STATUS_UNAUTHORIZED,
    HTTP_STATUS_NOT_FOUND,
    HTTP_STATUS_UNPROCESSABLE_ENTITY,
)
from ..config import logger
from preloop.models.models.project import Project
from preloop.models.crud import crud_organization, crud_project, crud_webhook


class GitHubTracker(BaseTracker):
    """GitHub tracker implementation."""

    API_BASE_URL = "https://api.github.com"

    def __init__(
        self, tracker_id: str, api_key: str, connection_details: Dict[str, Any]
    ):
        """
        Initialize the GitHub tracker.
        """
        super().__init__(tracker_id, api_key, connection_details)
        self.headers = {
            "Authorization": f"token {api_key}",
            "Accept": "application/vnd.github.v3+json",
        }

    @async_retry()
    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Make a request to the GitHub API, handling pagination.
        """
        if params is None:
            params = {}
        params.setdefault("per_page", GITHUB_DEFAULT_PAGE_SIZE)
        results = []
        url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
        async with httpx.AsyncClient() as client:
            while url:
                try:
                    response = await client.get(
                        url, headers=self.headers, params=params
                    )
                    params = None

                    if response.status_code == HTTP_STATUS_UNAUTHORIZED:
                        raise TrackerAuthenticationError("GitHub authentication failed")
                    elif response.status_code >= 400:
                        raise TrackerResponseError(
                            f"GitHub API error: {response.status_code} - {response.text}"
                        )

                    data = response.json()
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        return data

                    if "next" in response.links:
                        url = response.links["next"]["url"]
                    else:
                        url = None
                except httpx.RequestError as e:
                    raise TrackerConnectionError(f"GitHub connection error: {str(e)}")
        return results

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make a request to the GitHub API.

        Args:
            method: HTTP method (GET, POST, PATCH, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response data
        """
        url = (
            f"{self.API_BASE_URL}{endpoint}"
            if endpoint.startswith("/")
            else f"{self.API_BASE_URL}/{endpoint}"
        )

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    url,
                    headers=self.headers,
                    json=data,
                    params=params,
                )

                if response.status_code == HTTP_STATUS_UNAUTHORIZED:
                    raise TrackerAuthenticationError("GitHub authentication failed")
                elif response.status_code >= 400:
                    raise TrackerResponseError(
                        f"GitHub API error: {response.status_code} - {response.text}"
                    )

                return response.json()
            except httpx.RequestError as e:
                raise TrackerConnectionError(f"GitHub connection error: {str(e)}")

    def _parse_github_issue(self, issue_data: Dict[str, Any]) -> Issue:
        """Parse a GitHub issue into our standard format.

        Args:
            issue_data: Raw GitHub issue data.

        Returns:
            Standardized issue.
        """
        owner = self.connection_details.get("owner", "")
        repo = self.connection_details.get("repo", "")

        # Parse assignee
        assignee = None
        if issue_data.get("assignee"):
            assignee = IssueUser(
                id=str(issue_data["assignee"]["id"]),
                name=issue_data["assignee"]["login"],
                email=None,
                avatar_url=issue_data["assignee"]["avatar_url"],
            )

        # Parse reporter
        reporter = None
        if issue_data.get("user"):
            reporter = IssueUser(
                id=str(issue_data["user"]["id"]),
                name=issue_data["user"]["login"],
                email=None,
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

        # Parse priority from labels
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

        # Parse dates
        created_at = datetime.fromisoformat(
            issue_data["created_at"].replace("Z", "+00:00")
        )
        updated_at = datetime.fromisoformat(
            issue_data["updated_at"].replace("Z", "+00:00")
        )
        resolved_at = None
        if issue_data.get("closed_at"):
            resolved_at = datetime.fromisoformat(
                issue_data["closed_at"].replace("Z", "+00:00")
            )

        # Create issue key
        issue_key = (
            f"{owner}/{repo}#{issue_data['number']}"
            if repo
            else f"{owner}#{issue_data['number']}"
        )

        return Issue(
            id=str(issue_data["id"]),
            key=issue_key,
            title=issue_data["title"],
            description=issue_data.get("body") or "",
            status=status,
            priority=priority,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            reporter=reporter,
            assignee=assignee,
            labels=labels,
            components=[],
            parent=None,
            relations=[],
            comments=[],
            url=issue_data["html_url"],
            api_url=issue_data["url"],
            tracker_type="github",
            project_key=f"{owner}/{repo}" if repo else owner,
            custom_fields={},
        )

    @async_retry()
    async def _make_request_delete(self, endpoint: str) -> bool:
        """
        Make a DELETE request to the GitHub API.
        """
        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
                response = await client.delete(url, headers=self.headers)

                if response.status_code == HTTP_STATUS_UNAUTHORIZED:
                    raise TrackerAuthenticationError("GitHub authentication failed")
                elif response.status_code == HTTP_STATUS_NOT_FOUND:
                    logger.warning(
                        f"Resource not found during DELETE request to {endpoint}"
                    )
                    return True
                elif response.status_code >= 400:
                    raise TrackerResponseError(
                        f"GitHub API error: {response.status_code} - {response.text}"
                    )

                return response.status_code == HTTP_STATUS_NO_CONTENT
            except httpx.RequestError as e:
                raise TrackerConnectionError(f"GitHub connection error: {str(e)}")

    async def _parse_dependencies(
        self, content: str, current_repo: str
    ) -> List[Dict[str, str]]:
        """Parse dependencies from text content (issue body, comments)."""
        dependencies = []
        import re

        # Regex to find keywords like 'closes', 'fixes', 'relates to', etc.,
        # followed by an issue reference.
        # It supports cross-repo references like 'owner/repo#123'.
        pattern = re.compile(
            r"(closes|fixes|resolves|relates to|blocked by|blocks)\s+((?:[a-zA-Z0-9-]+\/[a-zA-Z0-9_.-]+)?#\d+)",
            re.IGNORECASE,
        )

        for match in pattern.finditer(content):
            relationship_type = match.group(1).lower()
            target_issue_ref = match.group(2)

            # Normalize relationship type for consistency
            if relationship_type in ["closes", "fixes", "resolves"]:
                relationship_type = "closes"
            elif relationship_type == "relates to":
                relationship_type = "related"
            elif relationship_type == "blocked by":
                relationship_type = "is blocked by"

            # Construct the full key for the target issue
            if "#" in target_issue_ref and "/" not in target_issue_ref:
                # It's a short reference like '#123', so it's in the same repo.
                target_key = f"{current_repo}{target_issue_ref}"
            else:
                # It's a full reference like 'owner/repo#123'.
                target_key = target_issue_ref

            dependencies.append(
                {
                    "target_key": target_key,
                    "type": relationship_type,
                }
            )

        return dependencies

    async def test_connection(self) -> TrackerConnection:
        """Test the connection to the tracker."""
        try:
            await self._make_request("user")
            return TrackerConnection(connected=True, message="Connection successful")
        except (
            TrackerAuthenticationError,
            TrackerConnectionError,
            TrackerResponseError,
        ) as e:
            return TrackerConnection(connected=False, message=str(e))

    async def get_project_metadata(self, project_key: str) -> ProjectMetadata:
        """Get metadata about a GitHub project.

        Args:
            project_key: Project key (owner/repo format).

        Returns:
            Project metadata.
        """
        owner = self.connection_details.get("owner")
        repo = self.connection_details.get("repo")

        if not owner or not repo:
            raise TrackerResponseError("Owner/repo not found in connection details")

        repo_full_name = f"{owner}/{repo}"

        # Get repository details
        repo_data = await self._make_request(f"repos/{repo_full_name}")

        # GitHub has simple status model: open/closed
        statuses = [
            IssueStatus(id="open", name="Open", category="todo"),
            IssueStatus(id="closed", name="Closed", category="done"),
        ]

        # GitHub doesn't have built-in priorities, but commonly uses labels
        priorities = [
            IssuePriority(id="high", name="priority:high", level=3),
            IssuePriority(id="medium", name="priority:medium", level=2),
            IssuePriority(id="low", name="priority:low", level=1),
        ]

        return ProjectMetadata(
            key=repo_full_name,
            name=repo_data.get("name", repo),
            description=repo_data.get("description"),
            statuses=statuses,
            priorities=priorities,
            url=repo_data.get("html_url"),
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
        owner = self.connection_details.get("owner")
        repo = self.connection_details.get("repo")

        # Build the search query
        query_parts = []

        if repo:
            query_parts.append(f"repo:{owner}/{repo}")
        else:
            query_parts.append(f"user:{owner}")

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
        """Get a specific issue by ID.

        Args:
            issue_id: Issue number in the repository.

        Returns:
            Issue object.
        """
        owner = self.connection_details.get("owner")
        repo = self.connection_details.get("repo")

        if not owner or not repo:
            raise TrackerResponseError("Owner/repo not found in connection details")

        repo_full_name = f"{owner}/{repo}"
        issue_data = await self._make_request(
            f"repos/{repo_full_name}/issues/{issue_id}"
        )

        if "pull_request" in issue_data:
            raise TrackerResponseError(
                f"Issue {issue_id} is a pull request, not an issue"
            )

        # Use the mapper to convert to Issue object
        return self._parse_github_issue(issue_data)

    async def get_comments(self, issue_id: str) -> List[IssueComment]:
        """Get comments for an issue."""
        owner = self.connection_details.get("owner")
        repo = self.connection_details.get("repo")

        if not owner or not repo:
            raise TrackerResponseError("Owner/repo not found in connection details")

        repo_full_name = f"{owner}/{repo}"
        comments_endpoint = f"repos/{repo_full_name}/issues/{issue_id}/comments"

        try:
            raw_comments_data = await self._make_request(
                comments_endpoint, params={"per_page": GITHUB_DEFAULT_PAGE_SIZE}
            )
            if isinstance(raw_comments_data, dict):
                raw_comments_data = [raw_comments_data]

            comments_data_transformed = []
            for comment_item in raw_comments_data:
                try:
                    comment_created_at = datetime.strptime(
                        comment_item["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                    )
                    comment_updated_at = datetime.strptime(
                        comment_item["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
                    )
                except (ValueError, TypeError):
                    comment_created_at = datetime.now()
                    comment_updated_at = datetime.now()

                comments_data_transformed.append(
                    IssueComment(
                        id=str(comment_item["id"]),
                        body=comment_item.get("body", "") or "",
                        author=IssueUser(
                            id=str(comment_item["user"]["id"]),
                            name=comment_item["user"]["login"],
                            avatar_url=comment_item["user"]["avatar_url"],
                        ),
                        created_at=comment_created_at,
                        updated_at=comment_updated_at,
                        url=comment_item.get("html_url"),
                    )
                )

            return comments_data_transformed
        except TrackerResponseError as e:
            logger.error(
                f"Failed to get comments for issue {repo_full_name}#{issue_id}: {e}"
            )
            return []

    async def create_issue(self, project_key: str, issue_data: IssueCreate) -> Issue:
        """Create a new GitHub issue.

        Args:
            project_key: Project key (ignored for GitHub).
            issue_data: Issue data.

        Returns:
            Created issue.
        """
        owner = self.connection_details.get("owner")
        repo = self.connection_details.get("repo")

        if not owner or not repo:
            raise TrackerResponseError("Owner/repo not found in connection details")

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
        issues_path = f"/repos/{owner}/{repo}/issues"
        created_issue_data = await self._request("POST", issues_path, data=body)

        # Parse and return the issue
        return self._parse_github_issue(created_issue_data)

    async def update_issue(self, issue_id: str, issue_data: IssueUpdate) -> Issue:
        """Update an existing GitHub issue.

        Args:
            issue_id: Issue number in the repository.
            issue_data: Updated issue data.

        Returns:
            Updated issue.
        """
        owner = self.connection_details.get("owner")
        repo = self.connection_details.get("repo")

        if not owner or not repo:
            raise TrackerResponseError("Owner/repo not found in connection details")

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
        issue_path = f"/repos/{owner}/{repo}/issues/{issue_number}"
        updated_issue_data = await self._request("PATCH", issue_path, data=body)

        # Parse and return the issue
        return self._parse_github_issue(updated_issue_data)

    async def add_comment(self, issue_id: str, comment: str) -> IssueComment:
        """Add a comment to a GitHub issue.

        Args:
            issue_id: Issue number in the repository.
            comment: Comment text.

        Returns:
            Created comment.
        """
        owner = self.connection_details.get("owner")
        repo = self.connection_details.get("repo")

        if not owner or not repo:
            raise TrackerResponseError("Owner/repo not found in connection details")

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
        comments_path = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
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
            url=comment_data.get("html_url"),
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

    async def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Get organizations from GitHub.
        """
        organizations = []
        user_data = await self._make_request("user")
        organizations.append(
            {
                "id": "personal",
                "name": f"{user_data['login']}",
                "url": user_data["html_url"],
            }
        )
        orgs_data = await self._make_request(
            "user/orgs", {"per_page": GITHUB_DEFAULT_PAGE_SIZE}
        )
        for org in orgs_data:
            organizations.append(
                {
                    "id": str(org["id"]),
                    "name": org["login"],
                    "url": org["url"]
                    .replace("api.github.com", "github.com")
                    .replace("/orgs/", "/"),
                }
            )
        return organizations

    async def get_projects(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get repositories (projects) for an organization from GitHub.
        """
        params = {
            "per_page": GITHUB_DEFAULT_PAGE_SIZE,
            "sort": "updated",
            "direction": "desc",
        }
        if organization_id == "personal":
            repos_data = await self._make_request("user/repos", params)
        else:
            repos_data = await self._make_request(
                f"orgs/{organization_id}/repos", params
            )
        projects = []
        for repo in repos_data:
            projects.append(
                {
                    "id": str(repo["id"]),
                    "identifier": str(repo["id"]),
                    "name": repo["name"],
                    "description": repo["description"] or "",
                    "url": repo["html_url"],
                    "meta_data": {
                        "full_name": repo["full_name"],
                        "default_branch": repo["default_branch"],
                        "language": repo.get("language"),
                        "created_at": repo["created_at"],
                        "updated_at": repo["pushed_at"],
                        "stars": repo["stargazers_count"],
                    },
                }
            )
        return projects

    async def get_issues(
        self,
        organization_id: str,
        project_id: str,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get issues for a repository from GitHub.
        """
        if "/" in project_id:
            repo_name = project_id
        else:
            try:
                repo_details = await self._make_request(f"repositories/{project_id}")
                repo_name = repo_details["full_name"]
            except TrackerResponseError as e:
                logger.error(
                    f"Failed to get repository details for project_id {project_id}: {e}"
                )
                return []

        params = {
            "state": "all",
            "per_page": GITHUB_DEFAULT_PAGE_SIZE,
            "sort": "updated",
            "direction": "desc",
        }
        if since:
            params["since"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        issues_endpoint = f"repos/{repo_name}/issues"
        try:
            raw_issues_data = await self._make_request(issues_endpoint, params)
        except TrackerResponseError as e:
            logger.error(f"Failed to get issues for repo {repo_name}: {e}")
            return []

        processed_issues = []
        for issue_data in raw_issues_data:
            if "pull_request" in issue_data:
                continue

            issue_number = issue_data["number"]
            comments_data_transformed = []
            comments_endpoint = f"repos/{repo_name}/issues/{issue_number}/comments"
            try:
                raw_comments_data = await self._make_request(
                    comments_endpoint, params={"per_page": GITHUB_DEFAULT_PAGE_SIZE}
                )
                if isinstance(raw_comments_data, dict):
                    raw_comments_data = [raw_comments_data]
                for comment_item in raw_comments_data:
                    # Store as dictionary for transform_comment compatibility
                    comments_data_transformed.append(
                        {
                            "id": comment_item["id"],
                            "body": comment_item.get("body", "") or "",
                            "user": comment_item["user"],
                            "created_at": comment_item["created_at"],
                            "updated_at": comment_item["updated_at"],
                            "html_url": comment_item.get("html_url"),
                        }
                    )
            except TrackerResponseError as e:
                logger.error(
                    f"Failed to get comments for issue {repo_name}#{issue_number}: {e}"
                )

            issue_data["comments"] = comments_data_transformed

            # Parse dependencies from issue body and comments
            dependencies = []
            if issue_data.get("body"):
                dependencies.extend(
                    await self._parse_dependencies(issue_data["body"], repo_name)
                )
            for comment in comments_data_transformed:
                if comment.get("body"):
                    dependencies.extend(
                        await self._parse_dependencies(comment["body"], repo_name)
                    )
            issue_data["dependencies"] = dependencies

            processed_issues.append(issue_data)
        return processed_issues

    async def register_webhook(
        self, db: Session, organization: Organization, webhook_url: str, secret: str
    ) -> bool:
        """
        Register a webhook for the given GitHub organization.
        """
        org_identifier = organization.identifier
        if org_identifier == "personal":
            logger.info(
                f"Skipping webhook registration for personal account '{self.connection_details.get('login', 'N/A')}'."
            )
            return True

        endpoint = f"orgs/{org_identifier}/hooks"
        events = [
            "issues",
            "issue_comment",
            "discussion",
            "project",
            "repository",
            "push",
        ]
        payload = {
            "name": "web",
            "active": True,
            "events": events,
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
                response = await client.post(url, headers=self.headers, json=payload)

            if response.status_code in [HTTP_STATUS_OK, HTTP_STATUS_CREATED]:
                response_data = response.json()
                webhook_id = response_data.get("id")
                if not webhook_id:
                    logger.error(
                        f"Successfully registered webhook for org '{org_identifier}' but could not get webhook ID from response."
                    )
                    return False

                crud_webhook.create(
                    db,
                    obj_in={
                        "organization_id": organization.id,
                        "external_id": str(webhook_id),
                        "url": webhook_url,
                        "secret": secret,
                        "events": events,
                    },
                )
                logger.info(
                    f"Successfully registered and stored webhook {webhook_id} for GitHub org '{org_identifier}'"
                )
                return True
            elif response.status_code == HTTP_STATUS_UNAUTHORIZED:
                logger.error(
                    f"GitHub authentication failed while trying to register webhook for org '{org_identifier}'."
                )
                return False
            elif response.status_code == 403:
                logger.error(
                    f"Permission denied: Unable to register webhook for GitHub org '{org_identifier}'. Check token permissions (needs admin:org_hook)."
                )
                return False
            elif response.status_code == HTTP_STATUS_NOT_FOUND:
                logger.error(
                    f"GitHub organization '{org_identifier}' not found while trying to register webhook."
                )
                return False
            elif response.status_code == HTTP_STATUS_UNPROCESSABLE_ENTITY:
                response_data = response.json()
                if "errors" in response_data and any(
                    "Hook already exists" in e.get("message", "")
                    for e in response_data["errors"]
                ):
                    logger.warning(
                        f"Webhook for GitHub org '{org_identifier}' pointing to {webhook_url} already exists."
                    )
                    return True
                else:
                    logger.error(
                        f"Failed to register webhook for GitHub org '{org_identifier}' (Unprocessable Entity - check config/permissions): {response.text}"
                    )
                    return False
            else:
                logger.error(
                    f"GitHub API error registering webhook for org '{org_identifier}': {response.status_code} - {response.text}"
                )
                return False

        except httpx.RequestError as e:
            logger.error(
                f"GitHub connection error while registering webhook for org '{org_identifier}': {e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error registering webhook for GitHub org '{org_identifier}': {e}",
                exc_info=True,
            )
            return False

    async def unregister_webhook(self, db: Session, webhook: Webhook) -> bool:
        """
        Unregister a webhook for the given GitHub organization.

        Args:
            db: The database session.
            webhook: The webhook to unregister.

        Returns:
            True if unregistration was successful, False otherwise.
        """
        org_identifier = None
        if webhook.organization:
            org_identifier = webhook.organization.identifier
        elif webhook.project:
            org_identifier = webhook.project.organization.identifier
        webhook_id = webhook.external_id

        if not org_identifier or org_identifier == "personal":
            logger.info(f"Skipping webhook unregistration for org '{org_identifier}'.")
            return True

        if webhook.project:
            repo_full_name = webhook.project.slug
            endpoint = f"repos/{repo_full_name}/hooks/{webhook_id}"
        else:
            endpoint = f"orgs/{org_identifier}/hooks/{webhook_id}"
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.API_BASE_URL}/{endpoint.lstrip('/')}"
                response = await client.delete(url, headers=self.headers)

            if response.status_code == HTTP_STATUS_NO_CONTENT:
                logger.info(
                    f"Successfully unregistered webhook {webhook_id} for GitHub org '{org_identifier}'."
                )
                crud_webhook.remove(db, id=webhook.id)
                return True
            elif response.status_code == HTTP_STATUS_NOT_FOUND:
                logger.warning(
                    f"Webhook {webhook_id} for GitHub org '{org_identifier}' not found during delete attempt. Assuming already unregistered."
                )
                crud_webhook.remove(db, id=webhook.id)
                return True
            else:
                logger.error(
                    f"Failed to unregister webhook {webhook_id} for GitHub org '{org_identifier}': {response.status_code} - {response.text}"
                )
                return False
        except httpx.RequestError as e:
            logger.error(
                f"GitHub connection error while unregistering webhook for org '{org_identifier}': {e}",
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error unregistering webhook for GitHub org '{org_identifier}': {e}",
                exc_info=True,
            )
            return False

    async def unregister_all_webhooks(
        self, db: Session, webhook_url_pattern: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Unregister all webhooks for all organizations managed by this tracker instance.
        Args:
            db: The database session.
        """
        results = {"unregistered": 0, "failed": 0, "not_found": 0}
        logger.info(
            f"Starting to unregister all webhooks for tracker {self.tracker_id}."
        )
        try:
            organizations = crud_organization.get_multi(db, tracker_id=self.tracker_id)
            organization_ids = [org.id for org in organizations]
            project_ids = []
            for org_id in organization_ids:
                projects = crud_project.get_for_organization(db, organization_id=org_id)
                project_ids.extend([proj.id for proj in projects])

            webhooks_to_delete = (
                db.query(Webhook)
                .filter(
                    (Webhook.organization_id.in_(organization_ids))
                    | (Webhook.project_id.in_(project_ids))
                )
                .all()
            )

            if not webhooks_to_delete:
                logger.info("No webhooks found in the database for this tracker.")
                return results

            for webhook in webhooks_to_delete:
                if await self.unregister_webhook(db=db, webhook=webhook):
                    results["unregistered"] += 1
                else:
                    results["failed"] += 1

        except Exception as e:
            logger.error(
                f"An unexpected error occurred during webhook unregistration for tracker {self.tracker_id}: {e}",
                exc_info=True,
            )
            results["failed"] += 1
        logger.info(
            f"Finished unregistering all webhooks for tracker {self.tracker_id}."
        )
        logger.info(f"GitHub unregister_all_webhooks summary: {results}")
        return results

    async def cleanup_stale_webhooks(
        self, preloop_url: str, cleanup_projects: bool = False
    ) -> dict:
        """
        Deletes stale webhooks pointing to the given Preloop URL.

        By default, this method cleans up organization-level webhooks.
        If `cleanup_projects` is True, it cleans up repository-level webhooks instead.

        Args:
            preloop_url: The base URL of the Preloop instance.
            cleanup_projects: If True, clean up repository-level webhooks. Defaults to False.

        Returns:
            A dictionary summarizing the actions taken, e.g., `{"unregistered": count, "failed": count}`.
        """
        results = {"unregistered": 0, "failed": 0}
        logger.info(
            f"Starting cleanup of stale webhooks for URL: {preloop_url} (cleanup_projects={cleanup_projects})"
        )

        if cleanup_projects:
            await self._cleanup_project_webhooks(preloop_url, results)
        else:
            await self._cleanup_organization_webhooks(preloop_url, results)

        logger.info(f"Webhook cleanup summary: {results}")
        return results

    async def _cleanup_organization_webhooks(
        self, preloop_url: str, results: dict
    ) -> None:
        """Helper to clean up organization-level webhooks."""
        try:
            organizations = await self.get_organizations()
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Failed to retrieve organizations: {e}")
            return

        for org in organizations:
            org_login = org.get("name")
            if not org_login or org.get("id") == "personal":
                continue

            logger.info(f"Checking webhooks for organization: {org_login}")
            try:
                hooks = await self._make_request(f"orgs/{org_login}/hooks")
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(f"Failed to list webhooks for {org_login}: {e}")
                results["failed"] += 1
                continue

            for hook in hooks:
                await self._process_hook(
                    hook, preloop_url, results, f"orgs/{org_login}/hooks"
                )

    async def _cleanup_project_webhooks(self, preloop_url: str, results: dict) -> None:
        """Helper to clean up repository-level webhooks."""
        try:
            organizations = await self.get_organizations()
        except (TrackerConnectionError, TrackerResponseError) as e:
            logger.error(f"Failed to retrieve organizations: {e}")
            return

        for org in organizations:
            org_id = org.get("id")
            if not org_id:
                continue

            try:
                projects = await self.get_projects(org_id)
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(
                    f"Failed to retrieve projects for org {org.get('name')}: {e}"
                )
                continue

            for repo in projects:
                repo_full_name = repo.get("meta_data", {}).get("full_name")
                if not repo_full_name:
                    continue

                logger.info(f"Checking webhooks for repository: {repo_full_name}")
                try:
                    hooks = await self._make_request(f"repos/{repo_full_name}/hooks")
                except (TrackerConnectionError, TrackerResponseError) as e:
                    logger.error(f"Failed to list webhooks for {repo_full_name}: {e}")
                    results["failed"] += 1
                    continue

                for hook in hooks:
                    await self._process_hook(
                        hook, preloop_url, results, f"repos/{repo_full_name}/hooks"
                    )

    async def _process_hook(
        self, hook: dict, preloop_url: str, results: dict, base_endpoint: str
    ) -> None:
        """
        Processes a single webhook for cleanup.

        Stale webhooks are webhooks that:
        1. Have a URL starting with preloop_url (they point to our Preloop instance)
        2. Are NOT registered in our database (they were created but not tracked, or orphaned)

        This method checks if the webhook is stale and deletes it if so.
        """
        hook_id = hook.get("id")
        hook_config = hook.get("config", {})
        hook_url = hook_config.get("url")

        if not all([hook_id, hook_url]):
            return

        # Only consider webhooks pointing to our Preloop instance
        if not hook_url.startswith(preloop_url):
            # This webhook points to a different service, ignore it
            return

        # Check if this webhook exists in our database
        from preloop.models.crud import crud_webhook
        from preloop.models.db.session import get_db_session

        db = next(get_db_session())
        try:
            # Look up webhook by external_id (the GitHub webhook ID)
            existing_webhook = crud_webhook.get_by_external_id(
                db, external_id=str(hook_id), tracker_id=self.tracker_id
            )

            if existing_webhook:
                # Webhook is in our database, keep it
                logger.debug(
                    f"Webhook {hook_id} in {base_endpoint} is registered in database, keeping it."
                )
                return

            # Webhook points to our Preloop but is NOT in database - it's stale
            logger.info(
                f"Found stale webhook {hook_id} in {base_endpoint} pointing to {hook_url}. "
                f"This webhook is not in our database. Deleting..."
            )
            try:
                delete_endpoint = f"{base_endpoint}/{hook_id}"
                if await self._make_request_delete(delete_endpoint):
                    logger.info(
                        f"Successfully deleted stale webhook {hook_id} from {base_endpoint}."
                    )
                    results["unregistered"] += 1
                else:
                    logger.error(
                        f"Failed to delete webhook {hook_id} from {base_endpoint}."
                    )
                    results["failed"] += 1
            except (TrackerConnectionError, TrackerResponseError) as e:
                logger.error(
                    f"An error occurred while deleting webhook {hook_id} from {base_endpoint}: {e}"
                )
                results["failed"] += 1
        finally:
            db.close()

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

        if not webhook.project:
            return False
        repo_full_name = webhook.project.slug
        endpoint = f"repos/{repo_full_name}/hooks/{webhook.external_id}"
        try:
            await self._make_request(endpoint)
            return True
        except TrackerResponseError as e:
            if "Not Found" in str(e):
                return False
            raise

    async def get_webhooks(self, organization_id: str) -> List[Dict[str, Any]]:
        """
        Get all webhooks for a specific organization's repositories.
        """
        all_webhooks = []
        repos = await self.get_projects(organization_id)
        for repo in repos:
            repo_full_name = repo["meta_data"]["full_name"]
            try:
                repo_webhooks = await self._make_request(
                    f"repos/{repo_full_name}/hooks",
                    params={"per_page": GITHUB_DEFAULT_PAGE_SIZE},
                )
                all_webhooks.extend(repo_webhooks)
            except TrackerResponseError as e:
                logger.error(f"Failed to get webhooks for repo {repo_full_name}: {e}")
        return all_webhooks

    async def delete_webhook(self, webhook: Dict[str, Any]) -> bool:
        """
        Delete a webhook from the tracker.

        Args:
            webhook: The webhook to delete.

        Returns:
            Whether the webhook was deleted successfully.
        """
        webhook_id = webhook.get("id")
        if not webhook_id:
            return False

        # The webhook response doesn't contain the org identifier, so we have to parse it from the url
        url = webhook.get("url")
        if not url:
            return False

        org_identifier = url.split("/")[-2]
        endpoint = f"orgs/{org_identifier}/hooks/{webhook_id}"
        try:
            return await self._make_request_delete(endpoint)
        except TrackerResponseError as e:
            logger.error(f"Failed to delete webhook {webhook_id}: {e}")
            return False

    async def is_webhook_registered_for_project(
        self, project: "Project", webhook_url: str
    ) -> bool:
        """
        Check if a webhook is registered for a project.

        Args:
            project: The project to check.
            webhook_url: The URL of the webhook.

        Returns:
            Whether the webhook is registered.
        """
        endpoint = f"repos/{project.slug}/hooks"
        try:
            hooks = await self._make_request(endpoint)
            for hook in hooks:
                if hook.get("config", {}).get("url") == webhook_url:
                    return True
            return False
        except TrackerResponseError:
            return False

    def transform_organization(self, org_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transforms a GitHub organization into the common format."""
        return {
            "identifier": str(org_data["id"]),
            "name": org_data["name"],
            "meta_data": {"source": "github", "url": org_data.get("url")},
        }

    def transform_project(
        self, proj_data: Dict[str, Any], organization_id: str
    ) -> Dict[str, Any]:
        """Transforms a GitHub repository into the common format."""
        return {
            "identifier": str(proj_data["id"]),
            "name": proj_data["name"],
            "description": proj_data.get("description"),
            "organization_id": organization_id,
            "slug": proj_data.get("meta_data", {}).get("full_name", ""),
            "meta_data": proj_data.get("meta_data"),
        }

    def transform_issue(
        self, issue_data: Dict[str, Any], project: "Project"
    ) -> Dict[str, Any]:
        """Transforms a GitHub issue into the common format."""
        return {
            "external_id": str(issue_data["id"]),
            "key": f"{project.slug}#{issue_data['number']}",
            "title": issue_data["title"],
            "description": issue_data.get("body"),
            "status": issue_data["state"],
            "created_at": datetime.strptime(
                issue_data["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ),
            "updated_at": datetime.strptime(
                issue_data["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
            ),
            "project_id": project.id,
            "tracker_id": self.tracker_id,
            "comments": issue_data.get("comments", []),
        }

    def transform_comment(
        self, comment_data: Dict[str, Any], issue_id: str
    ) -> Dict[str, Any]:
        """Transforms a GitHub comment into the common format."""
        return {
            "external_id": str(comment_data["id"]),
            "body": comment_data.get("body"),
            "created_at": datetime.strptime(
                comment_data["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ),
            "updated_at": datetime.strptime(
                comment_data["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
            ),
            "issue_id": issue_id,
            "tracker_id": self.tracker_id,
        }

    async def is_webhook_registered_for_organization(
        self, organization: "Organization", webhook_url: str
    ) -> bool:
        """
        Check if a webhook is registered for an organization.

        Args:
            organization: The organization to check.
            webhook_url: The URL of the webhook.

        Returns:
            Whether the webhook is registered.
        """
        endpoint = f"orgs/{organization.identifier}/hooks"
        try:
            hooks = await self._make_request(endpoint)
            for hook in hooks:
                if hook.get("config", {}).get("url") == webhook_url:
                    return True
            return False
        except TrackerResponseError:
            return False

    async def get_pull_request(self, pr_identifier: str) -> Dict[str, Any]:
        """
        Get details of a GitHub pull request.

        Args:
            pr_identifier: PR identifier (number, slug, or URL)

        Returns:
            Dict with PR details including title, description, state, comments, and changes
        """
        owner = self.connection_details.get("owner")
        repo = self.connection_details.get("repo")

        if not owner or not repo:
            raise TrackerResponseError("Owner/repo not found in connection details")

        # Extract PR number from various formats
        pr_number = pr_identifier
        if "/" in pr_identifier:
            # Handle formats like "owner/repo#123" or "owner/repo/pull/123"
            parts = pr_identifier.split("/")
            pr_number = parts[-1]
        if "#" in pr_number:
            pr_number = pr_number.split("#")[-1]

        try:
            # Get PR details
            pr_path = f"/repos/{owner}/{repo}/pulls/{pr_number}"
            pr_data = await self._request("GET", pr_path)

            # Get PR comments (review comments + issue comments)
            comments_path = f"/repos/{owner}/{repo}/pulls/{pr_number}/comments"
            review_comments = await self._request("GET", comments_path)

            issue_comments_path = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
            issue_comments = await self._request("GET", issue_comments_path)

            # Combine all comments
            all_comments = []
            for comment in review_comments:
                all_comments.append(
                    {
                        "id": str(comment["id"]),
                        "author": comment["user"]["login"],
                        "body": comment["body"],
                        "created_at": comment["created_at"],
                        "type": "review_comment",
                        "path": comment.get("path"),
                        "position": comment.get("position"),
                    }
                )

            for comment in issue_comments:
                all_comments.append(
                    {
                        "id": str(comment["id"]),
                        "author": comment["user"]["login"],
                        "body": comment["body"],
                        "created_at": comment["created_at"],
                        "type": "issue_comment",
                    }
                )

            # Get PR files/changes
            files_path = f"/repos/{owner}/{repo}/pulls/{pr_number}/files"
            files = await self._request("GET", files_path)

            changes = {
                "files_changed": len(files),
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0),
                "changed_files": [
                    {
                        "filename": f["filename"],
                        "status": f["status"],
                        "additions": f["additions"],
                        "deletions": f["deletions"],
                        "patch": f.get("patch", ""),
                    }
                    for f in files
                ],
            }

            return {
                "id": str(pr_data["id"]),
                "number": pr_data["number"],
                "title": pr_data["title"],
                "description": pr_data.get("body", ""),
                "state": pr_data["state"],
                "author": pr_data["user"]["login"],
                "assignees": [a["login"] for a in pr_data.get("assignees", [])],
                "reviewers": [
                    r["login"] for r in pr_data.get("requested_reviewers", [])
                ],
                "labels": [label["name"] for label in pr_data.get("labels", [])],
                "url": pr_data["html_url"],
                "source_branch": pr_data["head"]["ref"],
                "target_branch": pr_data["base"]["ref"],
                "created_at": pr_data["created_at"],
                "updated_at": pr_data["updated_at"],
                "merged_at": pr_data.get("merged_at"),
                "is_draft": pr_data.get("draft", False),
                "comments": all_comments,
                "changes": changes,
            }

        except Exception as e:
            logger.error(f"Error getting pull request {pr_number}: {e}")
            raise TrackerResponseError(f"Failed to get pull request: {e}")

    async def update_pull_request(
        self,
        pr_identifier: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        state: Optional[str] = None,
        assignees: Optional[List[str]] = None,
        reviewers: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
        draft: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update a GitHub pull request.

        Args:
            pr_identifier: PR identifier (number, slug, or URL)
            title: New PR title
            description: New PR description
            state: New state ("open" or "closed")
            assignees: List of assignee usernames
            reviewers: List of reviewer usernames
            labels: List of label names
            draft: Whether to mark as draft

        Returns:
            Dict with updated PR details
        """
        owner = self.connection_details.get("owner")
        repo = self.connection_details.get("repo")

        if not owner or not repo:
            raise TrackerResponseError("Owner/repo not found in connection details")

        # Extract PR number from various formats
        pr_number = pr_identifier
        if "/" in pr_identifier:
            parts = pr_identifier.split("/")
            pr_number = parts[-1]
        if "#" in pr_number:
            pr_number = pr_number.split("#")[-1]

        try:
            # Build update payload
            update_data = {}
            if title is not None:
                update_data["title"] = title
            if description is not None:
                update_data["body"] = description
            if state is not None:
                update_data["state"] = state
            if draft is not None:
                update_data["draft"] = draft

            # Update PR
            pr_path = f"/repos/{owner}/{repo}/pulls/{pr_number}"
            pr_data = await self._request("PATCH", pr_path, data=update_data)

            # Update assignees if provided
            if assignees is not None:
                assignees_path = f"/repos/{owner}/{repo}/issues/{pr_number}/assignees"
                await self._request(
                    "POST", assignees_path, data={"assignees": assignees}
                )

            # Update reviewers if provided
            if reviewers is not None:
                reviewers_path = (
                    f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers"
                )
                await self._request(
                    "POST", reviewers_path, data={"reviewers": reviewers}
                )

            # Update labels if provided
            if labels is not None:
                labels_path = f"/repos/{owner}/{repo}/issues/{pr_number}/labels"
                await self._request("PUT", labels_path, data={"labels": labels})

            # Return updated PR data
            return {
                "id": str(pr_data["id"]),
                "number": pr_data["number"],
                "title": pr_data["title"],
                "description": pr_data.get("body", ""),
                "state": pr_data["state"],
                "url": pr_data["html_url"],
                "is_draft": pr_data.get("draft", False),
            }

        except Exception as e:
            logger.error(f"Error updating pull request {pr_number}: {e}")
            raise TrackerResponseError(f"Failed to update pull request: {e}")
