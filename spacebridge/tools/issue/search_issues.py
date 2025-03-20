"""Search issues across issue trackers."""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from mcp.server.fastmcp import Context
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.crud.organization import CRUDOrganization
from spacemodels.crud.project import CRUDProject

from spacemodels.db.session import get_db_session as get_db
from spacebridge.trackers.base import IssueFilter
from spacebridge.trackers.factory import TrackerFactory

logger = logging.getLogger(__name__)


class ProjectInfo(BaseModel):
    """Project information in search response."""

    id: int
    name: str
    identifier: str


class IssueInfo(BaseModel):
    """Issue information."""

    id: str
    key: Optional[str] = None
    title: str
    description: str
    url: Optional[str] = None
    source: str
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    labels: Optional[List[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None


class TrackerError(BaseModel):
    """Error information for a tracker."""

    error: str
    message: str


class TrackerResult(BaseModel):
    """Search results from a tracker."""

    issues: List[IssueInfo]
    total_count: int


class SearchResponse(BaseModel):
    """Response model for search_issues tool."""

    project: ProjectInfo
    query: str
    results_by_tracker: Dict[str, Any]  # Can be TrackerResult or TrackerError
    combined_results: List[Dict[str, Any]]
    total_results: int


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    message: str


async def search_issues(
    organization: str,
    project: str,
    query: str,
    limit: int = 10,
    trackers: Optional[List[str]] = None,
    status: Optional[List[str]] = None,
    labels: Optional[List[str]] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    updated_after: Optional[str] = None,
    updated_before: Optional[str] = None,
    assigned_to: Optional[str] = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """Search for issues across trackers.

    Args:
        organization: Organization identifier
        project: Project identifier
        query: Search query
        limit: Maximum number of results (default: 10)
        trackers: Optional specific trackers to search
        status: Optional filter by issue status
        labels: Optional filter by issue labels
        created_after: Optional filter by creation date (ISO format)
        created_before: Optional filter by creation date (ISO format)
        updated_after: Optional filter by update date (ISO format)
        updated_before: Optional filter by update date (ISO format)
        assigned_to: Optional filter by assignee
        ctx: Optional MCP context

    Returns:
        Search results from each tracker
    """
    # Get database session
    db = next(get_db())

    try:
        # Log operation if context is available
        if ctx:
            await ctx.info(
                f"Searching for '{query}' in project {project}, organization {organization}"
            )

        # Initialize CRUD objects
        crud_organization = CRUDOrganization(Organization)
        crud_project = CRUDProject(Project)

        # Get organization using CRUD operations
        org = crud_organization.get_by_identifier(db, identifier=organization)
        if not org or not org.is_active:
            return ErrorResponse(
                error="not_found", message=f"Organization '{organization}' not found"
            ).model_dump()

        # Get project using CRUD operations
        proj = crud_project.get_by_identifier(
            db, organization_id=org.id, identifier=project
        )
        if not proj or not proj.is_active:
            return ErrorResponse(
                error="not_found",
                message=f"Project '{project}' not found in organization '{organization}'",
            ).model_dump()

        # In SpaceModels, we use tracker_settings instead of tracker_configurations
        tracker_settings = proj.tracker_settings or {}

        # If no tracker settings, return an error
        if not tracker_settings:
            return ErrorResponse(
                error="no_trackers",
                message=f"Project '{project}' has no configured trackers",
            ).model_dump()

        # Determine which trackers to search
        trackers_to_search = trackers if trackers else list(tracker_settings.keys())

        if ctx:
            await ctx.info(f"Searching in trackers: {', '.join(trackers_to_search)}")

        # Create an issue filter from the parameters
        filter_params = IssueFilter(
            query=query,
            status=status,
            labels=labels,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
            assigned_to=assigned_to,
        )

        # Search issues in each tracker
        results = {}
        all_issues = []

        for tracker in trackers_to_search:
            # If the tracker is not configured, skip it
            if tracker not in tracker_settings:
                results[tracker] = TrackerError(
                    error="not_configured",
                    message=f"Tracker '{tracker}' is not configured for this project",
                ).model_dump()
                continue

            try:
                if ctx:
                    await ctx.info(f"Searching in {tracker}")

                # Get the tracker configuration
                tracker_config = tracker_settings[tracker]

                # Create a tracker client
                tracker_client = await TrackerFactory.create_client(
                    tracker, tracker_config
                )

                if not tracker_client:
                    results[tracker] = TrackerError(
                        error="client_creation_failed",
                        message=f"Failed to create client for tracker '{tracker}'",
                    ).model_dump()
                    continue

                # Search for issues
                issues, total_count = await tracker_client.search_issues(
                    project_key=proj.identifier,
                    filter_params=filter_params,
                    limit=limit,
                    offset=0,
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
                results[tracker] = TrackerResult(
                    issues=issue_dicts, total_count=total_count
                ).model_dump()

                if ctx:
                    await ctx.info(f"Found {len(issues)} issues in {tracker}")

            except Exception as e:
                logger.exception(f"Error searching {tracker}: {e}")
                results[tracker] = TrackerError(
                    error="search_failed", message=f"Error searching issues: {str(e)}"
                ).model_dump()

        # Sort all issues by relevance or date
        # For now, we just sort by updated_at
        all_issues.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        # Limit the number of results
        all_issues = all_issues[:limit]

        if ctx:
            await ctx.info(f"Search completed with {len(all_issues)} total results")

        # Return using the response model
        return SearchResponse(
            project=ProjectInfo(id=proj.id, name=proj.name, identifier=proj.identifier),
            query=query,
            results_by_tracker=results,
            combined_results=all_issues,
            total_results=len(all_issues),
        ).model_dump()

    finally:
        db.close()
