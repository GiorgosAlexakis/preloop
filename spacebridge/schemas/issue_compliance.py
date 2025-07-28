"""Schemas for IssueComplianceResult model."""

from pydantic import BaseModel
from datetime import datetime


class IssueComplianceResultBase(BaseModel):
    prompt_id: str
    name: str
    compliance_factor: float
    reason: str
    issue_id: str


class IssueComplianceResultCreate(IssueComplianceResultBase):
    pass


class IssueComplianceResultResponse(IssueComplianceResultBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComplianceSuggestionResponse(BaseModel):
    title: str
    description: str
