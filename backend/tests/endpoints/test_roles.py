"""Tests for roles API endpoint."""

from fastapi.testclient import TestClient


class TestRolesEndpoint:
    """Test GET /api/v1/roles endpoint."""

    def test_get_roles_success(self, client: TestClient):
        """Test GET /roles returns 200 and list of roles."""
        response = client.get("/api/v1/roles")
        assert response.status_code == 200
        data = response.json()
        assert "roles" in data
        assert "total" in data
        assert isinstance(data["roles"], list)
        assert isinstance(data["total"], int)
        assert data["total"] == len(data["roles"])

    def test_get_roles_structure(self, client: TestClient):
        """Test that each role has expected fields."""
        response = client.get("/api/v1/roles")
        assert response.status_code == 200
        data = response.json()
        for role in data["roles"]:
            assert "id" in role
            assert "name" in role
            assert "description" in role
            assert "permissions" in role
            assert isinstance(role["permissions"], list)
            for perm in role["permissions"]:
                assert "id" in perm
                assert "name" in perm
                assert "description" in perm
