"""Endpoints for managing projects."""

import logging
import uuid
from typing import List, Optional  # Added Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, selectinload

from spacebridge.api.auth import get_current_active_user  # Import user dependency

from spacebridge.schemas.issue import IssueResponse
from spacebridge.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
)
from spacebridge.trackers.factory import TrackerFactory
from spacemodels.crud.organization import CRUDOrganization
from spacemodels.crud.project import CRUDProject
from spacemodels.crud.tracker import CRUDTracker  # Import tracker CRUD
from spacemodels.crud.issue import CRUDIssue
from spacemodels.crud.embedding import CRUDEmbeddingModel, CRUDIssueEmbedding
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.account import Account  # Import Account model
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.tracker import Tracker  # Import Tracker model
from spacemodels.models.issue import Issue
from spacemodels.models.issue import IssueEmbedding, EmbeddingModel

logger = logging.getLogger(__name__)
router = APIRouter()
crud_project = CRUDProject(Project)
crud_organization = CRUDOrganization(Organization)
crud_tracker = CRUDTracker(Tracker)  # Instantiate tracker CRUD
crud_issue = CRUDIssue(Issue)
crud_issue_embedding = CRUDIssueEmbedding(IssueEmbedding)
crud_embedding_model = CRUDEmbeddingModel(EmbeddingModel)


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> dict:
    """Create a new project, ensuring user has access to the organization."""
    # Check if organization exists
    organization = crud_organization.get(db, id=project.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Authorization check: Ensure the user owns the organization's tracker
    if not organization.tracker or organization.tracker.account_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Access denied to this organization"
        )

    # Check if project with this identifier already exists in the organization
    existing_project = crud_project.get_by_identifier(
        db, organization_id=project.organization_id, identifier=project.identifier
    )
    if existing_project:
        raise HTTPException(
            status_code=400,
            detail=f"Project with identifier '{project.identifier}' already exists in this organization",
        )

    # Create new project using CRUD operation
    # Note: Adapter code to handle the tracker_configurations from the old model
    # In SpaceModels, we have tracker_settings instead
    project_data = {
        "id": str(uuid.uuid4()),
        "name": project.name,
        "identifier": project.identifier,
        "description": project.description,
        "organization_id": project.organization_id,
        "settings": project.settings or {},
        "tracker_settings": project.tracker_configurations or {},
        "meta_data": {},
    }

    db_project = crud_project.create(db, obj_in=project_data)

    # Convert datetime objects to ISO format strings
    return {
        "id": db_project.id,
        "name": db_project.name,
        "identifier": db_project.identifier,
        "description": db_project.description,
        "organization_id": db_project.organization_id,
        "settings": db_project.settings,
        "tracker_configurations": db_project.tracker_settings,
        "created_at": db_project.created_at,
        "updated_at": db_project.updated_at,
    }


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(
    organization_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> List[dict]:
    """List projects accessible to the current user, optionally filtered by organization."""
    projects = []
    if organization_id:
        # If organization_id is provided, check access first
        organization = crud_organization.get(db, id=organization_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        if (
            not organization.tracker
            or organization.tracker.account_id != current_user.id
        ):
            raise HTTPException(
                status_code=403, detail="Access denied to this organization"
            )
        # Fetch projects for this specific organization
        projects = crud_project.get_for_organization(
            db, organization_id=organization_id, skip=offset, limit=limit
        )
    else:
        # List projects from all organizations the user has access to
        user_trackers = crud_tracker.get_for_account(db, account_id=current_user.id)
        tracker_ids = [t.id for t in user_trackers]
        if tracker_ids:
            user_orgs = (
                db.query(Organization)
                .filter(Organization.tracker_id.in_(tracker_ids))
                .all()
            )
            org_ids = [o.id for o in user_orgs]
            if org_ids:
                projects = (
                    db.query(Project)
                    .filter(Project.organization_id.in_(org_ids))
                    .filter(Project.is_active)
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
    # Convert datetime objects to ISO format strings
    result = []
    for project in projects:
        result.append(
            {
                "id": project.id,
                "name": project.name,
                "identifier": project.identifier,
                "description": project.description,
                "organization_id": project.organization_id,
                "settings": project.settings,
                "tracker_configurations": project.tracker_settings,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
            }
        )

    return result


@router.get("/organizations/{organization_id}/projects")
def list_organization_projects(
    organization_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
):
    """List all projects for an organization, ensuring user has access."""
    # Check if organization exists
    organization = crud_organization.get(db, id=organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Authorization check
    if not organization.tracker or organization.tracker.account_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Access denied to this organization"
        )

    # Use the CRUD method to get projects for the organization
    projects = crud_project.get_for_organization(
        db, organization_id=organization_id, skip=offset, limit=limit
    )

    # Count total projects for this organization
    total = crud_project.count_for_organization(db, organization_id=organization_id)

    # Convert SQLAlchemy model objects to dictionaries
    project_dicts = []
    for project in projects:
        project_dict = {
            "id": project.id,
            "name": project.name,
            "identifier": project.identifier,
            "description": project.description,
            "is_active": project.is_active,
            "organization_id": project.organization_id,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
            "settings": project.settings or {},
            "tracker_settings": project.tracker_settings or {},
            "meta_data": project.meta_data or {},
        }
        project_dicts.append(project_dict)

    # Format the response to match the expected structure
    return {"items": project_dicts, "total": total, "limit": limit, "offset": offset}


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> dict:
    """Get a project by ID, ensuring user has access."""
    project = crud_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Authorization check
    organization = crud_organization.get(db, id=project.organization_id)
    if (
        not organization
        or not organization.tracker
        or organization.tracker.account_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    # Convert datetime objects to ISO format strings
    return {
        "id": project.id,
        "name": project.name,
        "identifier": project.identifier,
        "description": project.description,
        "organization_id": project.organization_id,
        "settings": project.settings,
        "tracker_configurations": project.tracker_settings,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@router.get(
    "/organizations/{organization_id}/projects/{identifier}",
    response_model=ProjectResponse,
)
def get_project_by_identifier(
    organization_id: str,
    identifier: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> dict:
    """Get a project by organization ID and project identifier, ensuring user has access."""
    # Check organization access first
    organization = crud_organization.get(db, id=organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if not organization.tracker or organization.tracker.account_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Access denied to this organization"
        )

    # Now get the project within the authorized organization using slug or identifier
    project = crud_project.get_by_slug_or_identifier(
        db, organization_id=organization_id, slug_or_identifier=identifier
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Convert datetime objects to ISO format strings
    return {
        "id": project.id,
        "name": project.name,
        "identifier": project.identifier,
        "description": project.description,
        "organization_id": project.organization_id,
        "settings": project.settings,
        "tracker_configurations": project.tracker_settings,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> dict:
    """Update a project, ensuring user has access."""
    project = crud_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Authorization check
    organization = crud_organization.get(db, id=project.organization_id)
    if (
        not organization
        or not organization.tracker
        or organization.tracker.account_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    # Update project using CRUD operation
    # Note: Handle potential field name differences (e.g., tracker_configurations)
    update_data = project_update.dict(exclude_unset=True)

    # If tracker_configurations is present, map it to tracker_settings
    if "tracker_configurations" in update_data:
        update_data["tracker_settings"] = update_data.pop("tracker_configurations")

    updated_project = crud_project.update(db, db_obj=project, obj_in=update_data)

    # Convert datetime objects to ISO format strings
    return {
        "id": updated_project.id,
        "name": updated_project.name,
        "identifier": updated_project.identifier,
        "description": updated_project.description,
        "organization_id": updated_project.organization_id,
        "settings": updated_project.settings,
        "tracker_configurations": updated_project.tracker_settings,
        "created_at": updated_project.created_at.isoformat(),
        "updated_at": updated_project.updated_at.isoformat(),
    }


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> None:
    """Delete a project, ensuring user has access."""
    project = crud_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Authorization check
    organization = crud_organization.get(db, id=project.organization_id)
    if (
        not organization
        or not organization.tracker
        or organization.tracker.account_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete the project
    crud_project.delete(db, id=project_id)


@router.post("/projects/test-connection", response_model=TestConnectionResponse)
async def test_project_connection(
    request: TestConnectionRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_active_user),
) -> TestConnectionResponse:
    """Test the connection to an issue tracker for a project, ensuring user has access."""
    try:
        # Resolve organization
        organization_id = request.organization
        if len(organization_id) == 36:  # Simple UUID check
            organization = crud_organization.get(db, id=organization_id)
        else:
            organization = crud_organization.get_by_identifier(
                db, identifier=organization_id
            )

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Authorization check for organization
        if (
            not organization.tracker
            or organization.tracker.account_id != current_user.id
        ):
            raise HTTPException(
                status_code=403, detail="Access denied to this organization"
            )

        # Resolve project
        project_id = request.project
        if len(project_id) == 36:  # Simple UUID check
            project = crud_project.get(db, id=project_id)
        else:
            project = crud_project.get_by_identifier(
                db, organization_id=organization.id, identifier=project_id
            )

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Determine the tracker type and config
        tracker_type = "github"  # This should come from the organization or project
        tracker_config = project.tracker_settings or {}

        # Create the tracker client
        try:
            tracker_client = await TrackerFactory.create_client(
                tracker_type, tracker_config
            )
        except Exception as e:
            logger.error(f"Error creating tracker client: {e}")
            return TestConnectionResponse(
                success=False,
                message="Error creating tracker client",
                details={"error": str(e)},
            )

        # Test the connection
        try:
            connection_result = await tracker_client.test_connection()

            # Return the connection result
            return TestConnectionResponse(
                success=connection_result.success,
                message=connection_result.message,
                details=connection_result.details,
            )
        except Exception as e:
            logger.error(f"Error testing connection: {e}")
            return TestConnectionResponse(
                success=False,
                message="Error testing connection",
                details={"error": str(e)},
            )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error in test_project_connection: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error testing connection: {str(e)}"
        )
