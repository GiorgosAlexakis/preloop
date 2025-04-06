#!/usr/bin/env python
"""
Script to run PostgreSQL migrations from SQL files.

This script reads a SQL migration file and executes it against the database
specified in the DATABASE_URL environment variable.

Example:
    python run_migration.py --file migration_embedding_to_vector.sql

Environment Variables:
    DATABASE_URL: Connection string for the database (required)
                  Format: postgresql://username:password@host:port/dbname
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_migration(database_url: str, migration_file_path: str) -> bool:
    """Run the migration SQL file against the specified database.

    Args:
        database_url: Connection string for the database
        migration_file_path: Path to the SQL migration file

    Returns:
        bool: True if successful, False otherwise
    """
    # Get the path to the migration file
    migration_file = Path(migration_file_path)

    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        return False

    # Read the SQL file
    with open(migration_file, "r") as f:
        sql = f.read()

    try:
        # Create engine
        engine = create_engine(database_url)

        # Execute SQL
        with engine.connect() as conn:
            logger.info(f"Executing migration from {migration_file}")
            conn.execute(text(sql))
            conn.commit()

        logger.info("Migration completed successfully")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Error executing migration: {e}")
        return False


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a SQL migration file against a PostgreSQL database.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--file", "-f",
        required=True,
        help="Path to the SQL migration file to execute",
        dest="migration_file_path"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the script."""
    # Parse command line arguments
    args = parse_args()
    
    # Check if the DATABASE_URL environment variable is set
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error(
            "DATABASE_URL environment variable not set. "
            "Please set it to the connection string for the database."
        )
        sys.exit(1)

    # Run the migration
    success = run_migration(database_url, args.migration_file_path)
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
