"""Tests for the get_organization tool."""

from unittest.mock import MagicMock, patch

import pytest

from preloop_ai.tools.organization.get_organization import get_organization


class TestGetOrganizationTool:
    """Test cases for the get_organization tool."""

    def test_tool_registration(self):
        """Test that the tool is properly registered."""
        # Skip this test as the mcp_server module no longer exists
        # This test will be updated when a new tool registration mechanism is implemented
        pass

    @patch("preloop_ai.tools.organization.get_organization.get_db")
    @pytest.mark.asyncio
    async def test_execute_not_found(self, mock_get_db):
        """Test that the tool returns an error when the organization is not found."""
        # Mock the CRUD operation
        mock_crud = MagicMock()
        mock_crud.get_by_identifier.return_value = None

        # Mock the database session
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        # Patch the CRUD class
        with patch(
            "preloop_ai.tools.organization.get_organization.CRUDOrganization",
            return_value=mock_crud,
        ):
            # Execute the tool
            result = await get_organization(organization="nonexistent")

            # Check the result
            assert result["error"] == "not_found"
            assert "not found" in result["message"]

    @patch("preloop_ai.tools.organization.get_organization.get_db")
    @pytest.mark.asyncio
    async def test_execute_success(self, mock_get_db):
        """Test that the tool returns the organization details when found."""
        # Mock the organization
        mock_organization = MagicMock()
        mock_organization.id = 123
        mock_organization.name = "Test Organization"
        mock_organization.identifier = "test-org"
        mock_organization.description = "Test description"
        mock_organization.settings = {"setting1": "value1"}
        mock_organization.projects = []
        mock_organization.is_active = True
        mock_organization.created_at.isoformat.return_value = "2025-01-01T00:00:00"
        mock_organization.updated_at.isoformat.return_value = "2025-01-01T00:00:00"

        # Mock the CRUD operation
        mock_crud = MagicMock()
        mock_crud.get_by_identifier.return_value = mock_organization

        # Mock the database session
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        # Patch the CRUD class
        with patch(
            "preloop_ai.tools.organization.get_organization.CRUDOrganization",
            return_value=mock_crud,
        ):
            # Execute the tool
            result = await get_organization(organization="test-org")

            # Check the result
            assert result["id"] == 123
            assert result["name"] == "Test Organization"
            assert result["identifier"] == "test-org"
            assert result["description"] == "Test description"
            assert result["settings"] == {"setting1": "value1"}
            assert result["projects"] == []
            assert result["created_at"] == "2025-01-01T00:00:00"
            assert result["updated_at"] == "2025-01-01T00:00:00"
