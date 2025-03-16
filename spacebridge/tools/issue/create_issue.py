"""Create an issue in an issue tracker."""

import logging
from typing import Any, Dict

from spacebridge.db.session import get_db
from spacebridge.models.organization import Organization
from spacebridge.models.project import Project
from spacebridge.tools.base import MCPTool, MCPToolMetadata
from spacebridge.tools.registry import register_tool
from spacebridge.tools.utils import run_async
from spacebridge.trackers.base import IssueCreate
from spacebridge.trackers.factory import TrackerFactory

logger = logging.getLogger(__name__)


@register_tool
class CreateIssueTool(MCPTool):
    """Tool for creating issues in trackers."""

    @classmethod
    def metadata(cls) -> MCPToolMetadata:
        """Get tool metadata."""
        return MCPToolMetadata(
            name="create_issue",
            description="Creates a new issue in the specified tracker",
            required_parameters={"organization", "project", "title", "description"},
            optional_parameters={
                "tracker": None,
                "status": None,
                "priority": None,
                "labels": None,
                "assignee": None,
                "custom_fields": None,
                "check_duplicates": True,
            },
        )

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool.

        Args:
            parameters: Tool parameters.
                - organization: String - Organization identifier
                - project: String - Project identifier
                - title: String - Issue title
                - description: String - Issue description
                - tracker: Optional[String] - Specific tracker to create the issue in
                - status: Optional[String] - Initial issue status
                - priority: Optional[String] - Issue priority
                - labels: Optional[List[String]] - Issue labels
                - assignee: Optional[String] - Initial assignee
                - custom_fields: Optional[Dict] - Tracker-specific custom fields
                - check_duplicates: Optional[Bool] - Whether to check for potential duplicates

        Returns:
            The created issue.
        """
        # Validate parameters
        validated_params = self.validate_parameters(parameters)
        organization_identifier = validated_params["organization"]
        project_identifier = validated_params["project"]
        title = validated_params["title"]
        description = validated_params["description"]
        tracker_type = validated_params.get("tracker")
        check_duplicates = validated_params.get("check_duplicates", True)

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

            # Determine which tracker to use
            if tracker_type:
                # Use the specified tracker
                if tracker_type not in project.tracker_configurations:
                    return {
                        "error": "tracker_not_found",
                        "message": f"Tracker '{tracker_type}' is not configured for this project",
                    }
                tracker_to_use = tracker_type
            else:
                # Use the first available tracker
                tracker_to_use = project.trackers[0]

            # Create issue data
            issue_data = IssueCreate(
                title=title,
                description=description,
                status=validated_params.get("status"),
                priority=validated_params.get("priority"),
                assignee=validated_params.get("assignee"),
                labels=validated_params.get("labels"),
                custom_fields=validated_params.get("custom_fields"),
            )

            try:
                # Get the tracker configuration
                tracker_config = project.tracker_configurations[tracker_to_use]

                # Create a tracker client
                tracker_client = run_async(
                    TrackerFactory.create_client(tracker_to_use, tracker_config)
                )

                if not tracker_client:
                    return {
                        "error": "client_creation_failed",
                        "message": f"Failed to create client for tracker '{tracker_to_use}'",
                    }

                # Create the issue
                issue = run_async(
                    tracker_client.create_issue(
                        project_key=project.identifier,
                        issue_data=issue_data,
                    )
                )

                # Convert issue to dictionary
                issue_dict = issue.dict()

                # Add a source field to indicate which tracker this came from
                issue_dict["source"] = tracker_to_use

                return {
                    "issue": issue_dict,
                    "tracker": tracker_to_use,
                    "project": {
                        "id": project.id,
                        "name": project.name,
                        "identifier": project.identifier,
                    },
                    "organization": {
                        "id": organization.id,
                        "name": organization.name,
                        "identifier": organization.identifier,
                    },
                }

            except Exception as e:
                logger.exception(f"Error creating issue in {tracker_to_use}: {e}")
                return {
                    "error": "creation_failed",
                    "message": f"Error creating issue: {str(e)}",
                }

        finally:
            db.close()
