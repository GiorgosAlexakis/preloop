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

    def test_get_version_with_valid_token_logs_account(
        self, client: TestClient, test_user
    ):
        """Test GET /version with valid token returns version (auth is optional)."""
        from preloop.api.auth.jwt import create_access_token

        token = create_access_token(
            data={"sub": str(test_user.id), "account_id": str(test_user.account_id)}
        )
        response = client.get(
            "/api/v1/version",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Client-Version": "2.0.0",
                "X-Client-Organization": "my-org",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "server_version" in data

    def test_get_version_with_invalid_token_still_returns_version(
        self, client: TestClient
    ):
        """Test GET /version with invalid token still returns version (auth is optional)."""
        response = client.get(
            "/api/v1/version",
            headers={
                "Authorization": "Bearer invalid-token",
                "X-Client-Version": "1.0.0",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "server_version" in data

    def test_get_version_with_additional_info_header(self, client: TestClient):
        """Test GET /version with X-Additional-Info header is accepted."""
        response = client.get(
            "/api/v1/version",
            headers={
                "X-Client-Version": "1.0.0",
                "X-Additional-Info": "mobile-app",
            },
        )
        assert response.status_code == 200
