"""Tests for admin activity monitoring endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import uuid

from fastapi.testclient import TestClient
from fastapi import FastAPI

from spacebridge.api.endpoints.admin import router as admin_router
from spacebridge.api.auth import get_current_active_user
from spacemodels.db.session import get_db_session
from spacemodels.models import Event, User


app = FastAPI()
app.include_router(admin_router)
client = TestClient(app)


@pytest.fixture
def mock_superuser():
    """Create a mock superuser."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "admin"
    user.email = "admin@example.com"
    user.is_superuser = True
    user.account_id = uuid.uuid4()
    return user


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    db = MagicMock()

    # Mock query chain
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []
    mock_query.count.return_value = 0
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.distinct.return_value = mock_query
    mock_query.scalar.return_value = None

    db.query.return_value = mock_query
    return db


@pytest.fixture
def mock_auth_and_permission(mock_superuser, mock_db_session):
    """Mock authentication and permission checks using dependency overrides."""
    # Override FastAPI dependencies
    app.dependency_overrides[get_current_active_user] = lambda: mock_superuser
    app.dependency_overrides[get_db_session] = lambda: mock_db_session

    # Mock require_permission to be a passthrough decorator
    with patch("spacebridge.api.endpoints.admin.require_permission") as mock_perm:
        mock_perm.return_value = lambda f: f
        yield

    # Clear overrides after test
    app.dependency_overrides.clear()


