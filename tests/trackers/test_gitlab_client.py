"""Tests for the GitLab tracker client."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from spacebridge.trackers.gitlab.client import GitLabClient, GitLabCredentials


class TestGitLabClient:
    """Test cases for the GitLab tracker client."""

    def setup_method(self):
        """Set up test fixtures."""
        self.credentials = GitLabCredentials(token="test_token")
        self.client = GitLabClient(
            credentials=self.credentials,
            project_id="group/project",
            timeout=5,
        )

    @pytest.mark.asyncio
    async def test_request_success(self):
        """Test making a successful request to the GitLab API."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "name": "test"}

        # Set up the mock
        with patch(
            "httpx.AsyncClient.request", return_value=mock_response
        ) as mock_request:
            # Make request
            result = await self.client._request("GET", "/test")

            # Check result
            assert result == {"id": 1, "name": "test"}
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_rate_limit(self):
        """Test handling rate limiting in the GitLab API."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limit exceeded", request=MagicMock(), response=mock_response
        )

        # Set up the mock
        with patch(
            "httpx.AsyncClient.request", return_value=mock_response
        ) as mock_request:
            # Make request and check exception
            with pytest.raises(httpx.HTTPStatusError):
                await self.client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        """Test successful connection testing."""
        # Mock responses
        mock_responses = [
            {"id": 1, "name": "test-project", "path_with_namespace": "group/project"},
            {"version": "15.4.0"},
        ]

        # Set up the mock
        with patch(
            "spacebridge.trackers.gitlab.client.GitLabClient._request",
            side_effect=mock_responses,
        ) as mock_request:
            # Test connection
            result = await self.client.test_connection()

            # Check result
            assert result.connected is True
            assert "Successfully connected" in result.message

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        """Test connection testing failure."""
        # Set up the mock to raise an exception
        with patch(
            "spacebridge.trackers.gitlab.client.GitLabClient._request",
            side_effect=Exception("Connection failed"),
        ) as mock_request:
            # Test connection
            result = await self.client.test_connection()

            # Check result
            assert result.connected is False
            assert "Failed to connect" in result.message

    @pytest.mark.asyncio
    async def test_get_project_metadata(self):
        """Test getting project metadata."""
        # Mock responses
        mock_responses = [
            {
                "id": 1,
                "name": "test-project",
                "description": "Test description",
                "web_url": "https://gitlab.com/group/project",
            },
            [
                {"name": "bug", "color": "#ff0000"},
                {"name": "enhancement", "color": "#00ff00"},
                {"name": "priority::high", "color": "#0000ff"},
            ],
        ]

        # Set up the mock
        with patch(
            "spacebridge.trackers.gitlab.client.GitLabClient._request",
            side_effect=mock_responses,
        ) as mock_request:
            # Get metadata
            result = await self.client.get_project_metadata("ignored")

            # Check result
            assert result.name == "test-project"
            assert result.description == "Test description"
            assert len(result.statuses) == 2  # open, closed
            assert len(result.priorities) == 4  # critical, high, medium, low

    @pytest.mark.asyncio
    async def test_search_issues(self):
        """Test searching for issues."""
        # Mock response for issues
        issues_data = [
            {
                "id": 1,
                "iid": 1,
                "title": "Test issue",
                "description": "Test description",
                "state": "opened",
                "labels": ["bug", "priority::high"],
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z",
                "closed_at": None,
                "author": {
                    "id": 1,
                    "name": "Test User",
                    "username": "testuser",
                    "avatar_url": "https://gitlab.com/avatar",
                },
                "assignee": None,
                "web_url": "https://gitlab.com/group/project/-/issues/1",
                "_links": {"self": "https://gitlab.com/api/v4/projects/1/issues/1"},
            }
        ]

        # Set up the request mock
        with patch(
            "spacebridge.trackers.gitlab.client.GitLabClient._request",
            return_value=issues_data,
        ) as mock_request:
            # Set up the get_issue_comments mock
            with patch.object(
                self.client,
                "_get_issue_comments",
                return_value=AsyncMock(return_value=[]),
            ) as mock_comments:
                # Create a mock httpx response for the count headers
                mock_response = MagicMock()
                mock_response.headers = {"X-Total": "1"}

                # Set up the AsyncClient mock
                mock_client = MagicMock()
                mock_client.request = AsyncMock(return_value=mock_response)

                # Set up the AsyncClient context manager
                mock_cm = MagicMock()
                mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
                mock_cm.__aexit__ = AsyncMock()

                # Patch the AsyncClient constructor
                with patch("httpx.AsyncClient", return_value=mock_cm):
                    # Search issues
                    from spacebridge.trackers.base import IssueFilter

                    issues, count = await self.client.search_issues(
                        "ignored",
                        IssueFilter(query="test"),
                        limit=10,
                        offset=0,
                    )

                    # Check result
                    assert len(issues) == 1
                    assert count == 1
                    assert issues[0].title == "Test issue"
                    assert issues[0].status.id == "opened"
                    assert issues[0].tracker_type == "gitlab"

    @pytest.mark.asyncio
    async def test_create_issue(self):
        """Test creating an issue."""
        # Mock response
        issue_data = {
            "id": 1,
            "iid": 1,
            "title": "New issue",
            "description": "New description",
            "state": "opened",
            "labels": ["bug"],
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "closed_at": None,
            "author": {
                "id": 1,
                "name": "Test User",
                "username": "testuser",
                "avatar_url": "https://gitlab.com/avatar",
            },
            "assignee": None,
            "web_url": "https://gitlab.com/group/project/-/issues/1",
            "_links": {"self": "https://gitlab.com/api/v4/projects/1/issues/1"},
        }

        # Set up the mock
        with patch(
            "spacebridge.trackers.gitlab.client.GitLabClient._request",
            return_value=issue_data,
        ) as mock_request:
            # Create issue
            from spacebridge.trackers.base import IssueCreate

            issue = await self.client.create_issue(
                "ignored",
                IssueCreate(
                    title="New issue",
                    description="New description",
                    labels=["bug"],
                ),
            )

            # Check result
            assert issue.title == "New issue"
            assert issue.description == "New description"
            assert issue.status.id == "opened"
            assert issue.labels == ["bug"]
            mock_request.assert_called_once()
