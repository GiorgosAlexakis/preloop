"""Endpoints for managing projects."""

import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from spacebridge.db.session import get_db
from spacebridge.models.organization import Organization
from spacebridge.models.project import Project

router = APIRouter()


class ProjectBase(BaseModel):
    """Base model for project data."""

    name: str = Field(..., description="Project name")
    identifier: str = Field(..., description="Project identifier")
    description: Optional[str] = Field(None, description="Project description")
    settings: Optional[Dict] = Field(None, description="Project-specific settings")
    tracker_configurations: Optional[Dict] = Field(
        None, description="Issue tracker configurations"
    )


class ProjectCreate(ProjectBase):
    """Model for creating a new project."""

    organization_id: str = Field(..., description="Organization ID")


class ProjectUpdate(BaseModel):
    """Model for updating a project."""

    name: Optional[str] = Field(None, description="New project name")
    description: Optional[str] = Field(None, description="New project description")
    settings: Optional[Dict] = Field(None, description="Updated project settings")
    tracker_configurations: Optional[Dict] = Field(
        None, description="Updated issue tracker configurations"
    )


class ProjectResponse(ProjectBase):
    """Response model for project data."""

    id: str = Field(..., description="Project ID")
    organization_id: str = Field(..., description="Organization ID")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

    class Config:
        orm_mode = True


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    """Create a new project."""
    # Check if organization exists
    organization = (
        db.query(Organization).filter(Organization.id == project.organization_id).first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check if project with this identifier already exists in the organization
    existing_project = (
        db.query(Project)
        .filter(
            Project.organization_id == project.organization_id,
            Project.identifier == project.identifier,
        )
        .first()
    )
    if existing_project:
        raise HTTPException(
            status_code=400,
            detail=f"Project with identifier '{project.identifier}' already exists in this organization",
        )

    # Create new project
    db_project = Project(
        id=str(uuid.uuid4()),
        name=project.name,
        identifier=project.identifier,
        description=project.description,
        organization_id=project.organization_id,
        settings=project.settings or {},
        tracker_configurations=project.tracker_configurations or {},
    )

    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return db_project


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(
    organization_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Project]:
    """List all projects, optionally filtered by organization."""
    query = db.query(Project)
    if organization_id:
        query = query.filter(Project.organization_id == organization_id)

    projects = query.offset(offset).limit(limit).all()
    return projects


@router.get("/organizations/{organization_id}/projects", response_model=List[ProjectResponse])
def list_organization_projects(
    organization_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Project]:
    """List all projects for an organization."""
    # Check if organization exists
    organization = (
        db.query(Organization).filter(Organization.id == organization_id).first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    projects = (
        db.query(Project)
        .filter(Project.organization_id == organization_id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return projects


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    """Get a project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get(
    "/organizations/{organization_id}/projects/{identifier}",
    response_model=ProjectResponse,
)
def get_project_by_identifier(
    organization_id: str, identifier: str, db: Session = Depends(get_db)
) -> Project:
    """Get a project by organization ID and project identifier."""
    project = (
        db.query(Project)
        .filter(
            Project.organization_id == organization_id, Project.identifier == identifier
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str, project_update: ProjectUpdate, db: Session = Depends(get_db)
) -> Project:
    """Update a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update project fields
    update_data = project_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    return project


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
