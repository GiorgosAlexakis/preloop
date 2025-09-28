import pytest
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import httpx
from spacesync.exceptions import (
    TrackerAuthenticationError,
    TrackerConnectionError,
    TrackerResponseError,
)

from spacesync.trackers.github import GitHubTracker


@pytest.mark.asyncio
class TestGitHubTrackerDependencies(unittest.IsolatedAsyncioTestCase):
    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_get_issues_parses_dependencies_from_body_and_comments(
        self, mock_requests_get
    ):
        """Test that dependency parsing is integrated into issue fetching."""
        # Mock API responses
        mock_issues_response = {
            "json": MagicMock(
                return_value=[
                    {
                        "id": 1,
                        "number": 1,
                        "title": "Test issue",
                        "body": "This closes #123 and fixes owner/other-repo#456",
                        "state": "open",
                        "created_at": "2023-01-01T00:00:00Z",
                        "updated_at": "2023-01-01T00:00:00Z",
                        "user": {
                            "id": 1,
                            "login": "testuser",
                            "avatar_url": "https://avatar.url",
                        },
                    }
                ]
            ),
            "status_code": 200,
            "links": {},
        }

        mock_comments_response = {
            "json": MagicMock(
                return_value=[
                    {
                        "id": 1,
                        "body": "This relates to #789",
                        "created_at": "2023-01-01T01:00:00Z",
                        "updated_at": "2023-01-01T01:00:00Z",
                        "html_url": "https://github.com/owner/repo/issues/1#issuecomment-1",
                        "user": {
                            "id": 1,
                            "login": "testuser",
                            "avatar_url": "https://avatar.url",
                        },
                    }
                ]
            ),
            "status_code": 200,
            "links": {},
        }

        # Set up mock responses
        mock_requests_get.side_effect = [
            MagicMock(**mock_issues_response),  # Issues response
            MagicMock(**mock_comments_response),  # Comments response
        ]

        # Create tracker instance
        tracker = GitHubTracker("test-tracker", "test-token", {})

        # Call get_issues
        issues = await tracker.get_issues("test-org", "owner/repo")

        # Verify the issue was processed and dependencies were parsed
        assert len(issues) == 1
        issue = issues[0]

        # Check that dependencies were parsed and added
        assert "dependencies" in issue
        dependencies = issue["dependencies"]

        # Should have 3 dependencies: 2 from body + 1 from comment
        assert len(dependencies) == 3

        # Check dependencies from body
        body_deps = [
            d
            for d in dependencies
            if d["target_key"] in ["owner/repo#123", "owner/other-repo#456"]
        ]
        assert len(body_deps) == 2
        assert any(
            d["type"] == "closes" and d["target_key"] == "owner/repo#123"
            for d in body_deps
        )
        assert any(
            d["type"] == "closes" and d["target_key"] == "owner/other-repo#456"
            for d in body_deps
        )

        # Check dependency from comment
        comment_deps = [d for d in dependencies if d["target_key"] == "owner/repo#789"]
        assert len(comment_deps) == 1
        assert comment_deps[0]["type"] == "related"


