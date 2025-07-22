#!/usr/bin/env python
"""
Script to initialize the SpaceSync database tables.
This creates all the necessary tables if they don't exist.
"""

import sys
import os

import click
from dotenv import load_dotenv
from sqlalchemy import text

from spacemodels.db.session import get_engine, get_db_session
from spacemodels.db.setup import setup_database
from spacemodels.models import Base
from spacemodels.crud import crud_embedding_model
from spacemodels.crud import crud_llm_model

from spacemodels.db.vector_types import TRUNCATED_VECTOR_SIZE


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

        # Add the adaptive similarity search function to the database
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

        click.echo("Database tables created successfully!")
        db_session = next(get_db_session())

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
            click.echo("EMBEDDING_API_KEY not set, skipping embedding model creation.")

        # LLM model setup
        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        llm_model_name = os.getenv("LLM_MODEL_NAME", "o4-mini")
        llm_api_key = os.getenv("OPENAI_API_KEY")
        llm_api_url = os.getenv("LLM_API_URL", "https://api.openai.com/v1")
        llm_model_version = os.getenv("LLM_MODEL_VERSION", llm_model_name)

        if llm_api_key:
            if not crud_llm_model.default_model_exists(db_session):
                click.echo(f"Adding default LLM model '{llm_model_name}'...")
                crud_llm_model.create_with_account(
                    db=db_session,
                    name=llm_model_name,
                    provider_name=llm_provider,
                    api_key=llm_api_key,
                    api_url=llm_api_url,
                    model_name=llm_model_name,
                    model_version=llm_model_version,
                    is_default=True,
                    account_id=None,
                )
                click.echo(
                    f"Default LLM model '{llm_model_name}' created successfully."
                )
            else:
                click.echo("Default LLM model already exists, skipping.")
        else:
            click.echo("OPENAI_API_KEY not set, skipping LLM model creation.")

    except Exception as e:
        click.echo(f"ERROR: Failed to create tables: {str(e)}")
        sys.exit(1)

    click.echo("\nDatabase initialization complete.")


if __name__ == "__main__":
    init_db()
