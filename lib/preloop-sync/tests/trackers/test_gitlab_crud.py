"""
Tests for GitLab tracker CRUD methods.
"""

from unittest.mock import MagicMock, patch, AsyncMock
from unittest import IsolatedAsyncioTestCase

from spacesync.trackers.gitlab import GitLabTracker
from spacesync.exceptions import TrackerResponseError


class TestGitLabTrackerCRUD(IsolatedAsyncioTestCase):
    """Test GitLab tracker's CRUD methods."""

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    async def test_create_issue_success(self, mock_gitlab_constructor):
        """Test successful issue creation."""
        # Arrange
        from spacebridge.schemas.tracker_models import IssueCreate

        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"

        mock_issue = MagicMock()
        mock_issue.id = 12345
        mock_issue.iid = 1
        mock_issue.title = "New Issue"
        mock_issue.description = "Issue description"
        mock_issue.state = "opened"
        mock_issue.created_at = "2023-01-01T10:00:00.000Z"
        mock_issue.updated_at = "2023-01-01T10:00:00.000Z"
        mock_issue.web_url = "https://gitlab.com/testgroup/testproject/-/issues/1"
        mock_issue.labels = ["bug"]
        mock_issue.attributes = {
            "id": 12345,
            "iid": 1,
            "title": "New Issue",
            "description": "Issue description",
            "state": "opened",
            "created_at": "2023-01-01T10:00:00.000Z",
            "updated_at": "2023-01-01T10:00:00.000Z",
            "web_url": "https://gitlab.com/testgroup/testproject/-/issues/1",
            "labels": ["bug"],
            "assignee": None,
            "assignees": [],
            "author": {
                "id": 123,
                "name": "Author",
                "avatar_url": "https://example.com/avatar.png",
            },
            "_links": {"self": "https://gitlab.com/api/v4/projects/proj-1/issues/1"},
        }
        mock_project.issues.create.return_value = mock_issue

        connection_details = {"project_id": "proj-1", "url": "https://gitlab.com"}
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        tracker._make_request.side_effect = [mock_project, mock_issue]

        issue_create = IssueCreate(
            title="New Issue",
            description="Issue description",
            labels=["bug"],
        )

        # Act
        result = await tracker.create_issue("proj-1", issue_create)

        # Assert
        self.assertEqual(result.id, "12345")
        self.assertEqual(result.title, "New Issue")
        self.assertEqual(result.labels, ["bug"])

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    async def test_update_issue_success(self, mock_gitlab_constructor):
        """Test successful issue update."""
        # Arrange
        from spacebridge.schemas.tracker_models import IssueUpdate

        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"

        mock_issue = MagicMock()
        mock_issue.id = 12345
        mock_issue.iid = 1
        mock_issue.title = "Updated Issue"
        mock_issue.description = "Updated description"
        mock_issue.state = "closed"
        mock_issue.created_at = "2023-01-01T10:00:00.000Z"
        mock_issue.updated_at = "2023-01-02T10:00:00.000Z"
        mock_issue.web_url = "https://gitlab.com/testgroup/testproject/-/issues/1"
        mock_issue.attributes = {
            "id": 12345,
            "iid": 1,
            "title": "Updated Issue",
            "description": "Updated description",
            "state": "closed",
            "created_at": "2023-01-01T10:00:00.000Z",
            "updated_at": "2023-01-02T10:00:00.000Z",
            "web_url": "https://gitlab.com/testgroup/testproject/-/issues/1",
            "labels": [],
            "assignee": None,
            "assignees": [],
            "author": {
                "id": 123,
                "name": "Author",
                "avatar_url": "https://example.com/avatar.png",
            },
            "_links": {"self": "https://gitlab.com/api/v4/projects/proj-1/issues/1"},
        }
        mock_issue.save = MagicMock()

        connection_details = {"project_id": "proj-1", "url": "https://gitlab.com"}
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        tracker._make_request.side_effect = [mock_project, mock_issue, mock_issue]

        issue_update = IssueUpdate(
            title="Updated Issue",
            description="Updated description",
            status="closed",
        )

        # Act
        result = await tracker.update_issue("1", issue_update)

        # Assert
        self.assertEqual(result.title, "Updated Issue")
        self.assertEqual(result.status.id, "closed")

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    async def test_add_comment_success(self, mock_gitlab_constructor):
        """Test successful comment addition."""
        # Arrange
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"

        mock_issue = MagicMock()
        mock_issue.id = 1
        mock_issue.web_url = "https://gitlab.com/testgroup/testproject/-/issues/1"

        mock_note = MagicMock()
        mock_note.id = 1001
        mock_note.body = "Test comment"
        mock_note.created_at = "2023-01-01T12:00:00.000Z"
        mock_note.updated_at = "2023-01-01T12:00:00.000Z"
        mock_note.author = {
            "id": 123,
            "name": "testuser",
            "avatar_url": "https://avatar.png",
        }
        mock_issue.notes.create.return_value = mock_note

        connection_details = {"project_id": "proj-1", "url": "https://gitlab.com"}
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        # Return project, issue, then note
        tracker._make_request.side_effect = [mock_project, mock_issue, mock_note]

        # Act
        result = await tracker.add_comment("1", "Test comment")

        # Assert
        self.assertEqual(result.id, "1001")
        self.assertEqual(result.body, "Test comment")
        self.assertEqual(result.author.name, "testuser")

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    async def test_add_relation_success(self, mock_gitlab_constructor):
        """Test successful issue relation creation."""
        # Arrange
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"

        mock_issue = MagicMock()
        mock_link = MagicMock()
        mock_issue.links.create.return_value = mock_link

        connection_details = {"project_id": "proj-1", "url": "https://gitlab.com"}
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        tracker._make_request.side_effect = [mock_project, mock_issue, mock_link]

        # Act
        result = await tracker.add_relation("1", "2", "relates_to")

        # Assert
        self.assertTrue(result)

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    async def test_search_issues_success(self, mock_gitlab_constructor):
        """Test successful issue search."""
        # Arrange
        from spacebridge.schemas.tracker_models import IssueFilter

        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"

        mock_issue = MagicMock()
        mock_issue.id = 12345
        mock_issue.iid = 1
        mock_issue.title = "Bug Issue"
        mock_issue.description = "Bug description"
        mock_issue.state = "opened"
        mock_issue.created_at = "2023-01-01T10:00:00.000Z"
        mock_issue.updated_at = "2023-01-02T11:00:00.000Z"
        mock_issue.web_url = "https://gitlab.com/testgroup/testproject/-/issues/1"
        mock_issue.labels = ["critical"]
        mock_issue.attributes = {
            "id": 12345,
            "iid": 1,
            "title": "Bug Issue",
            "description": "Bug description",
            "state": "opened",
            "created_at": "2023-01-01T10:00:00.000Z",
            "updated_at": "2023-01-02T11:00:00.000Z",
            "web_url": "https://gitlab.com/testgroup/testproject/-/issues/1",
            "labels": ["critical"],
            "assignee": None,
            "assignees": [],
            "author": {
                "id": 123,
                "name": "Author",
                "avatar_url": "https://example.com/avatar.png",
            },
            "_links": {"self": "https://gitlab.com/api/v4/projects/proj-1/issues/1"},
        }
        mock_project.issues.list.return_value = [mock_issue]

        connection_details = {"project_id": "proj-1", "url": "https://gitlab.com"}
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        tracker._make_request.side_effect = [mock_project, [mock_issue]]

        filter_params = IssueFilter(query="bug", status=["opened"], labels=["critical"])

        # Act
        issues, total = await tracker.search_issues("proj-1", filter_params, limit=10)

        # Assert
        self.assertGreater(len(issues), 0)
        # search_issues doesn't pass project to parser, so it uses project_id from connection_details
        self.assertEqual(issues[0].key, "proj-1#1")

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    async def test_get_project_metadata_success(self, mock_gitlab_constructor):
        """Test successful project metadata retrieval."""
        # Arrange
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.id = 12345
        mock_project.name = "testproject"
        mock_project.path_with_namespace = "testgroup/testproject"
        mock_project.description = "Test project description"
        mock_project.web_url = "https://gitlab.com/testgroup/testproject"
        mock_project.attributes = {
            "id": 12345,
            "name": "testproject",
            "path_with_namespace": "testgroup/testproject",
            "description": "Test project description",
            "web_url": "https://gitlab.com/testgroup/testproject",
        }

        connection_details = {"project_id": "proj-1", "url": "https://gitlab.com"}
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock(return_value=mock_project)

        # Act
        result = await tracker.get_project_metadata("proj-1")

        # Assert
        self.assertEqual(result.key, "testgroup/testproject")
        self.assertEqual(result.name, "testproject")
        self.assertEqual(result.description, "Test project description")
        self.assertGreater(len(result.statuses), 0)

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    async def test_create_issue_project_not_found(self, mock_gitlab_constructor):
        """Test error when project doesn't exist."""
        # Arrange
        from spacebridge.schemas.tracker_models import IssueCreate

        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        connection_details = {
            "project_id": "nonexistent-project",
            "url": "https://gitlab.com",
        }
        tracker = GitLabTracker("tracker-1", "api-key", connection_details)

        # Mock the _make_request to raise an error when trying to get the project
        tracker._make_request = AsyncMock(
            side_effect=TrackerResponseError("Project not found")
        )

        issue_create = IssueCreate(title="New Issue")

        # Act & Assert
        with self.assertRaises(TrackerResponseError) as context:
            await tracker.create_issue("nonexistent-project", issue_create)

        self.assertIn("Project not found", str(context.exception))
