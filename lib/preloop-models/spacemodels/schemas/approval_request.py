"""Pydantic schemas for approval requests."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ApprovalRequestBase(BaseModel):
    """Base schema for approval requests."""

    tool_name: str = Field(..., description="Name of the tool being executed")
    tool_args: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the tool"
    )
    agent_reasoning: Optional[str] = Field(
        None, description="Agent's reasoning for the tool call"
    )
    execution_id: Optional[str] = Field(
        None, description="Flow execution ID (if applicable)"
    )


class ApprovalRequestCreate(ApprovalRequestBase):
    """Schema for creating a new approval request."""

    account_id: str
    tool_configuration_id: UUID
    approval_policy_id: UUID
    expires_at: Optional[datetime] = None


class ApprovalRequestUpdate(BaseModel):
    """Schema for updating an approval request."""

    status: Optional[str] = None
    approver_comment: Optional[str] = None
    resolved_at: Optional[datetime] = None
    webhook_posted_at: Optional[datetime] = None
    webhook_error: Optional[str] = None


class ApprovalRequestResponse(ApprovalRequestBase):
    """Schema for approval request response."""

    id: UUID
    account_id: UUID  # Changed from str to UUID for validation, serializer converts to str for JSON
    tool_configuration_id: UUID
    approval_policy_id: UUID
    status: str
    requested_at: datetime
    resolved_at: Optional[datetime]
    expires_at: Optional[datetime]
    approver_comment: Optional[str]
    webhook_posted_at: Optional[datetime]
    webhook_error: Optional[str]

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id", "account_id", "tool_configuration_id", "approval_policy_id")
    def serialize_uuid(self, value: Optional[UUID]) -> Optional[str]:
        """Serialize UUID to string."""
        return str(value) if value else None


class ApprovalDecision(BaseModel):
    """Schema for approval decision."""

    approved: bool = Field(
        ..., description="Whether the request is approved or declined"
    )
    comment: Optional[str] = Field(None, description="Comment from the approver")
