import pytest
from unittest.mock import AsyncMock, patch

from spacebridge.trackers.base import (
    IssueCreate,
    IssueFilter,
    TrackerConnection,
)
from spacebridge.trackers.github.client import GitHubClient, GitHubCredentials


@pytest.fixture
def github_credentials():
    """Create GitHub test credentials."""
    return GitHubCredentials(
        token="test-github-token",
    )


@pytest.fixture
def github_client(github_credentials):
    """Create a GitHub client for testing."""
    return GitHubClient(
        credentials=github_credentials,
        owner="test-owner",
        repo="test-repo"
    )


@pytest.mark.asyncio
async def test_github_test_connection_success(github_client):
    """Test successful connection to GitHub."""
    # _request is called twice: once for repo, once for rate_limit
    github_client._request = AsyncMock(side_effect=[
        {"full_name": "test-owner/test-repo"},  # Response for repo check
        {"resources": {"core": {"limit": 5000, "remaining": 4999}}}  # Response for rate_limit check
    ])

    result = await github_client.test_connection()

    assert isinstance(result, TrackerConnection)
    assert result.connected is True
    assert result.message == "Successfully connected to GitHub repository: test-owner/test-repo"
    # Check calls
    assert github_client._request.call_count == 2
    calls = github_client._request.call_args_list
    assert calls[0][0] == ("GET", f"/repos/{github_client.owner}/{github_client.repo}")
    assert calls[1][0] == ("GET", "/rate_limit")


@pytest.mark.asyncio
async def test_github_test_connection_failure(github_client):
    """Test failed connection to GitHub."""
    github_client._request = AsyncMock(
        side_effect=Exception("Connection error")
    )

    result = await github_client.test_connection()

    assert isinstance(result, TrackerConnection)
    assert result.connected is False
    assert "Failed to connect to GitHub: Connection error" in result.message


@pytest.mark.asyncio
async def test_github_search_issues(github_client):
    """Test searching for GitHub issues."""
    search_response = {
        "total_count": 1,
        "incomplete_results": False,
        "items": [
            {
                "id": 12345,
                "number": 1347,
                "title": "Found a bug",
                "user": {"login": "octocat", "id": 1, "avatar_url": "http://example.com/avatar.png"},
                "labels": [{"name": "bug"}, {"name": "high-priority"}],
                "state": "open",
                "assignee": {"login": "octocat", "id": 1, "avatar_url": "http://example.com/avatar.png"},
                "comments": 0,
                "created_at": "2011-04-22T13:33:48Z",
                "updated_at": "2011-04-22T13:33:48Z",
                "closed_at": None,
                "body": "I'm having a problem with this.",
                "html_url": "https://github.com/test-owner/test-repo/issues/1347",
                "url": "https://api.github.com/repos/test-owner/test-repo/issues/1347"
            }
        ],
    }
    github_client._request = AsyncMock(return_value=search_response)

    filter_params = IssueFilter(
        query="bug", status=["open"], labels=["bug"], sort_by="created", sort_direction="desc"
    )

    issues, total = await github_client.search_issues(
        project_key=f"{github_client.owner}/{github_client.repo}",
        filter_params=filter_params,
        limit=10,
        offset=0,
    )

    assert total == 1
    assert len(issues) == 1
    issue = issues[0]
    assert issue.id == "12345"
    assert issue.key == f"{github_client.owner}/{github_client.repo}#1347"
    assert issue.title == "Found a bug"
    assert issue.description == "I'm having a problem with this."
    assert issue.status.name == "Open"
    assert issue.status.category == "todo"  # Assuming 'open' maps to 'todo'
    assert issue.labels == ["bug", "high-priority"]
    assert issue.reporter.name == "octocat"
    assert issue.assignee.name == "octocat"
    assert issue.tracker_type == "github"
    assert issue.project_key == f"{github_client.owner}/{github_client.repo}"
    assert issue.url == "https://github.com/test-owner/test-repo/issues/1347"

    github_client._request.assert_called_once()
    call_args = github_client._request.call_args
    assert call_args[0][0] == "GET"
    assert call_args[0][1].startswith(f"/search/issues")
    assert f"repo:{github_client.owner}/{github_client.repo}" in call_args[1]["params"]["q"]
    assert "bug" in call_args[1]["params"]["q"] # query text
    assert "is:open" in call_args[1]["params"]["q"] # status filter
    assert 'label:"bug"' in call_args[1]["params"]["q"] # label filter
    assert call_args[1]["params"]["sort"] == "created"
    assert call_args[1]["params"]["order"] == "desc"
    assert call_args[1]["params"]["per_page"] == 10
    # assert call_args[1]["params"]["page"] == 1 # offset 0 should mean page 1


@pytest.mark.asyncio
async def test_github_create_issue(github_client):
    """Test creating a GitHub issue."""
    created_issue_response = {
        "id": 12345,
        "number": 1347,
        "title": "New Test Issue",
        "body": "This is a test issue.",
        "user": {"login": "octocat", "id": 1, "avatar_url": "http://example.com/avatar.png"}, # Reporter
        "labels": [],
        "state": "open", 
        "assignee": None, # No assignee initially
        "comments": 0,
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "html_url": "https://github.com/test-owner/test-repo/issues/1347",
        "url": "https://api.github.com/repos/test-owner/test-repo/issues/1347"
    }
    github_client._request = AsyncMock(return_value=created_issue_response)

    issue_data = IssueCreate(
        title="New Test Issue",
        description="This is a test issue.",
        # Optional: Add other fields like labels, assignee_id if your IssueCreate supports them
    )

    created_issue = await github_client.create_issue(
        project_key=f"{github_client.owner}/{github_client.repo}", issue_data=issue_data
    )

    assert created_issue.id == "12345"
    assert created_issue.key == f"{github_client.owner}/{github_client.repo}#1347"
    assert created_issue.title == "New Test Issue"
    assert created_issue.description == "This is a test issue."
    assert created_issue.status.name == "Open"
    # Add more assertions as needed (reporter, assignee, labels, etc.)

    github_client._request.assert_called_once()
    call_args = github_client._request.call_args
    assert call_args[0][0] == "POST"
    assert call_args[0][1] == f"/repos/{github_client.owner}/{github_client.repo}/issues"
    assert call_args[1]["data"]["title"] == "New Test Issue"  
    assert call_args[1]["data"]["body"] == "This is a test issue."
    # Add assertions for other payload fields if sent (e.g., labels, assignees)


@pytest.mark.asyncio
async def test_github_add_comment(github_client):
    """Test adding a comment to a GitHub issue."""
    comment_response = {
        "id": 1, # Comment ID
        "body": "This is a test comment",
        "user": {"login": "octocat", "id": 1, "avatar_url": "http://example.com/avatar.png"}, # Comment author
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "html_url": "https://github.com/test-owner/test-repo/issues/1347#issuecomment-1",
    }
    github_client._request = AsyncMock(return_value=comment_response)

    issue_key = "1347" # This is the issue number for GitHub
    comment_text = "This is a test comment"

    added_comment = await github_client.add_comment(
        issue_id=issue_key, # issue_id is the issue number for GitHub
        comment=comment_text
    )

    assert added_comment.id == "1"
    assert added_comment.body == "This is a test comment"
    assert added_comment.author.name == "octocat"
    # Add more assertions (created_at, updated_at, url)

    github_client._request.assert_called_once() 
    call_args = github_client._request.call_args
    assert call_args[0][0] == "POST"
    assert call_args[0][1] == f"/repos/{github_client.owner}/{github_client.repo}/issues/{issue_key}/comments" 
    assert call_args[1]["data"] == {"body": comment_text}