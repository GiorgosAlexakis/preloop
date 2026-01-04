"""Tests for APNs service."""

from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from preloop.services.push_notifications.apns_service import APNsService

pytestmark = pytest.mark.asyncio


class TestAPNsServiceInit:
    """Test APNs service initialization."""

    def test_initialization_success(self):
        """Test successful initialization of APNs service."""
        with patch("builtins.open", mock_open(read_data="fake_private_key")):
            service = APNsService(
                team_id="TESTTEAM12",
                key_id="TESTKEY123",
                auth_key_path="/fake/path.p8",
                bundle_id="com.test.app",
                use_sandbox=True,
            )

            assert service.team_id == "TESTTEAM12"
            assert service.key_id == "TESTKEY123"
            assert service.bundle_id == "com.test.app"
            assert service.auth_key == "fake_private_key"
            assert service.apns_server == "https://api.sandbox.push.apple.com"

    def test_production_server_url(self):
        """Test production server URL is used when use_sandbox=False."""
        with patch("builtins.open", mock_open(read_data="fake_key")):
            service = APNsService(
                team_id="TESTTEAM12",
                key_id="TESTKEY123",
                auth_key_path="/fake/path.p8",
                bundle_id="com.test.app",
                use_sandbox=False,
            )

            assert service.apns_server == "https://api.push.apple.com"

    def test_sandbox_server_url(self):
        """Test sandbox server URL is used when use_sandbox=True."""
        with patch("builtins.open", mock_open(read_data="fake_key")):
            service = APNsService(
                team_id="TESTTEAM12",
                key_id="TESTKEY123",
                auth_key_path="/fake/path.p8",
                bundle_id="com.test.app",
                use_sandbox=True,
            )

            assert service.apns_server == "https://api.sandbox.push.apple.com"


class TestJWTTokenGeneration:
    """Test JWT token generation and caching."""

    def test_generate_jwt_token(self):
        """Test JWT token generation."""
        with patch("builtins.open", mock_open(read_data="fake_key")):
            service = APNsService(
                team_id="TESTTEAM12",
                key_id="TESTKEY123",
                auth_key_path="/fake/path.p8",
                bundle_id="com.test.app",
            )

        with patch(
            "preloop.services.push_notifications.apns_service.jwt.encode"
        ) as mock_encode:
            mock_encode.return_value = "fake.jwt.token"

            token = service._generate_jwt_token()

            assert token == "fake.jwt.token"
            mock_encode.assert_called_once()

            # Verify JWT claims
            call_args = mock_encode.call_args
            payload = call_args[0][0]
            assert payload["iss"] == "TESTTEAM12"
            assert "iat" in payload

            # Verify headers
            headers = call_args[1]["headers"]
            assert headers["alg"] == "ES256"
            assert headers["kid"] == "TESTKEY123"

    def test_jwt_token_caching(self):
        """Test JWT token is cached and reused."""
        with patch("builtins.open", mock_open(read_data="fake_key")):
            service = APNsService(
                team_id="TESTTEAM12",
                key_id="TESTKEY123",
                auth_key_path="/fake/path.p8",
                bundle_id="com.test.app",
            )

        with patch(
            "preloop.services.push_notifications.apns_service.jwt.encode"
        ) as mock_encode:
            mock_encode.return_value = "fake.jwt.token"

            # First call should generate token
            token1 = service._generate_jwt_token()

            # Second call should return cached token
            token2 = service._generate_jwt_token()

            assert token1 == token2
            # JWT encode should only be called once due to caching
            assert mock_encode.call_count == 1

    def test_jwt_token_expiration_and_refresh(self):
        """Test JWT token is refreshed when expired."""
        with patch("builtins.open", mock_open(read_data="fake_key")):
            service = APNsService(
                team_id="TESTTEAM12",
                key_id="TESTKEY123",
                auth_key_path="/fake/path.p8",
                bundle_id="com.test.app",
            )

        with (
            patch(
                "preloop.services.push_notifications.apns_service.jwt.encode"
            ) as mock_encode,
            patch("time.time") as mock_time,
        ):
            mock_encode.side_effect = ["first.jwt.token", "second.jwt.token"]
            mock_time.return_value = 1000

            # First call generates token
            token1 = service._generate_jwt_token()
            assert token1 == "first.jwt.token"

            # Simulate time passage beyond expiration (58 minutes = 3480 seconds)
            mock_time.return_value = 1000 + 3500

            # Second call should generate new token
            token2 = service._generate_jwt_token()
            assert token2 == "second.jwt.token"
            assert mock_encode.call_count == 2


