"""
Core scanning functionality for SpaceSync.
"""

import datetime
from datetime import timedelta
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin
import secrets
from sqlalchemy.orm import Session

from spacemodels.crud import (
    crud_account,
    crud_issue,
    crud_issue_embedding,
    crud_organization,
    crud_project,
    crud_comment,
)
from spacemodels.models import Issue, Organization, Project, Tracker, TrackerScopeRule

from ..config import logger

POLLING_THRESHOLD = timedelta(seconds=os.getenv("POLLING_THRESHOLD", 3600))
RECHECK_PROJECT_WEBHOOK_INTERVAL = timedelta(days=1)


class TrackerClient:
    """Client for interacting with trackers."""

    def __init__(self, tracker: Tracker):
        """Initialize the tracker client."""
        self.tracker = tracker
        self.tracker_type = (
            tracker.tracker_type.value.lower()
            if hasattr(tracker.tracker_type, "value")
            else tracker.tracker_type.lower()
        )

        connection_details = (
            dict(tracker.connection_details) if tracker.connection_details else {}
        )
        if hasattr(tracker, "url") and tracker.url:
            connection_details["url"] = tracker.url

        if self.tracker_type == "github":
            from ..trackers.github import GitHubTracker

            self.client = GitHubTracker(tracker.id, tracker.api_key, connection_details)
        elif self.tracker_type == "gitlab":
            from ..trackers.gitlab import GitLabTracker

            self.client = GitLabTracker(tracker.id, tracker.api_key, connection_details)
        elif self.tracker_type == "jira":
            from ..trackers.jira import JiraTracker

            self.client = JiraTracker(tracker.id, tracker.api_key, connection_details)
        else:
            raise ValueError(f"Unsupported tracker type: {self.tracker_type}")

    def scan_organizations(self, db: Session) -> List[Organization]:
        """Scan and update organizations for this tracker."""
        org_data_list = self.client.get_organizations()
        logger.info(
            f"Found {len(org_data_list)} organizations in tracker {self.tracker.id}"
        )

        orgs = []
        rules = (
            db.query(TrackerScopeRule)
            .filter(TrackerScopeRule.tracker_id == self.tracker.id)
            .all()
        )

        # 1. Separate rules into four sets for efficient lookup
        org_inclusions = {
            r.identifier
            for r in rules
            if r.scope_type == "ORGANIZATION" and r.rule_type == "INCLUDE"
        }
        for org_data in org_data_list:
            if str(org_data["id"]) not in org_inclusions:
                logger.info(
                    f"Skipping organization {org_data['name']} ({org_data['id']}) because it is not in the "
                    f"explicit inclusion list for tracker {self.tracker.id}."
                )
                continue
            org_create_data = self.client.transform_organization(org_data)
            org = crud_organization.get_by_identifier(
                db,
                identifier=org_create_data["identifier"],
                account_id=self.tracker.account_id,
            )
            if org:
                org = crud_organization.update(db, db_obj=org, obj_in=org_create_data)
            else:
                org = crud_organization.create(db, obj_in=org_create_data)
            orgs.append(org)
        return orgs

    def scan_projects(self, db: Session, organization: Organization) -> List[Project]:
        """Scan and update projects for an organization."""
        logger.info(
            f"Scanning projects for organization {organization.id} ({organization.name})"
        )
        try:
            proj_data_list = self.client.get_projects(organization.identifier)
        except Exception as e:
            logger.error(
                f"Failed to get projects from tracker for org {organization.name}: {e}"
            )
            return []

        rules = (
            db.query(TrackerScopeRule)
            .filter(TrackerScopeRule.tracker_id == self.tracker.id)
            .all()
        )

        # 1. Separate rules into four sets for efficient lookup
        org_inclusions = {
            r.identifier
            for r in rules
            if r.scope_type == "ORGANIZATION" and r.rule_type == "INCLUDE"
        }
        project_inclusions = {
            r.identifier
            for r in rules
            if r.scope_type == "PROJECT" and r.rule_type == "INCLUDE"
        }
        project_exclusions = {
            r.identifier
            for r in rules
            if r.scope_type == "PROJECT" and r.rule_type == "EXCLUDE"
        }
        # 2. Check if the organization is explicitly included. This is a precondition for scanning any projects.
        if organization.identifier not in org_inclusions:
            logger.info(
                f"Skipping organization {organization.name} ({organization.identifier}) because it is not in the "
                f"explicit inclusion list for tracker {self.tracker.id}."
            )
            return []

        logger.info(
            f"Organization {organization.name} ({organization.identifier}) is included. Fetching and filtering projects."
        )

        processed_projects = []
        for proj_data in proj_data_list:
            try:
                proj_create_data = self.client.transform_project(
                    proj_data, organization.id
                )
                if (
                    "meta_data" in proj_data
                    and "full_name" in proj_data["meta_data"]
                    and not proj_create_data.get("slug")
                ):
                    proj_create_data["slug"] = proj_data["meta_data"]["full_name"]
                project_identifier = proj_create_data.get("identifier")
                project_name = proj_create_data.get("name", "N/A")

                if not project_identifier:
                    logger.warning(
                        f"Skipping project with missing identifier in org {organization.name}."
                    )
                    continue

                # Apply project-level filtering logic
                # Condition 2: The project's identifier is not in project_exclusions.
                if project_identifier in project_exclusions:
                    logger.info(
                        f"Skipping project {project_name} ({project_identifier}) because it is in the exclusion list."
                    )
                    continue

                # Condition 3: Either there are no project_inclusions rules, OR the project's identifier is in project_inclusions.
                if project_inclusions and project_identifier not in project_inclusions:
                    logger.info(
                        f"Skipping project {project_name} ({project_identifier}) because it is not in the "
                        f"project inclusion list, and one is defined."
                    )
                    continue

                # If all checks pass, the project is included.
                logger.info(
                    f"Project {project_name} ({project_identifier}) passed filters. Processing."
                )
                existing_project = crud_project.get_by_slug_or_identifier(
                    db,
                    slug_or_identifier=project_identifier,
                    organization_id=organization.id,
                    account_id=self.tracker.account_id,
                )
                if existing_project:
                    project = crud_project.update(
                        db, db_obj=existing_project, obj_in=proj_create_data
                    )
                else:
                    project = crud_project.create(db, obj_in=proj_create_data)
                processed_projects.append(project)
            except Exception as e:
                logger.error(
                    f"Error processing project data for {proj_data.get('name', 'N/A')}: {e}",
                    exc_info=True,
                )

        return processed_projects

    def scan_issues(
        self,
        db: Session,
        organization: Organization,
        project: Project,
        since: Optional[datetime.datetime] = None,
        force_update: bool = False,
    ) -> Tuple[List[Issue], int]:
        """Scan and update issues for a project."""
        logger.info(
            f"Scanning issues for project {project.id} ({project.name}) since {since}"
        )
        issue_data_list = self.client.get_issues(
            organization_id=organization.identifier,
            project_id=project.identifier,
            since=since,
        )

        issues_processed = []
        embedding_updates = 0
        for issue_data in issue_data_list:
            xformed_issue_data = self.client.transform_issue(issue_data, project)
            comment_data = xformed_issue_data.pop("comments", [])

            current_issue_model = crud_issue.get_by_external_id(
                db,
                external_id=xformed_issue_data["external_id"],
                project_id=project.id,
                account_id=self.tracker.account_id,
            )

            issue_changed = False
            if not isinstance(xformed_issue_data["updated_at"], datetime.datetime):
                xformed_issue_data["updated_at"] = datetime.datetime.fromisoformat(
                    xformed_issue_data["updated_at"]
                )
            if current_issue_model:
                if current_issue_model.updated_at < xformed_issue_data["updated_at"]:
                    issue_changed = True
                    current_issue_model = crud_issue.update(
                        db, db_obj=current_issue_model, obj_in=xformed_issue_data
                    )
            else:
                issue_changed = True
                current_issue_model = crud_issue.create(db, obj_in=xformed_issue_data)

            issues_processed.append(current_issue_model)

            for single_comment_data in comment_data:
                xformed_comment_data = self.client.transform_comment(
                    single_comment_data, current_issue_model.id
                )
                xformed_comment_data["tracker_id"] = self.tracker.id
                db_comment = crud_comment.get_by_external_id(
                    db,
                    external_id=xformed_comment_data["external_id"],
                    issue_id=current_issue_model.id,
                    account_id=self.tracker.account_id,
                )

                comment_changed = False
                if db_comment:
                    if db_comment.updated_at < xformed_comment_data["updated_at"]:
                        comment_changed = True
                        crud_comment.update(
                            db, db_obj=db_comment, obj_in=xformed_comment_data
                        )
                else:
                    comment_changed = True
                    db_comment = crud_comment.create(db, obj_in=xformed_comment_data)

                if comment_changed or force_update:
                    crud_issue_embedding.create_embeddings(
                        db=db,
                        issue_id=current_issue_model.id,
                        comment_id=db_comment.id,
                        force_update=force_update,
                    )

            if issue_changed or force_update:
                embedding_updates += 1
                crud_issue_embedding.create_embeddings(
                    db, issue_id=current_issue_model.id
                )

        return issues_processed, embedding_updates


