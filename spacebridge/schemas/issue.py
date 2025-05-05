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

    # Organization fields (optional if project is provided)
    organization_id: Optional[str] = Field(None, description="Organization ID (UUID)")
    organization_name: Optional[str] = Field(None, description="Organization name")
    organization: Optional[str] = Field(
        None, description="Organization identifier (name or ID)"
    )  # Keep for flexibility

    # Project fields (at least one is required)
    project_id: Optional[str] = Field(None, description="Project ID (UUID)")
    project_name: Optional[str] = Field(None, description="Project name")
    project: Optional[str] = Field(
        None, description="Project identifier (name or ID)"
    )  # Keep for flexibility

    @root_validator(pre=True)
    def check_project_or_org_provided(cls, values):
        """Validate that project information is provided, organization is optional."""
        has_project = (
            values.get("project_id")
            or values.get("project_name")
            or values.get("project")
        )

        if not has_project:
            raise ValueError(
                "At least one project parameter (project_id, project_name, or project) must be provided"
            )

        # Organization is optional if project is provided.
        # The endpoint logic will handle resolving the missing piece or raising errors if ambiguous.

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

    id: str = Field(..., description="Internal SpaceBridge database ID (UUID)")
    external_id: str = Field(..., description="Issue ID in the original tracker")
    key: str = Field(..., description="Human-readable issue key (e.g., PROJ-123)")
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
