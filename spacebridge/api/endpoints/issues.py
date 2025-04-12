"""Endpoints for managing issues across trackers."""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from spacebridge.schemas.issue import IssueCreate, IssueResponse, IssueUpdate
from spacemodels.crud import (
    CRUDIssue,
    CRUDOrganization,
    CRUDProject,
    crud_embedding_model,
    crud_issue_embedding,
)
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.issue import Issue
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project

# Initialize CRUD operations
crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)
crud_issue = CRUDIssue(Issue)


# Define the filter class for issue searching
class IssueFilter:
    def __init__(self, query: str, limit: int = 10):
        self.query = query
        self.limit = limit
        self.status = None
        self.labels = None
        self.assignee = None


logger = logging.getLogger(__name__)
router = APIRouter()

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


@router.get("/issues/search", response_model=List[IssueResponse])
async def search_issues(
    organization_id: Optional[str] = Query(None, description="Organization ID (UUID)"),
    organization: Optional[str] = Query(None, description="Organization name"),
    project_id: Optional[str] = Query(None, description="Project ID (UUID)"),
    project: Optional[str] = Query(None, description="Project name"),
    query: Optional[str] = Query("", description="Search query text"),
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of issues to return"
    ),
    semantic: bool = Query(
        True, description="Whether to use semantic search with vector embeddings"
    ),
    status: Optional[str] = Query(None, description="Filter by issue status"),
    labels: Optional[str] = Query(
        None, description="Filter by comma-separated list of labels"
    ),
    assignee: Optional[str] = Query(None, description="Filter by assignee"),
    db: Session = Depends(get_db),
):
    """
    Search for issues within a project using text query and optional semantic search.

    Args:
        organization_id: Organization ID (UUID)
        organization: Organization name
        project_id: Project ID (UUID)
        project: Project name
        query: Search query text
        limit: Maximum number of issues to return
        semantic: Whether to use semantic search with vector embeddings
        status: Filter by issue status
        labels: Filter by comma-separated list of labels
        assignee: Filter by assignee
        db: Database session

    Returns:
        List of matching issues
    """
    try:
        # Resolve organization and project using either ID, name, or identifier
        from spacemodels.crud import crud_organization, crud_project

        # Process organization parameters
        org = None
        org_id = None
        if organization_id:
            org = crud_organization.get(db, id=organization_id)
            if org:
                org_id = org.id
        elif organization:
            org = crud_organization.get_by_name(db, name=organization)
            if org:
                org_id = org.id

        # Process project parameters
        proj = None
        if project_id:
            proj = crud_project.get(db, id=project_id)
        elif project:
            # If we have an organization, use it to narrow down the project search
            if org_id:
                proj = crud_project.get_by_name(
                    db, name=project, organization_id=org_id
                )
            else:
                proj = crud_project.get_by_name(db, name=project)

        # Validate project (if project is specified but not found)
        if (project_id or project) and not proj:
            raise HTTPException(status_code=404, detail="Project not found")

        # Create filter object for traditional search
        filter_obj = IssueFilter(query=query, limit=limit)
        if status:
            filter_obj.status = status
        if labels:
            filter_obj.labels = labels.split(",")
        if assignee:
            filter_obj.assignee = assignee

        if semantic and query:
            # Get the active embedding model
            active_models = crud_embedding_model.get_active(db)
            model_id = active_models[0].id

            # Generate query vector
            query_vector = crud_issue_embedding._generate_embedding_vector(
                query, active_models[0]
            )

            # 2. Find similar issues using similarity search
            similar_issues = crud_issue_embedding.similarity_search(
                db, model_id=model_id, query_vector=query_vector, limit=limit
            )

            # 3. Extract issues and return them
            if proj:
                results = [
                    issue for issue, _ in similar_issues if issue.project_id == proj.id
                ]
            else:
                results = [issue for issue, _ in similar_issues]

            # Apply additional filters if specified
            if status:
                results = [issue for issue in results if issue.status == status]
            if labels and isinstance(filter_obj.labels, list):
                results = [
                    issue
                    for issue in results
                    if issue.meta_data
                    and "labels" in issue.meta_data
                    and all(
                        label in issue.meta_data["labels"]
                        for label in filter_obj.labels
                    )
                ]
            if assignee:
                results = [
                    issue
                    for issue in results
                    if issue.meta_data
                    and "assignee" in issue.meta_data
                    and issue.meta_data["assignee"] == assignee
                ]

            # Limit results to requested count
            results = results[:limit]

            # Convert database Issue models to IssueResponse objects
            # Need to handle datetime conversion and add required fields
            response_items = []
            for issue in results:
                # Format datetime fields as ISO strings
                created_at_str = (
                    issue.created_at.isoformat() if issue.created_at else None
                )
                updated_at_str = (
                    issue.updated_at.isoformat() if issue.updated_at else None
                )

                # Convert metadata to dictionary if it's not already
                metadata_dict = dict(issue.meta_data) if issue.meta_data else {}

                # Find the organization ID by looking up the project
                issue_project = crud_project.get(db, id=issue.project_id)
                organization_id = (
                    issue_project.organization_id if issue_project else "None"
                )

                # Create response object with all required fields
                response_item = IssueResponse(
                    id=issue.id,
                    title=issue.title,
                    description=issue.description,
                    status=issue.status,
                    priority=issue.priority,
                    tracker_id=issue.external_id,
                    organization=organization_id,  # Use the actual organization ID from the project
                    project=issue.project_id,  # Use the project ID from the request
                    url=issue.external_url
                    or f"https://spacebridge.ai/issues/{issue.id}",  # Provide fallback URL
                    created_at=created_at_str,
                    updated_at=updated_at_str,
                    metadata=metadata_dict,
                    # Include other fields from the issue as needed
                    labels=metadata_dict.get("labels", [])
                    if isinstance(metadata_dict.get("labels"), list)
                    else [],
                    assignee=metadata_dict.get("assignee"),
                )
                response_items.append(response_item)

            return response_items
        else:
            # Use regular text search
            issues = crud_issue.search(db, project_id=proj.id, filter_obj=filter_obj)
            return [IssueResponse.from_orm(issue) for issue in issues]
    except HTTPException:
        # Re-raise specific HTTP exceptions (like the 404 for project not found)
        raise
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error searching issues: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during issue search."
        )


