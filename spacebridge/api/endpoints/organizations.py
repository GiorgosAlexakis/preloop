"""Endpoints for managing organizations."""

import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from spacebridge.db.session import get_db
from spacebridge.models.organization import Organization

router = APIRouter()


class OrganizationBase(BaseModel):
    """Base model for organization data."""

    name: str = Field(..., description="Organization name")
    identifier: str = Field(..., description="Unique identifier for the organization")
    description: Optional[str] = Field(None, description="Organization description")
    settings: Optional[Dict] = Field(None, description="Organization-wide settings")


class OrganizationCreate(OrganizationBase):
    """Model for creating a new organization."""

    pass


class OrganizationUpdate(BaseModel):
    """Model for updating an organization."""

    name: Optional[str] = Field(None, description="New organization name")
    description: Optional[str] = Field(None, description="New organization description")
    settings: Optional[Dict] = Field(None, description="Updated organization settings")


class OrganizationResponse(OrganizationBase):
    """Response model for organization data."""

    id: str = Field(..., description="Organization ID")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

    class Config:
        orm_mode = True


@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
def create_organization(
    organization: OrganizationCreate, db: Session = Depends(get_db)
) -> Organization:
    """Create a new organization."""
    # Check if organization with this identifier already exists
    existing_org = (
        db.query(Organization)
        .filter(Organization.identifier == organization.identifier)
        .first()
    )
    if existing_org:
        raise HTTPException(
            status_code=400,
            detail=f"Organization with identifier '{organization.identifier}' already exists",
        )

    # Create new organization
    db_organization = Organization(
        id=str(uuid.uuid4()),
        name=organization.name,
        identifier=organization.identifier,
        description=organization.description,
        settings=organization.settings or {},
    )

    db.add(db_organization)
    db.commit()
    db.refresh(db_organization)

    return db_organization


@router.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Organization]:
    """List all organizations."""
    organizations = db.query(Organization).offset(offset).limit(limit).all()
    return organizations


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    organization_id: str, db: Session = Depends(get_db)
) -> Organization:
    """Get an organization by ID."""
    organization = (
        db.query(Organization).filter(Organization.id == organization_id).first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


@router.get(
    "/organizations/by-identifier/{identifier}", response_model=OrganizationResponse
)
def get_organization_by_identifier(
    identifier: str, db: Session = Depends(get_db)
) -> Organization:
    """Get an organization by identifier."""
    organization = (
        db.query(Organization).filter(Organization.identifier == identifier).first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


@router.put("/organizations/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    organization_id: str,
    organization_update: OrganizationUpdate,
    db: Session = Depends(get_db),
) -> Organization:
    """Update an organization."""
    organization = (
        db.query(Organization).filter(Organization.id == organization_id).first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Update organization fields
    update_data = organization_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(organization, field, value)

    db.commit()
    db.refresh(organization)

    return organization


@router.delete("/organizations/{organization_id}", status_code=204)
def delete_organization(organization_id: str, db: Session = Depends(get_db)) -> None:
    """Delete an organization."""
    organization = (
        db.query(Organization).filter(Organization.id == organization_id).first()
    )
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    db.delete(organization)
    db.commit()
