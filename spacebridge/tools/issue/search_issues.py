"""Search issues across issue trackers."""

import logging
from typing import Any, Dict

from spacebridge.db.session import get_db
from spacebridge.models.organization import Organization
from spacebridge.models.project import Project
from spacebridge.tools.base import MCPTool, MCPToolMetadata
from spacebridge.tools.registry import register_tool
from spacebridge.tools.utils import run_async
from spacebridge.trackers.base import IssueFilter
from spacebridge.trackers.factory import TrackerFactory

logger = logging.getLogger(__name__)


@register_tool
class SearchIssuesTool(MCPTool):
    """Tool for searching issues across trackers."""

    @classmethod
    def metadata(cls) -> MCPToolMetadata:
        """Get tool metadata."""
        return MCPToolMetadata(
            name="search_issues",
            description="Performs hybrid search using vector similarity and direct API queries",
            required_parameters={"organization", "project", "query"},
            optional_parameters={
                "limit": 10,
                "trackers": None,
                "status": None,
                "labels": None,
                "created_after": None,
                "created_before": None,
                "updated_after": None,
                "updated_before": None,
                "assigned_to": None,
            },
        )

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool.

        Args:
            parameters: Tool parameters.
                - organization: String - Organization identifier
                - project: String - Project identifier
                - query: String - Search query
                - limit: Optional[Int] - Maximum number of results (default: 10)
                - trackers: Optional[List[String]] - Specific trackers to search
                - status: Optional[List[String]] - Filter by issue status
                - labels: Optional[List[String]] - Filter by issue labels
                - created_after: Optional[String] - Filter by creation date (ISO format)
                - created_before: Optional[String] - Filter by creation date (ISO format)
                - updated_after: Optional[String] - Filter by update date (ISO format)
                - updated_before: Optional[String] - Filter by update date (ISO format)
                - assigned_to: Optional[String] - Filter by assignee

        Returns:
            Search results from each tracker.
        """
        # Validate parameters
        validated_params = self.validate_parameters(parameters)
        organization_identifier = validated_params["organization"]
        project_identifier = validated_params["project"]
        query = validated_params["query"]
        limit = validated_params.get("limit", 10)
        trackers = validated_params.get("trackers")

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

            # Determine which trackers to search
            trackers_to_search = trackers if trackers else project.trackers

            # Create an issue filter from the parameters
            filter_params = IssueFilter(
                query=query,
                status=validated_params.get("status"),
                labels=validated_params.get("labels"),
                created_after=validated_params.get("created_after"),
                created_before=validated_params.get("created_before"),
                updated_after=validated_params.get("updated_after"),
                updated_before=validated_params.get("updated_before"),
                assigned_to=validated_params.get("assigned_to"),
            )

            # Search issues in each tracker
            results = {}
            all_issues = []

            for tracker in trackers_to_search:
                # If the tracker is not configured, skip it
                if tracker not in project.tracker_configurations:
                    results[tracker] = {
                        "error": "not_configured",
                        "message": f"Tracker '{tracker}' is not configured for this project",
                    }
                    continue

                try:
                    # Get the tracker configuration
                    tracker_config = project.tracker_configurations[tracker]

                    # Create a tracker client
                    tracker_client = run_async(
                        TrackerFactory.create_client(tracker, tracker_config)
                    )

                    if not tracker_client:
                        results[tracker] = {
                            "error": "client_creation_failed",
                            "message": f"Failed to create client for tracker '{tracker}'",
                        }
                        continue

                    # Search for issues
                    issues, total_count = run_async(
                        tracker_client.search_issues(
                            project_key=project.identifier,
                            filter_params=filter_params,
                            limit=limit,
                            offset=0,
                        )
                    )

                    # Convert issues to dictionaries
                    issue_dicts = []
                    for issue in issues:
                        issue_dict = issue.dict()
                        # Add a source field to indicate which tracker this came from
                        issue_dict["source"] = tracker
                        issue_dicts.append(issue_dict)
                        all_issues.append(issue_dict)

                    # Store the results
                    results[tracker] = {
                        "issues": issue_dicts,
                        "total_count": total_count,
                    }

                except Exception as e:
                    logger.exception(f"Error searching {tracker}: {e}")
                    results[tracker] = {
                        "error": "search_failed",
                        "message": f"Error searching issues: {str(e)}",
                    }

            # Sort all issues by relevance or date
            # For now, we just sort by updated_at
            all_issues.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

            # Limit the number of results
            all_issues = all_issues[:limit]

            return {
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "identifier": project.identifier,
                },
                "query": query,
                "results_by_tracker": results,
                "combined_results": all_issues,
                "total_results": len(all_issues),
            }

        finally:
            db.close()
