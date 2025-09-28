"""
Tests for new Jira tracker methods (get_issue and get_comments).
"""

from unittest.mock import AsyncMock
from unittest import IsolatedAsyncioTestCase
from datetime import datetime

from spacesync.trackers.jira import JiraTracker
from spacesync.exceptions import TrackerResponseError


class TestJiraTrackerNewMethods(IsolatedAsyncioTestCase):
    """Test Jira tracker's new get_issue and get_comments methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.connection_details = {
            "url": "https://test.atlassian.net",
            "username": "test@example.com",
            "project_key": "TEST",
        }
        self.tracker = JiraTracker("tracker-1", "api-token", self.connection_details)
        # Set base_url attribute that is used in URL construction
        self.tracker.base_url = "https://test.atlassian.net"

    async def test_get_issue_success(self):
        """Test successful issue retrieval."""
        # Arrange
        issue_data = {
            "id": "12345",
            "key": "TEST-123",
            "fields": {
                "summary": "Test Issue",
                "description": "Issue description",
                "status": {"name": "Open"},
                "created": "2023-01-01T10:00:00.000+0000",
                "updated": "2023-01-02T11:00:00.000+0000",
                "labels": ["bug", "critical"],
                "assignee": {"name": "testuser"},
            },
        }

        self.tracker._make_request = AsyncMock(return_value=issue_data)

        # Act
        result = await self.tracker.get_issue("TEST-123")

        # Assert
        self.assertEqual(result["external_id"], "12345")
        self.assertEqual(result["key"], "TEST-123")
        self.assertEqual(result["title"], "Test Issue")
        self.assertEqual(result["description"], "Issue description")
        self.assertEqual(result["state"], "Open")
        self.assertEqual(result["labels"], ["bug", "critical"])
        self.assertEqual(result["assignees"], ["testuser"])
        self.assertEqual(result["url"], "https://test.atlassian.net/browse/TEST-123")

        # Verify API call
        self.tracker._make_request.assert_called_once_with(
            "GET", "issue/TEST-123", api_version="3"
        )

    async def test_get_issue_not_found(self):
        """Test error when issue is not found."""
        # Arrange
        self.tracker._make_request = AsyncMock(
            side_effect=TrackerResponseError("404 Not Found")
        )

        # Act & Assert
        with self.assertRaises(TrackerResponseError) as context:
            await self.tracker.get_issue("TEST-999")

        self.assertIn("Issue TEST-999 not found", str(context.exception))

    async def test_get_issue_no_assignee(self):
        """Test issue retrieval when no assignee is set."""
        # Arrange
        issue_data = {
            "id": "12345",
            "key": "TEST-123",
            "fields": {
                "summary": "Test Issue",
                "description": "Issue description",
                "status": {"name": "Open"},
                "created": "2023-01-01T10:00:00.000+0000",
                "updated": "2023-01-02T11:00:00.000+0000",
                "labels": [],
                "assignee": None,  # No assignee
            },
        }

        self.tracker._make_request = AsyncMock(return_value=issue_data)

        # Act
        result = await self.tracker.get_issue("TEST-123")

        # Assert
        self.assertEqual(result["assignees"], [])

    async def test_get_comments_success(self):
        """Test successful comments retrieval."""
        # Arrange
        comments_data = {
            "comments": [
                {
                    "id": "1001",
                    "body": "First comment",
                    "created": "2023-01-01T12:00:00.000+0000",
                    "updated": "2023-01-01T12:00:00.000+0000",
                    "author": {
                        "accountId": "101",
                        "displayName": "Test User 1",
                        "avatarUrls": {"48x48": "https://avatar1.png"},
                    },
                },
                {
                    "id": "1002",
                    "body": "Second comment",
                    "created": "2023-01-01T13:00:00.000+0000",
                    "updated": "2023-01-01T13:00:00.000+0000",
                    "author": {
                        "accountId": "102",
                        "displayName": "Test User 2",
                        "avatarUrls": {"48x48": "https://avatar2.png"},
                    },
                },
            ]
        }

        self.tracker._make_request = AsyncMock(return_value=comments_data)

        # Act
        result = await self.tracker.get_comments("TEST-123")

        # Assert
        self.assertEqual(len(result), 2)

        self.assertEqual(result[0].id, "1001")
        self.assertEqual(result[0].body, "First comment")
        self.assertEqual(result[0].author.id, "101")
        self.assertEqual(result[0].author.name, "Test User 1")
        self.assertEqual(result[0].author.avatar_url, "https://avatar1.png")
        self.assertEqual(
            result[0].url,
            "https://test.atlassian.net/browse/TEST-123?focusedCommentId=1001",
        )

        self.assertEqual(result[1].id, "1002")
        self.assertEqual(result[1].body, "Second comment")
        self.assertEqual(result[1].author.id, "102")
        self.assertEqual(result[1].author.name, "Test User 2")

        # Verify API call
        self.tracker._make_request.assert_called_once_with(
            "GET", "issue/TEST-123/comment", api_version="3"
        )

    async def test_get_comments_not_found(self):
        """Test error when issue is not found for comments."""
        # Arrange
        self.tracker._make_request = AsyncMock(
            side_effect=TrackerResponseError("404 Not Found")
        )

        # Act & Assert
        with self.assertRaises(TrackerResponseError) as context:
            await self.tracker.get_comments("TEST-999")

        self.assertIn("Issue TEST-999 not found", str(context.exception))

    async def test_get_comments_no_author(self):
        """Test comments retrieval when comment has no author."""
        # Arrange
        comments_data = {
            "comments": [
                {
                    "id": "1001",
                    "body": "Anonymous comment",
                    "created": "2023-01-01T12:00:00.000+0000",
                    "updated": "2023-01-01T12:00:00.000+0000",
                    "author": {},  # Empty author dict instead of None
                }
            ]
        }

        self.tracker._make_request = AsyncMock(return_value=comments_data)

        # Act
        result = await self.tracker.get_comments("TEST-123")

        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "1001")
        self.assertEqual(result[0].body, "Anonymous comment")
        # When author is empty dict, it should create an IssueUser with default "Anonymous" name
        self.assertIsNotNone(result[0].author)
        self.assertEqual(result[0].author.id, "")
        self.assertEqual(result[0].author.name, "Anonymous")

    async def test_get_comments_empty_list(self):
        """Test comments retrieval when no comments exist."""
        # Arrange
        comments_data = {"comments": []}

        self.tracker._make_request = AsyncMock(return_value=comments_data)

        # Act
        result = await self.tracker.get_comments("TEST-123")

        # Assert
        self.assertEqual(len(result), 0)

    async def test_get_issue_datetime_parsing_fallback(self):
        """Test datetime parsing fallback when date format is invalid."""
        # Arrange
        issue_data = {
            "id": "12345",
            "key": "TEST-123",
            "fields": {
                "summary": "Test Issue",
                "description": "Issue description",
                "status": {"name": "Open"},
                "created": "invalid-date",  # Invalid date format
                "updated": "also-invalid",  # Invalid date format
                "labels": [],
                "assignee": None,
            },
        }

        self.tracker._make_request = AsyncMock(return_value=issue_data)

        # Act
        result = await self.tracker.get_issue("TEST-123")

        # Assert - should not raise error and use current datetime as fallback
        self.assertIsInstance(result["created_at"], datetime)
        self.assertIsInstance(result["updated_at"], datetime)
