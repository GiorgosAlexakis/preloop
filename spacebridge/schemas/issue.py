"""Issue schemas for request and response validation."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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

    organization: str = Field(..., description="Organization identifier")
    project: str = Field(..., description="Project identifier")


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

    id: str = Field(..., description="Issue ID")
    tracker_id: str = Field(..., description="Issue ID in the original tracker")
    organization: str = Field(..., description="Organization identifier")
    project: str = Field(..., description="Project identifier")
    url: str = Field(..., description="URL to the issue in the original tracker")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class IssueSearchResults(BaseModel):
    """Response model for issue search results."""

    items: List[IssueResponse] = Field(..., description="Search result items")
    total: int = Field(..., description="Total number of matching issues")
    query: str = Field(..., description="Search query used")
