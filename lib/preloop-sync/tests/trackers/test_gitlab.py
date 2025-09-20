import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from spacesync.trackers.gitlab import GitLabTracker
# Assuming logger is available or mockable; for now, we proceed
# from spacesync.config import logger # If needed for more complex logger mocking


class TestGitLabTrackerComments(unittest.TestCase):
    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")  # Patch where it's looked up
    def test_get_issues_fetches_and_transforms_comments(self, mock_gitlab_constructor):
        # 1. Setup Mocks for GitLab API interaction
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None  # Mock auth call during init

        # Mock project object
        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"
        # Attributes that might be accessed by the tracker
        mock_project.attributes = {
            "id": "proj-123",
            "name": "Test Project",
            "web_url": "http://gitlab.com/testgroup/testproject",
            "path_with_namespace": "testgroup/testproject",  # Ensure this is available
        }
        mock_gl_instance.projects.get.return_value = mock_project

        # Mock issue object
        mock_issue1 = MagicMock()
        mock_issue1.iid = 1  # Internal ID for GitLab issues
        mock_issue1.title = "Test Issue 1"
        mock_issue1.description = "Description for issue 1"
        mock_issue1.state = "opened"
        mock_issue1.created_at = "2023-01-01T10:00:00.000Z"
        mock_issue1.updated_at = "2023-01-02T11:00:00.000Z"
        mock_issue1.web_url = "http://gitlab.com/testgroup/testproject/issues/1"
        mock_issue1.labels = ["bug", "critical"]
        mock_issue1.assignees = [{"username": "user1"}]
        # Ensure attributes are accessible if the code uses issue_obj.attribute
        for key, value in {
            "iid": 1,
            "title": "Test Issue 1",
            "description": "Description for issue 1",
            "state": "opened",
            "created_at": "2023-01-01T10:00:00.000Z",
            "updated_at": "2023-01-02T11:00:00.000Z",
            "web_url": "http://gitlab.com/testgroup/testproject/issues/1",
            "labels": ["bug", "critical"],
            "assignees": [{"username": "user1"}],
        }.items():
            setattr(mock_issue1, key, value)

        # Mock user comment (note)
        mock_note_user = MagicMock()
        mock_note_user.id = 101
        mock_note_user.body = "This is a user comment."
        mock_note_user.system = False
        mock_note_user.author = {
            "id": "user-id-1",
            "username": "commenter1",
            "name": "Commenter One",
        }
        mock_note_user.created_at = "2023-01-01T12:00:00.000Z"
        mock_note_user.updated_at = "2023-01-01T12:05:00.000Z"
        for key, value in {
            "id": 101,
            "body": "This is a user comment.",
            "system": False,
            "author": {
                "id": "user-id-1",
                "username": "commenter1",
                "name": "Commenter One",
            },
            "created_at": "2023-01-01T12:00:00.000Z",
            "updated_at": "2023-01-01T12:05:00.000Z",
        }.items():
            setattr(mock_note_user, key, value)

        # Mock system note
        mock_note_system = MagicMock()
        mock_note_system.id = 102
        mock_note_system.body = "User added label ~bug"
        mock_note_system.system = True
        mock_note_system.author = {
            "id": "user-id-2",
            "username": "gitlab-bot",
            "name": "GitLab Bot",
        }
        mock_note_system.created_at = "2023-01-01T13:00:00.000Z"
        mock_note_system.updated_at = "2023-01-01T13:00:00.000Z"
        for key, value in {
            "id": 102,
            "body": "User added label ~bug",
            "system": True,
            "author": {
                "id": "user-id-2",
                "username": "gitlab-bot",
                "name": "GitLab Bot",
            },
            "created_at": "2023-01-01T13:00:00.000Z",
            "updated_at": "2023-01-01T13:00:00.000Z",
        }.items():
            setattr(mock_note_system, key, value)

        mock_issue1.notes.list.return_value = [mock_note_user, mock_note_system]
        mock_project.issues.list.return_value = [mock_issue1]

        # 2. Initialize Tracker
        # Provide minimal connection_details as expected by the constructor
        tracker = GitLabTracker(
            tracker_id="test-gitlab-tracker",
            api_key="fake_token",
            connection_details={"url": "http://gitlab.com"},
        )

        # 3. Call get_issues
        issues_with_comments = tracker.get_issues(
            organization_id="org-1", project_id="proj-123"
        )

        # 4. Assertions
        self.assertEqual(len(issues_with_comments), 1, "Should return one issue")
        issue_data = issues_with_comments[0]

        self.assertIn(
            "comments", issue_data, "Issue data should contain 'comments' key"
        )
        self.assertEqual(
            len(issue_data["comments"]),
            1,
            "Should only include user comments, system notes filtered out",
        )

        comment_data = issue_data["comments"][0]
        self.assertEqual(comment_data["id"], str(mock_note_user.id))
        self.assertEqual(comment_data["body"], mock_note_user.body)
        self.assertEqual(comment_data["author"], mock_note_user.author["username"])
        self.assertEqual(
            comment_data["created_at"],
            datetime.strptime(mock_note_user.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"),
        )
        self.assertEqual(
            comment_data["updated_at"],
            datetime.strptime(mock_note_user.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"),
        )
        self.assertEqual(
            comment_data["url"], f"{mock_issue1.web_url}#note_{mock_note_user.id}"
        )

        # Verify API calls
        mock_gitlab_constructor.assert_called_once_with(
            "http://gitlab.com", private_token="fake_token"
        )
        mock_gl_instance.projects.get.assert_called_once_with("proj-123")
        mock_project.issues.list.assert_called_once_with(
            all=True, include_metadata=True
        )
        mock_issue1.notes.list.assert_called_once_with(
            all=True, sort="asc", order_by="created_at"
        )


if __name__ == "__main__":
    unittest.main()


class TestGitLabTracker(unittest.TestCase):
    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_get_organizations(self, mock_gitlab_constructor):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_group = MagicMock()
        mock_group.id = 1
        mock_group.name = "Test Group"
        mock_group.web_url = "http://gitlab.com/groups/test-group"
        mock_gl_instance.groups.list.return_value = [mock_group]

        tracker = GitLabTracker("tracker-1", "api-key", {})
        orgs = tracker.get_organizations()

        self.assertEqual(len(orgs), 1)
        self.assertEqual(orgs[0]["name"], "Test Group")

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_get_projects(self, mock_gitlab_constructor):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance

        mock_group = MagicMock()
        mock_gl_instance.groups.get.return_value = mock_group

        mock_project = MagicMock()
        mock_project.attributes = {
            "id": 1,
            "name": "Test Project",
            "description": "A test project",
            "web_url": "http://gitlab.com/test-group/test-project",
            "path_with_namespace": "test-group/test-project",
        }
        mock_group.projects.list.return_value = [mock_project]

        tracker = GitLabTracker("tracker-1", "api-key", {})
        projects = tracker.get_projects("group-1")

        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "Test Project")

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_get_issue(self, mock_gitlab_constructor):
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
        mock_project.issues.get.return_value = mock_issue

        tracker = GitLabTracker("tracker-1", "api-key", {})
        issue = tracker.get_issue("group-1", "proj-1", "1")

        # Verify API calls
        mock_gl_instance.projects.get.assert_called_once_with("proj-1")
        mock_project.issues.get.assert_called_once_with("1")

        # Verify issue data transformation
        self.assertEqual(issue["title"], "Test Issue")
        self.assertEqual(issue["external_id"], "12345")
        self.assertEqual(issue["key"], "testgroup/testproject#1")
        self.assertEqual(issue["state"], "opened")
        self.assertEqual(issue["labels"], ["bug", "critical"])
        self.assertEqual(issue["assignees"], ["user1"])
        self.assertEqual(issue["description"], "Description for issue")
        self.assertEqual(
            issue["created_at"],
            datetime.strptime("2023-01-01T10:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"),
        )
        self.assertEqual(
            issue["updated_at"],
            datetime.strptime("2023-01-02T11:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"),
        )
        self.assertEqual(
            issue["url"], "http://gitlab.com/testgroup/testproject/issues/1"
        )


class TestGitLabTrackerWebhooks(unittest.TestCase):
    @patch("spacesync.trackers.gitlab.crud_webhook")
    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_register_group_webhook_success(
        self, mock_gitlab_constructor, mock_crud_webhook
    ):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_group = MagicMock()
        mock_gl_instance.groups.get.return_value = mock_group
        mock_group.hooks.list.return_value = []  # No existing hooks

        mock_hook = MagicMock()
        mock_hook.id = "hook-123"
        mock_group.hooks.create.return_value = mock_hook

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_organization = MagicMock()
        mock_organization.identifier = "group-1"
        mock_organization.id = "org-db-id-1"

        result = tracker.register_group_webhook(
            mock_db_session,
            mock_organization,
            "http://test.com/webhook",
            "secret-token",
        )

        self.assertTrue(result)
        mock_group.hooks.create.assert_called_once()
        mock_crud_webhook.create.assert_called_once()

    @patch("spacesync.trackers.gitlab.crud_webhook")
    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_register_group_webhook_already_exists(
        self, mock_gitlab_constructor, mock_crud_webhook
    ):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_group = MagicMock()
        mock_gl_instance.groups.get.return_value = mock_group

        mock_existing_hook = MagicMock()
        mock_existing_hook.url = "http://test.com/webhook"
        mock_group.hooks.list.return_value = [mock_existing_hook]

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_organization = MagicMock()
        mock_organization.identifier = "group-1"

        result = tracker.register_group_webhook(
            mock_db_session,
            mock_organization,
            "http://test.com/webhook",
            "secret-token",
        )

        self.assertTrue(result)
        mock_group.hooks.create.assert_not_called()
        mock_crud_webhook.create.assert_not_called()

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_register_group_webhook_not_supported(self, mock_gitlab_constructor):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_group = MagicMock()
        mock_gl_instance.groups.get.return_value = mock_group

        # Simulate 404 error when listing hooks
        from gitlab.exceptions import GitlabListError

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_group.hooks.list.side_effect = GitlabListError(
            response_code=404, response_body="404 Group Hooks Not Found"
        )

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_organization = MagicMock()
        mock_organization.identifier = "group-1"

        result = tracker.register_group_webhook(
            mock_db_session,
            mock_organization,
            "http://test.com/webhook",
            "secret-token",
        )

        self.assertEqual(result, "group_hooks_not_supported")

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_register_group_webhook_api_error(self, mock_gitlab_constructor):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_group = MagicMock()
        mock_gl_instance.groups.get.return_value = mock_group
        mock_group.hooks.list.return_value = []  # No existing hooks

        # Simulate 500 error when creating hook
        from gitlab.exceptions import GitlabCreateError

        mock_group.hooks.create.side_effect = GitlabCreateError(
            response_code=500, response_body="Internal Server Error"
        )

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_organization = MagicMock()
        mock_organization.identifier = "group-1"

        result = tracker.register_group_webhook(
            mock_db_session,
            mock_organization,
            "http://test.com/webhook",
            "secret-token",
        )

        self.assertFalse(result)

    @patch("spacesync.trackers.gitlab.crud_webhook")
    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_register_project_webhook_success(
        self, mock_gitlab_constructor, mock_crud_webhook
    ):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_project = MagicMock()
        mock_gl_instance.projects.get.return_value = mock_project
        mock_project.hooks.list.return_value = []  # No existing hooks

        mock_hook = MagicMock()
        mock_hook.id = "hook-456"
        mock_project.hooks.create.return_value = mock_hook

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_db_project = MagicMock()
        mock_db_project.identifier = "proj-1"
        mock_db_project.id = "proj-db-id-1"

        result = tracker.register_project_webhook(
            mock_db_session,
            mock_db_project,
            "http://test.com/webhook",
            "secret-token",
        )

        self.assertTrue(result)
        mock_project.hooks.create.assert_called_once()
        mock_crud_webhook.create.assert_called_once()

    @patch("spacesync.trackers.gitlab.crud_webhook")
    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_register_project_webhook_already_exists(
        self, mock_gitlab_constructor, mock_crud_webhook
    ):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_project = MagicMock()
        mock_gl_instance.projects.get.return_value = mock_project

        mock_existing_hook = MagicMock()
        mock_existing_hook.url = "http://test.com/webhook"
        mock_project.hooks.list.return_value = [mock_existing_hook]

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_db_project = MagicMock()
        mock_db_project.identifier = "proj-1"

        result = tracker.register_project_webhook(
            mock_db_session,
            mock_db_project,
            "http://test.com/webhook",
            "secret-token",
        )

        self.assertTrue(result)
        mock_project.hooks.create.assert_not_called()
        mock_crud_webhook.create.assert_not_called()

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_register_project_webhook_api_error(self, mock_gitlab_constructor):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_project = MagicMock()
        mock_gl_instance.projects.get.return_value = mock_project
        mock_project.hooks.list.return_value = []  # No existing hooks

        # Simulate 500 error when creating hook
        from gitlab.exceptions import GitlabCreateError

        mock_project.hooks.create.side_effect = GitlabCreateError(
            response_code=500, response_body="Internal Server Error"
        )

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_db_project = MagicMock()
        mock_db_project.identifier = "proj-1"

        result = tracker.register_project_webhook(
            mock_db_session,
            mock_db_project,
            "http://test.com/webhook",
            "secret-token",
        )

        self.assertFalse(result)

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_unregister_project_webhook_success(self, mock_gitlab_constructor):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_project = MagicMock()
        mock_gl_instance.projects.get.return_value = mock_project

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_webhook = MagicMock()
        mock_webhook.project.identifier = "proj-1"
        mock_webhook.external_id = "hook-456"
        mock_webhook.organization = None

        result = tracker.unregister_webhook(mock_db_session, mock_webhook)

        self.assertTrue(result)
        mock_project.hooks.delete.assert_called_once_with("hook-456")

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_unregister_group_webhook_success(self, mock_gitlab_constructor):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_group = MagicMock()
        mock_gl_instance.groups.get.return_value = mock_group

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_webhook = MagicMock()
        mock_webhook.project = None
        mock_webhook.organization.identifier = "group-1"
        mock_webhook.external_id = "hook-123"

        result = tracker.unregister_webhook(mock_db_session, mock_webhook)

        self.assertTrue(result)
        mock_group.hooks.delete.assert_called_once_with("hook-123")

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_unregister_webhook_api_error(self, mock_gitlab_constructor):
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None

        mock_project = MagicMock()
        mock_gl_instance.projects.get.return_value = mock_project

        from gitlab.exceptions import GitlabDeleteError

        mock_project.hooks.delete.side_effect = GitlabDeleteError(
            response_code=500, response_body="Internal Server Error"
        )

        tracker = GitLabTracker("tracker-1", "api-key", {})
        mock_db_session = MagicMock()
        mock_webhook = MagicMock()
        mock_webhook.project.identifier = "proj-1"
        mock_webhook.external_id = "hook-456"
        mock_webhook.organization = None

        result = tracker.unregister_webhook(mock_db_session, mock_webhook)

        self.assertFalse(result)

    @patch("spacesync.trackers.gitlab.gitlab.Gitlab")
    def test_get_issue(self, mock_gitlab_constructor):
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
        mock_project.issues.get.return_value = mock_issue

        tracker = GitLabTracker("tracker-1", "api-key", {})
        issue = tracker.get_issue("group-1", "proj-1", "1")

        # Verify API calls
        mock_gl_instance.projects.get.assert_called_once_with("proj-1")
        mock_project.issues.get.assert_called_once_with("1")

        # Verify issue data transformation
        self.assertEqual(issue["title"], "Test Issue")
        self.assertEqual(issue["external_id"], "12345")
        self.assertEqual(issue["key"], "testgroup/testproject#1")
        self.assertEqual(issue["state"], "opened")
        self.assertEqual(issue["labels"], ["bug", "critical"])
        self.assertEqual(issue["assignees"], ["user1"])
        self.assertEqual(issue["description"], "Description for issue")
        self.assertEqual(
            issue["created_at"],
            datetime.strptime("2023-01-01T10:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"),
        )
        self.assertEqual(
            issue["updated_at"],
            datetime.strptime("2023-01-02T11:00:00.000Z", "%Y-%m-%dT%H:%M:%S.%fZ"),
        )
        self.assertEqual(
            issue["url"], "http://gitlab.com/testgroup/testproject/issues/1"
        )
