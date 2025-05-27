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

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_webhook_missing_organization(self, mock_crud_org):
        """Test webhook returns 403 if organization is not found."""
        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = None
        mock_crud_org.return_value = mock_crud_instance

        response = self.test_client.post(
            "/api/v1/private/webhooks/github/nonexistent-org",
            json={"event": "test"},
            headers={"X-Hub-Signature-256": "sha256=dummy"},
        )

        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier="nonexistent-org"
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid request"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_webhook_missing_secret(self, mock_crud_org, configured_mock_org_fixture):
        """Test webhook returns 403 if organization has no webhook_secret."""
        current_org_mock = configured_mock_org_fixture
        setup_mock_webhook_secret(current_org_mock, None)

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={"X-Hub-Signature-256": "sha256=dummy"},
        )
        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Webhook not configured correctly"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_github_webhook_missing_signature(
        self, mock_crud_org, configured_mock_org_fixture
    ):
        """Test GitHub webhook returns 403 if X-Hub-Signature-256 header is missing."""
        current_org_mock = configured_mock_org_fixture
        setup_mock_webhook_secret(current_org_mock, "a-test-secret")

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={},
        )
        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Missing GitHub signature"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_github_webhook_invalid_signature_method(
        self, mock_crud_org, configured_mock_org_fixture
    ):
        """Test GitHub webhook returns 403 when signature method is invalid."""
        current_org_mock = configured_mock_org_fixture
        setup_mock_webhook_secret(current_org_mock, "a-secret")

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={
                "X-Hub-Signature-256": "sha1=invalid-signature-format"
            },  # Invalid method
        )
        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Unsupported GitHub signature method"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_github_webhook_invalid_signature(
        self, mock_crud_org, configured_mock_org_fixture
    ):
        """Test GitHub webhook returns 403 when signature is invalid."""
        current_org_mock = configured_mock_org_fixture
        secret_to_use = "test-secret"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        payload_dict = {"event": "test"}
        payload_bytes_for_signature = json.dumps(payload_dict).encode("utf-8")
        # Signature generated with a different secret
        invalid_signature = hmac.new(
            b"wrong-secret", payload_bytes_for_signature, hashlib.sha256
        ).hexdigest()

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json=payload_dict,  # Send JSON directly
            headers={"X-Hub-Signature-256": f"sha256={invalid_signature}"},
        )

        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid GitHub signature"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_github_webhook_valid_signature(
        self, mock_crud_org, configured_mock_org_fixture
    ):
        """Test GitHub webhook with a valid signature (200)."""
        current_org_mock = configured_mock_org_fixture
        secret_to_use = "valid-github-secret-for-this-test"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        payload_dict = {"event": "push", "ref": "refs/heads/main"}
        payload_bytes_for_signature = json.dumps(
            payload_dict, separators=(",", ":")
        ).encode("utf-8")
        signature = hmac.new(
            secret_to_use.encode("utf-8"), payload_bytes_for_signature, hashlib.sha256
        ).hexdigest()

        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json=payload_dict,
            headers={"X-Hub-Signature-256": f"sha256={signature}"},
        )

        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["organization_id"] == current_org_mock.id
        # The actual datetime.now() will be called, so we check if it's not None
        # and that the mock_session was used to add and commit it.
        self.mock_session.add.assert_called_once_with(current_org_mock)
        self.mock_session.commit.assert_called_once()
        assert current_org_mock.last_webhook_update is not None

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_gitlab_webhook_missing_token(
        self, mock_crud_org, configured_mock_org_fixture
    ):
        """Test GitLab webhook returns 403 if X-Gitlab-Token header is missing."""
        current_org_mock = configured_mock_org_fixture
        # Secret is set, but header will be missing
        setup_mock_webhook_secret(current_org_mock, "a-gitlab-secret")

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        response = self.test_client.post(
            f"/api/v1/private/webhooks/gitlab/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={},  # No token header
        )
        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Missing GitLab token"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_gitlab_webhook_invalid_token(
        self, mock_crud_org, configured_mock_org_fixture
    ):
        """Test GitLab webhook returns 403 when token is invalid."""
        current_org_mock = configured_mock_org_fixture
        setup_mock_webhook_secret(current_org_mock, "correct-gitlab-secret")

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        response = self.test_client.post(
            f"/api/v1/private/webhooks/gitlab/{current_org_mock.identifier}",
            json={"event": "test"},
            headers={"X-Gitlab-Token": "invalid-token"},
        )
        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid GitLab token"

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_gitlab_webhook_valid_token(
        self, mock_crud_org, configured_mock_org_fixture
    ):
        """Test GitLab webhook succeeds with valid token."""
        current_org_mock = configured_mock_org_fixture
        secret_to_use = "valid-gitlab-secret"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        response = self.test_client.post(
            f"/api/v1/private/webhooks/gitlab/{current_org_mock.identifier}",
            json={"event": "test", "action": "merged"},
            headers={"X-Gitlab-Token": secret_to_use},
        )

        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["organization_id"] == current_org_mock.id
        self.mock_session.add.assert_called_once_with(current_org_mock)
        self.mock_session.commit.assert_called_once()
        assert current_org_mock.last_webhook_update is not None

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_unsupported_tracker_type(self, mock_crud_org, configured_mock_org_fixture):
        """Test webhook returns 400 for an unsupported tracker type."""
        current_org_mock = configured_mock_org_fixture
        # Webhook secret setup is irrelevant here as it fails before that check

        mock_crud_instance = MagicMock()
        # get_by_identifier should not be called if tracker type is invalid early
        # However, the current endpoint implementation calls it first.
        # If this changes, the test expectation for get_by_identifier might need adjustment.
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        tracker_name = "unsupported-tracker"
        response = self.test_client.post(
            f"/api/v1/private/webhooks/{tracker_name}/{current_org_mock.identifier}",
            json={"event": "test"},
            # Signature/token headers are irrelevant as it fails on tracker type
        )
        # Depending on implementation, get_by_identifier might or might not be called.
        # Current endpoint calls it, then checks tracker type.
        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 400
        assert (
            response.json()["detail"]
            == f"Webhook verification not supported for tracker type: {tracker_name}"
        )

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_invalid_json_payload(self, mock_crud_org, configured_mock_org_fixture):
        """Test webhook returns 400 when payload is not valid JSON, even with valid GitHub signature."""
        current_org_mock = configured_mock_org_fixture
        secret_to_use = "json-error-secret"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        invalid_payload_bytes = b"this is not json {{{{,"
        # Generate a signature for the invalid payload bytes, as if it were valid
        signature = hmac.new(
            secret_to_use.encode("utf-8"), invalid_payload_bytes, hashlib.sha256
        ).hexdigest()

        # No need to patch Request.json, TestClient will try to parse, or endpoint will fail
        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            content=invalid_payload_bytes,  # Send raw bytes
            headers={
                "X-Hub-Signature-256": f"sha256={signature}",
                "Content-Type": "application/json",  # Indicate it's supposed to be JSON
            },
        )

        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 400
        assert (
            "Invalid JSON payload" in response.json()["detail"]
        )  # Or check for FastAPI's default JSON error

    @patch("spacebridge.api.endpoints.webhooks.CRUDOrganization")
    def test_database_error_on_update(self, mock_crud_org, configured_mock_org_fixture):
        """Test webhook handles database errors gracefully during DB update (500)."""
        current_org_mock = configured_mock_org_fixture
        current_org_mock.identifier = "db-error-org-final"  # Unique identifier
        secret_to_use = "db-error-secret-final"
        setup_mock_webhook_secret(current_org_mock, secret_to_use)

        mock_crud_instance = MagicMock()
        mock_crud_instance.get_by_identifier.return_value = current_org_mock
        mock_crud_org.return_value = mock_crud_instance

        # Simulate a database error when self.mock_session.commit() is called
        self.mock_session.commit.side_effect = Exception("Simulated DB error on commit")
        self.mock_session.rollback.return_value = None  # Ensure rollback can be called

        payload_dict = {"event": "test", "action": "assigned"}
        payload_bytes_for_signature = json.dumps(
            payload_dict, separators=(",", ":")
        ).encode("utf-8")
        signature = hmac.new(
            secret_to_use.encode("utf-8"), payload_bytes_for_signature, hashlib.sha256
        ).hexdigest()

        # No need to patch Request.body or Request.json
        response = self.test_client.post(
            f"/api/v1/private/webhooks/github/{current_org_mock.identifier}",
            json=payload_dict,
            headers={"X-Hub-Signature-256": f"sha256={signature}"},
        )

        mock_crud_instance.get_by_identifier.assert_called_once_with(
            db=self.mock_session, identifier=current_org_mock.identifier
        )
        assert response.status_code == 500
        assert "Failed to update organization timestamp" in response.json()["detail"]
        self.mock_session.add.assert_called_once_with(current_org_mock)
        self.mock_session.commit.assert_called_once()
        self.mock_session.rollback.assert_called_once()