def _process_organization(
    db: Session,
    client: TrackerClient,
    org: Organization,
    since: datetime.datetime,
    force_update: bool,
) -> Tuple[Dict[str, Any], bool]:
    """Processes a single organization."""
    org_stats = {"projects": 0, "issues": 0, "embeddings_updated": 0, "errors": 0}
    now = datetime.datetime.now(datetime.timezone.utc)

    projects = client.scan_projects(db, org)
    org_stats["projects"] = len(projects)
    spacebridge_url_str = os.getenv("SPACEBRIDGE_URL")
    if spacebridge_url_str:
        try:
            webhook_target_path = (
                f"/api/v1/private/webhooks/{client.tracker_type}/{org.id}"
            )
            webhook_target_url = urljoin(spacebridge_url_str, webhook_target_path)
            current_secret_to_use = org.webhook_secret
            if not org.webhook_secret:
                current_secret_to_use = secrets.token_hex(32)

            if client.tracker_type == "jira":
                for project in projects:
                    try:
                        client.client.register_webhook(
                            db=db,
                            project=project,
                            webhook_url=webhook_target_url,
                            secret=current_secret_to_use,
                        )
                    except Exception as e:
                        logger.error(
                            f"Error registering webhook for Jira project {project.identifier}: {e}",
                            exc_info=True,
                        )
                        org_stats["errors"] += 1
            elif client.tracker_type == "github":
                try:
                    client.client.register_webhook(
                        db=db,
                        organization=org,
                        webhook_url=webhook_target_url,
                        secret=current_secret_to_use,
                    )
                except Exception as e:
                    logger.error(
                        f"Error registering webhook for GitHub organization {org.identifier}: {e}",
                        exc_info=True,
                    )
                    org_stats["errors"] += 1
            elif client.tracker_type == "gitlab":
                try:
                    result = client.client.register_group_webhook(
                        db=db,
                        organization=org,
                        webhook_url=webhook_target_url,
                        secret=current_secret_to_use,
                    )
                    if result == "group_hooks_not_supported":
                        logger.warning(
                            f"Group hooks are not supported for GitLab organization {org.identifier}."
                        )
                        for project in projects:
                            try:
                                client.client.register_project_webhook(
                                    db=db,
                                    project=project,
                                    webhook_url=webhook_target_url,
                                    secret=current_secret_to_use,
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error registering webhook for GitLab project {project.identifier}: {e}",
                                    exc_info=True,
                                )
                                org_stats["errors"] += 1
                except Exception as e:
                    logger.error(
                        f"Error registering webhook for GitLab organization {org.identifier}: {e}",
                        exc_info=True,
                    )
                    org_stats["errors"] += 1
            else:
                # Handle other tracker types here if necessary
                pass

            if not org.webhook_secret:
                crud_organization.update(
                    db,
                    db_obj=org,
                    obj_in={
                        "webhook_secret": current_secret_to_use,
                        "last_webhook_update": now,
                    },
                )

        except Exception as e:
            logger.error(
                f"Error during webhook registration for org {org.id}: {e}",
                exc_info=True,
            )
            org_stats["errors"] += 1

    # Polling logic
    for project in projects:
        issues, embeddings_updated = client.scan_issues(
            db, org, project, since, force_update
        )
        org_stats["issues"] += len(issues)
        org_stats["embeddings_updated"] += embeddings_updated

    crud_organization.update(db, db_obj=org, obj_in={"last_polling_update": now})
    return org_stats, False


