"""Tool configuration model for managing tool settings and approval policies."""

import uuid
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Boolean, JSON

from .base import Base

if TYPE_CHECKING:
    from .account import Account
    from .mcp_server import MCPServer
    from .approval_request import ApprovalRequest
    from .tool_approval_condition import ToolApprovalCondition


class ToolConfiguration(Base):
    """Tool configuration model for managing per-account tool settings.

    This model controls which tools are available to each account and
    their approval policies. It supports:
    - Built-in/default tools (always available)
    - External MCP server tools
    - Future HTTP tools

    Attributes:
        id: Unique identifier for the configuration.
        account_id: The account this configuration belongs to.
        tool_name: Name of the tool.
        tool_source: Source type ('builtin', 'mcp', 'http').
        mcp_server_id: Reference to MCP server (if tool_source='mcp').
        is_enabled: Whether the tool is enabled for this account.
        requires_approval: Whether the tool requires pre-execution approval ("preloop").
        approval_policy_id: Reference to approval policy (if requires_approval=True).
        tool_description: Description of what the tool does.
        tool_schema: JSON schema for tool parameters.
        custom_config: Additional configuration options.
    """

    __tablename__ = "tool_configuration"

    # Tool identification
    tool_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, comment="Name of the tool"
    )
    tool_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="builtin",
        index=True,
        comment="Source type: 'builtin', 'mcp', 'http'",
    )

    # For external tools, reference to the source
    mcp_server_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mcp_server.id", ondelete="CASCADE"),
        nullable=True,
        comment="Reference to MCP server (if tool_source='mcp')",
    )
    http_endpoint_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Reference to HTTP endpoint (future: if tool_source='http')",
    )

    # Configuration
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Whether the tool is enabled"
    )

    # Reference to reusable approval policy
    approval_policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_policy.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Reference to approval policy (if set, tool requires approval)",
    )

    # Metadata
    tool_description: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, comment="Description of what the tool does"
    )
    tool_schema: Mapped[Optional[Dict]] = mapped_column(
        JSON, nullable=True, comment="JSON schema for tool parameters"
    )
    custom_config: Mapped[Optional[Dict]] = mapped_column(
        JSON, nullable=True, comment="Additional configuration options"
    )

    # Foreign keys
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="tool_configurations"
    )
    mcp_server: Mapped[Optional["MCPServer"]] = relationship(
        "MCPServer", back_populates="tool_configurations"
    )
    approval_policy: Mapped[Optional["ApprovalPolicy"]] = relationship(
        "ApprovalPolicy",
        back_populates="tool_configurations",
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        back_populates="tool_configuration",
        cascade="all, delete-orphan",
    )
    approval_condition: Mapped[Optional["ToolApprovalCondition"]] = relationship(
        "ToolApprovalCondition",
        back_populates="tool_configuration",
        uselist=False,  # 1:1 relationship
        cascade="all, delete-orphan",
    )

    # Unique constraint: one configuration per tool+source per account
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "tool_name",
            "tool_source",
            "mcp_server_id",
            name="uq_account_tool_source",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of the configuration."""
        status = "enabled" if self.is_enabled else "disabled"
        approval = " (approval required)" if self.approval_policy_id else ""
        return f"<ToolConfiguration {self.tool_name} [{self.tool_source}] ({status}{approval}) for account {self.account_id}>"


class ApprovalPolicy(Base):
    """Reusable approval policy for tools that require pre-execution approval.

    This model defines how approval requests should be handled for tools
    with requires_approval=True. Policies are account-scoped and reusable
    across multiple tool configurations.

    Attributes:
        id: Unique identifier for the policy.
        account_id: The account this policy belongs to.
        name: Human-readable name for the policy.
        description: Optional description of what this policy does.
        approval_type: Type of approval mechanism ('slack', 'mattermost', etc.).
        channel: Slack/Mattermost channel for approval requests.
        user: Specific user to request approval from.
        approval_config: Generic configuration for approval mechanism.
        timeout_seconds: How long to wait for approval before timing out.
        require_reason: Whether approver must provide a reason.
    """

    __tablename__ = "approval_policy"

    # Policy identification
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The account this policy belongs to",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Human-readable name for the policy",
    )
    description: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        comment="Optional description of what this policy does",
    )

    # Approval mechanism
    approval_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="slack",
        comment="Type of approval: 'slack', 'mattermost', 'webhook', 'manual'",
    )

    # Slack/Mattermost configuration
    channel: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Channel for approval requests"
    )
    user: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Specific user to request approval from"
    )

    # Generic approval configuration (for future extensibility)
    approval_config: Mapped[Optional[Dict]] = mapped_column(
        JSON, nullable=True, comment="Generic configuration for approval mechanism"
    )

    # Policy settings
    timeout_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=300,
        comment="How long to wait for approval (default: 5 minutes)",
    )
    require_reason: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether approver must provide a reason",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this is the default policy for the account",
    )

    # Workflow configuration (Phase 2+)
    workflow_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="simple",
        comment="Type of approval workflow: 'simple', 'multi_stage', 'consensus'",
    )
    workflow_config: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Configuration for the approval workflow (stages, teams, voting rules)",
    )

    # Approvers (proprietary features)
    approver_user_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="List of user IDs who can approve (proprietary)",
    )
    approver_team_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="List of team IDs whose members can approve (proprietary)",
    )

    # Quorum configuration (proprietary)
    approvals_required: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Number of approvals required (quorum) - proprietary",
    )

    # Escalation configuration (proprietary)
    escalation_user_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="List of user IDs to escalate to on timeout (proprietary)",
    )
    escalation_team_ids: Mapped[Optional[List[uuid.UUID]]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
        comment="List of team IDs to escalate to on timeout (proprietary)",
    )

    # Notification configuration
    notification_channels: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=["email"],
        comment="Notification channels: email, mobile_push, slack, mattermost, webhook",
    )
    channel_configs: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Configuration for notification channels (Slack/Mattermost/webhook settings)",
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account")
    tool_configurations: Mapped[list["ToolConfiguration"]] = relationship(
        "ToolConfiguration", back_populates="approval_policy"
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        back_populates="approval_policy",
        cascade="all, delete-orphan",
    )

    # Unique constraint: one policy name per account
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "name",
            name="uq_account_policy_name",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of the policy."""
        target = self.channel or self.user or "unknown"
        return f"<ApprovalPolicy(name={self.name}, type={self.approval_type}, target={target})>"