@pytest.mark.asyncio
class TestGitHubTrackerComments(unittest.IsolatedAsyncioTestCase):
    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_get_issues_fetches_and_transforms_comments(self, mock_requests_get):
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
                "html_url": "https://github.com/octocat/Hello-World/issues/1347",
            }
        ]

        # Response for issue comments
        mock_comments_response = MagicMock()
        mock_comments_response.status_code = 200
        mock_comments_response.json.return_value = [
            {
                "id": 101,
                "user": {"login": "commenter", "id": 2, "avatar_url": ""},
                "body": "This is a comment on the issue.",
                "created_at": "2011-04-22T14:00:00Z",
                "updated_at": "2011-04-22T14:00:00Z",
                "html_url": "https://github.com/octocat/Hello-World/issues/1347#issuecomment-101",
            }
        ]

        # Configure mock_requests_get to return different responses based on URL
        async def side_effect_requests_get(url, headers, params=None):
            if "repositories/project-id-123" in url:
                return mock_repo_details_response  # If project_id is an ID
            if (
                "repos/octocat/Hello-World/issues"
                == url.split("?")[0].replace(GitHubTracker.API_BASE_URL + "/", "")
                and params.get("state") == "all"
            ):
                return mock_issues_list_response
            if "repos/octocat/Hello-World/issues/1347/comments" in url:
                return mock_comments_response
            # Fallback for unexpected calls
            fallback_response = MagicMock()
            fallback_response.status_code = 404
            fallback_response.json.return_value = {"message": "Not Found"}
            print(
                f"UNMOCKED URL in test: {url} with params {params}"
            )  # For debugging tests
            return fallback_response

        mock_requests_get.side_effect = side_effect_requests_get

        # --- Initialize Tracker ---
        tracker = GitHubTracker(
            tracker_id="test-github-tracker",
            api_key="fake_token",
            connection_details={},
        )

        # --- Call get_issues ---
        # Using 'octocat/Hello-World' directly as project_id to simplify one mock path
        raw_issues = await tracker.get_issues(
            organization_id="octocat", project_id="octocat/Hello-World"
        )

        # --- Assertions ---
        self.assertEqual(len(raw_issues), 1, "Should return one issue")

        project_mock = MagicMock()
        project_mock.id = "proj-123"
        project_mock.slug = "octocat/Hello-World"
        transformed_issue = tracker.transform_issue(raw_issues[0], project_mock)

        self.assertEqual(transformed_issue["external_id"], "1")
        self.assertEqual(transformed_issue["key"], "octocat/Hello-World#1347")
        self.assertEqual(transformed_issue["title"], "Found a bug")
        self.assertEqual(
            len(transformed_issue["comments"]), 1, "Should include one comment"
        )

        comment_data = transformed_issue["comments"][0]
        self.assertEqual(comment_data.id, "101")
        self.assertEqual(comment_data.body, "This is a comment on the issue.")
        self.assertEqual(comment_data.author.name, "commenter")
        self.assertEqual(
            comment_data.created_at,
            datetime.strptime("2011-04-22T14:00:00Z", "%Y-%m-%dT%H:%M:%SZ"),
        )

        # Verify API calls (simplified check of calls made)
        # Check that requests.get was called at least for issues and comments
        # A more specific check would involve asserting call_args_list
        self.assertTrue(mock_requests_get.call_count >= 2)


