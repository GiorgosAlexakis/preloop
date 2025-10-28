"""add_mcp_server_and_mcp_tool_tables

Revision ID: 06f1829bdac9
Revises: 3469ff2b292c
Create Date: 2025-10-13 03:51:03.762004

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "06f1829bdac9"
down_revision: Union[str, None] = "3469ff2b292c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create mcp_server table
    op.create_table(
        "mcp_server",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column(
            "transport",
            sa.String(length=50),
            nullable=False,
            server_default="http-streaming",
        ),
        sa.Column(
            "auth_type", sa.String(length=50), nullable=False, server_default="none"
        ),
        sa.Column(
            "auth_config",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status", sa.String(length=50), nullable=False, server_default="active"
        ),
        sa.Column("last_scan_at", sa.String(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mcp_server_account_id"), "mcp_server", ["account_id"], unique=False
    )

    # Create mcp_tool table
    op.create_table(
        "mcp_tool",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("mcp_server_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "input_schema",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("discovered_at", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(
            ["mcp_server_id"],
            ["mcp_server.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mcp_tool_mcp_server_id"), "mcp_tool", ["mcp_server_id"], unique=False
    )
    op.create_index(op.f("ix_mcp_tool_name"), "mcp_tool", ["name"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_mcp_tool_name"), table_name="mcp_tool")
    op.drop_index(op.f("ix_mcp_tool_mcp_server_id"), table_name="mcp_tool")
    op.drop_table("mcp_tool")
    op.drop_index(op.f("ix_mcp_server_account_id"), table_name="mcp_server")
    op.drop_table("mcp_server")
