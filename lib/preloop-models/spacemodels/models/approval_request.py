"""Approval request model for tool execution approvals."""

import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .account import Account
from .tool_configuration import ApprovalPolicy, ToolConfiguration

from .base import Base


class ApprovalRequestStatus(str):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalRequest(Base):
    """Approval request for tool execution.

    An approval request is created when a tool requiring approval is called.
    The MCP tool execution pauses and waits for approval/decline via webhook link.
    """

    __tablename__ = "approval_request"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The account this approval request belongs to",
    )

    tool_configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tool_configuration.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the tool configuration",
    )

    approval_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_policy.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the approval policy",
    )

    execution_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Flow execution ID (if applicable)",
    )

    tool_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Name of the tool being executed",
    )

    tool_args: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Arguments passed to the tool",
    )

    agent_reasoning: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Agent's reasoning for the tool call",
    )

    status: Mapped[str] = mapped_column(
        SQLEnum(
            "pending",
            "approved",
            "declined",
            "expired",
            "cancelled",
            name="approval_request_status",
        ),
        nullable=False,
        default=ApprovalRequestStatus.PENDING,
        index=True,
        comment="Current status of the approval request",
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When the approval was requested",
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="When the approval was resolved (approved/declined)",
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="When the approval request expires",
    )

    approver_comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Comment from the approver",
    )

    webhook_posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="When the webhook notification was posted",
    )

    webhook_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if webhook posting failed",
    )

    approval_token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: secrets.token_urlsafe(32),
        comment="Secure token for public approval links",
    )

    # Relationships
    account: Mapped["Account"] = relationship(
        "Account", back_populates="approval_requests"
    )
    tool_configuration: Mapped["ToolConfiguration"] = relationship(
        "ToolConfiguration", back_populates="approval_requests"
    )
    approval_policy: Mapped["ApprovalPolicy"] = relationship(
        "ApprovalPolicy", back_populates="approval_requests"
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ApprovalRequest(id={self.id}, tool_name={self.tool_name}, "
            f"status={self.status}, requested_at={self.requested_at})>"
        )
