"""Organization schemas for request and response validation."""

from typing import Dict, Optional

from pydantic import BaseModel, Field


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
        """Pydantic model configuration."""

        from_attributes = True  # Modern way of saying orm_mode = True
