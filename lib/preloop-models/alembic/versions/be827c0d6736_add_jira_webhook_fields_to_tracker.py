"""add_jira_webhook_fields_to_tracker

Revision ID: be827c0d6736
Revises: 017231752fde
Create Date: 2025-06-08 15:21:50.771256

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be827c0d6736"
down_revision: Union[str, None] = "017231752fde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tracker",
        sa.Column(
            "jira_webhook_id",
            sa.String(length=255),
            nullable=True,
            comment="Stored Jira Webhook ID",
        ),
    )
    op.add_column(
        "tracker",
        sa.Column(
            "jira_webhook_secret",
            sa.String(length=255),
            nullable=True,
            comment="Secret used to validate incoming Jira webhooks. Store encrypted if possible.",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tracker", "jira_webhook_secret")
    op.drop_column("tracker", "jira_webhook_id")
