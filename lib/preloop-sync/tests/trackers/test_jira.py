import unittest
from unittest.mock import patch, MagicMock
from jira import JIRAError

from spacesync.trackers.jira import JiraTracker
from spacemodels.models import Webhook


class TestJiraTrackerWebhooks(unittest.TestCase):
    def setUp(self):
        self.mock_jira_patcher = patch("spacesync.trackers.jira.JIRA")
        self.mock_crud_patcher = patch("spacesync.trackers.jira.crud_webhook")

        self.mock_jira_class = self.mock_jira_patcher.start()
        self.mock_crud_webhook = self.mock_crud_patcher.start()

        self.mock_jira_client = MagicMock()
        self.mock_jira_class.return_value = self.mock_jira_client

        self.mock_db_session = MagicMock()

        self.tracker = JiraTracker(
            tracker_id="test-webhook-tracker",
            api_key="fake_key",
            connection_details={
                "jira_url": "https://myjira.atlassian.net",
                "username": "user@example.com",
            },
        )

    def tearDown(self):
        self.mock_jira_patcher.stop()
        self.mock_crud_patcher.stop()

    def test_register_webhook_success(self):
        """Test successful webhook registration when none exists in DB."""
        self.mock_crud_webhook.get_by_project_id.return_value = None
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "12345"}
        self.mock_jira_client._session.post.return_value = mock_response

        result = self.tracker.register_webhook(
            db=self.mock_db_session,
            project_id="proj-db-id",
            project_key="TEST",
            webhook_url="https://example.com/webhook",
            secret="mysecret",
        )

        self.assertTrue(result)
        self.mock_crud_webhook.get_by_project_id.assert_called_once_with(
            self.mock_db_session, project_id="proj-db-id"
        )
        self.mock_jira_client._session.post.assert_called_once()
        self.mock_crud_webhook.create.assert_called_once()

    def test_register_webhook_already_in_db(self):
        """Test webhook registration is skipped if already in DB."""
        self.mock_crud_webhook.get_by_project_id.return_value = Webhook(
            id="wh-id", project_id="proj-db-id", external_id="123"
        )

        result = self.tracker.register_webhook(
            db=self.mock_db_session,
            project_id="proj-db-id",
            project_key="TEST",
            webhook_url="https://example.com/webhook",
            secret="mysecret",
        )

        self.assertTrue(result)
        self.mock_crud_webhook.get_by_project_id.assert_called_once_with(
            self.mock_db_session, project_id="proj-db-id"
        )
        self.mock_jira_client._session.post.assert_not_called()
        self.mock_crud_webhook.create.assert_not_called()

    def test_unregister_webhook_success(self):
        """Test successful unregistration of an existing webhook."""
        mock_webhook = Webhook(
            id="wh-db-id", project_id="proj-db-id", external_id="12345"
        )
        self.mock_crud_webhook.get_by_project_id.return_value = mock_webhook
        self.mock_jira_client._session.delete.return_value = MagicMock(status_code=204)

        result = self.tracker.unregister_webhook(
            db=self.mock_db_session, project_id="proj-db-id"
        )

        self.assertTrue(result)
        self.mock_crud_webhook.get_by_project_id.assert_called_once_with(
            self.mock_db_session, project_id="proj-db-id"
        )
        self.mock_jira_client._session.delete.assert_called_once_with(
            "https://myjira.atlassian.net/rest/webhooks/1.0/webhook/12345"
        )
        self.mock_crud_webhook.remove.assert_called_once_with(
            self.mock_db_session, id="wh-db-id"
        )

    def test_unregister_webhook_not_in_db(self):
        """Test unregistration is skipped if no webhook is in the DB."""
        self.mock_crud_webhook.get_by_project_id.return_value = None

        result = self.tracker.unregister_webhook(
            db=self.mock_db_session, project_id="proj-db-id"
        )

        self.assertTrue(result)
        self.mock_crud_webhook.get_by_project_id.assert_called_once_with(
            self.mock_db_session, project_id="proj-db-id"
        )
        self.mock_jira_client._session.delete.assert_not_called()
        self.mock_crud_webhook.remove.assert_not_called()

    def test_unregister_webhook_not_in_jira(self):
        """Test unregistration when webhook is in DB but not in Jira (404)."""
        mock_webhook = Webhook(
            id="wh-db-id", project_id="proj-db-id", external_id="12345"
        )
        self.mock_crud_webhook.get_by_project_id.return_value = mock_webhook
        self.mock_jira_client._session.delete.side_effect = JIRAError(
            status_code=404, text="Not Found"
        )

        result = self.tracker.unregister_webhook(
            db=self.mock_db_session, project_id="proj-db-id"
        )

        self.assertTrue(result)
        self.mock_crud_webhook.get_by_project_id.assert_called_once_with(
            self.mock_db_session, project_id="proj-db-id"
        )
        self.mock_jira_client._session.delete.assert_called_once_with(
            "https://myjira.atlassian.net/rest/webhooks/1.0/webhook/12345"
        )
        self.mock_crud_webhook.remove.assert_called_once_with(
            self.mock_db_session, id="wh-db-id"
        )


if __name__ == "__main__":
    unittest.main()
