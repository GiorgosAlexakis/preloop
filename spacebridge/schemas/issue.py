"""Issue schemas for request and response validation."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, root_validator


class IssueBase(BaseModel):
    """Base model for issue data."""

    title: str = Field(..., description="Issue title")
    description: Optional[str] = Field(None, description="Issue description")
    priority: Optional[str] = Field(
        None, description="Issue priority (Low, Medium, High)"
    )
    status: Optional[str] = Field(None, description="Issue status")
    assignee: Optional[str] = Field(None, description="Issue assignee")
    labels: Optional[List[str]] = Field(None, description="Issue labels")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional issue metadata"
    )


class IssueCreate(IssueBase):
    """Model for creating a new issue."""

    # Support multiple ways to specify organization
    organization_id: Optional[str] = Field(None, description="Organization ID (UUID)")
    organization_name: Optional[str] = Field(None, description="Organization name")
    organization: Optional[str] = Field(
        None, description="Organization identifier (deprecated)"
    )

    # Support multiple ways to specify project
    project_id: Optional[str] = Field(None, description="Project ID (UUID)")
    project_name: Optional[str] = Field(None, description="Project name")
    project: Optional[str] = Field(None, description="Project identifier (deprecated)")

    # Add validation to ensure at least one org and project parameter is provided
    @root_validator(pre=True)
    def check_org_project_provided(cls, values):
        """Validate that at least one organization and project parameter is provided."""
        # Check organization params
        has_org = (
            values.get("organization_id") is not None
            or values.get("organization_name") is not None
            or values.get("organization") is not None
        )

        # Check project params
        has_project = (
            values.get("project_id") is not None
            or values.get("project_name") is not None
            or values.get("project") is not None
        )

        if not has_org:
            raise ValueError("At least one organization parameter must be provided")

        if not has_project:
            raise ValueError("At least one project parameter must be provided")

        return values


class IssueUpdate(BaseModel):
    """Model for updating an issue."""

    title: Optional[str] = Field(None, description="New issue title")
    description: Optional[str] = Field(None, description="New issue description")
    status: Optional[str] = Field(None, description="New issue status")
    priority: Optional[str] = Field(None, description="New issue priority")
    assignee: Optional[str] = Field(None, description="New issue assignee")
    labels: Optional[List[str]] = Field(None, description="New issue labels")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional issue metadata"
    )


class IssueResponse(IssueBase):
    """Response model for issue data."""

    id: str = Field(..., description="Issue ID in the original tracker (external ID)")
    organization: str = Field(..., description="Organization name")
    project: str = Field(..., description="Project name")
    url: str = Field(..., description="URL to the issue in the original tracker")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    score: Optional[float] = Field(
        None, description="Similarity score for search results (if applicable)"
    )

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class IssueSearchResults(BaseModel):
    """Response model for issue search results."""

    items: List[IssueResponse] = Field(..., description="Search result items")
    total: int = Field(..., description="Total number of matching issues")
    query: str = Field(..., description="Search query used")
