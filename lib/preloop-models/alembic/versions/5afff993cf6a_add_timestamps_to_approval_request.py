"""add_timestamps_to_approval_request

Revision ID: 5afff993cf6a
Revises: 196418f4da7e
Create Date: 2025-10-17 05:02:07.643748

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5afff993cf6a"
down_revision: Union[str, None] = "196418f4da7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add created_at column with server default
    op.add_column(
        "approval_request",
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
    )

    # Add updated_at column with server default
    op.add_column(
        "approval_request",
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the timestamp columns
    op.drop_column("approval_request", "updated_at")
    op.drop_column("approval_request", "created_at")
