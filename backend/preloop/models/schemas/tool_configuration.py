"""Pydantic schemas for tool configuration and approval policies."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


# Tool Configuration Schemas


class ToolConfigurationBase(BaseModel):
    """Base schema for tool configuration."""

    tool_name: Optional[str] = Field(None, description="Name of the tool")
    tool_source: Optional[str] = Field(
        "builtin", description="Source type: 'builtin', 'mcp', 'http'"
    )
    mcp_server_id: Optional[str] = Field(
        None, description="Reference to MCP server (if tool_source='mcp')"
    )
    http_endpoint_id: Optional[str] = Field(
        None, description="Reference to HTTP endpoint (future: if tool_source='http')"
    )
    is_enabled: Optional[bool] = Field(True, description="Whether the tool is enabled")
    approval_policy_id: Optional[UUID] = Field(
        None,
        description="Reference to approval policy (approval required if set and condition matches)",
    )
    tool_description: Optional[str] = Field(
        None, description="Description of what the tool does"
    )
    tool_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON schema for tool parameters"
    )
    custom_config: Optional[Dict[str, Any]] = Field(
        None, description="Additional configuration options"
    )


class ToolConfigurationCreate(ToolConfigurationBase):
    """Schema for creating tool configuration."""

    tool_name: str
    account_id: str
    tool_source: str = "builtin"


class ToolConfigurationUpdate(ToolConfigurationBase):
    """Schema for updating tool configuration."""

    pass


class ToolConfigurationResponse(ToolConfigurationBase):
    """Schema for tool configuration response."""

    id: UUID
    account_id: UUID  # Changed from str to UUID for validation, serializer converts to str for JSON
    tool_name: str
    tool_source: str
    mcp_server_id: Optional[UUID] = None
    http_endpoint_id: Optional[UUID] = None
    approval_policy_id: Optional[UUID] = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer(
        "id", "account_id", "mcp_server_id", "http_endpoint_id", "approval_policy_id"
    )
    def serialize_uuid(self, value: Optional[UUID]) -> Optional[str]:
        """Serialize UUID to string."""
        return str(value) if value else None


# Approval Policy Schemas


class ApprovalPolicyBase(BaseModel):
    """Base schema for approval policy."""

    name: Optional[str] = Field(None, description="Human-readable name for the policy")
    description: Optional[str] = Field(
        None, description="Optional description of what this policy does"
    )
    approval_type: Optional[str] = Field(
        "slack",
        description="Type of approval: 'slack', 'mattermost', 'webhook', 'manual'",
    )
    channel: Optional[str] = Field(None, description="Channel for approval requests")
    user: Optional[str] = Field(
        None, description="Specific user to request approval from"
    )
    approval_config: Optional[Dict[str, Any]] = Field(
        None, description="Generic configuration for approval mechanism"
    )
    timeout_seconds: Optional[int] = Field(
        300, description="How long to wait for approval (default: 5 minutes)"
    )
    require_reason: Optional[bool] = Field(
        False, description="Whether approver must provide a reason"
    )
    is_default: Optional[bool] = Field(
        False, description="Whether this is the default policy for the account"
    )
    workflow_type: Optional[str] = Field(
        "simple",
        description="Type of approval workflow: 'simple', 'multi_stage', 'consensus'",
    )
    workflow_config: Optional[Dict[str, Any]] = Field(
        None, description="Workflow configuration"
    )
    # Proprietary fields
    approver_user_ids: Optional[List[UUID]] = Field(
        None, description="List of user IDs who can approve (proprietary)"
    )
    approver_team_ids: Optional[List[UUID]] = Field(
        None, description="List of team IDs whose members can approve (proprietary)"
    )
    approvals_required: Optional[int] = Field(
        1, description="Number of approvals required (quorum) - proprietary"
    )
    escalation_user_ids: Optional[List[UUID]] = Field(
        None, description="List of user IDs to escalate to on timeout (proprietary)"
    )
    escalation_team_ids: Optional[List[UUID]] = Field(
        None, description="List of team IDs to escalate to on timeout (proprietary)"
    )
    notification_channels: Optional[List[str]] = Field(
        ["email"],
        description="Notification channels: email, mobile_push, slack, mattermost, webhook",
    )
    channel_configs: Optional[Dict[str, Any]] = Field(
        None,
        description="Configuration for notification channels (Slack/Mattermost/webhook settings)",
    )
    # AI-driven approval fields
    approval_mode: Optional[str] = Field(
        "standard",
        description="Approval mode: 'standard' (human) or 'ai_driven' (AI makes decision)",
    )
    ai_model: Optional[str] = Field(
        None,
        description="AI model for approval decisions (e.g., 'gpt-4o', 'claude-sonnet-4-20250514')",
    )
    ai_guidelines: Optional[str] = Field(
        None, description="User-defined guidelines for AI approval decisions"
    )
    ai_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional context for AI decisions (e.g., examples, constraints)",
    )
    ai_confidence_threshold: Optional[float] = Field(
        0.8, description="Minimum confidence score required for AI to make a decision"
    )
    ai_fallback_behavior: Optional[str] = Field(
        "escalate",
        description="Behavior when AI confidence is below threshold: 'escalate', 'approve', 'deny'",
    )
    escalation_policy_id: Optional[UUID] = Field(
        None, description="Policy to escalate to when fallback_behavior='escalate'"
    )


class ApprovalPolicyCreate(ApprovalPolicyBase):
    """Schema for creating approval policy."""

    name: str
    approval_type: str = "slack"


class ApprovalPolicyUpdate(ApprovalPolicyBase):
    """Schema for updating approval policy."""

    pass


class ApprovalPolicyResponse(ApprovalPolicyBase):
    """Schema for approval policy response."""

    id: UUID
    account_id: UUID
    name: str
    approval_type: str
    is_default: bool
    # AI-driven approval fields
    approval_mode: str
    ai_model: Optional[str] = None
    ai_guidelines: Optional[str] = None
    ai_context: Optional[Dict[str, Any]] = None
    ai_confidence_threshold: float
    ai_fallback_behavior: str
    escalation_policy_id: Optional[UUID] = None
    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id", "account_id", "escalation_policy_id")
    def serialize_uuid(self, value: Optional[UUID]) -> Optional[str]:
        """Serialize UUID to string."""
        return str(value) if value else None

    @field_serializer(
        "approver_user_ids",
        "approver_team_ids",
        "escalation_user_ids",
        "escalation_team_ids",
    )
    def serialize_uuid_list(self, value: Optional[List[UUID]]) -> Optional[List[str]]:
        """Serialize list of UUIDs to strings."""
        if value is None:
            return None
        return [str(v) for v in value]
