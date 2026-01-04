"""Tests for request utility functions."""

from typing import Dict, Optional


from preloop.utils.request import get_client_ip, get_client_ip_optional


class MockHeaders:
    """Mock headers object for testing."""

    def __init__(self, headers: Dict[str, str]):
        self._headers = {k.lower(): v for k, v in headers.items()}

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get header value case-insensitively."""
        return self._headers.get(key.lower(), default)


class MockClient:
    """Mock client object for testing."""

    def __init__(self, host: str):
        self.host = host


class MockRequest:
    """Mock request object for testing."""

    def __init__(
        self,
        headers: Optional[Dict[str, str]] = None,
        client_host: Optional[str] = None,
    ):
        self.headers = MockHeaders(headers or {})
        self.client = MockClient(client_host) if client_host else None


class TestGetClientIp:
    """Tests for get_client_ip function."""

    def test_x_forwarded_for_single_ip(self):
        """Test extraction from X-Forwarded-For with single IP."""
        request = MockRequest(headers={"X-Forwarded-For": "203.0.113.195"})
        assert get_client_ip(request) == "203.0.113.195"

    def test_x_forwarded_for_multiple_ips(self):
        """Test extraction from X-Forwarded-For with multiple IPs (takes first)."""
        request = MockRequest(
            headers={"X-Forwarded-For": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
        )
        assert get_client_ip(request) == "203.0.113.195"

    def test_x_forwarded_for_with_spaces(self):
        """Test extraction from X-Forwarded-For with spaces around IPs."""
        request = MockRequest(
            headers={"X-Forwarded-For": " 203.0.113.195 , 70.41.3.18 "}
        )
        assert get_client_ip(request) == "203.0.113.195"

    def test_x_forwarded_for_case_insensitive(self):
        """Test that X-Forwarded-For is case-insensitive."""
        request = MockRequest(headers={"x-forwarded-for": "203.0.113.195"})
        assert get_client_ip(request) == "203.0.113.195"

    def test_x_real_ip(self):
        """Test extraction from X-Real-IP header."""
        request = MockRequest(headers={"X-Real-IP": "198.51.100.42"})
        assert get_client_ip(request) == "198.51.100.42"

    def test_x_real_ip_case_insensitive(self):
        """Test that X-Real-IP is case-insensitive."""
        request = MockRequest(headers={"x-real-ip": "198.51.100.42"})
        assert get_client_ip(request) == "198.51.100.42"

    def test_x_forwarded_for_takes_precedence_over_x_real_ip(self):
        """Test that X-Forwarded-For is checked before X-Real-IP."""
        request = MockRequest(
            headers={
                "X-Forwarded-For": "203.0.113.195",
                "X-Real-IP": "198.51.100.42",
            }
        )
        assert get_client_ip(request) == "203.0.113.195"

    def test_direct_client_ip(self):
        """Test fallback to direct client IP."""
        request = MockRequest(client_host="192.168.1.100")
        assert get_client_ip(request) == "192.168.1.100"

    def test_x_real_ip_takes_precedence_over_client_host(self):
        """Test that X-Real-IP is checked before client.host."""
        request = MockRequest(
            headers={"X-Real-IP": "198.51.100.42"}, client_host="10.0.0.173"
        )
        assert get_client_ip(request) == "198.51.100.42"

    def test_none_request(self):
        """Test with None request."""
        assert get_client_ip(None) == "unknown"

    def test_no_client_no_headers(self):
        """Test with request having no client and no headers."""
        request = MockRequest()
        assert get_client_ip(request) == "unknown"

    def test_kubernetes_ingress_scenario(self):
        """Test realistic Kubernetes ingress scenario with pod IP."""
        # In Kubernetes, ingress sets X-Forwarded-For, client.host is pod IP
        request = MockRequest(
            headers={"X-Forwarded-For": "203.0.113.195, 10.0.0.1"},
            client_host="10.0.0.173",  # Pod IP
        )
        assert get_client_ip(request) == "203.0.113.195"

    def test_ipv6_address(self):
        """Test with IPv6 address."""
        request = MockRequest(headers={"X-Forwarded-For": "2001:db8::1"})
        assert get_client_ip(request) == "2001:db8::1"

    def test_localhost_addresses(self):
        """Test with localhost addresses."""
        request = MockRequest(client_host="127.0.0.1")
        assert get_client_ip(request) == "127.0.0.1"

        request_ipv6 = MockRequest(client_host="::1")
        assert get_client_ip(request_ipv6) == "::1"


class TestGetClientIpOptional:
    """Tests for get_client_ip_optional function."""

    def test_x_forwarded_for(self):
        """Test extraction from X-Forwarded-For."""
        request = MockRequest(headers={"X-Forwarded-For": "203.0.113.195"})
        assert get_client_ip_optional(request) == "203.0.113.195"

    def test_x_real_ip(self):
        """Test extraction from X-Real-IP."""
        request = MockRequest(headers={"X-Real-IP": "198.51.100.42"})
        assert get_client_ip_optional(request) == "198.51.100.42"

    def test_direct_client_ip(self):
        """Test fallback to direct client IP."""
        request = MockRequest(client_host="192.168.1.100")
        assert get_client_ip_optional(request) == "192.168.1.100"

    def test_none_request(self):
        """Test with None request returns None."""
        assert get_client_ip_optional(None) is None

    def test_no_client_no_headers(self):
        """Test with request having no client and no headers returns None."""
        request = MockRequest()
        assert get_client_ip_optional(request) is None

    def test_returns_none_instead_of_unknown(self):
        """Test that function returns None instead of 'unknown' string."""
        request = MockRequest()
        result = get_client_ip_optional(request)
        assert result is None
        assert result != "unknown"


class TestWebSocketCompatibility:
    """Tests for WebSocket request compatibility."""

    def test_websocket_mock(self):
        """Test with WebSocket-like object (has same interface as Request)."""
        # WebSocket objects have the same headers and client attributes
        websocket = MockRequest(
            headers={"X-Forwarded-For": "203.0.113.195"}, client_host="10.0.0.173"
        )
        assert get_client_ip(websocket) == "203.0.113.195"

    def test_websocket_without_headers(self):
        """Test WebSocket without proxy headers falls back to client IP."""
        websocket = MockRequest(client_host="192.168.1.100")
        assert get_client_ip(websocket) == "192.168.1.100"


class TestRealWorldScenarios:
    """Tests for real-world scenarios."""

    def test_nginx_proxy(self):
        """Test with nginx proxy configuration."""
        request = MockRequest(
            headers={
                "X-Forwarded-For": "203.0.113.195",
                "X-Real-IP": "203.0.113.195",
            },
            client_host="172.17.0.5",  # Docker container IP
        )
        assert get_client_ip(request) == "203.0.113.195"

    def test_cloudflare_proxy(self):
        """Test with Cloudflare proxy (adds multiple IPs to X-Forwarded-For)."""
        request = MockRequest(
            headers={
                "X-Forwarded-For": "203.0.113.195, 173.245.48.0, 103.21.244.0",
                "CF-Connecting-IP": "203.0.113.195",
            }
        )
        assert get_client_ip(request) == "203.0.113.195"

    def test_aws_alb(self):
        """Test with AWS Application Load Balancer."""
        request = MockRequest(
            headers={"X-Forwarded-For": "203.0.113.195, 10.0.1.5"},
            client_host="10.0.1.10",
        )
        assert get_client_ip(request) == "203.0.113.195"

    def test_direct_connection_no_proxy(self):
        """Test direct connection without any proxy."""
        request = MockRequest(client_host="203.0.113.195")
        assert get_client_ip(request) == "203.0.113.195"

    def test_local_development(self):
        """Test local development scenario."""
        request = MockRequest(client_host="127.0.0.1")
        assert get_client_ip(request) == "127.0.0.1"

    def test_production_email_notification_scenario(self):
        """Test the specific scenario from the bug report."""
        # Before fix: router.py used request.client.host which gave pod IP
        # After fix: should extract real IP from X-Forwarded-For
        request = MockRequest(
            headers={"X-Forwarded-For": "203.0.113.195"},
            client_host="10.0.0.173",  # Kubernetes pod IP (the bug)
        )
        client_ip = get_client_ip(request)

        # Should get real client IP, not pod IP
        assert client_ip == "203.0.113.195"
        assert client_ip != "10.0.0.173"
