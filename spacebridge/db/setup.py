"""Database setup utilities for SpaceBridge."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from spacebridge.db.base import Base
from spacebridge.db.session import engine

# Import models to register them with Base.metadata
# This will be uncommented as models are implemented
# from spacebridge.models.organization import Organization
# from spacebridge.models.project import Project

logger = logging.getLogger(__name__)


def setup_database() -> None:
    """Set up the database schema.

    Creates all tables defined in the models and initializes the PGVector extension.
    """
    try:
        # Create the pgvector extension if it doesn't exist
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()

        # Create all tables
        Base.metadata.create_all(engine)
        logger.info("Database schema created successfully")
    except SQLAlchemyError as e:
        logger.error(f"Error setting up database: {e}")
        raise


def reset_database() -> None:
    """Reset the database schema.

    Drops all tables and recreates them. Use with caution!
    """
    try:
        # Drop all tables
        Base.metadata.drop_all(engine)
        logger.info("Database schema dropped successfully")

        # Recreate tables
        setup_database()
    except SQLAlchemyError as e:
        logger.error(f"Error resetting database: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_database()
    logger.info("Database setup complete")
