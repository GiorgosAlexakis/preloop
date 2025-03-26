"""
Core scanning functionality for SpaceSync.
"""

import datetime
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from spacemodels.crud import (
    crud_account,
    crud_issue,
    crud_issue_embedding,
    crud_organization,
    crud_project,
    crud_tracker,
)
from spacemodels.models import Issue, Organization, Project, Tracker

from ..config import logger


class TrackerClient:
    """Client for interacting with trackers."""

    def __init__(self, tracker: Tracker):
        """
        Initialize the tracker client.

        Args:
            tracker: Tracker model from database
        """
        self.tracker = tracker
        # Ensure tracker_type is lowercase for comparison
        if hasattr(tracker.tracker_type, "value"):
            # Handle if tracker_type is an enum
            self.tracker_type = tracker.tracker_type.value.lower()
        else:
            # Handle if tracker_type is a string
            self.tracker_type = tracker.tracker_type.lower()

        # Add URL to connection_details from tracker model
        connection_details = (
            dict(tracker.connection_details) if tracker.connection_details else {}
        )

        # Ensure URL is included in connection details
        if hasattr(tracker, "url") and tracker.url:
            connection_details["url"] = tracker.url
            print(f"  Adding URL to connection_details: {tracker.url}")

        # Create appropriate tracker instance based on type
        if self.tracker_type == "github":
            from ..trackers.github import GitHubTracker

            self.client = GitHubTracker(
                tracker_id=tracker.id,
                api_key=tracker.api_key,
                connection_details=connection_details,
            )
            # Set tracker reference for URL access
            self.client.tracker = tracker
        elif self.tracker_type == "gitlab":
            from ..trackers.gitlab import GitLabTracker

            self.client = GitLabTracker(
                tracker_id=tracker.id,
                api_key=tracker.api_key,
                connection_details=connection_details,
            )
            # Set tracker reference for URL access
            self.client.tracker = tracker
        elif self.tracker_type == "jira":
            from ..trackers.jira import JiraTracker

            self.client = JiraTracker(
                tracker_id=tracker.id,
                api_key=tracker.api_key,
                connection_details=connection_details,
            )
            # Set tracker reference for URL access
            self.client.tracker = tracker
        else:
            raise ValueError(f"Unsupported tracker type: {self.tracker_type}")

    def scan_organizations(self, db: Session) -> List[Organization]:
        """
        Scan and update organizations for this tracker.

        Args:
            db: Database session

        Returns:
            List of organization models
        """
        logger.info(
            f"Scanning organizations for tracker {self.tracker.id} ({self.tracker_type})"
        )

        # Get organizations from tracker
        org_data_list = self.client.get_organizations()
        logger.info(
            f"Found {len(org_data_list)} organizations in tracker {self.tracker.id}"
        )

        # Process each organization
        orgs = []
        for org_data in org_data_list:
            # Transform data for database
            org_create_data = self.client.transform_organization(org_data)
            # Find existing organization or create new one
            org = crud_organization.get_by_identifier(
                db, identifier=org_create_data["identifier"]
            )

            if org:
                # Update existing
                org = crud_organization.update(db, db_obj=org, obj_in=org_create_data)
                logger.debug(f"Updated organization {org.id} ({org.name})")
            else:
                # Create new
                org = crud_organization.create(db, obj_in=org_create_data)
                logger.info(f"Created organization {org.id} ({org.name})")

            orgs.append(org)

        return orgs

    def scan_projects(self, db: Session, organization: Organization) -> List[Project]:
        """
        Scan and update projects for an organization.

        Args:
            db: Database session
            organization: Organization model

        Returns:
            List of project models
        """
        logger.info(
            f"Scanning projects for organization {organization.id} ({organization.name})"
        )

        # Get projects from tracker
        proj_data_list = self.client.get_projects(organization.identifier)
        logger.info(
            f"Found {len(proj_data_list)} projects in organization {organization.id}"
        )

        # Process each project
        projects = []
        for proj_data in proj_data_list:
            # Transform data for database
            proj_create_data = self.client.transform_project(proj_data, organization.id)

            # Find existing project or create new one
            project = crud_project.get_by_identifier(
                db,
                identifier=proj_create_data["identifier"],
                organization_id=organization.id,
            )

            if project:
                # Update existing
                project = crud_project.update(
                    db, db_obj=project, obj_in=proj_create_data
                )
                logger.debug(f"Updated project {project.id} ({project.name})")
            else:
                # Create new
                project = crud_project.create(db, obj_in=proj_create_data)
                logger.info(f"Created project {project.id} ({project.name})")

            projects.append(project)

        return projects

    def scan_issues(
        self,
        db: Session,
        organization: Organization,
        project: Project,
        since: Optional[datetime.datetime] = None,
    ) -> Tuple[List[Issue], int]:
        """
        Scan and update issues for a project.

        Args:
            db: Database session
            organization: Organization model
            project: Project model
            since: Only update issues modified since this datetime

        Returns:
            Tuple of (list of issue models, count of issues with updated embeddings)
        """
        logger.info(f"Scanning issues for project {project.id} ({project.name})")

        # Get issues from tracker
        issue_data_list = self.client.get_issues(
            organization.identifier, project.identifier, since
        )
        logger.info(f"Found {len(issue_data_list)} issues in project {project.id}")

        # Process each issue
        issues = []
        embedding_updates = 0

        for issue_data in issue_data_list:
            # Transform data for database
            issue_create_data = self.client.transform_issue(issue_data, project.id)

            # Find existing issues for this project
            existing_issues = crud_issue.get_for_project(
                db,
                project_id=project.id,
                skip=0,
                limit=1000,  # Assume we won't have more than 1000 issues per project
            )

            # Find the matching issue by external_id
            issue = next(
                (
                    i
                    for i in existing_issues
                    if i.external_id == issue_create_data["external_id"]
                ),
                None,
            )

            content_changed = False

            if issue:
                # Check if content has changed to determine if we need to update embeddings
                if (
                    issue.title != issue_create_data["title"]
                    or issue.description != issue_create_data["description"]
                ):
                    content_changed = True

                # Update existing
                issue = crud_issue.update(db, db_obj=issue, obj_in=issue_create_data)
                logger.debug(f"Updated issue {issue.id} ({issue.title})")
            else:
                # Create new - always need embedding
                issue = crud_issue.create(db, obj_in=issue_create_data)
                content_changed = True
                logger.debug(f"Created issue {issue.id} ({issue.title})")

            issues.append(issue)

            # Update embeddings if content changed
            if content_changed:
                embedding_updates += 1
                # Create or update embeddings
                crud_issue_embedding.create_embeddings(db, issue_id=issue.id)
                logger.info(
                    f"Generated embeddings for issue {issue.id} - '{issue.title}'"
                )

        return issues, embedding_updates


