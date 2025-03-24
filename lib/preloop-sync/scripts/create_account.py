#!/usr/bin/env python
"""
Script to create an account in the SpaceSync database.
Uses values from .env file or from command line arguments.
"""

import os
import secrets
import sys
from typing import Optional

import click
from dotenv import load_dotenv

from spacemodels.crud import crud_account, crud_tracker
from spacemodels.db.session import get_db_session


def generate_password_hash(password: str) -> str:
    """Simple hashing for demo purposes."""
    import hashlib

    return hashlib.sha256(password.encode()).hexdigest()


@click.command()
@click.option("--username", default=None, help="Username for the account")
@click.option("--email", default=None, help="Email for the account")
@click.option("--full-name", default=None, help="Full name for the account")
@click.option("--password", default=None, help="Password for the account")
@click.option("--is-superuser", is_flag=True, help="Make the account a superuser")
@click.option("--force", is_flag=True, help="Skip confirmation")
def create_account(
    username: Optional[str],
    email: Optional[str],
    full_name: Optional[str],
    password: Optional[str],
    is_superuser: bool,
    force: bool,
):
    """
    Create a new account in the database.
    """
    # Load environment variables
    load_dotenv()

    # Use environment variables if parameters not provided
    username = username or os.getenv("ACCOUNT_USERNAME", "admin")
    email = email or os.getenv("ACCOUNT_EMAIL", "admin@example.com")
    full_name = full_name or os.getenv("ACCOUNT_FULL_NAME", "Administrator")
    password = password or os.getenv("ACCOUNT_PASSWORD") or secrets.token_urlsafe(12)

    # Show account details
    click.echo("Creating account with the following details:")
    click.echo(f"  Username: {username}")
    click.echo(f"  Email: {email}")
    click.echo(f"  Full Name: {full_name}")
    click.echo(f"  Password: {'*' * 8} (hidden)")
    click.echo(f"  Superuser: {is_superuser}")

    if not force:
        if not click.confirm("Continue?"):
            click.echo("Operation cancelled.")
            sys.exit(0)

    # Get database session
    db = next(get_db_session())

    # Check if account with this username or email already exists
    existing_by_username = crud_account.get_by_username(db, username=username)
    existing_by_email = crud_account.get_by_email(db, email=email)

    if existing_by_username:
        click.echo(f"An account with username '{username}' already exists.")
        db.close()
        sys.exit(1)

    if existing_by_email:
        click.echo(f"An account with email '{email}' already exists.")
        db.close()
        sys.exit(1)

    # Create account
    account_data = {
        "username": username,
        "email": email,
        "full_name": full_name,
        "hashed_password": generate_password_hash(password),
        "is_superuser": is_superuser,
    }

    account = crud_account.create(db, obj_in=account_data)

    click.echo(f"Account created successfully with ID: {account.id}")

    # Also create a tracker if TRACKER_TOKEN and TRACKER_URL are provided
    tracker_token = os.getenv("TRACKER_TOKEN")
    tracker_url = os.getenv("TRACKER_URL")

    # Determine tracker type from URL
    tracker_type = "github"
    if "gitlab" in tracker_url.lower():
        tracker_type = "gitlab"
    elif "jira" in tracker_url.lower():
        tracker_type = "jira"
    elif "linear" in tracker_url.lower():
        tracker_type = "linear"

    tracker_data = {
        "name": f"{tracker_type.capitalize()} Tracker",
        "tracker_type": tracker_type,
        "account_id": account.id,
        "api_key": tracker_token,
        "connection_details": {"gitlab_url": tracker_url},
    }

    tracker = crud_tracker.create(db, obj_in=tracker_data)
    click.echo(f"Tracker created successfully with ID: {tracker.id}")

    db.close()


if __name__ == "__main__":
    create_account()
