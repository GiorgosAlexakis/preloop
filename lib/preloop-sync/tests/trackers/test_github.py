import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from spacesync.trackers.github import GitHubTracker
from spacesync.exceptions import TrackerResponseError # For testing error paths if needed

class TestGitHubTrackerComments(unittest.TestCase):

    @patch('spacesync.trackers.github.requests.get')
    def test_get_issues_fetches_and_transforms_comments(self, mock_requests_get):
        # --- Mock API Responses --- 
        # Response for repo details (if project_id is not full_name)
        mock_repo_details_response = MagicMock()
        mock_repo_details_response.status_code = 200
        mock_repo_details_response.json.return_value = {
            "id": 1296269,
            "full_name": "octocat/Hello-World",
            "name": "Hello-World",
            # ... other fields if needed by the tracker
        }

        # Response for issues list
        mock_issues_list_response = MagicMock()
        mock_issues_list_response.status_code = 200
        mock_issues_list_response.json.return_value = [
            {
                "id": 1,
                "number": 1347,
                "title": "Found a bug",
                "body": "I'm having a problem with this.",
                "state": "open",
                "user": {"login": "octocat", "id": 1},
                "labels": [{"name": "bug"}],
                "assignees": [{"login": "octocat", "id": 1}],
                "created_at": "2011-04-22T13:33:48Z",
                "updated_at": "2011-04-22T13:33:48Z",
                "html_url": "https://github.com/octocat/Hello-World/issues/1347"
            }
        ]

        # Response for issue comments
        mock_comments_response = MagicMock()
        mock_comments_response.status_code = 200
        mock_comments_response.json.return_value = [
            {
                "id": 101,
                "user": {"login": "commenter", "id": 2},
                "body": "This is a comment on the issue.",
                "created_at": "2011-04-22T14:00:00Z",
                "updated_at": "2011-04-22T14:00:00Z",
                "html_url": "https://github.com/octocat/Hello-World/issues/1347#issuecomment-101"
            }
        ]

        # Configure mock_requests_get to return different responses based on URL
        def side_effect_requests_get(url, headers, params=None):
            if f"repositories/project-id-123" in url:
                return mock_repo_details_response # If project_id is an ID
            if f"repos/octocat/Hello-World/issues" == url.split('?')[0].replace(GitHubTracker.API_BASE_URL + "/", "") and params.get("state") == "all":
                 return mock_issues_list_response
            if f"repos/octocat/Hello-World/issues/1347/comments" in url:
                return mock_comments_response
            # Fallback for unexpected calls
            fallback_response = MagicMock()
            fallback_response.status_code = 404
            fallback_response.json.return_value = {"message": "Not Found"}
            print(f"UNMOCKED URL in test: {url} with params {params}") # For debugging tests
            return fallback_response

        mock_requests_get.side_effect = side_effect_requests_get

        # --- Initialize Tracker ---
        tracker = GitHubTracker(
            tracker_id="test-github-tracker",
            api_key="fake_token",
            connection_details={}
        )

        # --- Call get_issues ---
        # Using 'octocat/Hello-World' directly as project_id to simplify one mock path
        issues_with_comments = tracker.get_issues(organization_id="octocat", project_id="octocat/Hello-World")

        # --- Assertions ---
        self.assertEqual(len(issues_with_comments), 1, "Should return one issue")
        issue_data = issues_with_comments[0]

        self.assertEqual(issue_data["external_id"], "1")
        self.assertEqual(issue_data["key"], "octocat/Hello-World#1347")
        self.assertEqual(issue_data["title"], "Found a bug")
        self.assertIn("comments", issue_data, "Issue data should contain 'comments' key")
        self.assertEqual(len(issue_data["comments"]), 1, "Should include one comment")

        comment_data = issue_data["comments"][0]
        self.assertEqual(comment_data["id"], "101")
        self.assertEqual(comment_data["body"], "This is a comment on the issue.")
        self.assertEqual(comment_data["author_id"], "2")
        self.assertEqual(comment_data["author_name"], "commenter")
        self.assertEqual(comment_data["created_at"], datetime.strptime("2011-04-22T14:00:00Z", "%Y-%m-%dT%H:%M:%SZ"))
        self.assertEqual(comment_data["url"], "https://github.com/octocat/Hello-World/issues/1347#issuecomment-101")

        # Verify API calls (simplified check of calls made)
        # Check that requests.get was called at least for issues and comments
        # A more specific check would involve asserting call_args_list
        self.assertTrue(mock_requests_get.call_count >= 2) 
        # Example of more specific call assertion:
        # mock_requests_get.assert_any_call(f"{GitHubTracker.API_BASE_URL}/repos/octocat/Hello-World/issues", headers=tracker.headers, params={'state': 'all', 'per_page': 100, 'sort': 'updated', 'direction': 'desc'})
        # mock_requests_get.assert_any_call(f"{GitHubTracker.API_BASE_URL}/repos/octocat/Hello-World/issues/1347/comments", headers=tracker.headers, params={'per_page': 100})

if __name__ == '__main__':
    unittest.main()
