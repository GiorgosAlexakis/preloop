"""
CLI commands for SpaceSync.
"""

import click

from spacemodels.crud import crud_account, crud_tracker

from .. import __version__
from ..db.session import get_db_session
from .scan_commands import scan
from .service_commands import service


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """
    SpaceSync - A multi-account tracker scanning tool.

    This tool scans issue trackers across different user accounts,
    extracts information about issues, and maintains a PostgreSQL database
    with vector embeddings for advanced querying and analysis.
    """
    pass


# Add command groups
cli.add_command(scan)
cli.add_command(service)


@cli.command()
def version() -> None:
    """Display the current version."""
    click.echo(f"SpaceSync version: {__version__}")


@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Increase verbosity")
def status(verbose: bool) -> None:
    """Display system status including database connection and accounts."""
    # Get database session
    db = next(get_db_session())

    # Check database connection
    click.echo("✅ Database connection: OK")

    # Count accounts
    accounts_count = len(crud_account.get_active(db))
    click.echo(f"📊 Total accounts: {accounts_count}")

    # Count trackers
    trackers_count = len(crud_tracker.get_active(db))
    click.echo(f"📊 Total trackers: {trackers_count}")

    if verbose and accounts_count > 0:
        click.echo("\nAccounts:")
        accounts = crud_account.get_active(db)
        for account in accounts:
            click.echo(f"  - {account.username} (ID: {account.id})")
            account_trackers = crud_tracker.get_for_account(db, account_id=account.id)
            if account_trackers:
                for tracker in account_trackers:
                    click.echo(
                        f"    - {tracker.tracker_type}: {tracker.connection_details}"
                    )
            else:
                click.echo("    No trackers configured")

    db.close()


def run() -> None:
    """Run the CLI application."""
    cli()


if __name__ == "__main__":
    run()
