"""
Tests for new GitLab tracker methods (get_issue and get_comments).
"""

from unittest.mock import MagicMock, patch, AsyncMock
from unittest import IsolatedAsyncioTestCase

from preloop_sync.trackers.gitlab import GitLabTracker
from preloop_sync.exceptions import TrackerResponseError


class TestGitLabTrackerNewMethods(IsolatedAsyncioTestCase):
    """Test GitLab tracker's new get_issue and get_comments methods."""

    @patch("preloop_sync.trackers.gitlab.gitlab.Gitlab")
    async def test_get_comments_success(self, mock_gitlab_constructor):
        """Test successful comments retrieval."""
        # Arrange
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"
        mock_gl_instance.projects.get.return_value = mock_project

        mock_issue = MagicMock()
        mock_issue.id = 12345
        mock_issue.iid = 1
        mock_issue.web_url = "http://gitlab.com/testgroup/testproject/issues/1"
        mock_project.issues.get.return_value = mock_issue

        # Mock notes (comments)
        mock_note1 = MagicMock()
        mock_note1.id = 1001
        mock_note1.body = "First comment"
        mock_note1.system = False
        mock_note1.created_at = "2023-01-01T12:00:00.000Z"
        mock_note1.updated_at = "2023-01-01T12:00:00.000Z"
        mock_note1.author = {
            "id": 101,
            "username": "commenter1",
            "avatar_url": "http://gitlab.com/avatars/101.png",
        }

        mock_note2 = MagicMock()
        mock_note2.id = 1002
        mock_note2.body = "Second comment"
        mock_note2.system = False
        mock_note2.created_at = "2023-01-01T13:00:00.000Z"
        mock_note2.updated_at = "2023-01-01T13:00:00.000Z"
        mock_note2.author = {
            "id": 102,
            "username": "commenter2",
            "avatar_url": "http://gitlab.com/avatars/102.png",
        }

        mock_issue.notes.list.return_value = [mock_note1, mock_note2]

        connection_details = {"project_id": "proj-1"}
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        tracker._make_request.side_effect = [
            mock_project,
            mock_issue,
            [mock_note1, mock_note2],
        ]

        # Act
        result = await tracker.get_comments("1")

        # Assert
        self.assertEqual(len(result), 2)

        self.assertEqual(result[0].id, "1001")
        self.assertEqual(result[0].body, "First comment")
        self.assertEqual(result[0].author.id, "101")
        self.assertEqual(result[0].author.name, "commenter1")
        self.assertEqual(
            result[0].url, "http://gitlab.com/testgroup/testproject/issues/1#note_1001"
        )

        self.assertEqual(result[1].id, "1002")
        self.assertEqual(result[1].body, "Second comment")
        self.assertEqual(result[1].author.id, "102")
        self.assertEqual(result[1].author.name, "commenter2")

    @patch("preloop_sync.trackers.gitlab.gitlab.Gitlab")
    async def test_get_comments_missing_project_id(self, mock_gitlab_constructor):
        """Test error when project_id is missing from connection details."""
        # Arrange
        tracker = GitLabTracker("tracker-1", "api-key", {})

        # Act & Assert
        with self.assertRaises(TrackerResponseError) as context:
            await tracker.get_comments("1")

        self.assertIn(
            "Project ID not found in connection details", str(context.exception)
        )

    @patch("preloop_sync.trackers.gitlab.gitlab.Gitlab")
    async def test_get_comments_filters_system_notes(self, mock_gitlab_constructor):
        """Test that system notes are filtered out from comments."""
        # Arrange
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"
        mock_gl_instance.projects.get.return_value = mock_project

        mock_issue = MagicMock()
        mock_issue.id = 12345
        mock_issue.web_url = "http://gitlab.com/testgroup/testproject/issues/1"
        mock_project.issues.get.return_value = mock_issue

        # Mock notes with one system note that should be filtered
        mock_system_note = MagicMock()
        mock_system_note.id = 2000
        mock_system_note.system = True  # This should be filtered out

        mock_user_note = MagicMock()
        mock_user_note.id = 1001
        mock_user_note.body = "User comment"
        mock_user_note.system = False
        mock_user_note.created_at = "2023-01-01T12:00:00.000Z"
        mock_user_note.updated_at = "2023-01-01T12:00:00.000Z"
        mock_user_note.author = {
            "id": 101,
            "username": "commenter1",
            "avatar_url": "http://gitlab.com/avatars/101.png",
        }

        mock_issue.notes.list.return_value = [mock_system_note, mock_user_note]

        connection_details = {"project_id": "proj-1"}
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        tracker._make_request.side_effect = [
            mock_project,
            mock_issue,
            [mock_system_note, mock_user_note],
        ]

        # Act
        result = await tracker.get_comments("1")

        # Assert - only the user comment should be included
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "1001")
        self.assertEqual(result[0].body, "User comment")

    @patch("preloop_sync.trackers.gitlab.gitlab.Gitlab")
    async def test_get_issue_missing_project_id(self, mock_gitlab_constructor):
        """Test error when project_id is missing from connection details."""
        # Arrange
        tracker = GitLabTracker("tracker-1", "api-key", {})

        # Act & Assert
        with self.assertRaises(TrackerResponseError) as context:
            await tracker.get_issue("1")

        self.assertIn(
            "Project ID not found in connection details", str(context.exception)
        )

    @patch("preloop_sync.trackers.gitlab.gitlab.Gitlab")
    async def test_get_issue_with_project_context(self, mock_gitlab_constructor):
        """Test get_issue uses project_id from connection_details."""
        # Arrange
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"
        mock_gl_instance.projects.get.return_value = mock_project

        mock_issue = MagicMock()
        mock_issue.id = 12345
        mock_issue.iid = 1
        mock_issue.title = "Test Issue"
        mock_issue.description = "Description for issue"
        mock_issue.state = "opened"
        mock_issue.created_at = "2023-01-01T10:00:00.000Z"
        mock_issue.updated_at = "2023-01-02T11:00:00.000Z"
        mock_issue.web_url = "http://gitlab.com/testgroup/testproject/issues/1"
        mock_issue.labels = ["bug", "critical"]
        mock_issue.assignees = [{"username": "user1"}]
        # Add attributes dict for the parser
        mock_issue.attributes = {
            "id": 12345,
            "iid": 1,
            "title": "Test Issue",
            "description": "Description for issue",
            "state": "opened",
            "created_at": "2023-01-01T10:00:00.000Z",
            "updated_at": "2023-01-02T11:00:00.000Z",
            "web_url": "http://gitlab.com/testgroup/testproject/issues/1",
            "labels": ["bug", "critical"],
            "assignee": None,
            "assignees": [],
            "author": {
                "id": 123,
                "name": "Author",
                "avatar_url": "https://example.com/avatar.png",
            },
            "_links": {"self": "http://gitlab.com/api/v4/projects/proj-1/issues/1"},
        }
        mock_project.issues.get.return_value = mock_issue

        connection_details = {"project_id": "proj-1"}
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        tracker._make_request.side_effect = [mock_project, mock_issue]

        # Act
        result = await tracker.get_issue("1")

        # Assert - Now result is an Issue object
        self.assertEqual(result.id, "12345")
        self.assertEqual(result.key, "testgroup/testproject#1")
        self.assertEqual(result.title, "Test Issue")
        self.assertEqual(result.description, "Description for issue")
        self.assertEqual(result.status.id, "opened")
        self.assertEqual(result.labels, ["bug", "critical"])
        self.assertEqual(result.url, "http://gitlab.com/testgroup/testproject/issues/1")

        # Verify the project_id from connection_details was used
        tracker._make_request.assert_any_call(mock_gl_instance.projects.get, "proj-1")
