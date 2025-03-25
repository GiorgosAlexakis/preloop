"""Database setup utilities."""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Import all models to ensure they're registered with Base.metadata
from ..models.base import Base
from .session import get_engine

# Import models individually to control the order

logger = logging.getLogger(__name__)


def setup_database(database_url: Optional[str] = None) -> None:
    """Set up the database schema.

    Creates all tables defined in the models and initializes the PGVector extension.
    """
    try:
        # Get the database engine
        engine = get_engine(database_url)

        # Only create the pgvector extension if using PostgreSQL
        if database_url and "postgresql" in database_url:
            try:
                with engine.connect() as conn:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    conn.commit()
                logger.info("PGVector extension created successfully")
            except Exception as e:
                logger.warning(f"Failed to create vector extension: {e}")

        # Create all tables
        Base.metadata.create_all(engine)
        logger.info("Database schema created successfully")
    except SQLAlchemyError as e:
        logger.error(f"Error setting up database: {e}")
        raise


def reset_database(database_url: Optional[str] = None) -> None:
    """Reset the database schema.

    Drops all tables and recreates them. Use with caution!
    """
    try:
        # Get the database engine
        engine = get_engine(database_url)

        # Drop all tables
        Base.metadata.drop_all(engine)
        logger.info("Database schema dropped successfully")

        # Recreate tables
        setup_database(database_url)
    except SQLAlchemyError as e:
        logger.error(f"Error resetting database: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_database()
    logger.info("Database setup complete")
