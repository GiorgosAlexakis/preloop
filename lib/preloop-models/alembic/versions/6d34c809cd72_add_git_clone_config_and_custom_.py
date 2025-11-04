"""Add git_clone_config and custom_commands to flow

Revision ID: 6d34c809cd72
Revises: 5ce658ffa0e3
Create Date: 2025-11-03 02:23:05.351576

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6d34c809cd72"
down_revision: Union[str, None] = "5ce658ffa0e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add git_clone_config column to flow table
    op.add_column("flow", sa.Column("git_clone_config", sa.JSON(), nullable=True))

    # Add custom_commands column to flow table
    op.add_column("flow", sa.Column("custom_commands", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove custom_commands column
    op.drop_column("flow", "custom_commands")

    # Remove git_clone_config column
    op.drop_column("flow", "git_clone_config")
