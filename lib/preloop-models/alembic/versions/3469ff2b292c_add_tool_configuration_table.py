"""add_tool_configuration_table

Revision ID: 3469ff2b292c
Revises: 97d779394715
Create Date: 2025-10-12 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3469ff2b292c"
down_revision: Union[str, None] = "97d779394715"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create tool_configuration table for Phase 1A."""
    op.create_table(
        "tool_configuration",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "tool_identifier",
            sa.String(255),
            nullable=False,
            comment="Format: 'default:tool_name' or 'mcp_server_id:tool_name'",
        ),
        sa.Column(
            "is_default_tool",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="True for built-in tools, False for proxied tools",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Whether the tool is enabled",
        ),
        sa.Column(
            "preloop_policy",
            sa.String(50),
            nullable=True,
            comment="Approval policy: 'none', 'always', 'per_session', 'parameter_based'",
        ),
        sa.Column(
            "approval_config",
            sa.JSON(),
            nullable=True,
            comment="JSON configuration for approval workflow",
        ),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create indexes
    op.create_index(
        "ix_tool_configuration_account_id",
        "tool_configuration",
        ["account_id"],
    )
    op.create_index(
        "ix_tool_configuration_tool_identifier",
        "tool_configuration",
        ["tool_identifier"],
    )

    # Create unique constraint
    op.create_unique_constraint(
        "uq_account_tool",
        "tool_configuration",
        ["account_id", "tool_identifier"],
    )


def downgrade() -> None:
    """Downgrade schema: drop tool_configuration table."""
    op.drop_table("tool_configuration")
