"""add_model_configurations_table

Revision ID: 4a3fe57fc6ba
Revises: 52502e04d6ef
Create Date: 2025-06-10 19:39:21.157042

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4a3fe57fc6ba"
down_revision: Union[str, None] = "52502e04d6ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "model_configurations",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("model_identifier", sa.String(), nullable=False),
        sa.Column("api_endpoint", sa.String(), nullable=True),
        sa.Column("api_key_encrypted", sa.String(), nullable=True),
        sa.Column(
            "encryption_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "model_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_shareable", sa.Boolean(), nullable=False, default=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        op.f("ix_model_configurations_name"),
        "model_configurations",
        ["name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_configurations_model_identifier"),
        "model_configurations",
        ["model_identifier"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_configurations_owner_user_id"),
        "model_configurations",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_configurations_organization_id"),
        "model_configurations",
        ["organization_id"],
        unique=False,
    )
    # Add ForeignKey constraints if 'users' and 'organizations' tables exist and are managed by Alembic
    # Assuming 'users' table exists for owner_user_id
    op.create_foreign_key(
        "fk_model_configurations_owner_user_id_users",
        "model_configurations",
        "users",
        ["owner_user_id"],
        ["id"],
    )
    # Assuming 'organizations' table exists for organization_id
    op.create_foreign_key(
        "fk_model_configurations_organization_id_organizations",
        "model_configurations",
        "organizations",
        ["organization_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_model_configurations_organization_id_organizations",
        "model_configurations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_model_configurations_owner_user_id_users",
        "model_configurations",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_model_configurations_organization_id"),
        table_name="model_configurations",
    )
    op.drop_index(
        op.f("ix_model_configurations_owner_user_id"), table_name="model_configurations"
    )
    op.drop_index(
        op.f("ix_model_configurations_model_identifier"),
        table_name="model_configurations",
    )
    op.drop_index(
        op.f("ix_model_configurations_name"), table_name="model_configurations"
    )
    op.drop_table("model_configurations")
