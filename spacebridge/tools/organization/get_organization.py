"""Get organization tool implementation."""

import uuid
from typing import Any, Dict, Optional, Set

from sqlalchemy.orm import Session

from spacebridge.db.session import get_db
from spacebridge.models.organization import Organization
from spacebridge.tools.base import MCPTool, MCPToolMetadata
from spacebridge.tools.registry import register_tool


@register_tool
class GetOrganizationTool(MCPTool):
    """Tool for retrieving organization details."""

    @classmethod
    def metadata(cls) -> MCPToolMetadata:
        """Get tool metadata."""
        return MCPToolMetadata(
            name="get_organization",
            description="Retrieves organization details and configuration",
            required_parameters={"organization"},
            optional_parameters={},
        )

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool.

        Args:
            parameters: Tool parameters.
                - organization: String - Organization identifier

        Returns:
            Organization details including name, description, etc.
        """
        # Validate parameters
        validated_params = self.validate_parameters(parameters)
        organization_identifier = validated_params["organization"]

        # Get database session
        db = next(get_db())

        try:
            # Get organization by identifier
            organization = (
                db.query(Organization)
                .filter(Organization.identifier == organization_identifier)
                .first()
            )

            if not organization:
                return {
                    "error": "not_found",
                    "message": f"Organization '{organization_identifier}' not found",
                }

            # Get projects for the organization
            projects = [
                {
                    "id": project.id,
                    "name": project.name,
                    "identifier": project.identifier,
                    "description": project.description or "",
                    "trackers": project.trackers,
                }
                for project in organization.projects
            ]

            # Return organization details
            return {
                "id": organization.id,
                "name": organization.name,
                "identifier": organization.identifier,
                "description": organization.description or "",
                "settings": organization.settings or {},
                "projects": projects,
                "created_at": organization.created_at.isoformat(),
                "updated_at": organization.updated_at.isoformat(),
            }
        finally:
            db.close()