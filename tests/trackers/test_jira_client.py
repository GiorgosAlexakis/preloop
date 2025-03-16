"""Tests for the Jira client integration."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from spacebridge.trackers.jira.client import JiraClient, JiraCredentials
from spacebridge.trackers.base import Issue, IssueCreate, IssueFilter, TrackerConnection


@pytest.fixture
def jira_credentials():
    """Create Jira test credentials."""
    return JiraCredentials(
        token="test-token",
        username="test-user",
        url="https://test-jira.atlassian.net",
    )


@pytest.fixture
def jira_client(jira_credentials):
    """Create a Jira client for testing."""
    return JiraClient(credentials=jira_credentials)


@pytest.mark.asyncio
async def test_jira_test_connection_success(jira_client):
    """Test successful connection to Jira."""
    # Mock the _make_request method
    jira_client._make_request = AsyncMock(
        return_value={
            "baseUrl": "https://test-jira.atlassian.net",
            "version": "8.20.0",
            "buildNumber": 12345,
            "serverTitle": "Jira Test",
        }
    )

    result = await jira_client.test_connection()

    # Verify the result
    assert isinstance(result, TrackerConnection)
    assert result.connected is True
    assert "Successfully connected to Jira" in result.message
    assert result.server_info["version"] == "8.20.0"

    # Verify the make_request call
    jira_client._make_request.assert_called_once_with("GET", "serverInfo")


@pytest.mark.asyncio
async def test_jira_test_connection_failure(jira_client):
    """Test failed connection to Jira."""
    # Mock the _make_request method to raise an exception
    jira_client._make_request = AsyncMock(side_effect=ValueError("Connection failed"))

    result = await jira_client.test_connection()

    # Verify the result
    assert isinstance(result, TrackerConnection)
    assert result.connected is False
    assert "Failed to connect to Jira" in result.message
    assert result.server_info is None


@pytest.mark.asyncio
async def test_jira_search_issues(jira_client):
    """Test searching for Jira issues."""
    # Sample search response
    search_response = {
        "expand": "names,schema",
        "startAt": 0,
        "maxResults": 50,
        "total": 1,
        "issues": [
            {
                "id": "10001",
                "key": "TEST-1",
                "fields": {
                    "summary": "Test issue",
                    "description": "Test description",
                    "status": {
                        "id": "10000",
                        "name": "To Do",
                        "statusCategory": {"key": "new"},
                    },
                    "priority": {"id": "3", "name": "Medium"},
                    "created": "2023-01-01T00:00:00.000Z",
                    "updated": "2023-01-02T00:00:00.000Z",
                    "labels": ["bug", "critical"],
                    "components": [{"name": "frontend"}],
                    "reporter": {
                        "accountId": "user123",
                        "displayName": "Test User",
                        "emailAddress": "test@example.com",
                    },
                    "assignee": {
                        "accountId": "user456",
                        "displayName": "Assignee User",
                        "emailAddress": "assignee@example.com",
                    },
                    "comment": {
                        "comments": [
                            {
                                "id": "10001",
                                "body": "Test comment",
                                "created": "2023-01-01T12:00:00.000Z",
                                "author": {
                                    "accountId": "user123",
                                    "displayName": "Test User",
                                },
                            }
                        ]
                    },
                },
            }
        ],
    }

    # Mock the _make_request method
    jira_client._make_request = AsyncMock(return_value=search_response)

    # Create a filter
    filter_params = IssueFilter(
        query="test",
        status=["To Do"],
        labels=["bug"],
        sort_by="created",
        sort_direction="desc",
    )

    # Call the method
    issues, total = await jira_client.search_issues(
        project_key="TEST", filter_params=filter_params, limit=10, offset=0
    )

    # Verify the result
    assert total == 1
    assert len(issues) == 1

    issue = issues[0]
    assert issue.id == "10001"
    assert issue.key == "TEST-1"
    assert issue.title == "Test issue"
    assert issue.description == "Test description"
    assert issue.status.name == "To Do"
    assert issue.status.category == "todo"
    assert issue.priority.name == "Medium"
    assert issue.priority.level == 3
    assert issue.labels == ["bug", "critical"]
    assert issue.components == ["frontend"]
    assert issue.reporter.name == "Test User"
    assert issue.assignee.name == "Assignee User"
    assert len(issue.comments) == 1
    assert issue.comments[0].body == "Test comment"
    assert issue.tracker_type == "jira"
    assert issue.project_key == "TEST"

    # Verify the make_request call - check JQL query construction
    jira_client._make_request.assert_called_once()
    call_args = jira_client._make_request.call_args[1]
    assert call_args["json_data"]["jql"].startswith("project = 'TEST'")
    assert "(summary ~ 'test' OR description ~ 'test')" in call_args["json_data"]["jql"]
    assert "(status = 'To Do')" in call_args["json_data"]["jql"]
    assert "(labels = 'bug')" in call_args["json_data"]["jql"]
    assert "ORDER BY created DESC" in call_args["json_data"]["jql"]


@pytest.mark.asyncio
async def test_jira_create_issue(jira_client):
    """Test creating a Jira issue."""
    # Mock responses
    creation_response = {"id": "10001", "key": "TEST-1"}

    # Mock the issue details that will be returned after creation
    issue_response = {
        "id": "10001",
        "key": "TEST-1",
        "fields": {
            "summary": "New issue",
            "description": "Issue description",
            "status": {
                "id": "10000",
                "name": "To Do",
                "statusCategory": {"key": "new"},
            },
            "priority": {"id": "3", "name": "Medium"},
            "created": "2023-01-01T00:00:00.000Z",
            "updated": "2023-01-01T00:00:00.000Z",
            "project": {"key": "TEST"},
        },
    }

    # Setup the mock to return different responses for different calls
    async def mock_make_request(method, endpoint, **kwargs):
        if method == "POST" and endpoint == "issue":
            return creation_response
        elif method == "GET" and endpoint.startswith("issue/"):
            return issue_response
        return {}

    jira_client._make_request = AsyncMock(side_effect=mock_make_request)

    # Create issue data
    issue_data = IssueCreate(
        title="New issue",
        description="Issue description",
        priority="Medium",
        labels=["enhancement"],
    )

    # Call the method
    issue = await jira_client.create_issue(project_key="TEST", issue_data=issue_data)

    # Verify the result
    assert isinstance(issue, Issue)
    assert issue.id == "10001"
    assert issue.key == "TEST-1"
    assert issue.title == "New issue"
    assert issue.description == "Issue description"
    assert issue.priority.name == "Medium"

    # Verify the make_request calls
    assert jira_client._make_request.call_count == 2

    # First call should be to create the issue
    create_call = jira_client._make_request.call_args_list[0]
    assert create_call[0][0] == "POST"
    assert create_call[0][1] == "issue"
    assert create_call[1]["json_data"]["fields"]["summary"] == "New issue"
    assert create_call[1]["json_data"]["fields"]["project"]["key"] == "TEST"

    # Second call should be to get the created issue
    get_call = jira_client._make_request.call_args_list[1]
    assert get_call[0][0] == "GET"
    assert get_call[0][1] == "issue/10001"


@pytest.mark.asyncio
async def test_jira_add_comment(jira_client):
    """Test adding a comment to a Jira issue."""
    # Mock response
    comment_response = {
        "id": "10001",
        "body": {"content": [{"content": [{"text": "Test comment"}]}]},
        "created": "2023-01-01T00:00:00.000Z",
        "author": {
            "accountId": "user123",
            "displayName": "Test User",
            "emailAddress": "test@example.com",
        },
    }

    # Mock the _make_request method
    jira_client._make_request = AsyncMock(return_value=comment_response)

    # Call the method
    comment = await jira_client.add_comment(issue_id="TEST-1", comment="Test comment")

    # Verify the result
    assert comment.id == "10001"
    assert comment.author.name == "Test User"

    # Verify the make_request call
    jira_client._make_request.assert_called_once()
    call_args = jira_client._make_request.call_args
    assert call_args[0][0] == "POST"
    assert call_args[0][1] == "issue/TEST-1/comment"
    assert "Test comment" in str(call_args[1]["json_data"])
