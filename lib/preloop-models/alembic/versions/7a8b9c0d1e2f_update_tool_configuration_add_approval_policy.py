"""update_tool_configuration_add_approval_policy

Revision ID: 7a8b9c0d1e2f
Revises: 06f1829bdac9
Create Date: 2025-10-13 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, None] = "06f1829bdac9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: update tool_configuration and create approval_policy tables."""

    # First, drop the unique constraint that depends on old columns
    op.drop_constraint("uq_account_tool", "tool_configuration", type_="unique")

    # Drop old indexes
    op.drop_index(
        "ix_tool_configuration_tool_identifier", table_name="tool_configuration"
    )

    # Change id from String to UUID
    op.execute(
        "ALTER TABLE tool_configuration ALTER COLUMN id TYPE UUID USING id::uuid"
    )

    # Drop old columns
    op.drop_column("tool_configuration", "tool_identifier")
    op.drop_column("tool_configuration", "is_default_tool")
    op.drop_column("tool_configuration", "preloop_policy")
    op.drop_column("tool_configuration", "approval_config")

    # Add new columns
    op.add_column(
        "tool_configuration",
        sa.Column(
            "tool_name",
            sa.String(255),
            nullable=False,
            comment="Name of the tool",
            server_default="unknown",  # Temporary default for existing rows
        ),
    )
    op.add_column(
        "tool_configuration",
        sa.Column(
            "tool_source",
            sa.String(50),
            nullable=False,
            server_default="builtin",
            comment="Source type: 'builtin', 'mcp', 'http'",
        ),
    )
    op.add_column(
        "tool_configuration",
        sa.Column(
            "mcp_server_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Reference to MCP server (if tool_source='mcp')",
        ),
    )
    op.add_column(
        "tool_configuration",
        sa.Column(
            "http_endpoint_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Reference to HTTP endpoint (future: if tool_source='http')",
        ),
    )
    op.add_column(
        "tool_configuration",
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether the tool requires pre-execution approval (preloop)",
        ),
    )
    op.add_column(
        "tool_configuration",
        sa.Column(
            "tool_description",
            sa.String(),
            nullable=True,
            comment="Description of what the tool does",
        ),
    )
    op.add_column(
        "tool_configuration",
        sa.Column(
            "tool_schema",
            postgresql.JSONB(),
            nullable=True,
            comment="JSON schema for tool parameters",
        ),
    )
    op.add_column(
        "tool_configuration",
        sa.Column(
            "custom_config",
            postgresql.JSONB(),
            nullable=True,
            comment="Additional configuration options",
        ),
    )

    # Rename 'enabled' to 'is_enabled' for consistency
    op.alter_column("tool_configuration", "enabled", new_column_name="is_enabled")

    # Add foreign key for mcp_server_id
    op.create_foreign_key(
        "fk_tool_configuration_mcp_server_id",
        "tool_configuration",
        "mcp_server",
        ["mcp_server_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Create new indexes
    op.create_index(
        "ix_tool_configuration_tool_name",
        "tool_configuration",
        ["tool_name"],
    )
    op.create_index(
        "ix_tool_configuration_tool_source",
        "tool_configuration",
        ["tool_source"],
    )

    # Create new unique constraint
    op.create_unique_constraint(
        "uq_account_tool_source",
        "tool_configuration",
        ["account_id", "tool_name", "tool_source", "mcp_server_id"],
    )

    # Remove temporary default values
    op.alter_column("tool_configuration", "tool_name", server_default=None)

    # Create approval_policy table
    op.create_table(
        "approval_policy",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "tool_configuration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tool_configuration.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            comment="Reference to the tool configuration",
        ),
        sa.Column(
            "approval_type",
            sa.String(50),
            nullable=False,
            server_default="slack",
            comment="Type of approval: 'slack', 'mattermost', 'webhook', 'manual'",
        ),
        sa.Column(
            "channel",
            sa.String(255),
            nullable=True,
            comment="Channel for approval requests",
        ),
        sa.Column(
            "user",
            sa.String(255),
            nullable=True,
            comment="Specific user to request approval from",
        ),
        sa.Column(
            "approval_config",
            postgresql.JSONB(),
            nullable=True,
            comment="Generic configuration for approval mechanism",
        ),
        sa.Column(
            "timeout_seconds",
            sa.Integer(),
            nullable=True,
            server_default="300",
            comment="How long to wait for approval (default: 5 minutes)",
        ),
        sa.Column(
            "require_reason",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether approver must provide a reason",
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

    # Create indexes for approval_policy
    op.create_index(
        "ix_approval_policy_tool_configuration_id",
        "approval_policy",
        ["tool_configuration_id"],
    )


def downgrade() -> None:
    """Downgrade schema: revert changes."""

    # Drop approval_policy table
    op.drop_table("approval_policy")

    # Drop new unique constraint
    op.drop_constraint("uq_account_tool_source", "tool_configuration", type_="unique")

    # Drop new indexes
    op.drop_index("ix_tool_configuration_tool_name", table_name="tool_configuration")
    op.drop_index("ix_tool_configuration_tool_source", table_name="tool_configuration")

    # Drop foreign key
    op.drop_constraint(
        "fk_tool_configuration_mcp_server_id", "tool_configuration", type_="foreignkey"
    )

    # Rename is_enabled back to enabled
    op.alter_column("tool_configuration", "is_enabled", new_column_name="enabled")

    # Drop new columns
    op.drop_column("tool_configuration", "custom_config")
    op.drop_column("tool_configuration", "tool_schema")
    op.drop_column("tool_configuration", "tool_description")
    op.drop_column("tool_configuration", "requires_approval")
    op.drop_column("tool_configuration", "http_endpoint_id")
    op.drop_column("tool_configuration", "mcp_server_id")
    op.drop_column("tool_configuration", "tool_source")
    op.drop_column("tool_configuration", "tool_name")

    # Add back old columns
    op.add_column(
        "tool_configuration",
        sa.Column("approval_config", sa.JSON(), nullable=True),
    )
    op.add_column(
        "tool_configuration",
        sa.Column("preloop_policy", sa.String(50), nullable=True),
    )
    op.add_column(
        "tool_configuration",
        sa.Column(
            "is_default_tool", sa.Boolean(), nullable=False, server_default="true"
        ),
    )
    op.add_column(
        "tool_configuration",
        sa.Column("tool_identifier", sa.String(255), nullable=False, server_default=""),
    )

    # Change id back to String
    op.execute(
        "ALTER TABLE tool_configuration ALTER COLUMN id TYPE VARCHAR(36) USING id::text"
    )

    # Recreate old indexes
    op.create_index(
        "ix_tool_configuration_tool_identifier",
        "tool_configuration",
        ["tool_identifier"],
    )

    # Recreate old unique constraint
    op.create_unique_constraint(
        "uq_account_tool",
        "tool_configuration",
        ["account_id", "tool_identifier"],
    )