@pytest.mark.asyncio
class TestGitHubTracker(unittest.IsolatedAsyncioTestCase):
    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_get_organizations(self, mock_requests_get):
        mock_user_response = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            "login": "octocat",
            "html_url": "https://github.com/octocat",
        }

        mock_orgs_response = MagicMock()
        mock_orgs_response.status_code = 200
        mock_orgs_response.json.return_value = [
            {
                "id": 1,
                "login": "github",
                "url": "https://api.github.com/orgs/github",
            }
        ]

        mock_requests_get.side_effect = [mock_user_response, mock_orgs_response]

        tracker = GitHubTracker("tracker-1", "api-key", {})
        orgs = await tracker.get_organizations()

        self.assertEqual(len(orgs), 2)
        self.assertEqual(orgs[0]["name"], "octocat")
        self.assertEqual(orgs[1]["name"], "github")

    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_get_projects(self, mock_requests_get):
        mock_repos_response = MagicMock()
        mock_repos_response.status_code = 200
        mock_repos_response.json.return_value = [
            {
                "id": 1296269,
                "name": "Hello-World",
                "full_name": "octocat/Hello-World",
                "description": "My first repository on GitHub!",
                "html_url": "https://github.com/octocat/Hello-World",
                "default_branch": "main",
                "language": "JavaScript",
                "created_at": "2011-01-26T19:01:12Z",
                "pushed_at": "2011-01-26T19:14:43Z",
                "stargazers_count": 80,
            }
        ]
        mock_requests_get.return_value = mock_repos_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        projects = await tracker.get_projects("octocat")

        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "Hello-World")

    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_get_projects_personal(self, mock_requests_get):
        mock_repos_response = MagicMock()
        mock_repos_response.status_code = 200
        mock_repos_response.json.return_value = [
            {
                "id": 1296269,
                "name": "Hello-World",
                "full_name": "octocat/Hello-World",
                "description": "My first repository on GitHub!",
                "html_url": "https://github.com/octocat/Hello-World",
                "default_branch": "main",
                "language": "JavaScript",
                "created_at": "2011-01-26T19:01:12Z",
                "pushed_at": "2011-01-26T19:14:43Z",
                "stargazers_count": 80,
            }
        ]
        mock_requests_get.return_value = mock_repos_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        projects = await tracker.get_projects("personal")

        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "Hello-World")
        mock_requests_get.assert_called_with(
            "https://api.github.com/user/repos",
            headers=tracker.headers,
            params={"per_page": 100, "sort": "updated", "direction": "desc"},
        )

    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_get_issues_repo_details_error(self, mock_requests_get):
        mock_requests_get.side_effect = TrackerResponseError("Failed to fetch")

        tracker = GitHubTracker("tracker-1", "api-key", {})
        issues = await tracker.get_issues("octocat", "12345")

        self.assertEqual(len(issues), 0)

    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_get_issues_fetch_error(self, mock_requests_get):
        mock_repo_details_response = MagicMock()
        mock_repo_details_response.status_code = 200
        mock_repo_details_response.json.return_value = {
            "full_name": "octocat/Hello-World"
        }

        async def side_effect(*args, **kwargs):
            if "repositories" in args[0]:
                return mock_repo_details_response
            else:
                raise TrackerResponseError("Failed to fetch")

        mock_requests_get.side_effect = side_effect

        tracker = GitHubTracker("tracker-1", "api-key", {})
        issues = await tracker.get_issues("octocat", "12345")

        self.assertEqual(len(issues), 0)

    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_get_issues_skips_pull_requests(self, mock_requests_get):
        mock_issues_response = MagicMock()
        mock_issues_response.status_code = 200
        mock_issues_response.json.return_value = [
            {
                "id": 1,
                "number": 1347,
                "title": "Found a bug",
                "pull_request": {},
            }
        ]
        mock_requests_get.return_value = mock_issues_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        issues = await tracker.get_issues("octocat", "octocat/Hello-World")

        self.assertEqual(len(issues), 0)

    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_get_issues_no_comments(self, mock_requests_get):
        mock_issues_response = MagicMock()
        mock_issues_response.status_code = 200
        mock_issues_response.json.return_value = [
            {
                "id": 1,
                "number": 1347,
                "title": "Found a bug",
                "body": "I'm having a problem with this.",
                "state": "open",
                "user": {"login": "octocat"},
                "labels": [],
                "assignees": [],
                "created_at": "2011-04-22T13:33:48Z",
                "updated_at": "2011-04-22T13:33:48Z",
                "html_url": "https://github.com/octocat/Hello-World/issues/1347",
            }
        ]

        mock_comments_response = MagicMock()
        mock_comments_response.status_code = 200
        mock_comments_response.json.return_value = []

        async def side_effect(*args, **kwargs):
            if "comments" in args[0]:
                return mock_comments_response
            return mock_issues_response

        mock_requests_get.side_effect = side_effect

        tracker = GitHubTracker("tracker-1", "api-key", {})
        issues = await tracker.get_issues("octocat", "octocat/Hello-World")

        self.assertEqual(len(issues), 1)
        self.assertEqual(len(issues[0]["comments"]), 0)


