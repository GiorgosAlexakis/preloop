"""add_metadata_to_api_key

Revision ID: 6177910f8bd7
Revises: 42e000d008f4
Create Date: 2025-11-11 08:03:31.275608

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "6177910f8bd7"
down_revision: Union[str, None] = "42e000d008f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
