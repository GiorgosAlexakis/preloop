import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import logging

from spacesync.trackers.jira import JiraTracker

# Suppress logging during tests unless specifically needed for debugging a test
logging.disable(logging.CRITICAL)

class TestJiraTrackerComments(unittest.TestCase):

    @patch('spacesync.trackers.jira.requests.get')
    def test_get_issues_fetches_and_transforms_comments(self, mock_requests_get):
        # --- Mock API Response for issues with comments ---
        mock_jira_response = MagicMock()
        mock_jira_response.status_code = 200
        mock_jira_response.json.return_value = {
            "issues": [
                {
                    "id": "10001",
                    "key": "PROJ-123",
                    "fields": {
                        "summary": "Test Issue with Comments",
                        "description": "This is a test issue.",
                        "status": {"name": "Open"},
                        "created": "2023-01-01T10:00:00.000+0000",
                        "updated": "2023-01-02T11:00:00.000+0000",
                        "labels": ["test-label"],
                        "assignee": {"displayName": "Test User", "name": "testuser", "accountId": "12345"},
                        "issuetype": {"name": "Bug"},
                        "comment": {
                            "comments": [
                                {
                                    "id": "20001",
                                    "author": {"displayName": "Commenter One", "name": "commenter1", "accountId": "67890"},
                                    "body": "First comment on the issue.",
                                    "created": "2023-01-01T12:00:00.000+0000",
                                    "updated": "2023-01-01T12:05:00.000+0000"
                                },
                                {
                                    "id": "20002",
                                    "author": {"displayName": "Commenter Two", "name": "commenter2", "accountId": "54321"},
                                    "body": "Second comment here.",
                                    "created": "2023-01-02T09:30:00.000+0000",
                                    "updated": "2023-01-02T09:30:00.000+0000"
                                }
                            ],
                            "maxResults": 50,
                            "total": 2,
                            "startAt": 0
                        }
                    }
                }
            ],
            "maxResults": 50,
            "total": 1,
            "startAt": 0
        }
        mock_requests_get.return_value = mock_jira_response

        # --- Initialize Tracker ---
        tracker = JiraTracker(
            tracker_id="test-jira-tracker",
            api_key="fake_api_key",
            connection_details={
                "jira_url": "https://test.jira.com",
                "username": "testuser"
            }
        )

        # --- Call get_issues ---
        issues_with_comments = tracker.get_issues(organization_id="any_org", project_id="PROJ")

        # --- Assertions ---
        self.assertEqual(len(issues_with_comments), 1, "Should return one issue")
        issue_data = issues_with_comments[0]

        self.assertEqual(issue_data["external_id"], "10001")
        self.assertEqual(issue_data["key"], "PROJ-123")
        self.assertEqual(issue_data["title"], "Test Issue with Comments")
        self.assertIn("comments", issue_data, "Issue data should contain 'comments' key")
        self.assertEqual(len(issue_data["comments"]), 2, "Should include two comments")

        # Assert first comment
        comment1_data = issue_data["comments"][0]
        self.assertEqual(comment1_data["id"], "20001")
        self.assertEqual(comment1_data["body"], "First comment on the issue.")
        self.assertEqual(comment1_data["author_id"], "67890")
        self.assertEqual(comment1_data["created_at"], datetime(2023, 1, 1, 12, 0, 0))
        self.assertEqual(comment1_data["updated_at"], datetime(2023, 1, 1, 12, 5, 0))
        expected_url1 = "https://test.jira.com/browse/PROJ-123?focusedCommentId=20001#comment-20001"
        self.assertEqual(comment1_data["url"], expected_url1)

        # Assert second comment
        comment2_data = issue_data["comments"][1]
        self.assertEqual(comment2_data["id"], "20002")
        self.assertEqual(comment2_data["body"], "Second comment here.")
        self.assertEqual(comment2_data["author_id"], "54321")
        self.assertEqual(comment2_data["created_at"], datetime(2023, 1, 2, 9, 30, 0))
        self.assertEqual(comment2_data["updated_at"], datetime(2023, 1, 2, 9, 30, 0))
        expected_url2 = "https://test.jira.com/browse/PROJ-123?focusedCommentId=20002#comment-20002"
        self.assertEqual(comment2_data["url"], expected_url2)

        # Verify API call
        expected_api_url = "https://test.jira.com/rest/api/2/search"
        expected_params = {
            "jql": "project = PROJ",
            "maxResults": 100,
            "fields": "id,key,summary,description,status,created,updated,labels,assignee,issuetype,comment",
        }
        mock_requests_get.assert_called_once_with(expected_api_url, headers=tracker.headers, params=expected_params)

if __name__ == '__main__':
    unittest.main()
