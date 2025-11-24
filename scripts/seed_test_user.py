#!/usr/bin/env python
"""
Script to seed the database with a test user and API key.
"""

import os
import click
from dotenv import load_dotenv

from preloop_models.crud import crud_account, crud_api_key, crud_user
from preloop_models.db.session import get_db_session
from preloop_models.db.setup import setup_database
from preloop_ai.api.auth.jwt import get_password_hash
from preloop_ai.schemas.auth import ApiKeyCreate


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
    user = crud_user.get_by_email(db_session, email=email)

    if user:
        click.echo("Test user already exists.")
    else:
        click.echo("Creating new test user...")
        # First create an account (organization)
        account_in = {
            "organization_name": "Test Organization",
            "is_active": True,
            "email_verified": True,
        }
        account = crud_account.create(db_session, obj_in=account_in)
        db_session.flush()  # Ensure account.id is available

        # Then create a user with authentication credentials
        user_in = {
            "account_id": str(account.id),
            "email": email,
            "username": os.getenv("TEST_USER_USERNAME", "test_user"),
            "full_name": "Test User",
            "hashed_password": get_password_hash(password),
            "email_verified": True,
            "is_active": True,
            "user_source": "local",
        }
        user = crud_user.create(db_session, obj_in=user_in)
        db_session.flush()  # Ensure user.id is available

        # Update account to set primary_user_id
        account.primary_user_id = user.id
        db_session.commit()

        click.echo("Test user and account created successfully.")

    click.echo("Checking for test user API key...")
    # A simple check to see if any key exists for the user.
    # A more robust implementation might check for the specific key.
    existing_keys = crud_api_key.get_active_by_user(db_session, username=user.username)
    if any(k.key == api_key for k in existing_keys):
        click.echo("API key already exists for the test user.")
    else:
        click.echo("Creating API key for the test user...")
        api_key_in = ApiKeyCreate(name="Test API Key")
        crud_api_key.create_with_owner(
            db_session,
            obj_in=api_key_in,
            owner_username=user.username,
            key_value=api_key,
        )
        click.echo("API key created successfully.")

    click.echo("\nDatabase seeding complete.")


if __name__ == "__main__":
    seed_test_user()
