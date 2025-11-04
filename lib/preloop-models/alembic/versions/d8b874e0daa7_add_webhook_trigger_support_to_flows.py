"""add_webhook_trigger_support_to_flows

Revision ID: d8b874e0daa7
Revises: 6d34c809cd72
Create Date: 2025-11-04 14:16:31.182659

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8b874e0daa7"
down_revision: Union[str, None] = "6d34c809cd72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Make trigger_event_source and trigger_event_type nullable for webhook triggers
    op.alter_column(
        "flow", "trigger_event_source", existing_type=sa.String(), nullable=True
    )
    op.alter_column(
        "flow", "trigger_event_type", existing_type=sa.String(), nullable=True
    )

    # Add webhook_config column
    op.add_column("flow", sa.Column("webhook_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove webhook_config column
    op.drop_column("flow", "webhook_config")

    # Make trigger_event_source and trigger_event_type non-nullable again
    op.alter_column(
        "flow", "trigger_event_source", existing_type=sa.String(), nullable=False
    )
    op.alter_column(
        "flow", "trigger_event_type", existing_type=sa.String(), nullable=False
    )
