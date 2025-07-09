"""
Scan commands for SpaceSync CLI.
"""

import click


from spacemodels.crud import crud_account, crud_tracker
from spacemodels.db.session import get_db_session

# Import scanner functions
from ..scanner import scan_account, scan_all_accounts # Import scan_all_accounts
from ..scanner import scan_tracker as scan_tracker_func

# Import service components for the 'scan all' (now service start) command
from ..utils import safe_exit


@click.group()
def scan():
    """
    Commands for scanning issue trackers or starting the continuous sync service.
    """
    pass


@scan.command(name="all")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--force-update",
    "-f",
    is_flag=True,
    help="Force update of all embeddings even if content hasn't changed",
)
def scan_all_cmd(verbose: bool, force_update: bool):
    """
    Perform a ONE-OFF scan for all accounts and trackers.
    Does NOT start the continuous service.
    """
    # Get database session
    db = next(get_db_session())

    click.echo("Scanning all accounts and trackers...")

    # Scan all accounts (pass force_update)
    stats = scan_all_accounts(db=db, verbose=verbose, force_update=force_update)

    # Print summary
    click.echo("\n=== Scan Complete ===")
    click.echo(f"Accounts scanned: {stats['accounts_scanned']}")
    click.echo(f"Accounts with errors: {stats['accounts_with_errors']}")
    click.echo(f"Total trackers scanned: {stats['total_trackers_scanned']}")
    click.echo(f"Total trackers with errors: {stats['total_trackers_with_errors']}")
    click.echo(f"Total organizations: {stats['total_organizations']}")
    click.echo(f"Total projects: {stats['total_projects']}")
    click.echo(f"Total issues: {stats['total_issues']}")
    click.echo(f"Total embeddings updated: {stats['total_embeddings_updated']}")
    click.echo(f"Total duration: {stats['total_duration_seconds']:.2f} seconds")

    db.close()


@scan.command(name="account")
@click.argument("account_id", type=str)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--force-update",
    "-f",
    is_flag=True,
    help="Force update of all embeddings even if content hasn't changed",
)
def scan_account_cmd(account_id: str, verbose: bool, force_update: bool):
    """
    Perform a ONE-OFF scan for a specific account and all its trackers.
    Does NOT start the continuous service.

    ACCOUNT_ID: The ID of the account to scan (UUID string).
    """
    # Get database session
    db = next(get_db_session())

    # Check if account exists
    account = crud_account.get(db, id=account_id)
    if not account:
        safe_exit(1, f"Account with ID {account_id} not found")

    click.echo(f"Scanning account: {account.username} (ID: {account.id})...")

    # Scan the account (pass force_update)
    stats = scan_account(db=db, account_id=account_id, verbose=verbose, force_update=force_update)

    # Print summary
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
@click.option(
    "--force-update",
    "-f",
    is_flag=True,
    help="Force update of all embeddings even if content hasn't changed",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def scan_tracker_cmd(tracker_id: str, force_update: bool, verbose: bool):
    """
    Perform a ONE-OFF scan for a specific tracker.
    Does NOT start the continuous service.

    TRACKER_ID: The ID of the tracker to scan (UUID string).
    """
    # Get database session
    db = next(get_db_session())

    # Check if tracker exists
    tracker = crud_tracker.get(db, id=tracker_id)
    if not tracker:
        safe_exit(1, f"Tracker with ID {tracker_id} not found")

    click.echo(f"Scanning tracker: ID {tracker.id} ({tracker.tracker_type})...")

    # Scan the tracker (pass force_update)
    stats = scan_tracker_func(
        db=db, tracker=tracker, force_update=force_update, verbose=verbose
    )

    # Print summary
    click.echo("\n=== Scan Complete ===")
    click.echo(f"Organizations scanned: {stats['organizations']}")
    click.echo(f"Projects: {stats['projects']}")
    click.echo(f"Issues: {stats['issues']}")
    click.echo(f"Embeddings updated: {stats['embeddings_updated']}")
    click.echo(f"Errors: {stats['errors']}")

    db.close()
