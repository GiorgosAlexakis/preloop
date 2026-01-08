#!/usr/bin/env python
"""
Script to add an embedding model to the database.
This creates an active embedding model using a real embedding provider.

IMPORTANT: This script will delete all existing embedding models before adding a new one.
This prevents conflicts between models with different vector dimensions.
"""

import sys

import click
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import text

from preloop.models.crud import crud_embedding_model
from preloop.models.db.session import get_db_session


def clean_embedding_models(db: Session):
    """Delete all existing embedding models and their related embeddings."""
    # First delete all embedding records
    # Get all existing models to report them
    models = crud_embedding_model.get_multi(db)
    if not models:
        click.echo("No existing embedding models found to delete.")
        return

    for model in models:
        click.echo(f"Deleting embedding model: {model.name} (ID: {model.id})")

    # First delete all issueembedding records (due to foreign key constraints)
    db.execute(text("DELETE FROM issueembedding"))

    # Then delete all embedding models
    db.execute(text("DELETE FROM embeddingmodel"))

    # Commit the changes
    db.commit()
    click.echo(f"Deleted {len(models)} embedding models and their related embeddings.")


def add_embedding_model(
    provider: str,
    model_name: str,
    api_key: str,
    dimensions: int,
    version: str = None,
    is_active: bool = True,
):
    """
    Add an embedding model to the database.

    Args:
        provider: Provider name (e.g., 'openai', 'cohere', 'anthropic')
        model_name: Name to give this model in the database
        api_key: API key for the provider
        dimensions: Vector dimensions for this model
        version: Model version/name used by the provider
        is_active: Whether this model should be active
    """
    # Load environment variables
    load_dotenv()

    click.echo(f"Adding {provider} embedding model '{model_name}'...")

    try:
        # Get a database session
        db_session = next(get_db_session())

        # First, clean up existing models
        clean_embedding_models(db_session)

        # Create model data using a plain dictionary
        model_data = {
            "name": model_name,
            "provider": provider,
            "dimensions": dimensions,
            "version": version or model_name,
            "is_active": is_active,
            "meta_data": {"api_key": api_key, "model": version or model_name},
        }

        # Save to database
        db_model = crud_embedding_model.create(db_session, obj_in=model_data)
        click.echo(f"Embedding model created: {db_model.name} (ID: {db_model.id})")

        # Set as active if requested
        if is_active:
            click.echo(f"Model '{model_name}' is now active.")

    except Exception as e:
        click.echo(f"ERROR: Failed to create embedding model: {str(e)}")
        sys.exit(1)


@click.command()
@click.option(
    "--provider",
    type=click.Choice(["openai", "cohere", "anthropic", "huggingface"]),
    default="openai",
    help="Embedding provider",
)
@click.option(
    "--model-name",
    default="text-embedding-3-small",
    help="Name for this model in the database",
)
@click.option("--api-key", required=True, help="API key for the provider")
@click.option(
    "--dimensions",
    default=1536,
    help="Vector dimensions (1536 for OpenAI text-embedding-3-small)",
)
@click.option(
    "--version",
    default="text-embedding-3-small",
    help="Model version/name used by the provider",
)
@click.option(
    "--confirm/--no-confirm",
    default=True,
    help="Confirm before deleting existing models",
)
def main(provider, model_name, api_key, dimensions, version, confirm):
    """Add an embedding model to the database (deletes all existing models first)."""
    if confirm:
        click.echo(
            "\n⚠️  WARNING: This will delete ALL existing embedding models and their embeddings!"
        )
        if not click.confirm("Continue?"):
            click.echo("Operation cancelled.")
            sys.exit(0)

    add_embedding_model(
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        dimensions=dimensions,
        version=version,
        is_active=True,
    )

    click.echo("Done!")


if __name__ == "__main__":
    main()
