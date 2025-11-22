#!/usr/bin/env python
"""
Script to initialize the SpaceBridge database.
This creates all tables using Alembic migrations and sets up default models.
"""

import sys
import os
import subprocess
import logging

import click
from dotenv import load_dotenv
from sqlalchemy import text

from spacemodels.db.session import get_engine, get_db_session
from spacemodels.crud import crud_embedding_model
from spacemodels.crud import crud_ai_model

from spacemodels.db.vector_types import TRUNCATED_VECTOR_SIZE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--force", is_flag=True, help="Skip confirmation")
def init_db(force: bool):
    """
    Initialize the database by creating all tables using Alembic
    and setting up default embedding and AI models.
    """
    # Load environment variables
    load_dotenv()

    # Get database connection string from environment
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        click.echo("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)

    if not force:
        click.echo("This will create all database tables using Alembic migrations.")
        click.echo(f"Database: {db_url}")
        if not click.confirm("Continue?"):
            click.echo("Operation cancelled.")
            sys.exit(0)

    try:
        # Get the SpaceModels directory (parent of scripts directory)
        spacemodels_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Run alembic upgrade head
        click.echo("Running Alembic migrations to create database tables...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=spacemodels_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            click.echo(f"ERROR: Alembic migration failed: {result.stderr}")
            sys.exit(1)

        click.echo("Database tables created successfully via Alembic!")

        # Get engine for post-migration setup
        engine = get_engine()

        # Add the adaptive similarity search index to the database
        click.echo("Creating vector similarity search index...")
        with engine.connect() as connection:
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_issueembedding_vector_{vector_size} ON issueembedding
                    using hnsw ((subvector(embedding, 1, {vector_size})::vector({vector_size})) vector_cosine_ops)
                    with (m = 16, ef_construction = 40);
                    """.format(vector_size=TRUNCATED_VECTOR_SIZE)
                )
            )
            connection.commit()

        click.echo("Vector search index created successfully!")
        db_session = next(get_db_session())

        # Initialize system roles and permissions
        click.echo("Initializing system roles and permissions...")
        # Import here to avoid circular imports
        # Try to import from local scripts directory first (for CI)
        # Then fall back to parent scripts directory (for monorepo development)
        local_scripts_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, local_scripts_dir)
        try:
            from init_system_roles import initialize_system_roles
        except ImportError:
            # Fall back to parent scripts directory
            parent_scripts_dir = os.path.join(
                os.path.dirname(spacemodels_dir), "scripts"
            )
            sys.path.insert(0, parent_scripts_dir)
            from init_system_roles import initialize_system_roles

        if initialize_system_roles(db_session):
            click.echo("System roles and permissions initialized successfully!")
        else:
            click.echo("WARNING: Failed to initialize system roles and permissions")

        # Embedding model setup
        provider = os.getenv("EMBEDDING_PROVIDER", "openai")
        model_name = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
        api_key = os.getenv("OPENAI_API_KEY")
        dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        version = os.getenv("EMBEDDING_VERSION", model_name)

        if api_key:
            existing_model = crud_embedding_model.get_by_provider_version(
                db_session, provider=provider, version=version
            )
            if existing_model:
                click.echo(
                    f"Embedding model '{model_name}' already exists (ID: {existing_model.id}), skipping."
                )
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
            click.echo("OPENAI_API_KEY not set, skipping embedding model creation.")

        # AI model setup
        ai_provider = os.getenv("AI_PROVIDER", "openai")
        ai_model_name = os.getenv("AI_MODEL_NAME", "o4-mini")
        ai_model_api_key = os.getenv("OPENAI_API_KEY")
        ai_model_api_url = os.getenv("AI_API_URL", "https://api.openai.com/v1")
        ai_model_version = os.getenv("AI_MODEL_VERSION", ai_model_name)

        if ai_model_api_key:
            if not crud_ai_model.default_model_exists(db_session):
                click.echo(f"Adding default AI model '{ai_model_name}'...")
                ai_model_data = {
                    "name": ai_model_name,
                    "provider_name": ai_provider,
                    "api_key": ai_model_api_key,
                    "api_endpoint": ai_model_api_url,
                    "model_identifier": ai_model_version,
                    "is_default": True,
                }
                crud_ai_model.create_with_account(
                    db=db_session,
                    obj_in=ai_model_data,
                    account_id=None,
                )
                click.echo(f"Default AI model '{ai_model_name}' created successfully.")
            else:
                click.echo("Default AI model already exists, skipping.")
        else:
            click.echo("OPENAI_API_KEY not set, skipping AI model creation.")

    except Exception as e:
        click.echo(f"ERROR: Failed to initialize database: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    click.echo("\nDatabase initialization complete!")


if __name__ == "__main__":
    init_db()
