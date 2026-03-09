"""Tests for version API endpoint."""

from fastapi.testclient import TestClient


class TestVersionEndpoint:
    """Test GET /api/v1/version endpoint."""

    def test_get_version_success(self, client: TestClient):
        """Test GET /version returns 200 and version info."""
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        data = response.json()
        assert "server_version" in data
        assert "min_client_version" in data
        assert "max_client_version" in data
        assert isinstance(data["server_version"], str)
        assert len(data["server_version"]) > 0

    def test_get_version_without_auth(self, client: TestClient):
        """Test GET /version works without authentication (public endpoint)."""
        response = client.get("/api/v1/version")
        assert response.status_code == 200

    def test_get_version_with_headers(self, client: TestClient):
        """Test GET /version with optional X-Client-* headers."""
        response = client.get(
            "/api/v1/version",
            headers={
                "X-Client-Version": "1.0.0",
                "X-Client-Organization": "test-org",
                "X-Client-Project": "test-project",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "server_version" in data
