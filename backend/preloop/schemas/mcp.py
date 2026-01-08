"""
Pydantic schemas for the MCP API endpoints.
"""

from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID

from preloop.schemas.issue import IssueResponse
from preloop.schemas.issue_compliance import IssueComplianceResultResponse


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

    @field_validator("issue_id", mode="before")
    @classmethod
    def validate_issue_id(cls, value: UUID | str) -> str:
        """Convert UUID to string for validation."""
        return str(value) if isinstance(value, UUID) else value


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

    @field_validator("issue_id", mode="before")
    @classmethod
    def validate_issue_id(cls, value: UUID | str) -> str:
        """Convert UUID to string for validation."""
        return str(value) if isinstance(value, UUID) else value


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


class ProcessingMetadata(BaseModel):
    """Metadata about processing results."""

    total_requested: int
    successfully_processed: int
    failed_count: int
    failed_issues: List[str] = []
    errors: List[str] = []


class EstimateComplianceResponse(BaseModel):
    """Response for the estimate_compliance tool."""

    results: List[IssueComplianceResultResponse]
    metadata: Optional[ProcessingMetadata] = None


class SuggestedUpdate(BaseModel):
    """A suggested tool call to update an issue."""

    tool_name: str = "update_issue"
    issue_identifier: str
    arguments: UpdateIssueRequest

    @field_validator("issue_identifier", mode="before")
    @classmethod
    def validate_issue_identifier(cls, value: UUID | str) -> str:
        """Convert UUID to string for validation."""
        return str(value) if isinstance(value, UUID) else value


class ImproveComplianceRequest(BaseModel):
    """Request body for the improve_compliance tool."""

    issues: List[str]


class ImproveComplianceResponse(BaseModel):
    """Response for the improve_compliance tool."""

    suggested_updates: List[SuggestedUpdate]
    metadata: ProcessingMetadata


class AddCommentRequest(BaseModel):
    """Request body for the add_comment tool."""

    target: str  # Issue, PR, or MR identifier (URL, key, or ID)
    comment: str


class AddCommentResponse(BaseModel):
    """Response for the add_comment tool."""

    comment_id: str
    status: str  # e.g., "created"
    message: str
    url: Optional[str] = None

    @field_validator("comment_id", mode="before")
    @classmethod
    def validate_comment_id(cls, value: UUID | str) -> str:
        """Convert UUID to string for validation."""
        return str(value) if isinstance(value, UUID) else value


class GetPullRequestRequest(BaseModel):
    """Request body for the get_pull_request tool."""

    pull_request: str  # PR identifier (URL, slug, or number)


class PullRequestResponse(BaseModel):
    """Response for the get_pull_request tool."""

    id: str
    number: int
    title: str
    description: Optional[str] = None
    state: str  # e.g., "open", "closed", "merged"
    author: Optional[str] = None
    assignees: List[str] = []
    reviewers: List[str] = []
    labels: List[str] = []
    url: str
    source_branch: Optional[str] = None
    target_branch: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    merged_at: Optional[str] = None
    is_draft: bool = False
    comments: List[dict] = []
    changes: Optional[dict] = None  # Diff/changes information


class GetMergeRequestRequest(BaseModel):
    """Request body for the get_merge_request tool."""

    merge_request: str  # MR identifier (URL, slug, or number)


class MergeRequestResponse(BaseModel):
    """Response for the get_merge_request tool."""

    id: str
    iid: int  # GitLab internal ID
    title: str
    description: Optional[str] = None
    state: str  # e.g., "opened", "closed", "merged"
    author: Optional[str] = None
    assignees: List[str] = []
    reviewers: List[str] = []
    labels: List[str] = []
    url: str
    source_branch: Optional[str] = None
    target_branch: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    merged_at: Optional[str] = None
    work_in_progress: bool = False
    comments: List[dict] = []
    changes: Optional[dict] = None  # Diff/changes information


class UpdatePullRequestRequest(BaseModel):
    """Request body for the update_pull_request tool."""

    pull_request: str  # PR identifier (URL, slug, or number)
    title: Optional[str] = None
    description: Optional[str] = None
    state: Optional[str] = None  # "open", "closed"
    assignees: Optional[List[str]] = None
    reviewers: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    draft: Optional[bool] = None


class UpdatePullRequestResponse(BaseModel):
    """Response for the update_pull_request tool."""

    pull_request_id: str
    status: str  # e.g., "updated"
    message: str
    url: Optional[str] = None

    @field_validator("pull_request_id", mode="before")
    @classmethod
    def validate_pull_request_id(cls, value: UUID | str) -> str:
        """Convert UUID to string for validation."""
        return str(value) if isinstance(value, UUID) else value


class UpdateMergeRequestRequest(BaseModel):
    """Request body for the update_merge_request tool."""

    merge_request: str  # MR identifier (URL, slug, or number)
    title: Optional[str] = None
    description: Optional[str] = None
    state_event: Optional[str] = None  # "close", "reopen"
    assignee_ids: Optional[List[int]] = None
    reviewer_ids: Optional[List[int]] = None
    labels: Optional[List[str]] = None
    draft: Optional[bool] = None


class UpdateMergeRequestResponse(BaseModel):
    """Response for the update_merge_request tool."""

    merge_request_id: str
    status: str  # e.g., "updated"
    message: str
    url: Optional[str] = None

    @field_validator("merge_request_id", mode="before")
    @classmethod
    def validate_merge_request_id(cls, value: UUID | str) -> str:
        """Convert UUID to string for validation."""
        return str(value) if isinstance(value, UUID) else value


# Schemas for other tools will be added here.