class TestSendNotification:
    """Test send_notification method."""

    @pytest.fixture
    def apns_service(self):
        """Create APNs service for testing."""
        with patch("builtins.open", mock_open(read_data="fake_key")):
            return APNsService(
                team_id="TESTTEAM12",
                key_id="TESTKEY123",
                auth_key_path="/fake/path.p8",
                bundle_id="com.test.app",
                use_sandbox=True,
            )

    @pytest.fixture
    def mock_jwt(self):
        """Mock JWT encode for all tests."""
        with patch(
            "preloop.services.push_notifications.apns_service.jwt.encode",
            return_value="fake.jwt.token",
        ) as mock:
            yield mock

    async def test_send_notification_success_200(self, apns_service, mock_jwt):
        """Test successful notification send with 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            success, status_code, error_reason = await apns_service.send_notification(
                device_token="a" * 64, payload={"aps": {"alert": "Test"}}
            )

            assert success is True
            assert status_code == 200
            assert error_reason is None

    async def test_send_notification_invalid_token_410(self, apns_service, mock_jwt):
        """Test notification with invalid token (410 response)."""
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_response.json.return_value = {"reason": "Unregistered"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            success, status_code, error_reason = await apns_service.send_notification(
                device_token="a" * 64, payload={"aps": {"alert": "Test"}}
            )

            assert success is False
            assert status_code == 410
            assert error_reason == "Unregistered"

    async def test_send_notification_bad_request_400(self, apns_service, mock_jwt):
        """Test notification with bad request (400 response)."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"reason": "BadDeviceToken"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            success, status_code, error_reason = await apns_service.send_notification(
                device_token="invalid_token", payload={"aps": {"alert": "Test"}}
            )

            assert success is False
            assert status_code == 400
            assert error_reason == "BadDeviceToken"

    async def test_send_notification_auth_failure_403(self, apns_service, mock_jwt):
        """Test notification with authentication failure (403 response)."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"reason": "InvalidProviderToken"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            success, status_code, error_reason = await apns_service.send_notification(
                device_token="a" * 64, payload={"aps": {"alert": "Test"}}
            )

            assert success is False
            assert status_code == 403
            assert error_reason == "InvalidProviderToken"

    async def test_send_notification_payload_too_large_413(
        self, apns_service, mock_jwt
    ):
        """Test notification with payload too large (413 response)."""
        mock_response = MagicMock()
        mock_response.status_code = 413
        mock_response.json.return_value = {"reason": "PayloadTooLarge"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            large_payload = {"aps": {"alert": "X" * 5000}}
            success, status_code, error_reason = await apns_service.send_notification(
                device_token="a" * 64, payload=large_payload
            )

            assert success is False
            assert status_code == 413
            assert error_reason == "PayloadTooLarge"

    async def test_send_notification_rate_limited_429(self, apns_service, mock_jwt):
        """Test notification with rate limit (429 response)."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"reason": "TooManyRequests"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            success, status_code, error_reason = await apns_service.send_notification(
                device_token="a" * 64, payload={"aps": {"alert": "Test"}}
            )

            assert success is False
            assert status_code == 429
            assert error_reason == "TooManyRequests"

    async def test_send_notification_server_error_500(self, apns_service, mock_jwt):
        """Test notification with server error (500 response)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"reason": "InternalServerError"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            success, status_code, error_reason = await apns_service.send_notification(
                device_token="a" * 64, payload={"aps": {"alert": "Test"}}
            )

            assert success is False
            assert status_code == 500
            assert error_reason == "InternalServerError"

    async def test_send_notification_with_collapse_id(self, apns_service, mock_jwt):
        """Test notification with collapse ID."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            await apns_service.send_notification(
                device_token="a" * 64,
                payload={"aps": {"alert": "Test"}},
                collapse_id="test-collapse-id",
            )

            # Verify collapse_id was included in headers
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs["headers"]
            assert "apns-collapse-id" in headers
            assert headers["apns-collapse-id"] == "test-collapse-id"

    async def test_send_notification_with_priority(self, apns_service, mock_jwt):
        """Test notification with custom priority."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            await apns_service.send_notification(
                device_token="a" * 64,
                payload={"aps": {"alert": "Test"}},
                priority=5,
            )

            # Verify priority was included in headers
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs["headers"]
            assert headers["apns-priority"] == "5"

    async def test_send_notification_network_exception(self, apns_service, mock_jwt):
        """Test notification with network exception."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Network error")
            )

            success, status_code, error_reason = await apns_service.send_notification(
                device_token="a" * 64, payload={"aps": {"alert": "Test"}}
            )

            assert success is False
            assert status_code == 0
            assert "Network error" in error_reason

    async def test_send_notification_http2_enabled(self, apns_service, mock_jwt):
        """Test that HTTP/2 is enabled for APNs requests."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await apns_service.send_notification(
                device_token="a" * 64, payload={"aps": {"alert": "Test"}}
            )

            # Verify HTTP/2 was enabled
            mock_client_class.assert_called_with(http2=True)
