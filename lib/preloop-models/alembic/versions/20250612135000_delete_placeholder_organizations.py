"""Delete placeholder organizations with specific naming patterns

Revision ID: 20250612135000_delete_placeholder_organizations
Revises: dbd4003e5eef
Create Date: 2025-06-12 13:50:00.000000

"""
import logging
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250612135000"
down_revision = "dbd4003e5eef"  # Fixed: was pointing to non-existent 4a3fe57fc6ba
branch_labels = None
depends_on = None

# Configure logging
logger = logging.getLogger(f"alembic.revision.{revision}")
# Basic config in case not configured by Alembic runner
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def upgrade():
    """
    Deletes Organization records that:
    1. Have a name ending with " Organization".
    2. Have an identifier starting with the username of the associated account.
    """
    bind = op.get_bind()
    meta = sa.MetaData()

    # Define table structures for the query and delete operation
    # These definitions are for constructing the SQL and do not alter the DB schema here.
    organization_table = sa.Table(
        "organization",
        meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String),
        sa.Column("identifier", sa.String),
        sa.Column("tracker_id", sa.Integer, sa.ForeignKey("tracker.id")),
    )

    tracker_table = sa.Table(
        "tracker",
        meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("account.id")),
    )

    account_table = sa.Table(
        "account",
        meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String),
    )

    # Construct the query to find organizations to delete
    query = (
        sa.select(
            organization_table.c.id,
            organization_table.c.name,
            organization_table.c.identifier,
        )
        .select_from(
            organization_table.join(
                tracker_table, organization_table.c.tracker_id == tracker_table.c.id
            ).join(account_table, tracker_table.c.account_id == account_table.c.id)
        )
        .where(organization_table.c.name.endswith(" Organization"))
        .where(organization_table.c.identifier.startswith(account_table.c.username))
    )

    connection = op.get_bind()
    results = connection.execute(query).fetchall()

    ids_to_delete = []
    if results:
        logger.info(f"Found {len(results)} organization(s) matching deletion criteria:")
        for org_id, org_name, org_identifier in results:
            logger.info(
                f"  - ID: {org_id}, Name: '{org_name}', Identifier: '{org_identifier}' (to be deleted)"
            )
            ids_to_delete.append(org_id)

        if ids_to_delete:
            # Construct and execute the delete statement
            delete_stmt = organization_table.delete().where(
                organization_table.c.id.in_(ids_to_delete)
            )
            op.execute(delete_stmt)
            logger.info(f"Successfully deleted {len(ids_to_delete)} organization(s).")
    else:
        logger.info("No organizations found matching the specified deletion criteria.")


def downgrade():
    """
    Downgrade for this migration is a no-op.
    Re-creating these specific placeholder records is not a desirable rollback state.
    """
    pass
    logger.info(f"Downgrade for revision {revision} is a no-op as per design.")
