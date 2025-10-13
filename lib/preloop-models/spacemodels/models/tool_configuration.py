"""Tool configuration model for managing MCP tool settings."""

from typing import TYPE_CHECKING, Dict, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Boolean, JSON

from .base import Base

if TYPE_CHECKING:
    from .account import Account


class ToolConfiguration(Base):
    """Tool configuration model for managing per-account tool settings.

    This model controls which MCP tools are available to each account and
    their approval policies. It applies to both default (built-in) tools
    and proxied tools from external MCP servers.

    For Phase 1A, only default tools are supported. External tool support
    will be added in Phase 1B.

    Attributes:
        id: Unique identifier for the configuration.
        account_id: The account this configuration belongs to.
        tool_identifier: Unique identifier for the tool.
            Format: "default:tool_name" for built-in tools
                    "mcp_server_id:tool_name" for proxied tools (Phase 1B)
        is_default_tool: True for built-in tools, False for proxied tools.
        enabled: Whether the tool is enabled for this account.
        preloop_policy: Approval policy for the tool (Phase 2).
            Values: "none", "always", "per_session", "parameter_based"
        approval_config: JSON configuration for approval workflow (Phase 2).
            Example: {"slack_webhook": "...", "approvers": [...]}
    """

    __tablename__ = "tool_configuration"

    # Tool identification
    tool_identifier: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Format: 'default:tool_name' or 'mcp_server_id:tool_name'",
    )
    is_default_tool: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="True for built-in tools, False for proxied tools",
    )

    # Enablement
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Whether the tool is enabled"
    )

    # Approval workflow (Phase 2 - nullable for now)
    preloop_policy: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="none",
        comment="Approval policy: 'none', 'always', 'per_session', 'parameter_based'",
    )
    approval_config: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="JSON configuration for approval workflow",
    )

    # Foreign keys
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="tool_configurations"
    )

    # Unique constraint: one configuration per tool per account
    __table_args__ = (
        UniqueConstraint("account_id", "tool_identifier", name="uq_account_tool"),
    )

    def __repr__(self) -> str:
        """Return string representation of the configuration."""
        status = "enabled" if self.enabled else "disabled"
        return f"<ToolConfiguration {self.tool_identifier} ({status}) for account {self.account_id}>"
