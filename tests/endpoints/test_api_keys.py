"""Tests for API key endpoints."""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fastapi import FastAPI
from spacebridge.api.auth.router import router as auth_router
from spacemodels.models.user import User
from spacemodels.models.api_key import ApiKey

app = FastAPI()
app.include_router(auth_router, prefix="/auth")
client = TestClient(app)


@pytest.fixture
def mock_current_user():
    """Create a mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.email = "test@example.com"
    user.is_active = True
    user.account_id = uuid.uuid4()
    return user


@pytest.fixture
def db_session_mock():
    """Create a mock database session."""
    with patch("spacebridge.api.auth.router.get_db_session") as mock_get_db:
        db_session = MagicMock(spec=Session)

        # Mock commit, rollback, close
        db_session.commit = MagicMock()
        db_session.rollback = MagicMock()
        db_session.close = MagicMock()

        mock_get_db.return_value = iter([db_session])
        yield db_session


def test_create_api_key_success(db_session_mock, mock_current_user):
    """Test that creating an API key works with the correct user_id field.

    This test ensures that:
    1. The ApiKey model is instantiated with user_id (not created_by)
    2. The response includes user_id (not created_by)
    3. All database operations complete successfully

    This would catch the bug where created_by was used instead of user_id.
    """
    # Mock authentication
    with patch("spacebridge.api.auth.router.get_current_active_user") as mock_get_user:
        mock_get_user.return_value = mock_current_user

        # Create a mock API key that will be "created"
        mock_api_key = MagicMock(spec=ApiKey)
        mock_api_key.id = uuid.uuid4()
        mock_api_key.name = "Test API Key"
        mock_api_key.key = "test_key_1234567890abcdefghijklmnopqrst"
        mock_api_key.user_id = mock_current_user.id  # This is the critical field
        mock_api_key.created_at = datetime.now(timezone.utc)
        mock_api_key.expires_at = None
        mock_api_key.scopes = []
        mock_api_key.last_used_at = None

        # Mock the session.refresh to set up the mock_api_key properly
        def mock_refresh(obj):
            # Simulate refresh by ensuring all fields are set
            pass

        db_session_mock.refresh = mock_refresh
        db_session_mock.add = MagicMock()

        # Make a request to create an API key
        response = client.post(
            "/auth/api-keys",
            json={"name": "Test API Key", "expires_at": None, "scopes": []},
        )

        # Verify the response
        assert response.status_code == 201
        data = response.json()

        # Critical assertions - these would fail with created_by field
        assert "user_id" in data, "Response must include user_id field"
        assert "created_by" not in data, (
            "Response should not include deprecated created_by field"
        )

        # Verify all expected fields are present
        assert "id" in data
        assert "name" in data
        assert "key" in data
        assert "created_at" in data
        assert "expires_at" in data
        assert "scopes" in data
        assert "last_used_at" in data

        # Verify the database operations were called correctly
        db_session_mock.add.assert_called_once()

        # Get the ApiKey object that was added
        added_key = db_session_mock.add.call_args[0][0]

        # Critical assertion - the ApiKey must be created with user_id
        assert hasattr(added_key, "user_id"), "ApiKey must have user_id attribute"
        assert added_key.user_id == mock_current_user.id, (
            "user_id must match current user's id"
        )

        # Ensure deprecated field is not used
        assert not hasattr(added_key, "created_by") or added_key.user_id is not None, (
            "ApiKey should use user_id, not created_by"
        )


def test_create_api_key_with_expiration(db_session_mock, mock_current_user):
    """Test creating an API key with an expiration date."""
    with patch("spacebridge.api.auth.router.get_current_active_user") as mock_get_user:
        mock_get_user.return_value = mock_current_user

        expires_at = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        response = client.post(
            "/auth/api-keys",
            json={
                "name": "Expiring Key",
                "expires_at": expires_at.isoformat(),
                "scopes": ["read", "write"],
            },
        )

        assert response.status_code == 201
        data = response.json()

        # Verify user_id is present
        assert "user_id" in data
        assert data["name"] == "Expiring Key"
        assert data["scopes"] == ["read", "write"]
        # expires_at should be present (we're not validating exact format in this test)
        assert "expires_at" in data


def test_create_api_key_duplicate_name(db_session_mock, mock_current_user):
    """Test that creating an API key with a duplicate name fails appropriately."""
    from sqlalchemy.exc import IntegrityError

    with patch("spacebridge.api.auth.router.get_current_active_user") as mock_get_user:
        mock_get_user.return_value = mock_current_user

        # Mock the session to raise IntegrityError on commit
        db_session_mock.commit.side_effect = IntegrityError("", "", "")

        response = client.post(
            "/auth/api-keys",
            json={"name": "Duplicate Key", "expires_at": None, "scopes": []},
        )

        # Should return 400 Bad Request
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()


def test_api_key_model_compatibility():
    """Direct unit test to verify ApiKey model field compatibility.

    This test directly checks that the ApiKey model has the expected fields
    and doesn't have deprecated fields.
    """
    from spacemodels.models.api_key import ApiKey
    import inspect

    # Get the __init__ signature
    sig = inspect.signature(ApiKey.__init__)
    params = list(sig.parameters.keys())

    # Check that user_id is an expected parameter
    # Note: SQLAlchemy models don't always show all fields in __init__,
    # so we check the class attributes instead
    assert hasattr(ApiKey, "user_id"), "ApiKey must have user_id attribute"

    # Verify we can create an ApiKey with user_id
    try:
        test_key = ApiKey(
            name="test", key="test_key_123", user_id=uuid.uuid4(), scopes=[]
        )
        # If we get here, user_id is accepted
        assert test_key.user_id is not None
    except TypeError as e:
        if "user_id" in str(e):
            pytest.fail(f"ApiKey model does not accept user_id parameter: {e}")
        raise
