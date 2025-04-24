#!/usr/bin/env python
"""
Script to set the email_verified flag to True for all Account records in the database.
"""

import sys
import click
from sqlalchemy.orm import Session
from spacemodels.models.account import Account  # Corrected import path if needed
from spacemodels.db.session import get_db_session  # Corrected import path if needed

# Ensure the project root is in the Python path if running script directly
# import os
# project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# if project_root not in sys.path:
#     sys.path.insert(0, project_root)


@click.command()
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt.",
)
def main(yes: bool):
    """Sets the email_verified flag to True for all accounts."""

    if not yes:
        click.echo(
            "\n⚠️  WARNING: This will set email_verified=True for ALL accounts in the database."
        )
        if not click.confirm("Do you want to proceed?"):
            click.echo("Operation cancelled.")
            sys.exit(0)

    db_session: Session | None = None
    try:
        click.echo("Connecting to the database...")
        # Make sure environment variables (like DATABASE_URL) are loaded
        # You might need from dotenv import load_dotenv; load_dotenv() here
        # depending on how your environment is set up.
        db_session = next(get_db_session())

        click.echo("Fetching all accounts...")
        accounts = db_session.query(Account).all()

        if not accounts:
            click.echo("No accounts found in the database.")
            sys.exit(0)

        click.echo(f"Found {len(accounts)} accounts. Updating email_verified flag...")
        updated_count = 0
        for account in accounts:
            if not account.email_verified:
                account.email_verified = True
                updated_count += 1

        if updated_count > 0:
            click.echo(f"Updating {updated_count} accounts...")
            db_session.commit()
            click.echo(f"Successfully updated {updated_count} accounts.")
        else:
            click.echo("All accounts already have email_verified set to True.")

    except Exception as e:
        if db_session:
            db_session.rollback()  # Rollback in case of error during commit
        click.echo(f"ERROR: An error occurred: {str(e)}", err=True)
        sys.exit(1)
    finally:
        if db_session:
            db_session.close()
            click.echo("Database connection closed.")

    click.echo("Done!")


if __name__ == "__main__":
    main()
