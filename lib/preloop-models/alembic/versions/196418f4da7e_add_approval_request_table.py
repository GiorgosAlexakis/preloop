"""add_approval_request_table

Revision ID: 196418f4da7e
Revises: 9f557696858b
Create Date: 2025-10-17 04:16:51.622571

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "196418f4da7e"
down_revision: Union[str, None] = "9f557696858b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create approval_request_status enum
    from sqlalchemy.dialects.postgresql import ENUM

    approval_request_status = ENUM(
        "pending",
        "approved",
        "declined",
        "expired",
        "cancelled",
        name="approval_request_status",
        create_type=False,
    )

    # Create the enum type first
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE approval_request_status AS ENUM ('pending', 'approved', 'declined', 'expired', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create approval_request table
    op.create_table(
        "approval_request",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier for the approval request",
        ),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            comment="The account this approval request belongs to",
        ),
        sa.Column(
            "tool_configuration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tool_configuration.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            comment="Reference to the tool configuration",
        ),
        sa.Column(
            "approval_policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_policy.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
            comment="Reference to the approval policy",
        ),
        sa.Column(
            "execution_id",
            sa.String(255),
            nullable=True,
            index=True,
            comment="Flow execution ID (if applicable)",
        ),
        sa.Column(
            "tool_name",
            sa.String(255),
            nullable=False,
            comment="Name of the tool being executed",
        ),
        sa.Column(
            "tool_args",
            postgresql.JSONB,
            nullable=False,
            default={},
            comment="Arguments passed to the tool",
        ),
        sa.Column(
            "agent_reasoning",
            sa.Text,
            nullable=True,
            comment="Agent's reasoning for the tool call",
        ),
        sa.Column(
            "status",
            approval_request_status,
            nullable=False,
            server_default="pending",
            comment="Current status of the approval request",
        ),
        sa.Column(
            "requested_at",
            sa.DateTime,
            nullable=False,
            index=True,
            comment="When the approval was requested",
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime,
            nullable=True,
            comment="When the approval was resolved (approved/declined)",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime,
            nullable=True,
            comment="When the approval request expires",
        ),
        sa.Column(
            "approver_comment",
            sa.Text,
            nullable=True,
            comment="Comment from the approver",
        ),
        sa.Column(
            "webhook_posted_at",
            sa.DateTime,
            nullable=True,
            comment="When the webhook notification was posted",
        ),
        sa.Column(
            "webhook_error",
            sa.Text,
            nullable=True,
            comment="Error message if webhook posting failed",
        ),
    )

    # Create indexes
    op.create_index("ix_approval_request_status", "approval_request", ["status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_approval_request_status", table_name="approval_request")
    op.drop_table("approval_request")
    op.execute("DROP TYPE IF EXISTS approval_request_status")
