#!/usr/bin/env python
"""
Script to seed the database with a test user and API key.
"""

import os
import click
from dotenv import load_dotenv

from spacemodels.crud import crud_account, crud_api_key
from spacemodels.db.session import get_db_session
from spacemodels.db.setup import setup_database
from spacebridge.api.auth.jwt import get_password_hash
from spacebridge.schemas.auth import ApiKeyCreate


@click.command()
@click.option(
    "--email", envvar="TEST_USER_EMAIL", required=True, help="Email for the test user."
)
@click.option(
    "--password",
    envvar="TEST_USER_PASSWORD",
    required=True,
    help="Password for the test user.",
)
@click.option(
    "--api-key",
    envvar="TEST_USER_API_KEY",
    required=True,
    help="API key for the test user.",
)
def seed_test_user(email: str, password: str, api_key: str):
    """
    Creates a test user and an API key if they don't already exist.
    """
    load_dotenv()
    setup_database(os.getenv("DATABASE_URL"))
    db_session = next(get_db_session())

    click.echo(f"Checking for test user with email: {email}")
    user = crud_account.get_by_email(db_session, email=email)

    if user:
        click.echo("Test user already exists.")
    else:
        click.echo("Creating new test user...")
        user_in = {
            "email": email,
            "hashed_password": get_password_hash(password),
            "username": email.split("@")[0],
            "full_name": "Test User",
            "is_active": True,
            "email_verified": True,
        }
        user = crud_account.create(db_session, obj_in=user_in)
        click.echo("Test user created successfully.")

    click.echo("Checking for test user API key...")
    # A simple check to see if any key exists for the user.
    # A more robust implementation might check for the specific key.
    existing_keys = crud_api_key.get_active_by_user(db_session, username=user.username)
    if any(k.key == api_key for k in existing_keys):
        click.echo("API key already exists for the test user.")
    else:
        click.echo("Creating API key for the test user...")
        api_key_in = ApiKeyCreate(name="Test API Key", key=api_key, owner_id=user.id)
        crud_api_key.create_with_owner(
            db_session, obj_in=api_key_in, owner_username=user.username
        )
        click.echo("API key created successfully.")

    click.echo("\nDatabase seeding complete.")


if __name__ == "__main__":
    seed_test_user()
