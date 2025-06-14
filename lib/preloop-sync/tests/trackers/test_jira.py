import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import json # For creating content bytes for mock response
import requests # For spec in MagicMock
from jira import JIRAError

from spacesync.trackers.jira import JiraTracker
from spacesync.exceptions import TrackerAuthenticationError

class TestJiraTrackerComments(unittest.TestCase):

    @patch('spacesync.trackers.jira.requests.request') # Outer patch: For JiraTracker._make_request
    @patch('spacesync.trackers.jira.JIRA')          # Inner patch: For JIRA client __init__
    def test_get_issues_fetches_and_transforms_comments(self, mock_jira_class, mock_http_request_method):
        # 1. Mock JIRA client initialization (for server_info)
        mock_jira_client_instance = MagicMock()
        mock_jira_class.return_value = mock_jira_client_instance
        mock_jira_client_instance.server_info.return_value = { # This is what jira.JIRA().server_info() returns
            "baseUrl": "https://test.jira.com",
            "versionNumbers": [8, 20, 0],
            "serverTitle": "JIRA"
        }

        # 2. Prepare mock response for the /search API call made by JiraTracker._make_request
        # This is the dictionary that the actual response.json() from Jira API would return
        jira_search_api_response_json = {
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
                            "maxResults": 50, "total": 2, "startAt": 0
                        }
                    }
                }
            ],
            "maxResults": 50, "total": 1, "startAt": 0
        }

        # This mock object simulates a requests.Response object
        mock_search_response_obj = MagicMock(spec=requests.Response)
        mock_search_response_obj.status_code = 200
        mock_search_response_obj.ok = True
        mock_search_response_obj.json.return_value = jira_search_api_response_json
        # Ensure .content is truthy for JiraTracker._make_request logic
        mock_search_response_obj.content = json.dumps(jira_search_api_response_json).encode('utf-8')
        mock_search_response_obj.text = json.dumps(jira_search_api_response_json) # For completeness

        # Configure side_effect for the patched spacesync.trackers.jira.requests.request method
        def http_request_side_effect(method, url, headers=None, params=None, json=None, **kwargs):
            # This side_effect is for calls made by JiraTracker._make_request
            if method.upper() == 'GET' and "/rest/api/2/search" in url:
                # Basic check for JQL to ensure it's the issue search call
                if params and "project = PROJ" in params.get("jql", ""):
                    return mock_search_response_obj

            # Fallback for any other calls that might slip through or for debugging.
            # We don't expect other calls to the global 'spacesync.trackers.jira.requests.request'
            # from the code under test in this specific test case, as JIRA client init is fully mocked.
            raise Exception(
                f"Unexpected HTTP call to 'spacesync.trackers.jira.requests.request': "
                f"{method} {url} with params {params}"
            )

        mock_http_request_method.side_effect = http_request_side_effect

        # 3. Initialize Tracker
        # JiraTracker.__init__ will use mock_jira_class, so self.jira_client will be a mock.
        # The self.jira_client.server_info() call during init will use mock_jira_client_instance.server_info.
        tracker = JiraTracker(
            tracker_id="test-jira-tracker",
            api_key="fake_api_key",
            connection_details={
                "jira_url": "https://test.jira.com",
                "username": "testuser"
            }
        )

        # 4. Call get_issues
        # This will call tracker._make_request, which will use the mocked mock_http_request_method.
        issues_with_comments = tracker.get_issues(organization_id="any_org", project_id="PROJ")

        # 5. Assertions (should be same as original problem description's intent)
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

        # 6. Verify the call to requests.request (via _make_request)
        expected_search_url = "https://test.jira.com/rest/api/2/search"
        expected_jql = "project = PROJ" # As constructed in get_issues
        expected_search_params = {
            "jql": expected_jql,
            "maxResults": 100, # Hardcoded in JiraTracker.get_issues
            "fields": "id,key,summary,description,status,created,updated,labels,assignee,issuetype,comment", # Hardcoded
        }

        # JiraTracker._make_request calls requests.request(method, url, headers=self.headers, params=params, json=json_data)
        # For get_issues, method="GET", json_data=None.
        mock_http_request_method.assert_called_once_with(
            'GET',
            expected_search_url,
            headers=tracker.headers, # The headers initialized in JiraTracker
            params=expected_search_params,
            json=None # _make_request passes json_data=None for GET requests
        )

class TestJiraTrackerWebhooks(unittest.TestCase):

    def setUp(self):
        # Basic setup for all webhook tests
        self.mock_jira_patcher = patch('spacesync.trackers.jira.JIRA')
        self.mock_jira_class = self.mock_jira_patcher.start()

        self.mock_jira_client = MagicMock()
        self.mock_jira_class.return_value = self.mock_jira_client

        self.tracker = JiraTracker(
            tracker_id="test-webhook-tracker",
            api_key="fake_key",
            connection_details={
                "jira_url": "https://myjira.atlassian.net",
                "username": "user@example.com"
            }
        )

    def tearDown(self):
        self.mock_jira_patcher.stop()

    def test_register_webhook_success(self):
        """Test successful webhook registration."""
        self.mock_jira_client._session.post.return_value = MagicMock(status_code=201)

        result = self.tracker.register_webhook(
            project_key="TEST",
            webhook_url="https://example.com/webhook",
            secret="mysecret"
        )

        self.assertTrue(result)
        self.mock_jira_client._session.post.assert_called_once()
        call_args = self.mock_jira_client._session.post.call_args
        self.assertEqual(call_args[0][0], "https://myjira.atlassian.net/rest/webhooks/1.0/webhook")
        self.assertIn("SpaceBridge Sync for TEST", call_args[1]['json']['name'])
        self.assertIn("secret=mysecret", call_args[1]['json']['url'])
        self.assertIn("project_key=TEST", call_args[1]['json']['url'])

    def test_register_webhook_already_exists(self):
        """Test registration when webhook already exists (Jira 400 error)."""
        error_text = "webhook with same name and url already exists"
        self.mock_jira_client._session.post.side_effect = JIRAError(status_code=400, text=error_text)

        with self.assertLogs('spacesync.trackers.jira', level='WARNING') as cm:
            result = self.tracker.register_webhook(
                project_key="TEST",
                webhook_url="https://example.com/webhook",
                secret="mysecret"
            )
            self.assertTrue(result)
            # Check that a warning was logged about the webhook already existing
            self.assertTrue(any("already exists" in log_msg for log_msg in cm.output))

    def test_register_webhook_permission_denied(self):
        """Test registration failure due to permissions (Jira 403 error)."""
        error_text = "You do not have permission to configure webhooks for this project."
        self.mock_jira_client._session.post.side_effect = JIRAError(status_code=403, text=error_text)

        with self.assertRaises(TrackerAuthenticationError) as e:
            self.tracker.register_webhook(
                project_key="TEST",
                webhook_url="https://example.com/webhook",
                secret="mysecret"
            )
        self.assertIn("Jira permission denied", str(e.exception))


    def test_register_webhook_no_client(self):
        """Test registration when Jira client is not initialized."""
        self.tracker.jira_client = None
        with self.assertLogs('spacesync.trackers.jira', level='ERROR') as cm:
            result = self.tracker.register_webhook(
                project_key="TEST",
                webhook_url="https://example.com/webhook",
                secret="mysecret"
            )
            self.assertFalse(result)
            self.assertTrue(any("Jira client not initialized" in log_msg for log_msg in cm.output))


if __name__ == '__main__':
    unittest.main()
