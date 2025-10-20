"""add_approval_token_to_approval_request

Revision ID: 478fc3894fb0
Revises: 5afff993cf6a
Create Date: 2025-10-17 05:16:56.121948

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "478fc3894fb0"
down_revision: Union[str, None] = "5afff993cf6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add approval_token column (nullable first)
    op.add_column(
        "approval_request", sa.Column("approval_token", sa.String(64), nullable=True)
    )

    # Generate unique tokens for existing rows using MD5 of ID + random
    op.execute("""
        UPDATE approval_request
        SET approval_token = replace(md5(id::text || random()::text || now()::text), '-', '')
        WHERE approval_token IS NULL;
    """)

    # Make column non-nullable
    op.alter_column("approval_request", "approval_token", nullable=False)

    # Create unique index
    op.create_index(
        "ix_approval_request_approval_token",
        "approval_request",
        ["approval_token"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_approval_request_approval_token", table_name="approval_request")
    op.drop_column("approval_request", "approval_token")
