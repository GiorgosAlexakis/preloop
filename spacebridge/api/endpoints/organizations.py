"""Endpoints for managing organizations."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from spacebridge.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from spacemodels.crud.organization import CRUDOrganization
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models.organization import Organization
from spacemodels.models.tracker import Tracker

router = APIRouter()
crud_organization = CRUDOrganization(Organization)


@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
def create_organization(
    organization: OrganizationCreate, db: Session = Depends(get_db)
) -> Organization:
    """Create a new organization."""
    # Check if organization with this identifier already exists
    existing_org = crud_organization.get_by_identifier(
        db, identifier=organization.identifier
    )
    if existing_org:
        raise HTTPException(
            status_code=400,
            detail=f"Organization with identifier '{organization.identifier}' already exists",
        )

    # Note: In a real implementation, you would need to get the tracker_id from somewhere.
    # For now, let's use a placeholder that would need to be properly integrated
    # with your authentication and tracker selection flow.

    # TODO: Get the tracker_id from the authenticated user's default tracker
    # or from the request parameters.
    # For testing purposes, we'll get the first tracker:
    trackers = db.query(Tracker).limit(1).all()
    if not trackers:
        raise HTTPException(
            status_code=400,
            detail="No trackers found. Please create a tracker first.",
        )

    # Create new organization with CRUD operation
    org_data = {
        "id": str(uuid.uuid4()),
        "name": organization.name,
        "identifier": organization.identifier,
        "description": organization.description,
        "settings": organization.settings or {},
        "tracker_id": trackers[0].id,
        "meta_data": {},
    }

    db_organization = crud_organization.create(db, obj_in=org_data)
    return db_organization


@router.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Organization]:
    """List all organizations."""
    # Use CRUD operation without filtering for active organizations
    # Removed is_active=True filter because the column doesn't exist in the database
    organizations = crud_organization.get_multi(db, skip=offset, limit=limit)
    return organizations


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    organization_id: str, db: Session = Depends(get_db)
) -> Organization:
    """Get an organization by ID."""
    organization = crud_organization.get(db, id=organization_id)
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
    organization = crud_organization.get_by_identifier(db, identifier=identifier)
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
    organization = crud_organization.get(db, id=organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Update organization using CRUD operation
    update_data = organization_update.dict(exclude_unset=True)
    updated_organization = crud_organization.update(
        db, db_obj=organization, obj_in=update_data
    )

    return updated_organization


@router.delete("/organizations/{organization_id}", status_code=204)
def delete_organization(organization_id: str, db: Session = Depends(get_db)) -> None:
    """Delete an organization."""
    organization = crud_organization.get(db, id=organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Delete the organization
    crud_organization.delete(db, id=organization_id)
