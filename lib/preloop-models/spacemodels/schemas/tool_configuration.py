"""Pydantic schemas for tool configuration and approval policies."""

from datetime import datetime
from typing import Any, Dict, Optional
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
    requires_approval: Optional[bool] = Field(
        False, description="Whether the tool requires pre-execution approval (preloop)"
    )
    approval_policy_id: Optional[UUID] = Field(
        None, description="Reference to approval policy (if requires_approval=True)"
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
    account_id: str
    tool_name: str
    tool_source: str
    mcp_server_id: Optional[UUID] = None
    http_endpoint_id: Optional[UUID] = None
    approval_policy_id: Optional[UUID] = None
    is_enabled: bool
    requires_approval: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id", "mcp_server_id", "http_endpoint_id", "approval_policy_id")
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
    account_id: str
    name: str
    approval_type: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID to string."""
        return str(value)
