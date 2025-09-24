"""
Pydantic schemas for the MCP API endpoints.
"""

from pydantic import BaseModel
from typing import Optional, List

from spacebridge.schemas.issue import IssueResponse
from spacebridge.schemas.issue_compliance import IssueComplianceResultResponse


class GetIssueRequest(BaseModel):
    """Request body for the get_issue tool."""

    issue: str


class GetIssueResponse(IssueResponse):
    """Response for the get_issue tool, including compliance data."""

    compliance_results: Optional[List[IssueComplianceResultResponse]] = None


class CreateIssueRequest(BaseModel):
    """Request body for the create_issue tool."""

    project: str
    title: str
    description: str
    labels: Optional[List[str]] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    similarity_search: bool = True


class CreateIssueResponse(BaseModel):
    """Response for the create_issue tool."""

    issue_id: str
    status: str  # e.g., "created", "existing_duplicate_found"
    message: str
    url: Optional[str] = None


class UpdateIssueRequest(BaseModel):
    """Request body for the update_issue tool."""

    issue: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    labels: Optional[List[str]] = None


class UpdateIssueResponse(BaseModel):
    """Response for the update_issue tool."""

    issue_id: str
    status: str  # e.g., "updated", "failed"
    message: str
    url: Optional[str] = None


class SearchRequest(BaseModel):
    """Request body for the search tool."""

    query: str
    project: Optional[str] = None
    limit: Optional[int] = 10


# The response for the search tool can reuse the existing SearchResponse
# from the main API, but we'll define it here for clarity if needed.
# For now, we can rely on the endpoint to return the correct structure.


class EstimateComplianceRequest(BaseModel):
    """Request body for the estimate_compliance tool."""

    issues: List[str]


class EstimateComplianceResponse(BaseModel):
    """Response for the estimate_compliance tool."""

    results: List[IssueComplianceResultResponse]


class SuggestedUpdate(BaseModel):
    """A suggested tool call to update an issue."""

    tool_name: str = "update_issue"
    arguments: UpdateIssueRequest


class ImproveComplianceRequest(BaseModel):
    """Request body for the improve_compliance tool."""

    issues: List[str]


class ProcessingMetadata(BaseModel):
    """Metadata about processing results."""

    total_requested: int
    successfully_processed: int
    failed_count: int
    failed_issues: List[str] = []
    errors: List[str] = []


class ImproveComplianceResponse(BaseModel):
    """Response for the improve_compliance tool."""

    suggested_updates: List[SuggestedUpdate]
    metadata: ProcessingMetadata


# Schemas for other tools will be added here.
