"""Tests for activity tracking service."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
import uuid
import json

from preloop.services.activity_tracker import handle_activity
from preloop.services.session_manager import WebSocketSession
from preloop.models.models import Event


@pytest.fixture
def mock_session():
    """Create a mock WebSocket session."""
    return WebSocketSession(
        id=str(uuid.uuid4()),
        connection_id=str(uuid.uuid4()),
        websocket=MagicMock(),
        user_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        fingerprint="test_fingerprint_12345678",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0 Test Browser",
        connected_at=datetime.now(timezone.utc),
        last_activity=datetime.now(timezone.utc),
        metadata={},
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def mock_event_bus():
    """Mock the event bus service."""
    with patch("preloop.sync.services.event_bus.event_bus_service") as mock_bus:
        mock_nc = MagicMock()
        mock_nc.is_connected = True
        mock_nc.publish = AsyncMock()
        mock_bus.nc = mock_nc
        yield mock_bus


@pytest.mark.asyncio
async def test_track_page_view_creates_event(
    mock_session, mock_db_session, mock_event_bus
):
    """Test that tracking a page view creates an Event in the database."""
    data = {
        "event": "page_view",
        "path": "/admin/accounts",
        "referrer": "/admin/",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {"browser": "chrome"},
    }

    with patch("preloop.services.activity_tracker.session_manager") as mock_sm:
        mock_sm.update_activity = MagicMock()

        await handle_activity(data, mock_session, mock_db_session)

        # Verify event was added to database
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # Get the Event object that was added
        added_event = mock_db_session.add.call_args[0][0]
        assert isinstance(added_event, Event)
        assert added_event.event_type == "page_view"
        assert added_event.path == "/admin/accounts"
        assert added_event.referrer == "/admin/"
        assert added_event.session_id == uuid.UUID(mock_session.id)
        assert added_event.user_id == mock_session.user_id
        assert added_event.account_id == mock_session.account_id


@pytest.mark.asyncio
async def test_track_page_view_publishes_to_nats(
    mock_session, mock_db_session, mock_event_bus
):
    """Test that tracking a page view publishes to NATS."""
    data = {
        "event": "page_view",
        "path": "/admin/accounts",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with patch("preloop.services.activity_tracker.session_manager") as mock_sm:
        mock_sm.update_activity = MagicMock()

        await handle_activity(data, mock_session, mock_db_session)

        # Verify NATS publish was called
        mock_event_bus.nc.publish.assert_called_once()

        # Check the subject and message
        call_args = mock_event_bus.nc.publish.call_args
        assert call_args[0][0] == "admin.activity"

        # Decode and verify the message
        message_bytes = call_args[0][1]
        message = json.loads(message_bytes.decode())
        assert message["type"] == "activity_update"
        assert message["activity"]["event_type"] == "page_view"
        assert message["activity"]["path"] == "/admin/accounts"


@pytest.mark.asyncio
async def test_track_page_view_handles_nats_failure(mock_session, mock_db_session):
    """Test that activity tracking continues even if NATS publishing fails."""
    data = {
        "event": "page_view",
        "path": "/admin/accounts",
    }

    with patch("preloop.sync.services.event_bus.event_bus_service") as mock_bus:
        # NATS is not connected
        mock_bus.nc = None

        with patch("preloop.services.activity_tracker.session_manager") as mock_sm:
            mock_sm.update_activity = MagicMock()

            # Should not raise an exception
            await handle_activity(data, mock_session, mock_db_session)

            # Event should still be saved to database
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_track_action_creates_event(
    mock_session, mock_db_session, mock_event_bus
):
    """Test that tracking an action creates an Event in the database."""
    data = {
        "event": "action",
        "action": "click_signup_button",
        "metadata": {
            "element": "button",
            "text": "Sign Up",
        },
    }

    with patch("preloop.services.activity_tracker.session_manager") as mock_sm:
        mock_sm.update_activity = MagicMock()

        await handle_activity(data, mock_session, mock_db_session)

        # Verify event was added to database
        mock_db_session.add.assert_called_once()
        added_event = mock_db_session.add.call_args[0][0]
        assert added_event.event_type == "action"
        assert added_event.action == "click_signup_button"
        assert added_event.element == "button"
        assert added_event.element_text == "Sign Up"


@pytest.mark.asyncio
async def test_track_conversion_creates_event(
    mock_session, mock_db_session, mock_event_bus
):
    """Test that tracking a conversion creates an Event in the database."""
    data = {
        "event": "conversion",
        "conversion_event": "signup_completed",
        "value": 100.0,
    }

    with patch("preloop.services.activity_tracker.session_manager") as mock_sm:
        mock_sm.update_activity = MagicMock()

        await handle_activity(data, mock_session, mock_db_session)

        # Verify event was added to database
        mock_db_session.add.assert_called_once()
        added_event = mock_db_session.add.call_args[0][0]
        assert added_event.event_type == "conversion"
        assert added_event.conversion_event == "signup_completed"
        assert added_event.conversion_value == 100.0


@pytest.mark.asyncio
async def test_activity_tracking_updates_session_activity(
    mock_session, mock_db_session, mock_event_bus
):
    """Test that activity tracking updates the session's last activity timestamp."""
    data = {
        "event": "page_view",
        "path": "/admin/accounts",
    }

    with patch("preloop.services.activity_tracker.session_manager") as mock_sm:
        mock_sm.update_activity = MagicMock()

        await handle_activity(data, mock_session, mock_db_session)

        # Verify session activity was updated
        mock_sm.update_activity.assert_called_once_with(mock_session.id)


@pytest.mark.asyncio
async def test_activity_tracking_without_event_type(
    mock_session, mock_db_session, mock_event_bus
):
    """Test that activity tracking handles missing event type gracefully."""
    data = {
        "path": "/admin/accounts",
        # Missing 'event' field
    }

    with patch("preloop.services.activity_tracker.session_manager") as mock_sm:
        mock_sm.update_activity = MagicMock()

        await handle_activity(data, mock_session, mock_db_session)

        # Should not add anything to database
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_nats_message_format_is_correct(
    mock_session, mock_db_session, mock_event_bus
):
    """Test that the NATS message has the correct format for admin dashboard."""
    data = {
        "event": "page_view",
        "path": "/admin/accounts",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with patch("preloop.services.activity_tracker.session_manager") as mock_sm:
        mock_sm.update_activity = MagicMock()

        await handle_activity(data, mock_session, mock_db_session)

        # Get the published message
        call_args = mock_event_bus.nc.publish.call_args
        message_bytes = call_args[0][1]
        message = json.loads(message_bytes.decode())

        # Verify message structure
        assert "type" in message
        assert message["type"] == "activity_update"
        assert "activity" in message

        activity = message["activity"]
        assert "id" in activity
        assert "session_id" in activity
        assert "user_id" in activity
        assert "event_type" in activity
        assert "timestamp" in activity
        assert "path" in activity

        # Verify the activity data matches
        assert activity["session_id"] == mock_session.id
        assert activity["user_id"] == str(mock_session.user_id)
        assert activity["event_type"] == "page_view"
        assert activity["path"] == "/admin/accounts"
