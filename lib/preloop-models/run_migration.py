#!/usr/bin/env python
"""
Script to run PostgreSQL migration that adds timestamp fields to Account and Tracker tables.

This script reads the SQL migration file and executes it against the database
specified in the DATABASE_URL environment variable.

Usage:
    python run_migration.py

Environment Variables:
    DATABASE_URL: Connection string for the database (required)
                  Format: postgresql://username:password@host:port/dbname
"""

import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_migration(database_url: str) -> bool:
    """Run the migration SQL file against the specified database.

    Args:
        database_url: Connection string for the database

    Returns:
        bool: True if successful, False otherwise
    """
    # Get the path to the migration file
    migration_file = Path(__file__).parent / "migration_add_timestamps.sql"

    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        return False

    # Read the SQL file
    with open(migration_file, "r") as f:
        sql = f.read()

    try:
        # Create an engine to connect to the database
        engine = create_engine(database_url)

        # Execute the SQL
        with engine.begin() as conn:
            logger.info("Executing migration...")
            conn.execute(text(sql))

        logger.info("Migration completed successfully!")
        return True

    except SQLAlchemyError as e:
        logger.error(f"Database error during migration: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during migration: {str(e)}")
        return False


def main():
    """Main entry point for the script."""
    # Get database URL from environment
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        logger.error("DATABASE_URL environment variable is not set")
        logger.info("Example: postgresql://username:password@host:port/dbname")
        sys.exit(1)

    # Check if the URL is for PostgreSQL
    if not database_url.startswith("postgresql"):
        logger.error(
            "This migration script is only compatible with PostgreSQL databases"
        )
        sys.exit(1)

    # Run the migration
    success = run_migration(database_url)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
