"""Endpoints for managing issues across trackers."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from spacemodels.db.session import get_db_session as get_db
from spacebridge.schemas.issue import (
    IssueCreate,
    IssueResponse,
    IssueUpdate,
    IssueSearchResults,
)
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize CRUD instances
from spacemodels.crud.organization import CRUDOrganization
from spacemodels.crud.project import CRUDProject

crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)


# Helper Functions


async def get_tracker_client(organization_id: str, project_id: str, db: Session):
    """Get the appropriate tracker client for the given organization and project.

    Args:
        organization_id: The organization ID or identifier.
        project_id: The project ID or identifier.
        db: Database session.

    Returns:
        A tracker client instance.

    Raises:
        HTTPException: If the organization or project is not found, or if a tracker
            client cannot be created.
    """
    # Check if organization_id is a UUID or an identifier
    if len(organization_id) == 36:  # Simple UUID check
        organization = crud_organization.get(db, id=organization_id)
    else:
        organization = crud_organization.get_by_identifier(
            db, identifier=organization_id
        )

    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if project_id is a UUID or an identifier
    if len(project_id) == 36:  # Simple UUID check
        project = crud_project.get(db, id=project_id)
    else:
        project = crud_project.get_by_identifier(
            db, organization_id=organization.id, identifier=project_id
        )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Determine the tracker type from the organization's tracker_id
    # For now, we'll hardcode GitHub for testing purposes
    # In a real implementation, you'd retrieve this from the organization or project settings
    tracker_type = "github"  # This should come from the organization or project
    tracker_config = project.tracker_settings or {}

    try:
        # Create the tracker client
        tracker_client = await TrackerFactory.create_client(
            tracker_type, tracker_config
        )
        return tracker_client
    except Exception as e:
        logger.error(f"Error creating tracker client: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error creating tracker client: {str(e)}"
        )


# API Endpoints


@router.get("/issues/search", response_model=IssueSearchResults)
async def search_issues(
    organization: str = Query(..., description="Organization identifier"),
    project: str = Query(..., description="Project identifier"),
    query: str = Query(..., description="Search query text"),
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of issues to return"
    ),
    semantic: bool = Query(
        True, description="Whether to use semantic search with vector embeddings"
    ),
    status: Optional[str] = Query(None, description="Filter by issue status"),
    labels: Optional[str] = Query(
        None, description="Filter by issue labels (comma-separated)"
    ),
    assignee: Optional[str] = Query(None, description="Filter by issue assignee"),
    db: Session = Depends(get_db),
) -> IssueSearchResults:
    """Search for issues across configured trackers with optional semantic search."""
    try:
        # Get the tracker client
        tracker_client = await get_tracker_client(organization, project, db)

        # Prepare the filter
        issue_filter = IssueFilter(
            query=query,
            limit=limit,
        )

        # Add optional filters
        if status:
            issue_filter.status = status
        if labels:
            issue_filter.labels = labels.split(",")
        if assignee:
            issue_filter.assignee = assignee

        # Search for issues
        issues = await tracker_client.search_issues(issue_filter)

        # Convert tracker issues to API response model
        issue_responses = []
        for issue in issues:
            issue_responses.append(
                IssueResponse(
                    id=issue.id,
                    tracker_id=issue.tracker_id,
                    organization=organization,
                    project=project,
                    title=issue.title,
                    description=issue.description,
                    status=issue.status,
                    priority=issue.priority,
                    assignee=issue.assignee,
                    labels=issue.labels,
                    url=issue.url,
                    created_at=issue.created_at,
                    updated_at=issue.updated_at,
                    metadata=issue.metadata,
                )
            )

        # Return the search results
        return IssueSearchResults(
            items=issue_responses,
            total=len(
                issue_responses
            ),  # In a real implementation, this would come from the tracker
            query=query,
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error searching issues: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching issues: {str(e)}")


@router.post("/issues", response_model=IssueResponse, status_code=201)
async def create_issue(
    issue: IssueCreate,
    db: Session = Depends(get_db),
) -> IssueResponse:
    """Create a new issue in a specified project."""
    try:
        # Get the tracker client
        tracker_client = await get_tracker_client(issue.organization, issue.project, db)

        # Prepare the issue create model
        tracker_issue = TrackerIssueCreate(
            title=issue.title,
            description=issue.description,
            priority=issue.priority,
            assignee=issue.assignee,
            labels=issue.labels,
            metadata=issue.metadata,
        )

        # Create the issue
        created_issue = await tracker_client.create_issue(tracker_issue)

        # Convert tracker issue to API response model
        return IssueResponse(
            id=created_issue.id,
            tracker_id=created_issue.tracker_id,
            organization=issue.organization,
            project=issue.project,
            title=created_issue.title,
            description=created_issue.description,
            status=created_issue.status,
            priority=created_issue.priority,
            assignee=created_issue.assignee,
            labels=created_issue.labels,
            url=created_issue.url,
            created_at=created_issue.created_at,
            updated_at=created_issue.updated_at,
            metadata=created_issue.metadata,
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error creating issue: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating issue: {str(e)}")


@router.get("/issues/{issue_id}", response_model=IssueResponse)
async def get_issue(
    issue_id: str,
    organization: str = Query(..., description="Organization identifier"),
    project: str = Query(..., description="Project identifier"),
    db: Session = Depends(get_db),
) -> IssueResponse:
    """Get details of a specific issue."""
    try:
        # Get the tracker client
        tracker_client = await get_tracker_client(organization, project, db)

        # Get the issue
        issue = await tracker_client.get_issue(issue_id)

        # Convert tracker issue to API response model
        return IssueResponse(
            id=issue.id,
            tracker_id=issue.tracker_id,
            organization=organization,
            project=project,
            title=issue.title,
            description=issue.description,
            status=issue.status,
            priority=issue.priority,
            assignee=issue.assignee,
            labels=issue.labels,
            url=issue.url,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            metadata=issue.metadata,
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting issue: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting issue: {str(e)}")


@router.put("/issues/{issue_id}", response_model=IssueResponse)
async def update_issue(
    issue_id: str,
    issue_update: IssueUpdate,
    organization: str = Query(..., description="Organization identifier"),
    project: str = Query(..., description="Project identifier"),
    db: Session = Depends(get_db),
) -> IssueResponse:
    """Update an existing issue."""
    try:
        # Get the tracker client
        tracker_client = await get_tracker_client(organization, project, db)

        # Prepare the issue update model
        # Only include fields that are not None
        update_data = {k: v for k, v in issue_update.dict().items() if v is not None}
        tracker_issue_update = TrackerIssueUpdate(**update_data)

        # Update the issue
        updated_issue = await tracker_client.update_issue(
            issue_id, tracker_issue_update
        )

        # Convert tracker issue to API response model
        return IssueResponse(
            id=updated_issue.id,
            tracker_id=updated_issue.tracker_id,
            organization=organization,
            project=project,
            title=updated_issue.title,
            description=updated_issue.description,
            status=updated_issue.status,
            priority=updated_issue.priority,
            assignee=updated_issue.assignee,
            labels=updated_issue.labels,
            url=updated_issue.url,
            created_at=updated_issue.created_at,
            updated_at=updated_issue.updated_at,
            metadata=updated_issue.metadata,
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error updating issue: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating issue: {str(e)}")


@router.delete("/issues/{issue_id}", status_code=204)
async def delete_issue(
    issue_id: str,
    organization: str = Query(..., description="Organization identifier"),
    project: str = Query(..., description="Project identifier"),
    db: Session = Depends(get_db),
) -> None:
    """Delete an issue (if supported by the issue tracker)."""
    try:
        # Get the tracker client
        tracker_client = await get_tracker_client(organization, project, db)

        # Check if the issue exists
        issue = await tracker_client.get_issue(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        # Delete the issue
        # Note: Not all trackers support deletion, so this might raise an exception
        await tracker_client.delete_issue(issue_id)
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error deleting issue: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting issue: {str(e)}")
