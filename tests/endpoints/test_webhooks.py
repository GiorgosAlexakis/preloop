import hmac
import hashlib
import json
from unittest.mock import MagicMock, patch
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from spacebridge.api.app import create_app
from spacemodels.db.session import get_db_session


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    # This global fixture will be overridden by self.test_client in the class
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def configured_mock_org_fixture():
    """A basic mock organization instance. webhook_secret is configured per-test."""
    org = MagicMock(name="configured_org_instance_mock")
    org.id = "org-123"
    org.name = "Test Organization"
    org.identifier = "test-org-fixture"
    org.last_webhook_update = None
    return org


def setup_mock_webhook_secret(
    mock_org_instance: MagicMock, secret_value: Optional[str] = "test-secret"
) -> None:
    """Configure the webhook_secret attribute on a mock organization instance."""
    mock_org_instance.webhook_secret = secret_value


class TestWebhooksEndpoint:
    """Test cases for the webhooks endpoint."""

    def setup_method(self):
        """Set up the test environment for each test method."""
        self.app = create_app()
        self.mock_session = MagicMock(spec=Session)

        def override_get_db():
            try:
                yield self.mock_session
            finally:
                pass

        self.app.dependency_overrides[get_db_session] = override_get_db
        self.test_client = TestClient(self.app)

    def teardown_method(self):
        """Clean up dependency overrides after each test method."""
        self.app.dependency_overrides.clear()

    @patch(
        "spacebridge.api.endpoints.webhooks.CRUDOrganization"
    )  # Keep patch to avoid import errors if CRUDOrganization is used elsewhere, though not directly in this test logic anymore
    def test_webhook_missing_organization(
        self, mock_crud_org_unused_param
    ):  # Renamed param to indicate it's not used
        """Test webhook returns 404 if organization is not found."""  # Updated docstring
        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = None
        # mock_crud_org.return_value = mock_crud_instance
        # Instead, mock the direct SQLAlchemy query chain
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = None

        response = self.test_client.post(
            "/api/v1/private/webhooks/github/nonexistent-org",  # Assuming github for this test case
            json={"event": "test"},
            headers={
                "X-Hub-Signature-256": "sha256=dummy"
            },  # Dummy signature, won't be checked if org not found
        )

        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier="nonexistent-org"
        # )
        self.mock_session.query.assert_called_once()  # Check that a query was attempted
        assert response.status_code == 404  # Updated status code
        assert (
            response.json()["detail"] == "Organization not found"
        )  # Updated detail message

    @patch(
        "spacebridge.api.endpoints.webhooks.CRUDOrganization"
    )  # Keep patch for consistency
    def test_webhook_missing_secret(
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):
        """Test webhook returns 403 if organization has no webhook_secret."""
        current_org_mock = configured_mock_org_fixture
        setup_mock_webhook_secret(current_org_mock, None)  # webhook_secret is None
        # Ensure the mock tracker on the org mock is also set up if accessed
        current_org_mock.tracker = MagicMock()
        current_org_mock.tracker.is_active = True

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={
                "X-Hub-Signature-256": "sha256=dummy"
            },  # Signature won't be checked if secret is missing
        )
        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        self.mock_session.query.assert_called_once()
        assert response.status_code == 403
        assert response.json()["detail"] == "Webhook not configured correctly"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")  # Keep patch
    def test_github_webhook_missing_signature(
        self,
        mock_crud_org_unused_param,
        configured_mock_org_fixture,  # mock_crud_org not used
    ):
        """Test GitHub webhook returns 403 if X-Hub-Signature-256 header is missing."""
        current_org_mock = configured_mock_org_fixture
        setup_mock_webhook_secret(current_org_mock, "a-test-secret")
        # Ensure the mock tracker on the org mock is also set up
        current_org_mock.tracker = MagicMock()
        current_org_mock.tracker.is_active = True

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        # Instead, mock the direct SQLAlchemy query chain used in the endpoint
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={},  # No signature header
        )
        # The get_by_identifier mock is no longer relevant for this code path
        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        # We should assert that the query was made
        self.mock_session.query.assert_called_once()
        assert response.status_code == 403
        assert response.json()["detail"] == "Missing GitHub signature"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")  # Keep patch
    def test_github_webhook_invalid_signature_method(  # mock_crud_org not used
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):
        """Test GitHub webhook returns 403 when signature method is invalid."""
        current_org_mock = configured_mock_org_fixture
        setup_mock_webhook_secret(current_org_mock, "a-secret")
        current_org_mock.tracker = MagicMock()
        current_org_mock.tracker.is_active = True

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={
                "X-Hub-Signature-256": "sha1=invalid-signature-format"
            },  # Invalid method
        )
        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        self.mock_session.query.assert_called_once()
        assert response.status_code == 403
        assert response.json()["detail"] == "Unsupported GitHub signature method"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")  # Keep patch
    def test_github_webhook_invalid_signature(  # mock_crud_org not used
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):
        """Test GitHub webhook returns 403 when signature is invalid."""
        current_org_mock = configured_mock_org_fixture
        secret_to_use = "test-secret"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)
        current_org_mock.tracker = MagicMock()
        current_org_mock.tracker.is_active = True

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        payload_dict = {"event": "test"}
        # TestClient's `json=` param will do `json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")`
        # So, the signature must match this.
        payload_bytes_for_signature = json.dumps(
            payload_dict, separators=(",", ":")
        ).encode("utf-8")

        # Signature generated with a different secret
        invalid_signature = hmac.new(
            b"wrong-secret", payload_bytes_for_signature, hashlib.sha256
        ).hexdigest()

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json=payload_dict,
            headers={"X-Hub-Signature-256": f"sha256={invalid_signature}"},
        )

        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        self.mock_session.query.assert_called_once()
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid GitHub signature"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")  # Keep patch
    def test_github_webhook_valid_signature(  # mock_crud_org not used
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):
        """Test GitHub webhook with a valid signature (200)."""
        current_org_mock = configured_mock_org_fixture
        secret_to_use = "valid-github-secret-for-this-test"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)
        # Mock the tracker relationship on current_org_mock
        current_org_mock.tracker = MagicMock(name="MockTracker")
        current_org_mock.tracker.id = "tracker-gh-valid"
        current_org_mock.tracker.is_active = True
        current_org_mock.tracker.subscribed_events = [
            "push"
        ]  # Ensure 'push' is subscribed

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        payload_dict = {
            "ref": "refs/heads/main"
        }  # "event" key is not usually in GH payload, type is from header
        # TestClient's `json=` param will do `json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")`
        payload_bytes_for_signature = json.dumps(
            payload_dict, separators=(",", ":")
        ).encode("utf-8")
        signature = hmac.new(
            secret_to_use.encode("utf-8"), payload_bytes_for_signature, hashlib.sha256
        ).hexdigest()

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json=payload_dict,
            headers={
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "push",
            },  # Add event header
        )

        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        self.mock_session.query.assert_called_once()
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["status"] == "success"
        assert (
            response_json["tracker_id"] == current_org_mock.tracker.id
        )  # Check tracker_id
        # The actual datetime.now() will be called, so we check if it's not None
        # and that the mock_session was used to add and commit it.
        self.mock_session.add.assert_called_once_with(current_org_mock)
        self.mock_session.commit.assert_called_once()
        assert current_org_mock.last_webhook_update is not None

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")  # Keep patch
    def test_gitlab_webhook_missing_token(  # mock_crud_org not used
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):
        """Test GitLab webhook returns 403 if X-Gitlab-Token header is missing."""
        current_org_mock = configured_mock_org_fixture
        setup_mock_webhook_secret(current_org_mock, "a-gitlab-secret")
        current_org_mock.tracker = MagicMock()
        current_org_mock.tracker.is_active = True

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        response = self.test_client.post(
            f"/api/v1/private/webhooks/gitlab/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={},  # No token header
        )
        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        self.mock_session.query.assert_called_once()
        assert response.status_code == 403
        assert response.json()["detail"] == "Missing GitLab token"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")  # Keep patch
    def test_gitlab_webhook_invalid_token(  # mock_crud_org not used
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):
        """Test GitLab webhook returns 403 when token is invalid."""
        current_org_mock = configured_mock_org_fixture
        setup_mock_webhook_secret(
            current_org_mock, "correct-gitlab-secret"
        )  # This sets a string secret
        current_org_mock.tracker = MagicMock()
        current_org_mock.tracker.is_active = True

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        response = self.test_client.post(
            f"/api/v1/private/webhooks/gitlab/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={"X-Gitlab-Token": "invalid-token"},
        )
        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        self.mock_session.query.assert_called_once()
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid GitLab token"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")  # Keep patch
    def test_gitlab_webhook_valid_token(  # mock_crud_org not used
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):
        """Test GitLab webhook succeeds with valid token."""
        current_org_mock = configured_mock_org_fixture
        secret_to_use = "valid-gitlab-secret"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)
        # Mock the tracker relationship
        current_org_mock.tracker = MagicMock(name="MockTrackerGL")
        current_org_mock.tracker.id = "tracker-gl-valid"
        current_org_mock.tracker.is_active = True
        # For GitLab, the event type is in the header, e.g., "Push Hook", "Merge Request Hook"
        # The subscribed_events should match these header values.
        current_org_mock.tracker.subscribed_events = ["Push Hook"]

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        response = self.test_client.post(
            f"/api/v1/private/webhooks/gitlab/{current_org_mock.identifier}",
            json={
                "event_name": "push_events",
                "action": "merged",
            },  # Payload for GitLab
            headers={
                "X-Gitlab-Token": secret_to_use,
                "X-Gitlab-Event": "Push Hook",
            },  # Actual event type from header
        )

        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        self.mock_session.query.assert_called_once()
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["status"] == "success"
        assert (
            response_json["tracker_id"] == current_org_mock.tracker.id
        )  # Check tracker_id
        self.mock_session.add.assert_called_once_with(current_org_mock)
        self.mock_session.commit.assert_called_once()
        assert current_org_mock.last_webhook_update is not None

    @patch(
        "spacebridge.api.endpoints.webhooks.CRUDOrganization"
    )  # Keep patch, though mock_crud_org not directly used
    def test_unsupported_tracker_type(
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):  # Corrected fixture name
        """Test webhook returns 400 for an unsupported tracker type."""
        # current_org_mock = configured_mock_org_fixture # Not needed
        # setup_mock_webhook_secret is irrelevant

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        # No db query should happen for an unsupported type before the type check

        tracker_name = "unsupported-tracker"
        response = self.test_client.post(
            f"/api/v1/private/webhooks/{tracker_name}/any-identifier",  # Identifier doesn't matter
            json={"event": "test"},
        )
        # mock_crud_instance.get_by_identifier.assert_not_called() # DB query for org should not happen
        self.mock_session.query.assert_not_called()  # No SQLAlchemy query should be made
        assert response.status_code == 400
        assert (
            response.json()["detail"]
            == f"Unsupported tracker_type: {tracker_name}"  # Updated expected message
        )

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")  # Keep patch
    def test_invalid_json_payload(
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):  # mock_crud_org not used
        """Test webhook returns 400 when payload is not valid JSON, even with valid GitHub signature."""
        current_org_mock = configured_mock_org_fixture
        secret_to_use = "json-error-secret"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)
        # Mock the tracker relationship
        current_org_mock.tracker = MagicMock(name="MockTrackerJsonError")
        current_org_mock.tracker.id = "tracker-gh-json-error"
        current_org_mock.tracker.is_active = True
        # Subscribed events don't matter as much if JSON parsing fails before event type check
        current_org_mock.tracker.subscribed_events = ["some_event"]

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        invalid_payload_bytes = b"this is not json {{{{,"
        signature = hmac.new(
            secret_to_use.encode("utf-8"), invalid_payload_bytes, hashlib.sha256
        ).hexdigest()

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            content=invalid_payload_bytes,
            headers={
                "X-Hub-Signature-256": f"sha256={signature}",
                "Content-Type": "application/json",  # Important for FastAPI to attempt JSON parsing
                "X-GitHub-Event": "some_event",  # Provide event header
            },
        )

        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        self.mock_session.query.assert_called_once()
        assert response.status_code == 400
        assert "Invalid JSON payload" in response.json()["detail"]

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")  # Keep patch
    def test_database_error_on_update(
        self, mock_crud_org_unused_param, configured_mock_org_fixture
    ):  # mock_crud_org not used
        """Test webhook handles database errors gracefully during DB update."""
        current_org_mock = configured_mock_org_fixture
        current_org_mock.identifier = "db-error-org-final"
        secret_to_use = "db-error-secret-final"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)
        # Mock the tracker relationship
        current_org_mock.tracker = MagicMock(name="MockTrackerDBError")
        current_org_mock.tracker.id = "tracker-gh-db-error"
        current_org_mock.tracker.is_active = True
        current_org_mock.tracker.subscribed_events = [
            "test_event"
        ]  # Event type for the test

        # mock_crud_instance = MagicMock()
        # mock_crud_instance.get_by_identifier.return_value = current_org_mock
        # mock_crud_org.return_value = mock_crud_instance
        self.mock_session.query.return_value.options.return_value.filter.return_value.first.return_value = current_org_mock

        self.mock_session.commit.side_effect = Exception("Simulated DB error on commit")
        self.mock_session.rollback.return_value = None

        payload_dict = {"action": "assigned"}  # "event" key not in GH payload
        payload_bytes_for_signature = json.dumps(
            payload_dict, separators=(",", ":")
        ).encode("utf-8")
        signature = hmac.new(
            secret_to_use.encode("utf-8"), payload_bytes_for_signature, hashlib.sha256
        ).hexdigest()

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json=payload_dict,
            headers={
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "test_event",
            },  # Provide event header
        )

        # mock_crud_instance.get_by_identifier.assert_called_once_with(
        #     db=self.mock_session, identifier=current_org_mock.identifier
        # )
        self.mock_session.query.assert_called_once()
        # The endpoint now logs the error and returns 200 to prevent retries if NATS part was (simulated) ok.
        # The critical failure is logged. If NATS publish itself failed, that might be a 500.
        # For a timestamp DB error post-NATS, we expect 200.
        assert response.status_code == 200
        assert (
            response.json()["status"] == "success"
        )  # The main operation (NATS publish) is considered success
        assert response.json()["tracker_id"] == current_org_mock.tracker.id

        self.mock_session.add.assert_called_once_with(current_org_mock)
        self.mock_session.commit.assert_called_once()  # Commit was attempted
        self.mock_session.rollback.assert_called_once()  # Rollback was called due to error