@pytest.mark.asyncio
class TestGitHubTrackerRequestErrors(unittest.IsolatedAsyncioTestCase):
    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_make_request_authentication_error(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_requests_get.return_value = mock_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        with self.assertRaises(TrackerAuthenticationError):
            await tracker._make_request("user")

    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_make_request_connection_error(self, mock_requests_get):
        mock_requests_get.side_effect = httpx.RequestError(
            "Connection failed", request=MagicMock()
        )

        tracker = GitHubTracker("tracker-1", "api-key", {})
        with self.assertRaises(TrackerConnectionError):
            await tracker._make_request("user")

    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_make_request_response_error(self, mock_requests_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_requests_get.return_value = mock_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        with self.assertRaises(TrackerResponseError):
            await tracker._make_request("user")


@pytest.mark.asyncio
class TestGitHubTrackerDeleteRequest(unittest.IsolatedAsyncioTestCase):
    @patch("spacesync.trackers.github.httpx.AsyncClient.delete")
    async def test_make_request_delete_success(self, mock_requests_delete):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_requests_delete.return_value = mock_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        self.assertTrue(await tracker._make_request_delete("hooks/1"))

    @patch("spacesync.trackers.github.httpx.AsyncClient.delete")
    async def test_make_request_delete_not_found(self, mock_requests_delete):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests_delete.return_value = mock_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        self.assertTrue(await tracker._make_request_delete("hooks/1"))

    @patch("spacesync.trackers.github.httpx.AsyncClient.delete")
    async def test_make_request_delete_authentication_error(self, mock_requests_delete):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_requests_delete.return_value = mock_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        with self.assertRaises(TrackerAuthenticationError):
            await tracker._make_request_delete("hooks/1")

    @patch("spacesync.trackers.github.httpx.AsyncClient.delete")
    async def test_make_request_delete_connection_error(self, mock_requests_delete):
        mock_requests_delete.side_effect = httpx.RequestError(
            "Connection failed", request=MagicMock()
        )

        tracker = GitHubTracker("tracker-1", "api-key", {})
        with self.assertRaises(TrackerConnectionError):
            await tracker._make_request_delete("hooks/1")

    @patch("spacesync.trackers.github.httpx.AsyncClient.delete")
    async def test_make_request_delete_response_error(self, mock_requests_delete):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_requests_delete.return_value = mock_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        with self.assertRaises(TrackerResponseError):
            await tracker._make_request_delete("hooks/1")


@pytest.mark.asyncio
class TestGitHubTrackerWebhooks(unittest.IsolatedAsyncioTestCase):
    @patch("spacesync.trackers.github.GitHubTracker.get_projects")
    @patch("spacesync.trackers.github.GitHubTracker._make_request")
    async def test_get_webhooks(self, mock_make_request, mock_get_projects):
        mock_get_projects.return_value = [
            {"meta_data": {"full_name": "octocat/Hello-World"}}
        ]
        mock_make_request.return_value = [
            {
                "id": 1,
                "url": "https://example.com/webhook",
                "config": {"url": "https://example.com/webhook"},
            }
        ]

        tracker = GitHubTracker("tracker-1", "api-key", {})
        webhooks = await tracker.get_webhooks("octocat")

        self.assertEqual(len(webhooks), 1)
        self.assertEqual(webhooks[0]["id"], 1)
        mock_make_request.assert_called_with(
            "repos/octocat/Hello-World/hooks", params={"per_page": 100}
        )

    @patch("spacesync.trackers.github.httpx.AsyncClient.post")
    @patch("spacesync.trackers.github.crud_webhook.create")
    async def test_register_webhook(self, mock_crud_create, mock_requests_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": 1,
            "url": "https://example.com/webhook",
            "config": {"url": "https://example.com/webhook"},
        }
        mock_requests_post.return_value = mock_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        db_mock = MagicMock()
        organization_mock = MagicMock()
        organization_mock.identifier = "octocat"
        result = await tracker.register_webhook(
            db=db_mock,
            organization=organization_mock,
            webhook_url="https://example.com/webhook",
            secret="secret",
        )

        self.assertTrue(result)

    @patch("spacesync.trackers.github.crud_webhook.remove")
    @patch("spacesync.trackers.github.httpx.AsyncClient.delete")
    async def test_unregister_webhook(self, mock_requests_delete, mock_crud_remove):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_requests_delete.return_value = mock_response

        tracker = GitHubTracker("tracker-1", "api-key", {})
        db_mock = MagicMock()
        webhook_mock = MagicMock()
        webhook_mock.id = "webhook-db-id"
        webhook_mock.external_id = "1"
        webhook_mock.project.slug = "octocat/Hello-World"
        webhook_mock.organization.identifier = "octocat"
        result = await tracker.unregister_webhook(db=db_mock, webhook=webhook_mock)

        self.assertTrue(result)
        mock_requests_delete.assert_called_with(
            "https://api.github.com/repos/octocat/Hello-World/hooks/1",
            headers=tracker.headers,
        )
        mock_crud_remove.assert_called_with(db_mock, id="webhook-db-id")

    @patch("spacesync.trackers.github.GitHubTracker._make_request")
    async def test_is_webhook_registered_for_project(self, mock_make_request):
        mock_make_request.return_value = [
            {"config": {"url": "https://example.com/webhook"}}
        ]

        tracker = GitHubTracker("tracker-1", "api-key", {})
        project_mock = MagicMock()
        project_mock.slug = "octocat/Hello-World"
        is_registered = await tracker.is_webhook_registered_for_project(
            project_mock, "https://example.com/webhook"
        )

        self.assertTrue(is_registered)
        mock_make_request.assert_called_with("repos/octocat/Hello-World/hooks")

    @patch("spacesync.trackers.github.GitHubTracker._make_request")
    async def test_is_webhook_not_registered_for_project(self, mock_make_request):
        mock_make_request.return_value = [
            {"config": {"url": "https://example.com/other-webhook"}}
        ]

        tracker = GitHubTracker("tracker-1", "api-key", {})
        project_mock = MagicMock()
        project_mock.slug = "octocat/Hello-World"
        is_registered = await tracker.is_webhook_registered_for_project(
            project_mock, "https://example.com/webhook"
        )

        self.assertFalse(is_registered)
        mock_make_request.assert_called_with("repos/octocat/Hello-World/hooks")


class TestGitHubTrackerPagination(unittest.IsolatedAsyncioTestCase):
    @patch("spacesync.trackers.github.httpx.AsyncClient.get")
    async def test_make_request_pagination(self, mock_requests_get):
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = [{"id": 1}]
        mock_response_1.links = {
            "next": {"url": "https://api.github.com/user/repos?page=2"}
        }

        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = [{"id": 2}]
        mock_response_2.links = {}

        mock_requests_get.side_effect = [mock_response_1, mock_response_2]

        tracker = GitHubTracker("tracker-1", "api-key", {})
        results = await tracker._make_request("user/repos")

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], 1)
        self.assertEqual(results[1]["id"], 2)
        self.assertEqual(mock_requests_get.call_count, 2)


