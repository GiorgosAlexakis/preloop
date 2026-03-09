"""Tests for account API endpoints."""

from fastapi.testclient import TestClient


class TestAccountDetails:
    """Test GET and PATCH /api/v1/account/details endpoints."""

    def test_get_account_details_success(self, client: TestClient):
        """Test GET /account/details returns current account info."""
        response = client.get("/api/v1/account/details")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "organization_name" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert isinstance(data["id"], str)
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

    def test_patch_account_details_success(self, client: TestClient):
        """Test PATCH /account/details updates organization name."""
        response = client.patch(
            "/api/v1/account/details",
            json={"organization_name": "Updated Org Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["organization_name"] == "Updated Org Name"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_patch_account_details_partial(self, client: TestClient):
        """Test PATCH /account/details with empty org name (clear)."""
        response = client.patch(
            "/api/v1/account/details",
            json={"organization_name": None},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["organization_name"] is None
