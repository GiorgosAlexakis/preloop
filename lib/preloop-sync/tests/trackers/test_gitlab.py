import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from spacesync.trackers.gitlab import GitLabTracker
# Assuming logger is available or mockable; for now, we proceed
# from spacesync.config import logger # If needed for more complex logger mocking

class TestGitLabTrackerComments(unittest.TestCase):

    @patch('spacesync.trackers.gitlab.gitlab.Gitlab') # Patch where it's looked up
    def test_get_issues_fetches_and_transforms_comments(self, mock_gitlab_constructor):
        # 1. Setup Mocks for GitLab API interaction
        mock_gl_instance = MagicMock()
        mock_gitlab_constructor.return_value = mock_gl_instance
        mock_gl_instance.auth.return_value = None # Mock auth call during init

        # Mock project object
        mock_project = MagicMock()
        mock_project.path_with_namespace = "testgroup/testproject"
        # Attributes that might be accessed by the tracker
        mock_project.attributes = {
            'id': 'proj-123',
            'name': 'Test Project',
            'web_url': 'http://gitlab.com/testgroup/testproject',
            'path_with_namespace': "testgroup/testproject" # Ensure this is available
        }
        mock_gl_instance.projects.get.return_value = mock_project

        # Mock issue object
        mock_issue1 = MagicMock()
        mock_issue1.iid = 1 # Internal ID for GitLab issues
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
            "iid": 1, "title": "Test Issue 1", "description": "Description for issue 1",
            "state": "opened", "created_at": "2023-01-01T10:00:00.000Z",
            "updated_at": "2023-01-02T11:00:00.000Z", "web_url": "http://gitlab.com/testgroup/testproject/issues/1",
            "labels": ["bug", "critical"], "assignees": [{"username": "user1"}]
        }.items():
            setattr(mock_issue1, key, value)

        # Mock user comment (note)
        mock_note_user = MagicMock()
        mock_note_user.id = 101
        mock_note_user.body = "This is a user comment."
        mock_note_user.system = False
        mock_note_user.author = {"id": "user-id-1", "username": "commenter1", "name": "Commenter One"}
        mock_note_user.created_at = "2023-01-01T12:00:00.000Z"
        mock_note_user.updated_at = "2023-01-01T12:05:00.000Z"
        for key, value in {
            "id": 101, "body": "This is a user comment.", "system": False,
            "author": {"id": "user-id-1", "username": "commenter1", "name": "Commenter One"},
            "created_at": "2023-01-01T12:00:00.000Z", "updated_at": "2023-01-01T12:05:00.000Z"
        }.items():
            setattr(mock_note_user, key, value)

        # Mock system note
        mock_note_system = MagicMock()
        mock_note_system.id = 102
        mock_note_system.body = "User added label ~bug"
        mock_note_system.system = True
        mock_note_system.author = {"id": "user-id-2", "username": "gitlab-bot", "name": "GitLab Bot"}
        mock_note_system.created_at = "2023-01-01T13:00:00.000Z"
        mock_note_system.updated_at = "2023-01-01T13:00:00.000Z"
        for key, value in {
            "id": 102, "body": "User added label ~bug", "system": True,
            "author": {"id": "user-id-2", "username": "gitlab-bot", "name": "GitLab Bot"},
            "created_at": "2023-01-01T13:00:00.000Z", "updated_at": "2023-01-01T13:00:00.000Z"
        }.items():
            setattr(mock_note_system, key, value)

        mock_issue1.notes.list.return_value = [mock_note_user, mock_note_system]
        mock_project.issues.list.return_value = [mock_issue1]

        # 2. Initialize Tracker
        # Provide minimal connection_details as expected by the constructor
        tracker = GitLabTracker(
            tracker_id="test-gitlab-tracker", 
            api_key="fake_token", 
            connection_details={"url": "http://gitlab.com"}
        )

        # 3. Call get_issues
        issues_with_comments = tracker.get_issues(organization_id="org-1", project_id="proj-123")

        # 4. Assertions
        self.assertEqual(len(issues_with_comments), 1, "Should return one issue")
        issue_data = issues_with_comments[0]

        self.assertIn("comments", issue_data, "Issue data should contain 'comments' key")
        self.assertEqual(len(issue_data["comments"]), 1, "Should only include user comments, system notes filtered out")

        comment_data = issue_data["comments"][0]
        self.assertEqual(comment_data["id"], str(mock_note_user.id))
        self.assertEqual(comment_data["body"], mock_note_user.body)
        self.assertEqual(comment_data["author_id"], mock_note_user.author["id"])
        self.assertEqual(comment_data["author_name"], mock_note_user.author["username"])
        self.assertEqual(comment_data["created_at"], datetime.strptime(mock_note_user.created_at, "%Y-%m-%dT%H:%M:%S.%fZ"))
        self.assertEqual(comment_data["updated_at"], datetime.strptime(mock_note_user.updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"))
        self.assertEqual(comment_data["url"], f"{mock_issue1.web_url}#note_{mock_note_user.id}")

        # Verify API calls
        mock_gitlab_constructor.assert_called_once_with("http://gitlab.com", private_token="fake_token")
        mock_gl_instance.projects.get.assert_called_once_with("proj-123")
        mock_project.issues.list.assert_called_once_with(all=True, include_metadata=True)
        mock_issue1.notes.list.assert_called_once_with(all=True, sort='asc', order_by='created_at')

if __name__ == '__main__':
    unittest.main()
