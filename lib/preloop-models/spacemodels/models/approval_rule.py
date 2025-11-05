"""Approval rule model for conditional approval based on tool arguments."""

import uuid
from typing import TYPE_CHECKING, Dict, Optional

from sqlalchemy import ForeignKey, String, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Boolean, JSON

from .base import Base

if TYPE_CHECKING:
    from .account import Account
    from .tool_configuration import ToolConfiguration, ApprovalPolicy


class ApprovalRule(Base):
    """Approval rule for conditional tool approval based on arguments.

    Approval rules allow fine-grained control over when tools require approval.
    Instead of always requiring approval, rules can evaluate tool arguments
    using a configurable condition evaluator (e.g., CEL expressions).

    Example rules:
        - Require approval for transactions over $1000
        - Require approval for production deployments
        - Require approval for critical priority issues

    Attributes:
        id: Unique identifier for the rule.
        account_id: The account this rule belongs to.
        tool_configuration_id: Reference to the tool configuration.
        name: Human-readable name for the rule.
        description: Optional description of what this rule does.
        is_enabled: Whether the rule is currently active.
        priority: Order of evaluation (lower = higher priority).
        condition_type: Type of condition evaluator ('argument', 'state', 'risk').
        condition_config: Configuration for the condition evaluator.
        approval_policy_id: Reference to approval policy when condition matches.
        created_at: When the rule was created.
        updated_at: When the rule was last modified.
    """

    __tablename__ = "approval_rule"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The account this rule belongs to",
    )

    tool_configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tool_configuration.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the tool configuration",
    )

    # Rule identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Human-readable name for the rule",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of what this rule does",
    )

    # Rule status and priority
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether the rule is currently active",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
        comment="Order of evaluation (lower = higher priority)",
    )

    # Condition configuration
    condition_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="argument",
        index=True,
        comment="Type of condition evaluator: 'argument', 'state', 'risk'",
    )

    condition_config: Mapped[Dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Configuration for the condition evaluator (e.g., CEL expression)",
    )

    # Approval policy to use when condition matches
    approval_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_policy.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to approval policy when condition matches",
    )

    # Timestamps

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="approval_rules"
    )
    tool_configuration: Mapped["ToolConfiguration"] = relationship(
        "ToolConfiguration", back_populates="approval_rules"
    )
    approval_policy: Mapped["ApprovalPolicy"] = relationship(
        "ApprovalPolicy", back_populates="approval_rules"
    )

    def __repr__(self) -> str:
        """String representation."""
        status = "enabled" if self.is_enabled else "disabled"
        return (
            f"<ApprovalRule(name={self.name}, type={self.condition_type}, "
            f"priority={self.priority}, {status})>"
        )
