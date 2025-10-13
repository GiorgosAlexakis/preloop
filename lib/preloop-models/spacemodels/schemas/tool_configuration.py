"""Pydantic schemas for tool configuration."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolConfigurationBase(BaseModel):
    """Base schema for tool configuration."""

    tool_identifier: Optional[str] = Field(
        None,
        description="Tool identifier in format 'default:tool_name' or 'mcp_server_id:tool_name'",
    )
    is_default_tool: Optional[bool] = Field(
        True, description="True for built-in tools, False for proxied tools"
    )
    enabled: Optional[bool] = Field(
        True, description="Whether the tool is enabled for this account"
    )
    preloop_policy: Optional[str] = Field(
        "none",
        description="Approval policy: 'none', 'always', 'per_session', 'parameter_based'",
    )
    approval_config: Optional[Dict[str, Any]] = Field(
        None, description="JSON configuration for approval workflow"
    )


class ToolConfigurationCreate(ToolConfigurationBase):
    """Schema for creating tool configuration."""

    tool_identifier: str
    account_id: str


class ToolConfigurationUpdate(ToolConfigurationBase):
    """Schema for updating tool configuration."""

    pass


class ToolConfigurationResponse(ToolConfigurationBase):
    """Schema for tool configuration response."""

    id: str
    account_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
