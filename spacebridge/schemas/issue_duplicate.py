"""Issue Duplicate schemas for request and response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel


class IssueDuplicateBase(BaseModel):
    """Base schema for IssueDuplicate."""

    issue1_id: str
    issue2_id: str
    decision: str
    decision_at: Optional[datetime] = None
    llm_model_id: str
    llm_model_name: Optional[str] = None
    reason: Optional[str] = None


class IssueDuplicateCreate(IssueDuplicateBase):
    """Schema for creating an IssueDuplicate."""

    pass


class IssueDuplicateUpdate(IssueDuplicateBase):
    """Schema for updating an IssueDuplicate."""

    pass


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

class IssueDuplicateStats(BaseModel):
    projects: Dict[str, IssueDuplicateProjectStats]