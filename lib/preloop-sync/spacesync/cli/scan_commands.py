"""
Scan commands for SpaceSync CLI.
"""

from typing import Optional

import click

from spacemodels.crud import crud_account, crud_tracker

from ..config import logger
from spacemodels.db.session import get_db_session
from ..scanner import scan_account, scan_all_accounts
from ..scanner import scan_tracker as scan_tracker_func
from ..utils import safe_exit


@click.group()
def scan():
    """
    Commands for scanning issue trackers.
    """
    pass


@scan.command(name="all")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def scan_all(verbose: bool):
    """
    Scan all accounts, trackers, projects, and issues.

    This will scan all active accounts in the database, retrieve all their trackers,
    and scan all projects and issues from those trackers. For each issue, it will
    extract information and store it in the database, and generate a vector embedding
    if the issue content has changed.
    """
    # Get database session
    db = next(get_db_session())

    click.echo("Starting scan of all accounts...")

    # Scan all accounts
    stats = scan_all_accounts(db, verbose)

    if not verbose:
        # If not verbose mode, print a summary
        click.echo("\n=== Scan Complete ===")
        click.echo(f"Accounts scanned: {stats['accounts_scanned']}")
        click.echo(f"Accounts with errors: {stats['accounts_with_errors']}")
        click.echo(f"Trackers scanned: {stats['trackers_scanned']}")
        click.echo(f"Trackers with errors: {stats['trackers_with_errors']}")
        click.echo(f"Total organizations: {stats['organizations']}")
        click.echo(f"Total projects: {stats['projects']}")
        click.echo(f"Total issues: {stats['issues']}")
        click.echo(f"Total embeddings updated: {stats['embeddings_updated']}")
        click.echo(f"Total duration: {stats['duration_seconds']:.2f} seconds")

    db.close()


@scan.command(name="account")
@click.argument("account_id", type=str)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def scan_account_cmd(account_id: str, verbose: bool):
    """
    Scan a specific account and all its trackers.

    ACCOUNT_ID: The ID of the account to scan (UUID string).
    """
    # Get database session
    db = next(get_db_session())

    # Check if account exists
    account = crud_account.get(db, id=account_id)
    if not account:
        safe_exit(1, f"Account with ID {account_id} not found")

    click.echo(f"Scanning account: {account.username} (ID: {account.id})...")

    # Scan the account
    stats = scan_account(db, account_id, verbose)

    if not verbose:
        # If not verbose mode, print a summary
        click.echo("\n=== Scan Complete ===")
        click.echo(f"Trackers scanned: {stats['trackers_scanned']}")
        click.echo(f"Trackers with errors: {stats['trackers_with_errors']}")
        click.echo(f"Total organizations: {stats['organizations']}")
        click.echo(f"Total projects: {stats['projects']}")
        click.echo(f"Total issues: {stats['issues']}")
        click.echo(f"Total embeddings updated: {stats['embeddings_updated']}")
        click.echo(f"Total duration: {stats['duration_seconds']:.2f} seconds")

    db.close()


@scan.command(name="tracker")
@click.argument("tracker_id", type=str)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def scan_tracker_cmd(tracker_id: str, verbose: bool):
    """
    Scan a specific tracker.

    TRACKER_ID: The ID of the tracker to scan (UUID string).
    """
    # Get database session
    db = next(get_db_session())

    # Check if tracker exists
    tracker = crud_tracker.get(db, id=tracker_id)
    if not tracker:
        safe_exit(1, f"Tracker with ID {tracker_id} not found")

    click.echo(f"Scanning tracker: ID {tracker.id} ({tracker.tracker_type})...")

    # Scan the tracker
    stats = scan_tracker_func(db, tracker, verbose)

    if not verbose:
        # If not verbose mode, print a summary
        click.echo("\n=== Scan Complete ===")
        click.echo(f"Organizations: {stats['organizations']}")
        click.echo(f"Projects: {stats['projects']}")
        click.echo(f"Issues: {stats['issues']}")
        click.echo(f"Embeddings updated: {stats['embeddings_updated']}")
        click.echo(f"Errors: {stats['errors']}")
        click.echo(f"Duration: {stats['duration_seconds']:.2f} seconds")

    db.close()
