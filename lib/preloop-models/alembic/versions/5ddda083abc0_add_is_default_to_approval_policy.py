"""add_is_default_to_approval_policy

Revision ID: 5ddda083abc0
Revises: 59d885f87415
Create Date: 2025-10-28 22:45:14.699781

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5ddda083abc0"
down_revision: Union[str, None] = "59d885f87415"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_default column to approval_policy table
    op.add_column(
        "approval_policy",
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether this is the default policy for the account",
        ),
    )
    # Create index on is_default for faster lookups
    op.create_index("ix_approval_policy_is_default", "approval_policy", ["is_default"])

    # For each account that has policies, mark the first one as default
    # This is done via SQL to handle existing data
    op.execute("""
        UPDATE approval_policy
        SET is_default = true
        WHERE id IN (
            SELECT DISTINCT ON (account_id) id
            FROM approval_policy
            ORDER BY account_id, created_at ASC
        )
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index first
    op.drop_index("ix_approval_policy_is_default", table_name="approval_policy")
    # Drop the column
    op.drop_column("approval_policy", "is_default")
