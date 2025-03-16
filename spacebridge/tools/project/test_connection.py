"""Test connection to an issue tracker."""

import logging
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from spacebridge.db.session import get_db
from spacebridge.models.organization import Organization
from spacebridge.models.project import Project
from spacebridge.tools.base import MCPTool, MCPToolMetadata
from spacebridge.tools.registry import register_tool
from spacebridge.tools.utils import run_async
from spacebridge.trackers.factory import TrackerFactory

logger = logging.getLogger(__name__)


@register_tool
class TestConnectionTool(MCPTool):
    """Tool for testing connectivity to a project's issue trackers."""

    @classmethod
    def metadata(cls) -> MCPToolMetadata:
        """Get tool metadata."""
        return MCPToolMetadata(
            name="test_connection",
            description="Tests connectivity to configured issue trackers",
            required_parameters={"organization", "project"},
            optional_parameters={"tracker": None},
        )

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool.

        Args:
            parameters: Tool parameters.
                - organization: String - Organization identifier
                - project: String - Project identifier
                - tracker: Optional[String] - Specific tracker to test (tests all if not specified)

        Returns:
            Connection status for each tracker.
        """
        # Validate parameters
        validated_params = self.validate_parameters(parameters)
        organization_identifier = validated_params["organization"]
        project_identifier = validated_params["project"]
        tracker_type = validated_params.get("tracker")

        # Get database session
        db = next(get_db())

        try:
            # Get organization
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

            # Get project
            project = (
                db.query(Project)
                .filter(
                    Project.organization_id == organization.id,
                    Project.identifier == project_identifier,
                )
                .first()
            )

            if not project:
                return {
                    "error": "not_found",
                    "message": f"Project '{project_identifier}' not found in organization '{organization_identifier}'",
                }

            # If no tracker configurations, return an error
            if not project.tracker_configurations:
                return {
                    "error": "no_trackers",
                    "message": f"Project '{project_identifier}' has no configured trackers",
                }

            # Test connection to each tracker
            results = {}
            trackers_to_test = [tracker_type] if tracker_type else project.trackers

            # For each tracker configuration
            for tracker in trackers_to_test:
                # If the tracker is not configured, skip it
                if tracker not in project.tracker_configurations:
                    results[tracker] = {
                        "connected": False,
                        "message": f"Tracker '{tracker}' is not configured for this project",
                    }
                    continue

                try:
                    # Get the tracker configuration
                    tracker_config = project.tracker_configurations[tracker]
                    
                    # Create a tracker client based on tracker type
                    # Handles all supported trackers: github, gitlab, jira
                    tracker_client = run_async(
                        TrackerFactory.create_client(tracker, tracker_config)
                    )
                    
                    if not tracker_client:
                        results[tracker] = {
                            "connected": False,
                            "message": f"Failed to create client for tracker '{tracker}'",
                        }
                        continue
                    
                    # Test the connection
                    connection_result = run_async(tracker_client.test_connection())
                    
                    # Store the result
                    results[tracker] = {
                        "connected": connection_result.connected,
                        "message": connection_result.message,
                        "rate_limit": connection_result.rate_limit,
                        "server_info": connection_result.server_info,
                    }
                
                except Exception as e:
                    logger.exception(f"Error testing connection to {tracker}: {e}")
                    results[tracker] = {
                        "connected": False,
                        "message": f"Error testing connection: {str(e)}",
                    }

            return {
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "identifier": project.identifier,
                },
                "connection_results": results,
            }
        
        finally:
            db.close()