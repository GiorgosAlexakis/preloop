"""Endpoints for managing projects."""

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

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
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project

logger = logging.getLogger(__name__)
router = APIRouter()
crud_project = CRUDProject(Project)
crud_organization = CRUDOrganization(Organization)


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    """Create a new project."""
    # Check if organization exists
    organization = crud_organization.get(db, id=project.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

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
        "created_at": db_project.created_at.isoformat()
        if db_project.created_at
        else None,
        "updated_at": db_project.updated_at.isoformat()
        if db_project.updated_at
        else None,
    }


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(
    organization_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[dict]:
    """List all projects, optionally filtered by organization."""
    if organization_id:
        # If organization_id is provided, use the CRUD method with filter
        projects = crud_project.get_multi(
            db,
            skip=offset,
            limit=limit,
            organization_id=organization_id,
            is_active=True,
        )
    else:
        # Otherwise, get all active projects
        projects = crud_project.get_active(db, skip=offset, limit=limit)

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
                "created_at": project.created_at.isoformat()
                if project.created_at
                else None,
                "updated_at": project.updated_at.isoformat()
                if project.updated_at
                else None,
            }
        )

    return result


@router.get("/organizations/{organization_id}/projects")
def list_organization_projects(
    organization_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List all projects for an organization."""
    # Check if organization exists
    organization = crud_organization.get(db, id=organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

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
            "created_at": project.created_at.isoformat()
            if project.created_at
            else None,
            "updated_at": project.updated_at.isoformat()
            if project.updated_at
            else None,
            "settings": project.settings or {},
            "tracker_settings": project.tracker_settings or {},
            "meta_data": project.meta_data or {},
        }
        project_dicts.append(project_dict)

    # Format the response to match the expected structure
    return {"items": project_dicts, "total": total, "limit": limit, "offset": offset}


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    """Get a project by ID."""
    project = crud_project.get(db, id=project_id)
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
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.get(
    "/organizations/{organization_id}/projects/{identifier}",
    response_model=ProjectResponse,
)
def get_project_by_identifier(
    organization_id: str, identifier: str, db: Session = Depends(get_db)
) -> dict:
    """Get a project by organization ID and project identifier."""
    project = crud_project.get_by_identifier(
        db, organization_id=organization_id, identifier=identifier
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
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str, project_update: ProjectUpdate, db: Session = Depends(get_db)
) -> dict:
    """Update a project."""
    project = crud_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
        "created_at": updated_project.created_at.isoformat()
        if updated_project.created_at
        else None,
        "updated_at": updated_project.updated_at.isoformat()
        if updated_project.updated_at
        else None,
    }


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a project."""
    project = crud_project.get(db, id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete the project
    crud_project.delete(db, id=project_id)


@router.post("/projects/test-connection", response_model=TestConnectionResponse)
async def test_project_connection(
    request: TestConnectionRequest, db: Session = Depends(get_db)
) -> TestConnectionResponse:
    """Test the connection to an issue tracker for a project."""
    try:
        # First check if organization exists
        organization_id = request.organization
        if len(organization_id) == 36:  # Simple UUID check
            organization = crud_organization.get(db, id=organization_id)
        else:
            organization = crud_organization.get_by_identifier(
                db, identifier=organization_id
            )

        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Check if project exists
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