def scan_tracker(
    db: Session, tracker: Tracker, verbose: bool = False
) -> Dict[str, Any]:
    """
    Scan a single tracker and update the database.

    Args:
        db: Database session
        tracker: Tracker model to scan
        verbose: Whether to print verbose output

    Returns:
        Dictionary containing scan statistics
    """
    start_time = time.time()
    stats = {
        "organizations": 0,
        "projects": 0,
        "issues": 0,
        "embeddings_updated": 0,
        "errors": 0,
    }

    # Debug information about the tracker
    print("\nTracker Debug Info:")
    print(f"  ID: {tracker.id}")
    print(f"  Type: {tracker.tracker_type}")
    print(f"  URL: {tracker.url if hasattr(tracker, 'url') else 'None'}")
    print(
        f"  API Key (first 5 chars): {tracker.api_key[:5] if len(tracker.api_key) > 5 else '***'}"
    )
    print(f"  Connection Details: {tracker.connection_details}")

    # Create tracker client
    client = TrackerClient(tracker)

    # Determine the last 30 days as a default scan period
    # This can be adjusted as needed based on usage patterns
    since = datetime.datetime.now() - datetime.timedelta(days=30)

    # Scan organizations
    orgs = client.scan_organizations(db)
    stats["organizations"] = len(orgs)

    # Scan projects for each organization
    all_projects = []
    for org in orgs:
        projects = client.scan_projects(db, org)
        all_projects.extend(projects)

    stats["projects"] = len(all_projects)

    # Scan issues for each project
    for project in all_projects:
        org = next(org for org in orgs if org.id == project.organization_id)
        issues, embedding_updates = client.scan_issues(db, org, project, since)
        stats["issues"] += len(issues)
        stats["embeddings_updated"] += embedding_updates

    # Try to store the current time as the last scan time
    # This is optional and we continue even if it fails (field might not exist)
    try:
        crud_tracker.update(
            db, db_obj=tracker, obj_in={"last_scan_time": datetime.datetime.now()}
        )
    except Exception as e:
        # If last_scan_time doesn't exist, we can ignore this error
        logger.debug(
            f"Could not update last_scan_time for tracker {tracker.id}: {str(e)}"
        )

    stats["duration_seconds"] = time.time() - start_time

    if verbose:
        print(f"Tracker {tracker.id} ({tracker.tracker_type}) scan completed:")
        print(f"  Organizations: {stats['organizations']}")
        print(f"  Projects: {stats['projects']}")
        print(f"  Issues: {stats['issues']}")
        print(f"  Embeddings updated: {stats['embeddings_updated']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Duration: {stats['duration_seconds']:.2f} seconds")

    return stats