@pytest.mark.asyncio
class TestGitHubTrackerUnregisterAllWebhooks(unittest.IsolatedAsyncioTestCase):
    @patch("spacesync.trackers.github.crud_project.get_for_organization")
    @patch("spacesync.trackers.github.crud_organization.get_multi")
    @patch("spacesync.trackers.github.GitHubTracker.unregister_webhook")
    async def test_unregister_all_webhooks_success(
        self,
        mock_unregister_webhook,
        mock_crud_organization_get_multi,
        mock_crud_project_get_for_organization,
    ):
        # Arrange
        tracker = GitHubTracker("tracker-1", "api-key", {})
        db_mock = MagicMock()

        mock_org = MagicMock()
        mock_org.id = "org-id-1"
        mock_crud_organization_get_multi.return_value = [mock_org]

        mock_project = MagicMock()
        mock_project.id = "project-id-1"
        mock_crud_project_get_for_organization.return_value = [mock_project]

        mock_webhook = MagicMock()
        db_mock.query.return_value.filter.return_value.all.return_value = [
            mock_webhook,
            mock_webhook,
        ]
        mock_unregister_webhook.return_value = True

        # Act
        results = await tracker.unregister_all_webhooks(db_mock)

        # Assert
        self.assertEqual(results["unregistered"], 2)
        self.assertEqual(results["failed"], 0)

    @patch("spacesync.trackers.github.crud_project.get_for_organization")
    @patch("spacesync.trackers.github.crud_organization.get_multi")
    @patch("spacesync.trackers.github.GitHubTracker.unregister_webhook")
    async def test_unregister_all_webhooks_failure(
        self,
        mock_unregister_webhook,
        mock_crud_organization_get_multi,
        mock_crud_project_get_for_organization,
    ):
        # Arrange
        tracker = GitHubTracker("tracker-1", "api-key", {})
        db_mock = MagicMock()

        mock_org = MagicMock()
        mock_org.id = "org-id-1"
        mock_crud_organization_get_multi.return_value = [mock_org]

        mock_project = MagicMock()
        mock_project.id = "project-id-1"
        mock_crud_project_get_for_organization.return_value = [mock_project]

        mock_webhook = MagicMock()
        db_mock.query.return_value.filter.return_value.all.return_value = [
            mock_webhook,
            mock_webhook,
        ]
        mock_unregister_webhook.side_effect = [True, False]

        # Act
        results = await tracker.unregister_all_webhooks(db_mock)

        # Assert
        self.assertEqual(results["unregistered"], 1)
        self.assertEqual(results["failed"], 1)

    @patch("spacesync.trackers.github.crud_project.get_for_organization")
    @patch("spacesync.trackers.github.crud_organization.get_multi")
    async def test_unregister_all_webhooks_no_webhooks(
        self, mock_crud_organization_get_multi, mock_crud_project_get_for_organization
    ):
        # Arrange
        tracker = GitHubTracker("tracker-1", "api-key", {})
        db_mock = MagicMock()

        mock_org = MagicMock()
        mock_org.id = "org-id-1"
        mock_crud_organization_get_multi.return_value = [mock_org]

        mock_project = MagicMock()
        mock_project.id = "project-id-1"
        mock_crud_project_get_for_organization.return_value = [mock_project]

        db_mock.query.return_value.filter.return_value.all.return_value = []

        # Act
        results = await tracker.unregister_all_webhooks(db_mock)

        # Assert
        self.assertEqual(results["unregistered"], 0)
        self.assertEqual(results["failed"], 0)


