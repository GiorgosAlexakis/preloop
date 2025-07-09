"""Issue Duplicate schemas for request and response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel


class IssueDuplicateBase(BaseModel):
    """Base schema for IssueDuplicate."""

    issue1_id: str
    issue2_id: str

    # LLM's decision
    decision: str
    decision_at: Optional[datetime] = None
    reason: Optional[str] = None

    # User's resolution
    resolution: Optional[str] = None
    resolution_at: Optional[datetime] = None
    resolution_reason: Optional[str] = None
    resulting_issue1_id: Optional[str] = None
    resulting_issue2_id: Optional[str] = None

    llm_model_id: str
    llm_model_name: Optional[str] = None


class IssueDuplicateCreate(IssueDuplicateBase):
    """Schema for creating an IssueDuplicate."""

    pass


class IssueDuplicateUpdate(IssueDuplicateBase):
    """Schema for updating an IssueDuplicate."""

    pass


class IssueDuplicateResolve(BaseModel):
    """Schema for resolving an IssueDuplicate."""

    issue1_id: str
    issue2_id: str
    resolution: str
    resolution_reason: Optional[str] = None
    resulting_issue1_id: Optional[str] = None
    resulting_issue2_id: Optional[str] = None
    merged_title: Optional[str] = None
    merged_description: Optional[str] = None
    disambiguated_title1: Optional[str] = None
    disambiguated_description1: Optional[str] = None
    disambiguated_title2: Optional[str] = None
    disambiguated_description2: Optional[str] = None


class IssueDuplicate(IssueDuplicateBase):
    """Schema for returning an IssueDuplicate."""

    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class PaginatedIssueDuplicateResponse(BaseModel):
    total: int
    items: List[IssueDuplicate]
    page: int
    size: int


class IssueDuplicateProjectStats(BaseModel):
    project_id: str
    project_name: str
    total: int
    duplicates: int


class IssueDuplicateSuggestionRequest(BaseModel):
    issue1_id: str
    issue2_id: str
    resolution: str


class IssueDuplicateSuggestionResponse(BaseModel):
    merged_title: Optional[str] = None
    merged_description: Optional[str] = None
    disambiguated_title1: Optional[str] = None
    disambiguated_description1: Optional[str] = None
    disambiguated_title2: Optional[str] = None
    disambiguated_description2: Optional[str] = None
    explanation: str


class IssueDuplicateStats(BaseModel):
    projects: Dict[str, IssueDuplicateProjectStats]
