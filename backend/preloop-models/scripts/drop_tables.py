#!/usr/bin/env python
"""
Script to drop all tables in the SpaceSync database.
Use with caution - this will delete all data!
"""

import os
import sys

import click
import psycopg2
from dotenv import load_dotenv


@click.command()
@click.option("--force", is_flag=True, help="Skip confirmation and force deletion")
def drop_tables(force: bool):
    """
    Drop all tables in the SpaceSync database.
    """
    # Load environment variables
    load_dotenv()

    # Get database connection string from environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        click.echo("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)

    # Connect to database
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
    except Exception as e:
        click.echo(f"ERROR: Could not connect to database: {str(e)}")
        sys.exit(1)

    # Get list of tables
    try:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        )
        tables = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        click.echo(f"ERROR: Could not get table list: {str(e)}")
        conn.close()
        sys.exit(1)

    if not tables:
        click.echo("No tables found in database.")
        conn.close()
        return

    if not force:
        click.echo("WARNING: This will delete ALL data in the database.")
        click.echo("Tables to be dropped:")
        for table in tables:
            click.echo(f"  - {table}")

        # Ask for confirmation
        if not click.confirm("Are you sure you want to continue?"):
            click.echo("Operation cancelled.")
            conn.close()
            sys.exit(0)

    click.echo("Dropping all tables...")

    # Drop all tables (disable foreign key constraints first)
    try:
        cursor.execute("SET session_replication_role = 'replica';")
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
        cursor.execute("SET session_replication_role = 'origin';")
        click.echo("All tables have been dropped successfully.")
    except Exception as e:
        click.echo(f"ERROR: Could not drop tables: {str(e)}")
    finally:
        conn.close()


if __name__ == "__main__":
    drop_tables()
