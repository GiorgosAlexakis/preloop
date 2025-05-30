"""Comment schemas for request and response validation."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CommentBase(BaseModel):
    """Base model for comment data."""

    body: str = Field(..., description="Comment text")
    metadata: Optional[Dict] = Field(None, description="Additional comment metadata")


class CommentCreate(CommentBase):
    """Model for creating a new comment."""

    pass


class CommentResponse(CommentBase):
    """Response model for comment data."""

    id: str = Field(..., description="Comment unique identifier")
    issue_id: str = Field(..., description="Issue ID this comment belongs to")
    author: str = Field(..., description="Comment author")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class CommentList(BaseModel):
    """Response model for a list of comments with pagination details."""

    items: List[CommentResponse]
    total: int
    limit: int
    offset: int


class CommentSearchResults(BaseModel):
    """Response model for comment search results."""

    items: List[CommentResponse] = Field(..., description="Search result items")
    total: int = Field(..., description="Total number of matching comments")
    query: str = Field(..., description="Search query used")