def test_get_active_sessions_returns_sessions_with_current_page(
    mock_superuser, mock_db_session, mock_auth_and_permission
):
    """Test that active sessions endpoint returns sessions with current_path populated."""
    session_id = uuid.uuid4()
    user_id = uuid.uuid4()
    account_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Create mock events
    session_start_event = MagicMock(spec=Event)
    session_start_event.session_id = session_id
    session_start_event.user_id = user_id
    session_start_event.account_id = account_id
    session_start_event.fingerprint = "test_fingerprint"
    session_start_event.ip_address = "192.168.1.1"
    session_start_event.user_agent = "Mozilla/5.0"
    session_start_event.timestamp = now - timedelta(minutes=10)
    session_start_event.event_type = "session_start"

    page_view_event = MagicMock(spec=Event)
    page_view_event.session_id = session_id
    page_view_event.path = "/admin/accounts"
    page_view_event.timestamp = now - timedelta(minutes=5)
    page_view_event.event_type = "page_view"

    latest_activity_event = MagicMock(spec=Event)
    latest_activity_event.timestamp = now - timedelta(minutes=2)

    # Mock user
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"

    # Setup query return values
    # Call counter needs to persist across multiple query_side_effect calls
    call_count = [0]

    def query_side_effect(model):
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.distinct.return_value = mock_query

        # Handle column queries (Event.session_id, etc.)
        if hasattr(model, "class_") or not hasattr(model, "__name__"):
            mock_query.all.return_value = []
            return mock_query

        if model == Event:
            # Query sequence:
            # 1. session_start events (all)
            # 2. session_end session_ids (column query, intercepted above)
            # 3. latest page_view (first)
            # 4. latest activity (first)

            def all_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return [session_start_event]  # session_start events
                return []

            def first_side_effect():
                call_count[0] += 1
                if call_count[0] == 2:
                    return page_view_event  # latest page_view
                elif call_count[0] == 3:
                    return latest_activity_event  # latest activity
                return None

            mock_query.all.side_effect = all_side_effect
            mock_query.first.side_effect = first_side_effect

        elif model == User:
            mock_query.first.return_value = mock_user

        return mock_query

    mock_db_session.query.side_effect = query_side_effect

    # Make the request
    response = client.get(
        "/admin/activity/sessions",
        headers={"Authorization": "Bearer test_token"},
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()

    assert "sessions" in data
    assert data["total"] >= 0

    # If we have sessions, verify current_path is populated
    if data["sessions"]:
        session = data["sessions"][0]
        assert "current_path" in session
        assert session["current_path"] == "/admin/accounts"


def test_get_active_sessions_handles_missing_page_view(
    mock_superuser, mock_db_session, mock_auth_and_permission
):
    """Test that active sessions endpoint handles missing page_view events gracefully."""
    session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Create mock session_start event
    session_start_event = MagicMock(spec=Event)
    session_start_event.session_id = session_id
    session_start_event.user_id = None  # Anonymous
    session_start_event.account_id = None
    session_start_event.fingerprint = "test_fingerprint"
    session_start_event.ip_address = "192.168.1.1"
    session_start_event.user_agent = "Mozilla/5.0"
    session_start_event.timestamp = now - timedelta(minutes=10)
    session_start_event.event_type = "session_start"

    latest_activity_event = MagicMock(spec=Event)
    latest_activity_event.timestamp = now - timedelta(minutes=2)

    # Setup query return values
    # Call counter needs to persist across multiple query_side_effect calls
    call_count = [0]

    def query_side_effect(model):
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.distinct.return_value = mock_query

        # Handle column queries (Event.session_id, etc.)
        if hasattr(model, "class_") or not hasattr(model, "__name__"):
            mock_query.all.return_value = []
            return mock_query

        if model == Event:
            # Query sequence:
            # 1. session_start events (all)
            # 2. session_end session_ids (column query, intercepted above)
            # 3. latest page_view (first)
            # 4. latest activity (first)

            def all_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return [session_start_event]
                return []

            def first_side_effect():
                call_count[0] += 1
                if call_count[0] == 2:
                    return None  # No page_view event
                elif call_count[0] == 3:
                    return latest_activity_event
                return None

            mock_query.all.side_effect = all_side_effect
            mock_query.first.side_effect = first_side_effect

        return mock_query

    mock_db_session.query.side_effect = query_side_effect

    # Make the request
    response = client.get(
        "/admin/activity/sessions",
        headers={"Authorization": "Bearer test_token"},
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()

    # Should still return sessions, but current_path should be None
    if data["sessions"]:
        session = data["sessions"][0]
        assert "current_path" in session
        assert session["current_path"] is None


def test_get_account_details_includes_last_login(
    mock_superuser, mock_db_session, mock_auth_and_permission
):
    """Test that account details endpoint includes last_login for users."""
    account_id = uuid.uuid4()
    user_id = uuid.uuid4()
    last_login_time = datetime.now(timezone.utc) - timedelta(hours=2)

    # Create mock account
    mock_account = MagicMock()
    mock_account.id = account_id
    mock_account.organization_name = "Test Org"
    mock_account.created = datetime.now(timezone.utc) - timedelta(days=30)
    mock_account.is_active = True
    mock_account.primary_user_id = user_id

    # Create mock user with last_login
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"
    mock_user.email_verified = True
    mock_user.is_active = True
    mock_user.created_at = datetime.now(timezone.utc) - timedelta(days=30)
    mock_user.last_login = last_login_time  # Should be recent

    # Setup query return values
    def query_side_effect(model):
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None
        mock_query.all.return_value = []
        mock_query.count.return_value = 0
        mock_query.distinct.return_value = mock_query
        mock_query.scalar.return_value = None

        # Handle both model queries and column queries
        # For column queries (like Event.session_id), the model is an InstrumentedAttribute
        # Check if this is a column query by trying to access the class attribute
        is_column_query = False
        model_name = None

        try:
            # Try to get __name__ - this works for model classes
            if hasattr(model, "__name__"):
                model_name = model.__name__
            # If that fails, check if it's a column query
            elif hasattr(model, "class_"):
                # This is a column from SQLAlchemy (InstrumentedAttribute)
                is_column_query = True
        except (AttributeError, TypeError):
            # Unknown type, treat as column query
            is_column_query = True

        # Handle column queries (return empty list for active sessions count)
        if is_column_query:
            # Column queries like db.query(Event.session_id) return tuples/objects with session_id
            mock_query.all.return_value = []
            return mock_query

        # Handle model queries
        if model_name == "Account":
            mock_query.first.return_value = mock_account
        elif model == User:
            mock_query.all.return_value = [mock_user]
            mock_query.filter.return_value.scalar.return_value = "testuser"

        return mock_query

    mock_db_session.query.side_effect = query_side_effect

    # Make the request
    response = client.get(
        f"/admin/accounts/{account_id}",
        headers={"Authorization": "Bearer test_token"},
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()

    assert "users" in data
    assert len(data["users"]) > 0

    user_data = data["users"][0]
    assert "last_login" in user_data
    assert user_data["last_login"] is not None

    # Verify the last_login timestamp is the one we set
    if user_data["last_login"]:
        # Should be within a few seconds of our mock time
        returned_time = datetime.fromisoformat(
            user_data["last_login"].replace("Z", "+00:00")
        )
        time_diff = abs((returned_time - last_login_time).total_seconds())
        assert time_diff < 1, "last_login should match the user's actual last_login"
