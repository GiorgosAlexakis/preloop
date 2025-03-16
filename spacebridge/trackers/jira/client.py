"""Jira client implementation for SpaceBridge."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

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


class JiraCredentials(BaseModel):
    """Credentials for Jira API authentication."""

    token: str = Field(..., description="Jira API token or password")
    username: str = Field(..., description="Jira username or email")
    url: str = Field(..., description="Jira instance URL (e.g., https://your-domain.atlassian.net)")


class JiraClient(TrackerInterface):
    """Client for interacting with Jira's API."""

    def __init__(
        self,
        credentials: JiraCredentials,
        timeout: int = 10,
    ):
        """Initialize the Jira client.

        Args:
            credentials: Jira API credentials
            timeout: Request timeout in seconds
        """
        self.credentials = credentials
        self.timeout = timeout
        self.base_url = credentials.url.rstrip("/")
        self.api_url = f"{self.base_url}/rest/api/3"

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated request to the Jira API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (without base URL)
            params: URL parameters
            json_data: JSON body data
            headers: Additional headers

        Returns:
            Response JSON data

        Raises:
            ValueError: If the request fails
        """
        import aiohttp
        import base64
        import json

        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        auth_str = f"{self.credentials.username}:{self.credentials.token}"
        auth_header = f"Basic {base64.b64encode(auth_str.encode()).decode()}"

        default_headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if headers:
            default_headers.update(headers)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=default_headers,
                    timeout=self.timeout,
                ) as response:
                    response_text = await response.text()
                    if response.status >= 400:
                        logger.error(
                            f"Jira API error: {response.status} - {response_text}"
                        )
                        raise ValueError(
                            f"Jira API error: {response.status} - {response_text}"
                        )

                    if response_text:
                        return json.loads(response_text)
                    return {}
        except aiohttp.ClientError as e:
            logger.exception(f"Jira API request failed: {e}")
            raise ValueError(f"Jira API request failed: {e}")

    def _map_jira_status(self, jira_status: Dict[str, Any]) -> IssueStatus:
        """Map Jira status to SpaceBridge status.

        Args:
            jira_status: Jira status object

        Returns:
            Mapped status
        """
        status_id = jira_status["id"]
        status_name = jira_status["name"]
        
        # Map status category
        category_key = jira_status.get("statusCategory", {}).get("key", "")
        category_map = {
            "new": "todo",
            "indeterminate": "in_progress",
            "done": "done",
        }
        category = category_map.get(category_key, "other")
        
        return IssueStatus(id=status_id, name=status_name, category=category)

    def _map_jira_priority(self, jira_priority: Dict[str, Any]) -> IssuePriority:
        """Map Jira priority to SpaceBridge priority.

        Args:
            jira_priority: Jira priority object

        Returns:
            Mapped priority
        """
        priority_id = jira_priority["id"]
        priority_name = jira_priority["name"]
        
        # Extract numeric level from Jira priority
        # Typically higher number = higher priority in Jira
        level_map = {
            "Highest": 5,
            "High": 4,
            "Medium": 3,
            "Low": 2,
            "Lowest": 1,
        }
        level = level_map.get(priority_name, 3)  # Default to medium priority
        
        return IssuePriority(id=priority_id, name=priority_name, level=level)

    def _map_jira_user(self, jira_user: Dict[str, Any]) -> IssueUser:
        """Map Jira user to SpaceBridge user.

        Args:
            jira_user: Jira user object

        Returns:
            Mapped user
        """
        user_id = jira_user.get("accountId", "")
        user_name = jira_user.get("displayName", "")
        user_email = jira_user.get("emailAddress")
        user_avatar = jira_user.get("avatarUrls", {}).get("48x48")
        
        return IssueUser(
            id=user_id,
            name=user_name,
            email=user_email,
            avatar_url=user_avatar,
        )

    def _parse_jira_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse Jira datetime string to Python datetime.

        Args:
            date_str: Jira datetime string

        Returns:
            Parsed datetime or None
        """
        if not date_str:
            return None
        
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse Jira datetime: {date_str}")
            return None

    def _map_jira_issue(self, jira_issue: Dict[str, Any], project_key: str) -> Issue:
        """Map Jira issue to SpaceBridge issue.

        Args:
            jira_issue: Jira issue object
            project_key: Project key

        Returns:
            Mapped issue
        """
        issue_id = jira_issue["id"]
        issue_key = jira_issue["key"]
        fields = jira_issue["fields"]
        
        # Core issue data
        title = fields.get("summary", "")
        description = fields.get("description", "")
        
        # Status and priority
        status = self._map_jira_status(fields.get("status", {}))
        priority = None
        if "priority" in fields and fields["priority"]:
            priority = self._map_jira_priority(fields["priority"])
        
        # Timeline
        created_at = self._parse_jira_datetime(fields.get("created")) or datetime.now()
        updated_at = self._parse_jira_datetime(fields.get("updated")) or created_at
        resolved_at = self._parse_jira_datetime(fields.get("resolutiondate"))
        
        # People
        reporter = None
        if "reporter" in fields and fields["reporter"]:
            reporter = self._map_jira_user(fields["reporter"])
        
        assignee = None
        if "assignee" in fields and fields["assignee"]:
            assignee = self._map_jira_user(fields["assignee"])
        
        # Labels and components
        labels = fields.get("labels", [])
        components = [c["name"] for c in fields.get("components", [])]
        
        # Issue relations
        parent = None
        if "parent" in fields:
            parent_data = fields["parent"]
            parent = IssueRelation(
                relation_type="parent",
                issue_id=parent_data["id"],
                issue_key=parent_data["key"],
                summary=parent_data["fields"].get("summary"),
            )
        
        relations = []
        if "issuelinks" in fields:
            for link in fields["issuelinks"]:
                relation_type = link.get("type", {}).get("name", "relates_to").lower()
                
                # Jira has inward/outward relations
                if "inwardIssue" in link:
                    related = link["inwardIssue"]
                    relations.append(
                        IssueRelation(
                            relation_type=relation_type,
                            issue_id=related["id"],
                            issue_key=related["key"],
                            summary=related["fields"].get("summary"),
                        )
                    )
                elif "outwardIssue" in link:
                    related = link["outwardIssue"]
                    relations.append(
                        IssueRelation(
                            relation_type=relation_type,
                            issue_id=related["id"],
                            issue_key=related["key"],
                            summary=related["fields"].get("summary"),
                        )
                    )
        
        # Comments
        comments = []
        if "comment" in fields and "comments" in fields["comment"]:
            for comment_data in fields["comment"]["comments"]:
                comment_id = comment_data["id"]
                comment_body = comment_data.get("body", "")
                comment_created = self._parse_jira_datetime(comment_data.get("created")) or datetime.now()
                comment_updated = self._parse_jira_datetime(comment_data.get("updated"))
                comment_author = self._map_jira_user(comment_data.get("author", {}))
                
                comments.append(
                    IssueComment(
                        id=comment_id,
                        body=comment_body,
                        created_at=comment_created,
                        updated_at=comment_updated,
                        author=comment_author,
                    )
                )
        
        # URLs
        url = f"{self.base_url}/browse/{issue_key}"
        api_url = f"{self.api_url}/issue/{issue_id}"
        
        # Custom fields
        custom_fields = {}
        for field_key, field_value in fields.items():
            if field_key.startswith("customfield_") and field_value is not None:
                custom_fields[field_key] = field_value
        
        return Issue(
            id=issue_id,
            key=issue_key,
            title=title,
            description=description,
            status=status,
            priority=priority,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            reporter=reporter,
            assignee=assignee,
            labels=labels,
            components=components,
            parent=parent,
            relations=relations,
            comments=comments,
            url=url,
            api_url=api_url,
            tracker_type="jira",
            project_key=project_key,
            custom_fields=custom_fields,
        )

    async def test_connection(self) -> TrackerConnection:
        """Test the connection to Jira.
        
        Returns:
            Connection status.
        """
        try:
            # Get server info
            response = await self._make_request("GET", "serverInfo")
            
            # Get rate limiting info if available
            rate_limit = None
            
            return TrackerConnection(
                connected=True,
                message=f"Successfully connected to Jira {response.get('version', 'unknown version')}",
                rate_limit=rate_limit,
                server_info={
                    "baseUrl": response.get("baseUrl"),
                    "version": response.get("version"),
                    "buildNumber": response.get("buildNumber"),
                    "serverTitle": response.get("serverTitle"),
                },
            )
        except Exception as e:
            logger.exception(f"Failed to connect to Jira: {e}")
            return TrackerConnection(
                connected=False,
                message=f"Failed to connect to Jira: {str(e)}",
                rate_limit=None,
                server_info=None,
            )
    
    async def get_project_metadata(self, project_key: str) -> ProjectMetadata:
        """Get metadata about a Jira project.
        
        Args:
            project_key: Project key in Jira.
            
        Returns:
            Project metadata.
        """
        # Get project details
        project_data = await self._make_request("GET", f"project/{project_key}")
        
        # Get available statuses
        statuses_data = await self._make_request(
            "GET", f"project/{project_key}/statuses"
        )
        
        statuses = []
        for issue_type in statuses_data:
            for status in issue_type.get("statuses", []):
                status_obj = self._map_jira_status(status)
                if status_obj not in statuses:  # Avoid duplicates
                    statuses.append(status_obj)
        
        # Get available priorities
        priorities_data = await self._make_request("GET", "priority")
        priorities = [self._map_jira_priority(p) for p in priorities_data]
        
        return ProjectMetadata(
            key=project_key,
            name=project_data.get("name", project_key),
            description=project_data.get("description"),
            statuses=statuses,
            priorities=priorities,
            url=f"{self.base_url}/projects/{project_key}",
        )
    
    async def search_issues(
        self, project_key: str, filter_params: IssueFilter, limit: int = 10, offset: int = 0
    ) -> Tuple[List[Issue], int]:
        """Search for issues in a Jira project.
        
        Args:
            project_key: Project key in Jira.
            filter_params: Filter parameters.
            limit: Maximum number of issues to return.
            offset: Pagination offset.
            
        Returns:
            Tuple of (list of issues, total count).
        """
        # Build JQL query
        jql_parts = [f"project = '{project_key}'"]
        
        if filter_params.query:
            jql_parts.append(f"(summary ~ '{filter_params.query}' OR description ~ '{filter_params.query}')")
        
        if filter_params.status:
            status_clause = " OR ".join([f"status = '{s}'" for s in filter_params.status])
            jql_parts.append(f"({status_clause})")
        
        if filter_params.labels:
            label_clause = " OR ".join([f"labels = '{l}'" for l in filter_params.labels])
            jql_parts.append(f"({label_clause})")
        
        if filter_params.created_after:
            jql_parts.append(
                f"created >= '{filter_params.created_after.strftime('%Y-%m-%d')}'"
            )
        
        if filter_params.created_before:
            jql_parts.append(
                f"created <= '{filter_params.created_before.strftime('%Y-%m-%d')}'"
            )
        
        if filter_params.updated_after:
            jql_parts.append(
                f"updated >= '{filter_params.updated_after.strftime('%Y-%m-%d')}'"
            )
        
        if filter_params.updated_before:
            jql_parts.append(
                f"updated <= '{filter_params.updated_before.strftime('%Y-%m-%d')}'"
            )
        
        if filter_params.assigned_to:
            jql_parts.append(f"assignee = '{filter_params.assigned_to}'")
        
        if filter_params.reported_by:
            jql_parts.append(f"reporter = '{filter_params.reported_by}'")
        
        jql_query = " AND ".join(jql_parts)
        
        # Add sorting
        if filter_params.sort_by:
            direction = "DESC" if filter_params.sort_direction == "desc" else "ASC"
            jql_query += f" ORDER BY {filter_params.sort_by} {direction}"
        else:
            jql_query += " ORDER BY updated DESC"
        
        # Fields to retrieve
        fields = [
            "summary", "description", "status", "priority", "created", "updated",
            "resolutiondate", "reporter", "assignee", "labels", "components",
            "parent", "issuelinks", "comment"
        ]
        
        # Make search request
        search_data = await self._make_request(
            "POST",
            "search",
            json_data={
                "jql": jql_query,
                "startAt": offset,
                "maxResults": limit,
                "fields": fields,
                "expand": ["names", "renderedFields"],
            },
        )
        
        # Map results
        total = search_data.get("total", 0)
        issues = [self._map_jira_issue(issue, project_key) for issue in search_data.get("issues", [])]
        
        return issues, total
    
    async def get_issue(self, issue_id: str) -> Issue:
        """Get a specific Jira issue by ID.
        
        Args:
            issue_id: Issue ID in Jira. Can be the numeric ID or the issue key (e.g., PROJECT-123).
            
        Returns:
            Issue details.
        """
        # Fields to retrieve
        fields = [
            "summary", "description", "status", "priority", "created", "updated",
            "resolutiondate", "reporter", "assignee", "labels", "components",
            "parent", "issuelinks", "comment", "project"
        ]
        
        # Get issue details
        issue_data = await self._make_request(
            "GET",
            f"issue/{issue_id}",
            params={"fields": ",".join(fields), "expand": "renderedFields,names"},
        )
        
        # Extract project key
        project_key = issue_data.get("fields", {}).get("project", {}).get("key", "")
        
        return self._map_jira_issue(issue_data, project_key)
    
    async def create_issue(self, project_key: str, issue_data: IssueCreate) -> Issue:
        """Create a new Jira issue.
        
        Args:
            project_key: Project key in Jira.
            issue_data: Issue data.
            
        Returns:
            Created issue.
        """
        # Map SpaceBridge issue data to Jira fields
        fields = {
            "project": {"key": project_key},
            "summary": issue_data.title,
        }
        
        # Only add non-empty fields
        if issue_data.description:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": issue_data.description}],
                    }
                ],
            }
        
        # Set issue type (default to Task if not specified)
        fields["issuetype"] = {"name": "Task"}
        
        if issue_data.status:
            # Note: Jira doesn't allow setting status directly on creation
            # Status transitions would need to be handled post-creation
            pass
        
        if issue_data.priority:
            fields["priority"] = {"name": issue_data.priority}
        
        if issue_data.assignee:
            fields["assignee"] = {"name": issue_data.assignee}
        
        if issue_data.labels:
            fields["labels"] = issue_data.labels
        
        if issue_data.components:
            fields["components"] = [{"name": c} for c in issue_data.components]
        
        if issue_data.parent:
            fields["parent"] = {"key": issue_data.parent}
        
        # Add custom fields if specified
        if issue_data.custom_fields:
            for field_key, field_value in issue_data.custom_fields.items():
                fields[field_key] = field_value
        
        # Create the issue
        creation_data = await self._make_request(
            "POST",
            "issue",
            json_data={"fields": fields},
        )
        
        # Get the created issue
        issue_id = creation_data.get("id")
        if not issue_id:
            raise ValueError("Failed to create Jira issue: no issue ID returned")
        
        return await self.get_issue(issue_id)
    
    async def update_issue(self, issue_id: str, issue_data: IssueUpdate) -> Issue:
        """Update an existing Jira issue.
        
        Args:
            issue_id: Issue ID in Jira. Can be the numeric ID or the issue key.
            issue_data: Updated issue data.
            
        Returns:
            Updated issue.
        """
        # Map SpaceBridge issue data to Jira fields
        fields = {}
        
        if issue_data.title is not None:
            fields["summary"] = issue_data.title
        
        if issue_data.description is not None:
            fields["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": issue_data.description}],
                    }
                ],
            }
        
        if issue_data.priority is not None:
            fields["priority"] = {"name": issue_data.priority}
        
        if issue_data.assignee is not None:
            if issue_data.assignee == "":
                # Unassign the issue
                fields["assignee"] = None
            else:
                fields["assignee"] = {"name": issue_data.assignee}
        
        if issue_data.labels is not None:
            fields["labels"] = issue_data.labels
        
        if issue_data.components is not None:
            fields["components"] = [{"name": c} for c in issue_data.components]
        
        # Add custom fields if specified
        if issue_data.custom_fields:
            for field_key, field_value in issue_data.custom_fields.items():
                fields[field_key] = field_value
        
        # Update the issue
        await self._make_request(
            "PUT",
            f"issue/{issue_id}",
            json_data={"fields": fields},
        )
        
        # Handle status transitions separately if needed
        if issue_data.status is not None:
            # Get available transitions
            transitions = await self._make_request(
                "GET", f"issue/{issue_id}/transitions"
            )
            
            # Find matching transition
            for transition in transitions.get("transitions", []):
                if transition.get("to", {}).get("name", "") == issue_data.status:
                    # Execute the transition
                    await self._make_request(
                        "POST",
                        f"issue/{issue_id}/transitions",
                        json_data={"transition": {"id": transition["id"]}},
                    )
                    break
        
        # Get the updated issue
        return await self.get_issue(issue_id)
    
    async def add_comment(self, issue_id: str, comment: str) -> IssueComment:
        """Add a comment to a Jira issue.
        
        Args:
            issue_id: Issue ID in Jira. Can be the numeric ID or the issue key.
            comment: Comment text.
            
        Returns:
            Created comment.
        """
        # Format comment in Jira Atlassian Document Format
        comment_body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}],
                    }
                ],
            }
        }
        
        # Add the comment
        comment_data = await self._make_request(
            "POST",
            f"issue/{issue_id}/comment",
            json_data=comment_body,
        )
        
        # Extract comment details
        comment_id = comment_data.get("id", "")
        comment_body = comment_data.get("body", "")
        
        if isinstance(comment_body, dict):
            # Extract text from Atlassian Document Format
            # Simplified extraction - might need more complex parsing for richly formatted content
            comment_body = comment_data.get("body", {}).get("content", [{}])[0].get("content", [{}])[0].get("text", "")
        
        comment_created = self._parse_jira_datetime(comment_data.get("created")) or datetime.now()
        comment_updated = self._parse_jira_datetime(comment_data.get("updated"))
        
        # Map the author
        author = self._map_jira_user(comment_data.get("author", {}))
        
        return IssueComment(
            id=comment_id,
            body=comment_body,
            created_at=comment_created,
            updated_at=comment_updated,
            author=author,
        )
    
    async def add_relation(
        self, issue_id: str, related_issue_id: str, relation_type: str
    ) -> bool:
        """Add a relation between Jira issues.
        
        Args:
            issue_id: Source issue ID.
            related_issue_id: Target issue ID.
            relation_type: Relation type.
            
        Returns:
            Whether the operation was successful.
        """
        # Map SpaceBridge relation type to Jira link type
        relation_map = {
            "blocks": "Blocks",
            "blocked_by": "Blocked by",
            "relates_to": "Relates",
            "duplicates": "Duplicates",
            "duplicated_by": "Duplicated by",
            "depends_on": "Depends",
            "dependent": "Dependent",
        }
        
        jira_relation_type = relation_map.get(relation_type, "Relates")
        
        try:
            # Create the link
            await self._make_request(
                "POST",
                "issueLink",
                json_data={
                    "type": {"name": jira_relation_type},
                    "inwardIssue": {"key": issue_id},
                    "outwardIssue": {"key": related_issue_id},
                },
            )
            return True
        except Exception as e:
            logger.exception(f"Failed to add issue relation: {e}")
            return False