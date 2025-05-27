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
    crud_comment,
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

    def _get_project_identifier(self, proj_data: Dict[str, Any]) -> Optional[str]:
        """Extract a consistent identifier from raw project data."""
        # Try common fields from different trackers
        if 'full_name' in proj_data.get('meta_data', {}): # GitHub repo name (owner/repo)
            return proj_data['meta_data']['full_name']
        if self.tracker_type == 'gitlab' and 'id' in proj_data: # GitLab project path
            return proj_data['id']
        if 'key' in proj_data: # Jira project key
            return proj_data['key']
        if 'url' in proj_data: # Generic URL
            return '/'.join(proj_data['url'].split('/')[-2:])

        # Add more potential fields if needed (e.g., 'id' as a last resort?)
        logger.warning(f"Could not determine identifier for project data: {proj_data.get('name', 'N/A')}")
        return None

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
        Scan and update projects for an organization, applying inclusion/exclusion rules.

        Args:
            db: Database session
            organization: Organization model

        Returns:
            List of processed (created or updated) project models that match the rules.
        """
        logger.info(
            f"Scanning projects for organization {organization.id} ({organization.name})"
        )

        # Get project selection rules from the tracker
        included_list = set(self.tracker.included_project_identifiers or [])
        excluded_list = set(self.tracker.excluded_project_identifiers or [])
        include_future = self.tracker.include_future_projects
        has_includes = bool(included_list)

        logger.debug(f"Tracker {self.tracker.id} rules: include_future={include_future}, "
                     f"includes={included_list}, excludes={excluded_list}")

        # Get all projects from the tracker API
        try:
            proj_data_list = self.client.get_projects(organization.identifier)
            logger.info(
                f"Found {len(proj_data_list)} raw projects in tracker for organization {organization.id}"
            )
        except Exception as e:
            logger.error(f"Failed to get projects from tracker for org {organization.identifier}: {e}")
            return [] # Return empty list if API call fails

        # Filter projects based on inclusion/exclusion rules
        filtered_proj_data_list = []
        for proj_data in proj_data_list:
            identifier = self._get_project_identifier(proj_data)
            if not identifier:
                logger.warning(f"Skipping project with no identifier: {proj_data.get('name')}")
                continue

            # Apply exclusion first
            if identifier in excluded_list:
                logger.debug(f"Excluding project '{identifier}' based on exclusion list.")
                continue


            # Apply inclusion if an inclusion list exists
            if has_includes and identifier not in included_list:
                logger.debug(f"Skipping project '{identifier}' as it's not in the inclusion list.")
                continue

            # If it passes filters, add to the list to be processed
            filtered_proj_data_list.append(proj_data)

        logger.info(f"Processing {len(filtered_proj_data_list)} projects after filtering for org {organization.id}")

        # Process the filtered projects
        processed_projects = []
        for proj_data in filtered_proj_data_list:
            try:
                # Transform data for database
                proj_create_data = self.client.transform_project(proj_data, organization.id)
                project_identifier = proj_create_data.get("identifier") # Use identifier from transformed data

                if not project_identifier:
                     logger.warning(f"Skipping project due to missing identifier after transform: {proj_create_data.get('name')}")
                     continue

                # Find existing project or create new one
                existing_project = crud_project.get_by_slug_or_identifier(
                    db,
                    slug_or_identifier=project_identifier,
                    organization_id=organization.id,
                )

                if existing_project:
                    # Update existing project
                    project = crud_project.update(
                        db, db_obj=existing_project, obj_in=proj_create_data
                    )
                    logger.debug(f"Updated project {project.id} ({project.name})")
                    processed_projects.append(project)
                else:
                    # Check include_future logic before creating a new project
                    create_new = True
                    if not include_future and has_includes:
                        # If not including future and there's an include list,
                        # only create if it was explicitly included.
                        if project_identifier not in included_list:
                            create_new = False
                            logger.debug(f"Skipping creation of new project '{project_identifier}' due to include_future=False and not in inclusion list.")

                    if create_new:
                        project = crud_project.create(db, obj_in=proj_create_data)
                        logger.info(f"Created project {project.id} ({project.name})")
                        processed_projects.append(project)

            except Exception as e:
                 logger.error(f"Error processing project data {proj_data.get('name', 'N/A')}: {e}", exc_info=True)
                 # Continue processing other projects

        return processed_projects

    def scan_issues(
        self,
        db: Session,
        organization: Organization,
        project: Project,
        since: Optional[datetime.datetime] = None,
        force_update: bool = False,
    ) -> Tuple[List[Issue], int]:
        """
        Scan and update issues for a project.

        Args:
            db: Database session
            organization: Organization model
            project: Project model
            since: Only update issues modified since this datetime
            force_update: Whether to force update all embeddings even if content hasn't changed

        Returns:
            Tuple of (list of issue models, count of issues with updated embeddings)
        """
        logger.info(f"Scanning issues for project {project.id} ({project.name})")

        # Get issues from tracker, passing the 'since' parameter
        logger.debug(f"Calling get_issues for project {project.identifier} since {since}")
        issue_data_list = self.client.get_issues(
            organization_id=organization.identifier, # Pass org_id/identifier
            project_id=project.identifier,       # Pass proj_id/identifier
            since=since                          # Pass the since parameter
        )
        logger.info(f"Found {len(issue_data_list)} issues in project {project.id} since {since}")

        issues_processed = [] # Renamed from 'issues' to avoid conflict with model name
        embedding_updates = 0

        for issue_data in issue_data_list:
            transformed_data = self.client.transform_issue(issue_data, project.id)

            comments_payload = transformed_data.pop("comments", [])

            existing_issues_for_project = crud_issue.get_for_project(
                db,
                project_id=project.id,
                skip=0,
                limit=10000,
            )

            current_issue_model = next(
                (
                    i
                    for i in existing_issues_for_project
                    if i.external_id == transformed_data.get("external_id")
                ),
                None,
            )

            content_changed = False
            created_new_issue = False

            if current_issue_model:
                if (
                    current_issue_model.title != transformed_data.get("title")
                    or current_issue_model.description != transformed_data.get("description")
                ):
                    content_changed = True

                current_issue_model = crud_issue.update(db, db_obj=current_issue_model, obj_in=transformed_data)
                logger.debug(f"Updated issue {current_issue_model.id} ({current_issue_model.title})")
            else:
                current_issue_model = crud_issue.create(db, obj_in=transformed_data)
                content_changed = True
                created_new_issue = True
                logger.debug(f"Created issue {current_issue_model.id} ({current_issue_model.title})")

            issues_processed.append(current_issue_model)

            if comments_payload:
                logger.info(f"Processing {len(comments_payload)} comments for issue {current_issue_model.id} ('{current_issue_model.title}')")
                db_comments_for_issue = crud_comment.get_multi_by_issue(db, issue_id=current_issue_model.id, limit=10000)
                db_comments_map_by_external_id = {
                    c.id: c for c in db_comments_for_issue if c.id
                }
                processed_comment_external_ids = set()

                for single_comment_data in comments_payload:
                    comment_obj_in_for_crud = single_comment_data.copy()
                    comment_obj_in_for_crud["issue_id"] = current_issue_model.id

                    comment_external_id = comment_obj_in_for_crud.get("id")

                    if not comment_external_id:
                        # For comments without an external ID, we assume they are always new if encountered.
                        transformed_new_comment_data = self.client.transform_comment(comment_obj_in_for_crud, issue_db_id=current_issue_model.id)
                        new_db_comment = crud_comment.create(db, obj_in=transformed_new_comment_data)
                        logger.debug(f"Created new comment {new_db_comment.id} (no external_id) for issue {current_issue_model.id}")
                        if new_db_comment.body: # Ensure there's text to embed
                            crud_issue_embedding.create_embeddings(
                                db=db,
                                issue_id=current_issue_model.id,
                                comment_id=new_db_comment.id,
                                force_update=force_update # New comments are effectively 'forced' if body exists
                            )
                            logger.debug(f"Attempted embedding creation for new comment {new_db_comment.id} (no external_id)")
                        continue

                    processed_comment_external_ids.add(comment_external_id)
                    existing_db_comment = db_comments_map_by_external_id.get(comment_external_id)

                    transformed_comment_data = self.client.transform_comment(comment_obj_in_for_crud, issue_db_id=current_issue_model.id)

                    if existing_db_comment:
                        old_body = existing_db_comment.body
                        updated_comment = crud_comment.update(db, db_obj=existing_db_comment, obj_in=transformed_comment_data)
                        logger.debug(f"Updated comment {updated_comment.id} (ext_id: {comment_external_id}) for issue {current_issue_model.id}")

                        comment_body_changed = (old_body != updated_comment.body)
                        if updated_comment.body and (comment_body_changed or force_update):
                            crud_issue_embedding.create_embeddings(
                                db=db,
                                issue_id=current_issue_model.id,
                                comment_id=updated_comment.id,
                                force_update=force_update # Respect force_update, otherwise only if body changed
                            )
                            logger.debug(f"Attempted embedding creation for updated comment {updated_comment.id} (body_changed: {comment_body_changed}, force_update: {force_update})")
                    else:
                        new_db_comment = crud_comment.create(db, obj_in=transformed_comment_data)
                        logger.debug(f"Created new comment {new_db_comment.id} (ext_id: {comment_external_id}) for issue {current_issue_model.id}")
                        if new_db_comment.body:
                            crud_issue_embedding.create_embeddings(
                                db=db,
                                issue_id=current_issue_model.id,
                                comment_id=new_db_comment.id,
                                force_update=force_update # New comments are effectively 'forced' if body exists
                            )
                            logger.debug(f"Attempted embedding creation for new comment {new_db_comment.id} (ext_id: {comment_external_id})")

            if content_changed or force_update:
                embedding_updates += 1
                crud_issue_embedding.create_embeddings(db, issue_id=current_issue_model.id)
                logger.info(
                    f"Generated embeddings for issue {current_issue_model.id} - '{current_issue_model.title}'"
                )

        return issues_processed, embedding_updates

def scan_tracker(
    db: Session, tracker: Tracker, verbose: bool = False, force_update: bool = False
) -> Dict[str, Any]:
    """
    Scan a single tracker and update the database.

    Args:
        db: Database session
        tracker: Tracker model to scan
        verbose: Whether to print verbose output
        force_update: Whether to force update all embeddings even if content hasn't changed

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

    # Use epoch time (Jan 1, 1970) to effectively scan all issues
    since = datetime.datetime(1970, 1, 1)

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
        issues, embedding_updates = client.scan_issues(
            db, org, project, since, force_update
        )
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


