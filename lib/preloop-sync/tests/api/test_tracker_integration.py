"""
Integration tests for tracker methods called by the API.
"""

from unittest.mock import MagicMock, patch, AsyncMock
from unittest import IsolatedAsyncioTestCase

from spacesync.trackers.github import GitHubTracker
from spacesync.trackers.gitlab import GitLabTracker
from spacesync.trackers.jira import JiraTracker


class TestTrackerApiIntegration(IsolatedAsyncioTestCase):
    """Test integration between API and tracker methods."""

    async def test_github_tracker_get_issue_api_integration(self):
        """Test GitHub tracker get_issue method works with API connection details format."""
        # Arrange - simulate how get_tracker_client creates connection_details for GitHub
        connection_details = {
            "owner": "testowner",
            "repo": "testrepo",
            "url": "https://github.com",
        }

        tracker = GitHubTracker("tracker-1", "api-key", connection_details)

        # Mock the _make_request method directly instead of httpx
        issue_data = {
            "id": 12345,
            "number": 1,
            "title": "Test Issue",
            "body": "Issue description",
            "state": "open",
            "created_at": "2023-01-01T10:00:00Z",
            "updated_at": "2023-01-02T11:00:00Z",
            "html_url": "https://github.com/testowner/testrepo/issues/1",
            "labels": [{"name": "bug"}],
            "assignees": [{"login": "user1"}],
        }

        tracker._make_request = AsyncMock(return_value=issue_data)

        # Act
        result = await tracker.get_issue("1")

        # Assert
        self.assertEqual(result["external_id"], "12345")
        self.assertEqual(result["key"], "testowner/testrepo#1")
        self.assertEqual(result["title"], "Test Issue")

        # Verify the correct API endpoint was called
        expected_endpoint = "repos/testowner/testrepo/issues/1"
        tracker._make_request.assert_called_once_with(expected_endpoint)

    async def test_github_tracker_get_comments_api_integration(self):
        """Test GitHub tracker get_comments method works with API connection details format."""
        # Arrange
        connection_details = {
            "owner": "testowner",
            "repo": "testrepo",
            "url": "https://github.com",
        }

        tracker = GitHubTracker("tracker-1", "api-key", connection_details)

        comments_data = [
            {
                "id": 1001,
                "body": "Test comment",
                "user": {
                    "id": 101,
                    "login": "commenter1",
                    "avatar_url": "https://avatars.github.com/u/101",
                },
                "created_at": "2023-01-01T12:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
                "html_url": "https://github.com/testowner/testrepo/issues/1#issuecomment-1001",
            }
        ]

        tracker._make_request = AsyncMock(return_value=comments_data)

        # Act
        result = await tracker.get_comments("1")

        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "1001")
        self.assertEqual(result[0].body, "Test comment")

        # Verify the correct API endpoint was called
        expected_endpoint = "repos/testowner/testrepo/issues/1/comments"
        tracker._make_request.assert_called_once_with(
            expected_endpoint, params={"per_page": 100}
        )

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    async def test_gitlab_tracker_get_issue_api_integration(
        self, mock_gitlab_constructor
    ):
        """Test GitLab tracker get_issue method works with API connection details format."""
        # Arrange - simulate how get_tracker_client creates connection_details for GitLab
        connection_details = {
            "project_id": "123",
            "url": "https://gitlab.com",
        }

        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"

        mock_issue = MagicMock()
        mock_issue.id = 12345
        mock_issue.iid = 1
        mock_issue.title = "Test Issue"
        mock_issue.description = "Issue description"
        mock_issue.state = "opened"
        mock_issue.created_at = "2023-01-01T10:00:00.000Z"
        mock_issue.updated_at = "2023-01-02T11:00:00.000Z"
        mock_issue.web_url = "https://gitlab.com/testgroup/testproject/-/issues/1"
        mock_issue.labels = ["bug"]
        mock_issue.assignees = [{"username": "user1"}]

        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        tracker._make_request.side_effect = [mock_project, mock_issue]

        # Act
        result = await tracker.get_issue("1")

        # Assert
        self.assertEqual(result["external_id"], "12345")
        self.assertEqual(result["key"], "testgroup/testproject#1")
        self.assertEqual(result["title"], "Test Issue")

        # Verify the project_id from connection_details was used
        tracker._make_request.assert_any_call(mock_gl_instance.projects.get, "123")

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    async def test_gitlab_tracker_get_comments_api_integration(
        self, mock_gitlab_constructor
    ):
        """Test GitLab tracker get_comments method works with API connection details format."""
        # Arrange
        connection_details = {
            "project_id": "123",
            "url": "https://gitlab.com",
        }

        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"

        mock_issue = MagicMock()
        mock_issue.id = 12345
        mock_issue.web_url = "https://gitlab.com/testgroup/testproject/-/issues/1"

        mock_note = MagicMock()
        mock_note.id = 1001
        mock_note.body = "Test comment"
        mock_note.system = False
        mock_note.created_at = "2023-01-01T12:00:00.000Z"
        mock_note.updated_at = "2023-01-01T12:00:00.000Z"
        mock_note.author = {
            "id": 101,
            "username": "commenter1",
            "avatar_url": "https://gitlab.com/avatars/101.png",
        }

        tracker = GitLabTracker("tracker-1", "api-key", connection_details)
        tracker._make_request = AsyncMock()
        tracker._make_request.side_effect = [mock_project, mock_issue, [mock_note]]

        # Act
        result = await tracker.get_comments("1")

        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "1001")
        self.assertEqual(result[0].body, "Test comment")

        # Verify the project_id from connection_details was used
        tracker._make_request.assert_any_call(mock_gl_instance.projects.get, "123")

    async def test_jira_tracker_get_issue_api_integration(self):
        """Test Jira tracker get_issue method works with API connection details format."""
        # Arrange - simulate how get_tracker_client creates connection_details for Jira
        connection_details = {
            "project_key": "TEST",
            "url": "https://test.atlassian.net",
            "username": "test@example.com",
        }

        tracker = JiraTracker("tracker-1", "api-token", connection_details)
        tracker.base_url = "https://test.atlassian.net"

        issue_data = {
            "id": "12345",
            "key": "TEST-123",
            "fields": {
                "summary": "Test Issue",
                "description": "Issue description",
                "status": {"name": "Open"},
                "created": "2023-01-01T10:00:00.000+0000",
                "updated": "2023-01-02T11:00:00.000+0000",
                "labels": ["bug"],
                "assignee": {"name": "testuser"},
            },
        }

        tracker._make_request = AsyncMock(return_value=issue_data)

        # Act
        result = await tracker.get_issue("TEST-123")

        # Assert
        self.assertEqual(result["external_id"], "12345")
        self.assertEqual(result["key"], "TEST-123")
        self.assertEqual(result["title"], "Test Issue")
        self.assertEqual(result["url"], "https://test.atlassian.net/browse/TEST-123")

        # Verify the correct API endpoint was called
        tracker._make_request.assert_called_once_with(
            "GET", "issue/TEST-123", api_version="3"
        )

    async def test_jira_tracker_get_comments_api_integration(self):
        """Test Jira tracker get_comments method works with API connection details format."""
        # Arrange
        connection_details = {
            "project_key": "TEST",
            "url": "https://test.atlassian.net",
            "username": "test@example.com",
        }

        tracker = JiraTracker("tracker-1", "api-token", connection_details)
        tracker.base_url = "https://test.atlassian.net"

        comments_data = {
            "comments": [
                {
                    "id": "1001",
                    "body": "Test comment",
                    "created": "2023-01-01T12:00:00.000+0000",
                    "updated": "2023-01-01T12:00:00.000+0000",
                    "author": {
                        "accountId": "101",
                        "displayName": "Test User",
                        "avatarUrls": {"48x48": "https://avatar.png"},
                    },
                }
            ]
        }

        tracker._make_request = AsyncMock(return_value=comments_data)

        # Act
        result = await tracker.get_comments("TEST-123")

        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "1001")
        self.assertEqual(result[0].body, "Test comment")

        # Verify the correct API endpoint was called
        tracker._make_request.assert_called_once_with(
            "GET", "issue/TEST-123/comment", api_version="3"
        )

    async def test_tracker_get_projects_method_name_consistency(self):
        """Test that all trackers have get_projects method (not list_projects)."""
        # This test ensures the API fix we made is correct

        # Test GitHub tracker has get_projects
        github_tracker = GitHubTracker(
            "tracker-1", "api-key", {"owner": "test", "repo": "test"}
        )
        self.assertTrue(hasattr(github_tracker, "get_projects"))
        self.assertFalse(hasattr(github_tracker, "list_projects"))

        # Test GitLab tracker has get_projects
        with patch("spacesync.trackers.gitlab.gitlab.Gitlab"):
            gitlab_tracker = GitLabTracker(
                "tracker-1", "api-key", {"url": "https://gitlab.com"}
            )
            self.assertTrue(hasattr(gitlab_tracker, "get_projects"))
            self.assertFalse(hasattr(gitlab_tracker, "list_projects"))

        # Test Jira tracker has get_projects
        jira_tracker = JiraTracker(
            "tracker-1",
            "api-key",
            {"url": "https://test.atlassian.net", "username": "test@example.com"},
        )
        self.assertTrue(hasattr(jira_tracker, "get_projects"))
        self.assertFalse(hasattr(jira_tracker, "list_projects"))

    async def test_all_trackers_have_required_methods(self):
        """Test that all trackers implement the required get_issue and get_comments methods."""
        # Test GitHub tracker
        github_tracker = GitHubTracker(
            "tracker-1", "api-key", {"owner": "test", "repo": "test"}
        )
        self.assertTrue(hasattr(github_tracker, "get_issue"))
        self.assertTrue(hasattr(github_tracker, "get_comments"))
        self.assertTrue(callable(github_tracker.get_issue))
        self.assertTrue(callable(github_tracker.get_comments))

        # Test GitLab tracker
        with patch("spacesync.trackers.gitlab.gitlab.Gitlab"):
            gitlab_tracker = GitLabTracker(
                "tracker-1", "api-key", {"url": "https://gitlab.com"}
            )
            self.assertTrue(hasattr(gitlab_tracker, "get_issue"))
            self.assertTrue(hasattr(gitlab_tracker, "get_comments"))
            self.assertTrue(callable(gitlab_tracker.get_issue))
            self.assertTrue(callable(gitlab_tracker.get_comments))

        # Test Jira tracker
        jira_tracker = JiraTracker(
            "tracker-1",
            "api-key",
            {"url": "https://test.atlassian.net", "username": "test@example.com"},
        )
        self.assertTrue(hasattr(jira_tracker, "get_issue"))
        self.assertTrue(hasattr(jira_tracker, "get_comments"))
        self.assertTrue(callable(jira_tracker.get_issue))
        self.assertTrue(callable(jira_tracker.get_comments))