def scan_account(db: Session, account_id: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Scan all trackers for a single account and update the database.

    Args:
        db: Database session
        account_id: ID of the account to scan (UUID string)
        verbose: Whether to print verbose output

    Returns:
        Dictionary containing scan statistics
    """
    logger.info(f"Scanning account {account_id}")

    start_time = time.time()
    account_stats = {
        "trackers_scanned": 0,
        "trackers_with_errors": 0,
        "organizations": 0,
        "projects": 0,
        "issues": 0,
        "embeddings_updated": 0,
    }

    # Get trackers for account
    trackers = crud_tracker.get_for_account(db, account_id=account_id)
    logger.info(f"Found {len(trackers)} trackers for account {account_id}")
    if not trackers:
        logger.warning(f"No trackers found for account {account_id}")
        return account_stats

    # Scan each tracker
    for tracker in trackers:
        stats = scan_tracker(db, tracker, verbose)

        # Aggregate statistics
        account_stats["trackers_scanned"] += 1
        if stats["errors"] > 0:
            account_stats["trackers_with_errors"] += 1
        account_stats["organizations"] += stats["organizations"]
        account_stats["projects"] += stats["projects"]
        account_stats["issues"] += stats["issues"]
        account_stats["embeddings_updated"] += stats["embeddings_updated"]

    account_stats["duration_seconds"] = time.time() - start_time

    if verbose:
        print(f"\nAccount {account_id} scan completed:")
        print(f"  Trackers scanned: {account_stats['trackers_scanned']}")
        print(f"  Trackers with errors: {account_stats['trackers_with_errors']}")
        print(f"  Total organizations: {account_stats['organizations']}")
        print(f"  Total projects: {account_stats['projects']}")
        print(f"  Total issues: {account_stats['issues']}")
        print(f"  Total embeddings updated: {account_stats['embeddings_updated']}")
        print(f"  Duration: {account_stats['duration_seconds']:.2f} seconds")

    return account_stats


def scan_all_accounts(db: Session, verbose: bool = False) -> Dict[str, Any]:
    """
    Scan all accounts and their trackers and update the database.

    Args:
        db: Database session
        verbose: Whether to print verbose output

    Returns:
        Dictionary containing scan statistics
    """
    logger.info("Starting scan of all accounts")

    start_time = time.time()
    overall_stats = {
        "accounts_scanned": 0,
        "accounts_with_errors": 0,
        "trackers_scanned": 0,
        "trackers_with_errors": 0,
        "organizations": 0,
        "projects": 0,
        "issues": 0,
        "embeddings_updated": 0,
    }

    # Get all active accounts
    accounts = crud_account.get_active(db)
    logger.info(f"Found {len(accounts)} active accounts")

    if not accounts:
        logger.warning("No active accounts found")
        return overall_stats

    # Scan each account
    for account in accounts:
        if verbose:
            print(f"\nScanning account: {account.username} (ID: {account.id})")

        account_stats = scan_account(db, account.id, verbose)

        # Aggregate statistics
        overall_stats["accounts_scanned"] += 1
        if account_stats["trackers_with_errors"] > 0:
            overall_stats["accounts_with_errors"] += 1
        overall_stats["trackers_scanned"] += account_stats["trackers_scanned"]
        overall_stats["trackers_with_errors"] += account_stats["trackers_with_errors"]
        overall_stats["organizations"] += account_stats["organizations"]
        overall_stats["projects"] += account_stats["projects"]
        overall_stats["issues"] += account_stats["issues"]
        overall_stats["embeddings_updated"] += account_stats["embeddings_updated"]

    overall_stats["duration_seconds"] = time.time() - start_time

    if verbose:
        print("\n=== Overall Scan Results ===")
        print(f"Accounts scanned: {overall_stats['accounts_scanned']}")
        print(f"Accounts with errors: {overall_stats['accounts_with_errors']}")
        print(f"Trackers scanned: {overall_stats['trackers_scanned']}")
        print(f"Trackers with errors: {overall_stats['trackers_with_errors']}")
        print(f"Total organizations: {overall_stats['organizations']}")
        print(f"Total projects: {overall_stats['projects']}")
        print(f"Total issues: {overall_stats['issues']}")
        print(f"Total embeddings updated: {overall_stats['embeddings_updated']}")
        print(f"Total duration: {overall_stats['duration_seconds']:.2f} seconds")

    logger.info(f"Scan completed in {overall_stats['duration_seconds']:.2f} seconds")
    logger.info(
        f"Processed {overall_stats['issues']} issues, updated {overall_stats['embeddings_updated']} embeddings"
    )

    return overall_stats