def scan_account(
    db: Session, account_id: str, verbose: bool = False, force_update: bool = False
) -> Dict[str, Any]:
    """
    Scan all trackers for a single account and update the database.

    Args:
        db: Database session
        account_id: ID of the account to scan (UUID string)
        verbose: Whether to print verbose output
        force_update: Whether to force update all embeddings even if content hasn't changed

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
        stats = scan_tracker(db, tracker, verbose, force_update)

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


def scan_all_accounts(db: Session, verbose: bool = False, force_update: bool = False) -> Dict[str, Any]:
    """
    Scan all accounts and their trackers, updating the database.

    Args:
        db: Database session.
        verbose: Whether to print verbose output during scans.
        force_update: Whether to force update all embeddings even if content hasn't changed.

    Returns:
        Dictionary containing scan statistics.
    """
    logger.info("Starting scan of all accounts")

    start_time = time.time()
    # Use consistent naming for stats dictionary keys as used in scan_account and scan_tracker
    overall_stats = {
        "accounts_scanned": 0,
        "accounts_with_errors": 0,
        "total_trackers_scanned": 0, # Renamed for clarity
        "total_trackers_with_errors": 0, # Renamed for clarity
        "total_organizations": 0, # Renamed for clarity
        "total_projects": 0, # Renamed for clarity
        "total_issues": 0, # Renamed for clarity
        "total_embeddings_updated": 0, # Renamed for clarity
    }

    # Get all active accounts
    accounts = crud_account.get_active(db)
    logger.info(f"Found {len(accounts)} active accounts")

    if not accounts:
        logger.warning("No active accounts found")
        # Add duration before returning early
        overall_stats["total_duration_seconds"] = time.time() - start_time
        return overall_stats

    # Scan each account
    for account in accounts:
        logger.info(f"Starting scan for account: {account.username} (ID: {account.id})")
        # Ensure verbose and force_update are passed explicitly by name for clarity
        account_stats = scan_account(db, account.id, verbose=verbose, force_update=force_update)

        # Aggregate statistics using the renamed keys
        overall_stats["accounts_scanned"] += 1
        if account_stats["trackers_with_errors"] > 0:
            overall_stats["accounts_with_errors"] += 1
        overall_stats["total_trackers_scanned"] += account_stats["trackers_scanned"]
        overall_stats["total_trackers_with_errors"] += account_stats["trackers_with_errors"]
        overall_stats["total_organizations"] += account_stats["organizations"]
        overall_stats["total_projects"] += account_stats["projects"]
        overall_stats["total_issues"] += account_stats["issues"]
        overall_stats["total_embeddings_updated"] += account_stats["embeddings_updated"]
        logger.info(f"Finished scan for account: {account.username} (ID: {account.id})")


    overall_stats["total_duration_seconds"] = time.time() - start_time # Renamed for clarity

    logger.info(f"Finished scanning all accounts in {overall_stats['total_duration_seconds']:.2f} seconds.")
    # Use the renamed keys for the verbose printout to match the return dict and CLI output
    if verbose:
        print("\n=== Overall Scan Summary ===")
        print(f"  Accounts scanned: {overall_stats['accounts_scanned']}")
        print(f"  Accounts with errors: {overall_stats['accounts_with_errors']}")
        print(f"  Total trackers scanned: {overall_stats['total_trackers_scanned']}")
        print(f"  Total trackers with errors: {overall_stats['total_trackers_with_errors']}")
        print(f"  Total organizations: {overall_stats['total_organizations']}")
        print(f"  Total projects: {overall_stats['total_projects']}")
        print(f"  Total issues: {overall_stats['total_issues']}")
        print(f"  Total embeddings updated: {overall_stats['total_embeddings_updated']}")
        print(f"  Total duration: {overall_stats['total_duration_seconds']:.2f} seconds")

    # Remove redundant logging already covered by verbose output or logger above
    # logger.info(f"Scan completed in {overall_stats['total_duration_seconds']:.2f} seconds")
    # logger.info(
    #     f"Processed {overall_stats['total_issues']} issues, updated {overall_stats['total_embeddings_updated']} embeddings"
    # )

    return overall_stats
