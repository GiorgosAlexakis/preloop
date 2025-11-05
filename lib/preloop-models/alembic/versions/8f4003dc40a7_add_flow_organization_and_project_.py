"""add_flow_organization_and_project_scoping

Revision ID: 8f4003dc40a7
Revises: d8b874e0daa7
Create Date: 2025-11-04 22:15:04.353369

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f4003dc40a7"
down_revision: Union[str, None] = "d8b874e0daa7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add trigger_organization_id and trigger_project_id columns to flow table
    op.add_column(
        "flow", sa.Column("trigger_organization_id", sa.String(), nullable=True)
    )
    op.add_column("flow", sa.Column("trigger_project_id", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the columns
    op.drop_column("flow", "trigger_project_id")
    op.drop_column("flow", "trigger_organization_id")
