"""Schemas for IssueComplianceResult model."""

from pydantic import BaseModel
from datetime import datetime


class IssueComplianceResultBase(BaseModel):
    prompt_id: str
    name: str
    compliance_factor: float
    reason: str
    suggestion: str
    issue_id: str


class IssueComplianceResultCreate(IssueComplianceResultBase):
    pass


class IssueComplianceResultResponse(IssueComplianceResultBase):
    id: str
    short_name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComplianceSuggestionResponse(BaseModel):
    title: str
    description: str
    changes: str


class CompliancePromptMetadata(BaseModel):
    id: str
    name: str
    short_name: str


class Prompt(BaseModel):
    name: str
    system: str
    user: str


class ComplianceWorkflow(BaseModel):
    name: str
    short_name: str
    evaluate: Prompt
    propose_improvement: Prompt
