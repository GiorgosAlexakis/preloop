"""Issue Duplicate schemas for request and response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict
from uuid import UUID
from pydantic import BaseModel


class IssueDuplicate(BaseModel):
    """Base schema for IssueDuplicate."""

    issue1_id: str
    issue2_id: str

    # AI model's decision
    decision: str
    decision_at: Optional[datetime] = None
    reason: Optional[str] = None

    # User's resolution
    resolution: Optional[str] = None
    resolution_at: Optional[datetime] = None
    resolution_reason: Optional[str] = None
    resulting_issue1_id: Optional[str] = None
    resulting_issue2_id: Optional[str] = None
    ai_model_id: Optional[UUID] = None
    ai_model_name: Optional[str] = None


class IssueDuplicateUpdate(BaseModel):
    """Schema for updating an IssueDuplicate."""

    resolution: Optional[str] = None
    resolution_at: Optional[datetime] = None
    resolution_reason: Optional[str] = None


class IssueDuplicateSuggestionRequest(BaseModel):
    """Schema for suggesting a resolution for an IssueDuplicate."""

    issue1_id: str
    issue2_id: str
    resolution: str
    resolution_reason: Optional[str] = None
    resulting_issue1_id: Optional[str] = None
    resulting_issue2_id: Optional[str] = None


class IssueDuplicateSuggestionResponse(BaseModel):
    merged_title: Optional[str] = None
    merged_description: Optional[str] = None
    deconflicted_title1: Optional[str] = None
    deconflicted_description1: Optional[str] = None
    deconflicted_title2: Optional[str] = None
    deconflicted_description2: Optional[str] = None
    explanation: str


class IssueDuplicateResolutionRequest(BaseModel):
    issue1_id: str
    issue2_id: str
    resolution: str
    resolution_reason: Optional[str] = None
    resulting_issue_1_title: Optional[str] = None
    resulting_issue_1_description: Optional[str] = None
    resulting_issue_2_title: Optional[str] = None
    resulting_issue_2_description: Optional[str] = None


class IssueDuplicateResolutionResponse(BaseModel):
    issue1_id: str
    issue2_id: str
    resolution: str


class IssueDuplicateProjectStats(BaseModel):
    project_id: str
    project_name: str
    total: int
    duplicates: int


class IssueDuplicateStats(BaseModel):
    projects: Dict[str, IssueDuplicateProjectStats]
