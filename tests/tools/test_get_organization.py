"""Tests for the get_organization tool."""

import unittest
from unittest.mock import MagicMock, patch

from spacebridge.tools.organization import GetOrganizationTool


class TestGetOrganizationTool(unittest.TestCase):
    """Test cases for the get_organization tool."""

    def test_metadata(self):
        """Test that the tool metadata is correct."""
        metadata = GetOrganizationTool.metadata()
        self.assertEqual(metadata.name, "get_organization")
        self.assertEqual(metadata.required_parameters, {"organization"})

    @patch("spacebridge.tools.organization.get_organization.get_db")
    def test_execute_not_found(self, mock_get_db):
        """Test that the tool returns an error when the organization is not found."""
        # Mock the database session
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        mock_get_db.return_value = iter([mock_session])

        # Execute the tool
        tool = GetOrganizationTool()
        result = tool.execute({"organization": "nonexistent"})

        # Check the result
        self.assertEqual(result["error"], "not_found")
        self.assertIn("not found", result["message"])

    @patch("spacebridge.tools.organization.get_organization.get_db")
    def test_execute_success(self, mock_get_db):
        """Test that the tool returns the organization details when found."""
        # Mock the organization
        mock_organization = MagicMock()
        mock_organization.id = "org_id"
        mock_organization.name = "Test Organization"
        mock_organization.identifier = "test-org"
        mock_organization.description = "Test description"
        mock_organization.settings = {"setting1": "value1"}
        mock_organization.projects = []
        mock_organization.created_at.isoformat.return_value = "2025-01-01T00:00:00"
        mock_organization.updated_at.isoformat.return_value = "2025-01-01T00:00:00"

        # Mock the database session
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_organization
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query
        mock_get_db.return_value = iter([mock_session])

        # Execute the tool
        tool = GetOrganizationTool()
        result = tool.execute({"organization": "test-org"})

        # Check the result
        self.assertEqual(result["id"], "org_id")
        self.assertEqual(result["name"], "Test Organization")
        self.assertEqual(result["identifier"], "test-org")
        self.assertEqual(result["description"], "Test description")
        self.assertEqual(result["settings"], {"setting1": "value1"})
        self.assertEqual(result["projects"], [])
        self.assertEqual(result["created_at"], "2025-01-01T00:00:00")
        self.assertEqual(result["updated_at"], "2025-01-01T00:00:00")