@router.post("/issues", response_model=IssueResponse, status_code=201)
async def create_issue(
    issue: IssueCreate,
    db: Session = Depends(get_db),
) -> IssueResponse:
    """Create a new issue in a specified project.

    Supports specifying organization/project by:
    - ID (organization_id/project_id)
    - Name (organization_name/project_name)
    - Identifier (organization/project - deprecated)
    """
    try:
        # Resolve organization and project using either ID, name, or identifier
        from spacemodels.crud import crud_organization, crud_project

        # Process organization parameters (prioritize new parameters over deprecated ones)
        org = None
        org_id = None

        if issue.organization_id:
            org = crud_organization.get(db, id=issue.organization_id)
            if org:
                org_id = org.id
        elif issue.organization_name:
            org = crud_organization.get_by_name(db, name=issue.organization_name)
            if org:
                org_id = org.id
        elif issue.organization:
            # For backward compatibility
            org_id = issue.organization

        if not org_id:
            raise HTTPException(status_code=400, detail="Organization not found")

        # Process project parameters
        proj = None
        proj_id = None

        if issue.project_id:
            proj = crud_project.get(db, id=issue.project_id)
            if proj:
                proj_id = proj.id
        elif issue.project_name:
            # If we have an organization, use it to narrow down the project search
            proj = crud_project.get_by_name(
                db, name=issue.project_name, organization_id=org_id
            )
            if proj:
                proj_id = proj.id
        elif issue.project:
            # For backward compatibility with identifier
            proj = crud_project.get_by_identifier(
                db, organization_id=org_id, identifier=issue.project
            )
            if proj:
                proj_id = proj.id

        if not proj_id:
            raise HTTPException(status_code=400, detail="Project not found")

        # Get the tracker client using the resolved IDs
        tracker_client = await get_tracker_client(org_id, proj_id, db)

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

        # For the response, use the IDs we found (which might be different from what was passed in)
        return IssueResponse(
            id=created_issue.id,
            tracker_id=created_issue.tracker_id,
            organization=org_id,
            project=proj_id,
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


@router.get("/issues/{issue_id}")
def get_issue(
    issue_id: str,
    db: Session = Depends(get_db),
):
    """Get details of a specific issue."""
    try:
        # Get the issue directly from the database
        issue = crud_issue.get(db, id=issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        # Get the project and organization
        project = crud_project.get(db, id=issue.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        organization = crud_organization.get(db, id=project.organization_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Extract data from JSON fields if available
        meta_data = issue.meta_data or {}
        labels_list = meta_data.get("labels", []) if isinstance(meta_data, dict) else []
        assignees_list = (
            meta_data.get("assignees", []) if isinstance(meta_data, dict) else []
        )

        # Convert to dictionary
        issue_dict = {
            "id": issue.id,
            "tracker_id": issue.external_id or "",
            "organization": organization.name,
            "project": project.name,
            "title": issue.title,
            "description": issue.description or "",
            "status": issue.status,
            "priority": issue.priority or "",
            "assignee": assignees_list[0] if assignees_list else "",
            "labels": labels_list,
            "url": issue.external_url or meta_data.get("url", ""),
            "created_at": issue.created_at.isoformat() if issue.created_at else "",
            "updated_at": issue.updated_at.isoformat() if issue.updated_at else "",
            "metadata": meta_data,
        }

        return issue_dict
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
