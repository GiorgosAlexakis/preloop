#!/usr/bin/env python
"""
Script to initialize the SpaceSync database tables.
This creates all the necessary tables if they don't exist.
"""

import sys
import os

import click
from dotenv import load_dotenv

from spacemodels.db.session import get_engine, get_db_session
from spacemodels.db.setup import setup_database
from spacemodels.models import Base
from spacemodels.crud import crud_embedding_model


@click.command()
@click.option("--force", is_flag=True, help="Skip confirmation")
def init_db(force: bool):
    """
    Initialize the database by creating all tables.
    """
    # Load environment variables
    load_dotenv()
    setup_database(os.getenv("DATABASE_URL"))
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
        # Embedding model setup
        provider = os.getenv("EMBEDDING_PROVIDER", "openai")
        model_name = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
        api_key = os.getenv("OPENAI_API_KEY")
        dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        version = os.getenv("EMBEDDING_VERSION", model_name)
        if api_key:
            db_session = next(get_db_session())
            existing_model = crud_embedding_model.get_by_provider_version(
                db_session, provider=provider, version=version
            )
            if existing_model:
                click.echo(f"Embedding model '{model_name}' already exists (ID: {existing_model.id}), skipping.")
            else:
                click.echo(f"Adding embedding model '{model_name}'...")
                model_data = {
                    "name": model_name,
                    "provider": provider,
                    "dimensions": dimensions,
                    "version": version,
                    "is_active": True,
                    "meta_data": {"api_key": api_key, "model": version},
                }
                crud_embedding_model.create(db_session, obj_in=model_data)
                click.echo(f"Embedding model '{model_name}' created successfully.")
        else:
            click.echo("EMBEDDING_API_KEY not set, skipping embedding model creation.")
    except Exception as e:
        click.echo(f"ERROR: Failed to create tables: {str(e)}")
        sys.exit(1)

    click.echo("\nDatabase initialization complete.")


if __name__ == "__main__":
    init_db()