def scan_tracker(
    db: Session,
    tracker: Tracker,
    force_update: bool = False,
    since: Optional[datetime.datetime] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Scan a single tracker."""
    logger.info(f"Scanning tracker {tracker.id} ({tracker.tracker_type})")
    stats = {
        "organizations": 0,
        "projects": 0,
        "issues": 0,
        "embeddings_updated": 0,
        "errors": 0,
    }

    try:
        client = TrackerClient(tracker)
        organizations = client.scan_organizations(db)
        stats["organizations"] = len(organizations)

        for org in organizations:
            org_stats, skipped = _process_organization(
                db, client, org, since, force_update
            )
            for key in stats:
                stats[key] += org_stats.get(key, 0)
    except Exception as e:
        logger.error(f"Failed to scan tracker {tracker.id}: {e}", exc_info=True)
        stats["errors"] += 1

    if verbose:
        logger.info(f"Stats for tracker {tracker.id}: {stats}")
    return stats


def scan_account(
    db: Session,
    account_id: str,
    force_update: bool = False,
    since: Optional[datetime.datetime] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Scan all trackers for a given account."""
    account = crud_account.get(db, id=account_id)
    if not account:
        logger.error(f"Account with id {account_id} not found.")
        return {}

    total_stats = {
        "trackers": 0,
        "organizations": 0,
        "projects": 0,
        "issues": 0,
        "embeddings_updated": 0,
        "errors": 0,
    }
    for tracker in account.trackers:
        if tracker.is_active:
            total_stats["trackers"] += 1
            tracker_stats = scan_tracker(db, tracker, force_update, since, verbose)
            for key in total_stats:
                total_stats[key] += tracker_stats.get(key, 0)
    if verbose:
        logger.info(f"Stats for account {account_id}: {total_stats}")
    return total_stats


def scan_all_accounts(
    db: Session, force_update: bool = False, verbose: bool = False
) -> Dict[str, Any]:
    """Scan all active accounts and their trackers."""
    accounts = crud_account.get_multi(db, skip=0, limit=1000)
    logger.info(f"Found {len(accounts)} accounts to scan.")
    overall_stats = {
        "accounts_scanned": 0,
        "accounts_with_errors": 0,
        "total_trackers_scanned": 0,
        "total_trackers_with_errors": 0,
        "total_organizations": 0,
        "total_projects": 0,
        "total_issues": 0,
        "total_embeddings_updated": 0,
        "total_duration_seconds": 0.0,
    }
    for account in accounts:
        if account.is_active:
            overall_stats["accounts_scanned"] += 1
            account_stats = scan_account(db, account.id, force_update, verbose=verbose)
            if account_stats.get("errors", 0) > 0:
                overall_stats["accounts_with_errors"] += 1
            overall_stats["total_trackers_scanned"] += account_stats.get("trackers", 0)
            overall_stats["total_organizations"] += account_stats.get(
                "organizations", 0
            )
            overall_stats["total_projects"] += account_stats.get("projects", 0)
            overall_stats["total_issues"] += account_stats.get("issues", 0)
            overall_stats["total_embeddings_updated"] += account_stats.get(
                "embeddings_updated", 0
            )
            # Note: duration is not summed up from individual accounts.
            # This would require more complex logic to run scans in parallel and measure total time.

    logger.info(f"Finished scanning all accounts. Stats: {overall_stats}")
    return overall_stats
