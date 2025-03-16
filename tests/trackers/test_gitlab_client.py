"""Tests for the GitLab tracker client."""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from spacebridge.trackers.gitlab.client import GitLabClient, GitLabCredentials


class TestGitLabClient(unittest.TestCase):
    """Test cases for the GitLab tracker client."""

    def setUp(self):
        """Set up test fixtures."""
        self.credentials = GitLabCredentials(token="test_token")
        self.client = GitLabClient(
            credentials=self.credentials,
            project_id="group/project",
            timeout=5,
        )

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_request_success(self, mock_request):
        """Test making a successful request to the GitLab API."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "name": "test"}
        mock_request.return_value = mock_response

        # Make request
        result = await self.client._request("GET", "/test")

        # Check result
        self.assertEqual(result, {"id": 1, "name": "test"})
        mock_request.assert_called_once()

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.request")
    async def test_request_rate_limit(self, mock_request):
        """Test handling rate limiting in the GitLab API."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limit exceeded", request=MagicMock(), response=mock_response
        )
        mock_request.return_value = mock_response

        # Make request
        with self.assertRaises(httpx.HTTPStatusError):
            await self.client._request("GET", "/test")

    @pytest.mark.asyncio
    @patch("spacebridge.trackers.gitlab.client.GitLabClient._request")
    async def test_test_connection_success(self, mock_request):
        """Test successful connection testing."""
        # Mock responses
        mock_request.side_effect = [
            {"id": 1, "name": "test-project", "path_with_namespace": "group/project"},
            {"version": "15.4.0"},
        ]

        # Test connection
        result = await self.client.test_connection()

        # Check result
        self.assertTrue(result.connected)
        self.assertIn("Successfully connected", result.message)

    @pytest.mark.asyncio
    @patch("spacebridge.trackers.gitlab.client.GitLabClient._request")
    async def test_test_connection_failure(self, mock_request):
        """Test connection testing failure."""
        # Mock failure
        mock_request.side_effect = Exception("Connection failed")

        # Test connection
        result = await self.client.test_connection()

        # Check result
        self.assertFalse(result.connected)
        self.assertIn("Failed to connect", result.message)

    @pytest.mark.asyncio
    @patch("spacebridge.trackers.gitlab.client.GitLabClient._request")
    async def test_get_project_metadata(self, mock_request):
        """Test getting project metadata."""
        # Mock responses
        mock_request.side_effect = [
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

        # Get metadata
        result = await self.client.get_project_metadata("ignored")

        # Check result
        self.assertEqual(result.name, "test-project")
        self.assertEqual(result.description, "Test description")
        self.assertEqual(len(result.statuses), 2)  # open, closed
        self.assertEqual(len(result.priorities), 4)  # critical, high, medium, low

    @pytest.mark.asyncio
    @patch("spacebridge.trackers.gitlab.client.GitLabClient._request")
    async def test_search_issues(self, mock_request):
        """Test searching for issues."""
        # Mock response for issues
        mock_request.return_value = [
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

        # Mock client methods
        self.client._get_issue_comments = AsyncMock(return_value=[])

        # Create a mock httpx.AsyncClient context manager response
        mock_cm = MagicMock()
        mock_cm.__aenter__.return_value = MagicMock()
        mock_cm.__aenter__.return_value.request.return_value = MagicMock()
        mock_cm.__aenter__.return_value.request.return_value.headers = {"X-Total": "1"}
        
        # Patch the AsyncClient constructor to return our mock
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
            self.assertEqual(len(issues), 1)
            self.assertEqual(count, 1)
            self.assertEqual(issues[0].title, "Test issue")
            self.assertEqual(issues[0].status.id, "opened")
            self.assertEqual(issues[0].tracker_type, "gitlab")

    @pytest.mark.asyncio
    @patch("spacebridge.trackers.gitlab.client.GitLabClient._request")
    async def test_create_issue(self, mock_request):
        """Test creating an issue."""
        # Mock response
        mock_request.return_value = {
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
        self.assertEqual(issue.title, "New issue")
        self.assertEqual(issue.description, "New description")
        self.assertEqual(issue.status.id, "opened")
        self.assertEqual(issue.labels, ["bug"])
        mock_request.assert_called_once()


if __name__ == "__main__":
    unittest.main()