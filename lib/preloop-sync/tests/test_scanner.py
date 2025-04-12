"""Tests for the scanner module."""

import unittest
from unittest.mock import MagicMock, patch

from spacesync.scanner.core import TrackerClient


class MockTrackerClient(TrackerClient):
    """Mock version of TrackerClient that overrides methods that make external calls."""

    def __init__(self, tracker):
        """Initialize with the mock tracker."""
        self.tracker = tracker
        self.tracker_type = (
            tracker.tracker_type.lower()
            if hasattr(tracker.tracker_type, "value")
            else tracker.tracker_type.lower()
        )
        # Mock the client directly
        self.client = MagicMock()

    def get_issues(self, org_identifier, project_identifier, since=None):
        """Mock implementation that returns empty list."""
        return []


class TestTrackerClient(unittest.TestCase):
    """Test the TrackerClient class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock tracker
        self.mock_tracker = MagicMock()
        self.mock_tracker.tracker_type = "github"
        self.mock_tracker.connection_details = {
            "token": "test_token",
            "owner": "test_owner",
            "repo": "test_repo",
        }

        # Create a mock client that inherits from TrackerClient
        self.client = MockTrackerClient(self.mock_tracker)

    def test_init(self):
        """Test initialization of the tracker client."""
        self.assertEqual(self.client.tracker, self.mock_tracker)
        self.assertEqual(self.client.tracker_type, "github")

    @patch("spacesync.scanner.core.crud_issue")
    def test_scan_issues(self, mock_crud_issue):
        """Test scanning issues."""
        # Create mock organization and project
        mock_org = MagicMock()
        mock_org.id = "test-org-id"
        mock_org.identifier = "test-org"

        mock_project = MagicMock()
        mock_project.id = "test-project-id"
        mock_project.identifier = "test-proj"
        mock_project.name = "Test Project"

        # Setup mocks
        mock_crud_issue.get_last_updated.return_value = None
        mock_crud_issue.get_for_project.return_value = []

        # Mock the transform_issue method
        self.client.client.transform_issue = MagicMock(
            return_value={
                "title": "Test Issue",
                "description": "Test Description",
                "status": "open",
            }
        )

        # Instead of mocking self.get_issues, mock self.client.get_issues which is what's actually called
        mock_get_issues = MagicMock(
            return_value=[{"id": "1234"}]
        )  # Return a sample issue
        self.client.client.get_issues = mock_get_issues

        # Call the method under test
        issues, count = self.client.scan_issues(MagicMock(), mock_org, mock_project)

        # Assert client.get_issues was called with correct arguments
        mock_get_issues.assert_called_once_with(
            mock_org.identifier, mock_project.identifier, None
        )
