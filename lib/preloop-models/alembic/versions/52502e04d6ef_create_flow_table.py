"""create_flow_table

Revision ID: 52502e04d6ef
Revises: be827c0d6736
Create Date: 2025-06-08 18:26:56.389643

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "52502e04d6ef"
down_revision: Union[str, None] = "be827c0d6736"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "flow",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            nullable=False,  # Changed from UUID
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_event_source", sa.String(), nullable=False),
        sa.Column("trigger_event_type", sa.String(), nullable=False),
        sa.Column(
            "trigger_config",
            sa.JSON(),
            nullable=True,  # Changed from postgresql.JSONB
        ),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column(
            "model_configuration_id",
            sa.String(36),
            nullable=True,  # Changed from UUID
        ),
        sa.Column(
            "openhands_agent_config",
            sa.JSON(),  # Changed from postgresql.JSONB
            nullable=False,
        ),
        sa.Column(
            "allowed_mcp_servers",
            sa.JSON(),  # Changed from postgresql.JSONB
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "allowed_mcp_tools",
            sa.JSON(),  # Changed from postgresql.JSONB
            nullable=False,
            server_default="[]",
        ),
        sa.Column("is_preset", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by_user_id", sa.String(36), nullable=True
        ),  # Changed from UUID
        sa.Column(
            "organization_id", sa.String(36), nullable=False
        ),  # Changed from UUID
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_flow_organization_id_organization"),
        ),
        # TODO: Add ForeignKeyConstraint for model_configuration_id when ModelConfiguration model is created (Issue #60)
        # sa.ForeignKeyConstraint(["model_configuration_id"], ["model_configuration.id"], name=op.f("fk_flow_model_configuration_id_model_configuration")),
        # TODO: Add ForeignKeyConstraint for created_by_user_id when User model is finalized
        # sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], name=op.f("fk_flow_created_by_user_id_user")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("flow")