@pytest.mark.asyncio
class TestGitHubTrackerCleanupStaleWebhooks(unittest.IsolatedAsyncioTestCase):
    @patch("spacesync.trackers.github.GitHubTracker._make_request_delete")
    @patch("spacesync.trackers.github.GitHubTracker._make_request")
    async def test_cleanup_stale_webhooks_org_hooks(
        self, mock_make_request, mock_make_request_delete
    ):
        # Arrange
        tracker = GitHubTracker("tracker-1", "api-key", {})
        mock_make_request.side_effect = [
            {"login": "user", "html_url": ""},
            [{"login": "org1", "url": "...", "id": "org1", "name": "org1"}],
            [{"config": {"url": "http://stale.com/webhook"}, "id": 1}],
        ]
        mock_make_request_delete.return_value = True

        # Act
        results = await tracker.cleanup_stale_webhooks("http://my-spacebridge.com")

        # Assert
        self.assertEqual(results["unregistered"], 1)
        self.assertEqual(results["failed"], 0)
        mock_make_request_delete.assert_called_with("orgs/org1/hooks/1")

    @patch("spacesync.trackers.github.GitHubTracker._make_request_delete")
    @patch("spacesync.trackers.github.GitHubTracker._make_request")
    async def test_cleanup_stale_webhooks_project_hooks(
        self, mock_make_request, mock_make_request_delete
    ):
        # Arrange
        tracker = GitHubTracker("tracker-1", "api-key", {})
        repo_meta = {
            "full_name": "org1/repo1",
            "id": "123",
            "name": "repo1",
            "description": "",
            "html_url": "",
            "default_branch": "main",
            "created_at": "2021-01-01T00:00:00Z",
            "pushed_at": "2021-01-01T00:00:00Z",
            "stargazers_count": 0,
            "meta_data": {"full_name": "org1/repo1"},
        }
        mock_make_request.side_effect = [
            {"login": "user", "html_url": ""},
            [{"login": "org1", "url": "...", "id": "org1", "name": "org1"}],
            [repo_meta],
            [{"config": {"url": "http://stale.com/webhook"}, "id": 2}],
            [],
        ]
        mock_make_request_delete.return_value = True

        # Act
        results = await tracker.cleanup_stale_webhooks(
            "http://my-spacebridge.com", cleanup_projects=True
        )

        # Assert
        self.assertEqual(results["unregistered"], 1)
        self.assertEqual(results["failed"], 0)
        mock_make_request_delete.assert_called_with("repos/org1/repo1/hooks/2")

    @patch("spacesync.trackers.github.GitHubTracker._make_request_delete")
    @patch("spacesync.trackers.github.GitHubTracker._make_request")
    async def test_cleanup_stale_webhooks_no_stale_hooks(
        self, mock_make_request, mock_make_request_delete
    ):
        # Arrange
        tracker = GitHubTracker("tracker-1", "api-key", {})
        mock_make_request.side_effect = [
            {"login": "user", "html_url": ""},
            [{"login": "org1", "url": "...", "id": "org1", "name": "org1"}],
            [{"config": {"url": "http://my-spacebridge.com/webhook"}, "id": 1}],
        ]

        # Act
        results = await tracker.cleanup_stale_webhooks("http://my-spacebridge.com")

        # Assert
        self.assertEqual(results["unregistered"], 0)
        self.assertEqual(results["failed"], 0)
        mock_make_request_delete.assert_not_called()
