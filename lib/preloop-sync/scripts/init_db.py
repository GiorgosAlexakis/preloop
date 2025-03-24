#!/usr/bin/env python
"""
Script to initialize the SpaceSync database tables.
This creates all the necessary tables if they don't exist.
"""

import os
import sys

import click
from dotenv import load_dotenv

from spacemodels.db.session import get_engine
from spacemodels.models import Account, Base, Issue, Organization, Project, Tracker


@click.command()
@click.option("--force", is_flag=True, help="Skip confirmation")
def init_db(force: bool):
    """
    Initialize the database by creating all tables.
    """
    # Load environment variables
    load_dotenv()

    if not force:
        click.echo("This will create all necessary tables in the database.")
        if not click.confirm("Continue?"):
            click.echo("Operation cancelled.")
            sys.exit(0)

    click.echo("Creating database tables...")

    # Import all models to ensure they're registered with SQLAlchemy
    try:
        # Get engine and create tables
        engine = get_engine()
        Base.metadata.create_all(engine)
        click.echo("Database tables created successfully!")
    except Exception as e:
        click.echo(f"ERROR: Failed to create tables: {str(e)}")
        sys.exit(1)

    click.echo("\nDatabase initialization complete.")


if __name__ == "__main__":
    init_db()
