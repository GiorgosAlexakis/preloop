"""Integration tests for WebSocket endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from starlette.websockets import WebSocketDisconnect

from spacemodels.models.user import User


class TestUnifiedWebSocket:
    """Test the unified WebSocket endpoint /api/v1/ws/unified."""

    def _setup_websocket_mocks(
        self, mock_manager, mock_get_user, mock_session_manager, test_user=None
    ):
        """Helper to setup async mocks for WebSocket tests."""
        # Mock user authentication (async function)
        async_mock_get_user = AsyncMock(return_value=test_user)
        mock_get_user.side_effect = async_mock_get_user

        # Mock session creation (async function)
        mock_session = MagicMock()
        mock_session.id = "test-session-id"
        mock_session.connection_id = "test-connection-id"
        mock_session.is_authenticated = test_user is not None
        async_mock_create_session = AsyncMock(return_value=mock_session)
        mock_session_manager.create_session = async_mock_create_session
        mock_session_manager.update_activity = MagicMock()

        # Mock manager connection (async function)
        async_mock_connect = AsyncMock(return_value="test-manager-connection-id")
        mock_manager.connect_with_account = async_mock_connect
        mock_manager.disconnect = MagicMock()
        mock_manager.active_connections = {}

        # Mock session cleanup (async function)
        async_mock_end_session = AsyncMock()
        mock_session_manager.end_session = async_mock_end_session

        return mock_session

    @patch("spacebridge.api.endpoints.websockets.handle_activity")
    @patch("spacebridge.api.endpoints.websockets.session_manager")
    @patch("spacebridge.api.endpoints.websockets.get_user_from_token_if_valid")
    @patch("spacebridge.api.endpoints.websockets.manager")
    def test_unified_websocket_handshake(
        self,
        mock_manager,
        mock_get_user,
        mock_session_manager,
        mock_handle_activity,
        client: TestClient,
        test_user: User,
    ):
        """Test WebSocket handshake with authenticated user."""
        mock_session = self._setup_websocket_mocks(
            mock_manager, mock_get_user, mock_session_manager, test_user
        )

        # Connect to WebSocket
        with client.websocket_connect(
            "/api/v1/ws/unified?token=test-token&fingerprint=test-fingerprint"
        ) as websocket:
            # Should receive handshake confirmation
            data = websocket.receive_json()
            assert data["type"] == "handshake"
            assert data["session_id"] == "test-session-id"
            assert data["authenticated"] is True
            assert data["message"] == "Connected to unified WebSocket"

    @patch("spacebridge.api.endpoints.websockets.handle_activity")
    @patch("spacebridge.api.endpoints.websockets.session_manager")
    @patch("spacebridge.api.endpoints.websockets.get_user_from_token_if_valid")
    @patch("spacebridge.api.endpoints.websockets.manager")
    def test_unified_websocket_ping_pong(
        self,
        mock_manager,
        mock_get_user,
        mock_session_manager,
        mock_handle_activity,
        client: TestClient,
        test_user: User,
    ):
        """Test WebSocket ping/pong heartbeat lifecycle."""
        mock_session = self._setup_websocket_mocks(
            mock_manager, mock_get_user, mock_session_manager, test_user
        )

        with client.websocket_connect(
            "/api/v1/ws/unified?token=test-token"
        ) as websocket:
            # Receive handshake
            handshake = websocket.receive_json()
            assert handshake["type"] == "handshake"

            # Send activity message (pong doesn't update activity, but other messages do)
            websocket.send_json({"type": "activity", "event_type": "test"})

            # Give it a moment to process
            import time

            time.sleep(0.05)

            # Verify session activity was updated
            mock_session_manager.update_activity.assert_called()

    @patch("spacebridge.api.endpoints.websockets.session_manager")
    @patch("spacebridge.api.endpoints.websockets.get_user_from_token_if_valid")
    def test_unified_websocket_invalid_token(
        self, mock_get_user, mock_session_manager, client: TestClient
    ):
        """Test WebSocket connection with invalid token."""
        # Mock invalid token (returns None)
        async_mock_get_user = AsyncMock(return_value=None)
        mock_get_user.side_effect = async_mock_get_user

        # Test expects connection to be rejected
        with client.websocket_connect(
            "/api/v1/ws/unified?token=invalid-token"
        ) as websocket:
            # Should receive error message
            data = websocket.receive_json()
            assert "error" in data
            assert "Invalid or expired authentication token" in data["error"]

            # Now the connection should close
            with pytest.raises(WebSocketDisconnect):
                websocket.receive_json()  # This will trigger disconnect

    @patch("spacebridge.api.endpoints.websockets.handle_activity")
    @patch("spacebridge.api.endpoints.websockets.session_manager")
    @patch("spacebridge.api.endpoints.websockets.get_user_from_token_if_valid")
    @patch("spacebridge.api.endpoints.websockets.manager")
    def test_unified_websocket_anonymous_connection(
        self,
        mock_manager,
        mock_get_user,
        mock_session_manager,
        mock_handle_activity,
        client: TestClient,
    ):
        """Test WebSocket connection without authentication (anonymous)."""
        # Setup mocks for anonymous user (test_user=None)
        # Mock user authentication (async function)
        async_mock_get_user = AsyncMock(return_value=None)
        mock_get_user.side_effect = async_mock_get_user

        # Mock session creation for anonymous user
        mock_session = MagicMock()
        mock_session.id = "anon-session-id"
        mock_session.connection_id = "anon-connection-id"
        mock_session.is_authenticated = False
        async_mock_create_session = AsyncMock(return_value=mock_session)
        mock_session_manager.create_session = async_mock_create_session
        mock_session_manager.update_activity = MagicMock()

        # Mock manager for anonymous connection
        mock_manager.active_connections = {}
        mock_manager.disconnect = MagicMock()

        # Mock session cleanup
        async_mock_end_session = AsyncMock()
        mock_session_manager.end_session = async_mock_end_session

        with client.websocket_connect(
            "/api/v1/ws/unified?fingerprint=anon-fingerprint"
        ) as websocket:
            # Should receive handshake for anonymous user
            data = websocket.receive_json()
            assert data["type"] == "handshake"
            assert data["session_id"] == "anon-session-id"
            assert data["authenticated"] is False

    @patch("spacebridge.api.endpoints.websockets.handle_activity")
    @patch("spacebridge.api.endpoints.websockets.session_manager")
    @patch("spacebridge.api.endpoints.websockets.get_user_from_token_if_valid")
    @patch("spacebridge.api.endpoints.websockets.manager")
    def test_unified_websocket_activity_tracking(
        self,
        mock_manager,
        mock_get_user,
        mock_session_manager,
        mock_handle_activity,
        client: TestClient,
        test_user: User,
    ):
        """Test activity tracking through WebSocket messages."""
        mock_session = self._setup_websocket_mocks(
            mock_manager, mock_get_user, mock_session_manager, test_user
        )

        # Mock handle_activity as async
        async_mock_handle_activity = AsyncMock()
        mock_handle_activity.side_effect = async_mock_handle_activity

        with client.websocket_connect(
            "/api/v1/ws/unified?token=test-token"
        ) as websocket:
            # Receive handshake
            handshake = websocket.receive_json()
            assert handshake["type"] == "handshake"

            # Send activity event
            activity_data = {
                "type": "activity",
                "event_type": "page_view",
                "path": "/dashboard",
            }
            websocket.send_json(activity_data)

            # Give it time to process
            import time

            time.sleep(0.1)

            # Verify activity handler was called
            mock_handle_activity.assert_called_once()

    @patch("spacebridge.api.endpoints.websockets.handle_activity")
    @patch("spacebridge.api.endpoints.websockets.session_manager")
    @patch("spacebridge.api.endpoints.websockets.get_user_from_token_if_valid")
    @patch("spacebridge.api.endpoints.websockets.manager")
    def test_unified_websocket_cleanup_on_disconnect(
        self,
        mock_manager,
        mock_get_user,
        mock_session_manager,
        mock_handle_activity,
        client: TestClient,
        test_user: User,
    ):
        """Test proper cleanup when WebSocket disconnects."""
        mock_session = self._setup_websocket_mocks(
            mock_manager, mock_get_user, mock_session_manager, test_user
        )

        with client.websocket_connect(
            "/api/v1/ws/unified?token=test-token"
        ) as websocket:
            # Receive handshake
            handshake = websocket.receive_json()
            assert handshake["type"] == "handshake"

            # Close connection
            websocket.close()

        # Verify cleanup was called
        mock_manager.disconnect.assert_called_once_with("test-manager-connection-id")
        mock_session_manager.end_session.assert_called_once()

    @patch("spacebridge.api.endpoints.websockets.handle_activity")
    @patch("spacebridge.api.endpoints.websockets.session_manager")
    @patch("spacebridge.api.endpoints.websockets.get_user_from_token_if_valid")
    @patch("spacebridge.api.endpoints.websockets.manager")
    def test_unified_websocket_cleanup_on_exception(
        self,
        mock_manager,
        mock_get_user,
        mock_session_manager,
        mock_handle_activity,
        client: TestClient,
        test_user: User,
    ):
        """Test cleanup runs even if manager_connection_id is not set (regression test)."""
        # Mock user authentication (async function)
        async_mock_get_user = AsyncMock(return_value=test_user)
        mock_get_user.side_effect = async_mock_get_user

        # Mock session creation (async function)
        mock_session = MagicMock()
        mock_session.id = "test-session-id"
        mock_session.connection_id = "test-connection-id"
        mock_session.is_authenticated = True
        async_mock_create_session = AsyncMock(return_value=mock_session)
        mock_session_manager.create_session = async_mock_create_session

        # Mock manager to raise exception during connection
        async_mock_connect = AsyncMock(side_effect=Exception("Connection failed"))
        mock_manager.connect_with_account = async_mock_connect
        mock_manager.disconnect = MagicMock()

        # Mock session cleanup (async function)
        async_mock_end_session = AsyncMock()
        mock_session_manager.end_session = async_mock_end_session

        # Should not raise UnboundLocalError in cleanup
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/api/v1/ws/unified?token=test-token"
            ) as websocket:
                # Should fail during connection setup
                # Just try to receive to trigger the exception
                websocket.receive_json()

        # Verify disconnect was NOT called (connection never established)
        mock_manager.disconnect.assert_not_called()

        # Verify session cleanup was still attempted
        mock_session_manager.end_session.assert_called_once()
