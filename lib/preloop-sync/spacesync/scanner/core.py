"""
Core scanning functionality for SpaceSync.
"""

import datetime
from datetime import timedelta
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

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
        self.tracker_type = tracker.tracker_type.value.lower() if hasattr(tracker.tracker_type, "value") else tracker.tracker_type.lower()

        connection_details = dict(tracker.connection_details) if tracker.connection_details else {}
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
        logger.info(f"Scanning organizations for tracker {self.tracker.id} ({self.tracker_type})")
        org_data_list = self.client.get_organizations()
        logger.info(f"Found {len(org_data_list)} organizations in tracker {self.tracker.id}")

        orgs = []
        for org_data in org_data_list:
            org_create_data = self.client.transform_organization(org_data)
            org = crud_organization.get_by_identifier(db, identifier=org_create_data["identifier"])
            if org:
                org = crud_organization.update(db, db_obj=org, obj_in=org_create_data)
            else:
                org = crud_organization.create(db, obj_in=org_create_data)
            orgs.append(org)
        return orgs

    def scan_projects(self, db: Session, organization: Organization) -> List[Project]:
        """Scan and update projects for an organization."""
        logger.info(f"Scanning projects for organization {organization.id} ({organization.name})")
        try:
            proj_data_list = self.client.get_projects(organization.identifier)
        except Exception as e:
            logger.error(f"Failed to get projects from tracker for org {organization.name}: {e}")
            return []

        rules = db.query(TrackerScopeRule).filter(TrackerScopeRule.tracker_id == self.tracker.id).all()

        if not rules:
            # No rules, include everything
            processed_projects = []
            for proj_data in proj_data_list:
                try:
                    proj_create_data = self.client.transform_project(proj_data, organization.id)
                    project_identifier = proj_create_data.get("identifier")
                    if not project_identifier:
                        continue

                    existing_project = crud_project.get_by_slug_or_identifier(
                        db, slug_or_identifier=project_identifier, organization_id=organization.id
                    )
                    if existing_project:
                        project = crud_project.update(db, db_obj=existing_project, obj_in=proj_create_data)
                    else:
                        project = crud_project.create(db, obj_in=proj_create_data)
                    processed_projects.append(project)
                except Exception as e:
                    logger.error(f"Error processing project data {proj_data.get('name', 'N/A')}: {e}", exc_info=True)
            return processed_projects

        # Apply rules
        included_projects = set()
        excluded_projects = set()

        # Get all project identifiers from the API response
        all_project_identifiers = {p.get("id") for p in proj_data_list if p.get("id")}

        for rule in rules:
            if rule.scope_type == "ORGANIZATION":
                if rule.rule_type == "INCLUDE":
                    included_projects.update(all_project_identifiers)
                elif rule.rule_type == "EXCLUDE":
                    excluded_projects.update(all_project_identifiers)
            elif rule.scope_type == "PROJECT":
                if rule.rule_type == "INCLUDE":
                    included_projects.add(rule.identifier)
                elif rule.rule_type == "EXCLUDE":
                    excluded_projects.add(rule.identifier)

        final_project_ids = included_projects - excluded_projects

        processed_projects = []
        for proj_data in proj_data_list:
            identifier = proj_data.get("id")
            if identifier not in final_project_ids:
                continue
            try:
                proj_create_data = self.client.transform_project(proj_data, organization.id)
                project_identifier = proj_create_data.get("identifier")
                if not project_identifier:
                    continue

                existing_project = crud_project.get_by_slug_or_identifier(
                    db, slug_or_identifier=project_identifier, organization_id=organization.id
                )
                if existing_project:
                    project = crud_project.update(db, db_obj=existing_project, obj_in=proj_create_data)
                else:
                    project = crud_project.create(db, obj_in=proj_create_data)
                processed_projects.append(project)
            except Exception as e:
                logger.error(f"Error processing project data {proj_data.get('name', 'N/A')}: {e}", exc_info=True)
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
        logger.info(f"Scanning issues for project {project.id} ({project.name}) since {since}")
        issue_data_list = self.client.get_issues(
            organization_id=organization.identifier, project_id=project.identifier, since=since
        )

        issues_processed = []
        embedding_updates = 0
        for issue_data in issue_data_list:
            xformed_issue_data = self.client.transform_issue(issue_data, project)
            comment_data = xformed_issue_data.pop("comments", [])

            current_issue_model = crud_issue.get_by_external_id(db, external_id=xformed_issue_data["external_id"], project_id=project.id)

            issue_changed = False
            if current_issue_model:
                if current_issue_model.updated_at < xformed_issue_data["updated_at"]:
                    issue_changed = True
                    current_issue_model = crud_issue.update(db, db_obj=current_issue_model, obj_in=xformed_issue_data)
            else:
                issue_changed = True
                current_issue_model = crud_issue.create(db, obj_in=xformed_issue_data)

            issues_processed.append(current_issue_model)

            for single_comment_data in comment_data:
                xformed_comment_data = self.client.transform_comment(single_comment_data, current_issue_model.id)
                db_comment = crud_comment.get_by_external_id(db, external_id=xformed_comment_data["external_id"], issue_id=current_issue_model.id)

                comment_changed = False
                if db_comment:
                    if db_comment.updated_at < xformed_comment_data["updated_at"]:
                        comment_changed = True
                        crud_comment.update(db, db_obj=db_comment, obj_in=xformed_comment_data)
                else:
                    comment_changed = True
                    db_comment = crud_comment.create(db, obj_in=xformed_comment_data)

                if comment_changed or force_update:
                    crud_issue_embedding.create_embeddings(db=db, issue_id=current_issue_model.id, comment_id=db_comment.id, force_update=force_update)

            if issue_changed or force_update:
                embedding_updates += 1
                crud_issue_embedding.create_embeddings(db, issue_id=current_issue_model.id)

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

    spacebridge_url_str = os.getenv("SPACEBRIDGE_URL")
    if spacebridge_url_str:
        try:
            webhook_target_path = f"/api/v1/private/webhooks/{client.tracker_type}/{org.identifier}"
            webhook_target_url = urljoin(spacebridge_url_str, webhook_target_path)
            current_secret_to_use = org.webhook_secret

            if client.tracker_type == "jira":
                projects = crud_project.get_for_organization(db, organization_id=org.id)
                for project in projects:
                    try:
                        client.client.register_webhook(
                            db=db,
                            project_id=project.id,
                            project_key=project.identifier,
                            webhook_url=webhook_target_url,
                            secret=current_secret_to_use,
                        )
                    except Exception as e:
                        logger.error(f"Error registering webhook for Jira project {project.identifier}: {e}", exc_info=True)
                        org_stats["errors"] += 1
            elif client.tracker_type == "github":
                try:
                    client.client.register_webhook(
                        org_identifier=org.identifier,
                        webhook_url=webhook_target_url,
                        secret=current_secret_to_use,
                    )
                except Exception as e:
                    logger.error(f"Error registering webhook for GitHub organization {org.identifier}: {e}", exc_info=True)
                    org_stats["errors"] += 1
            else:
                # Handle other tracker types here if necessary
                pass

            if not org.webhook_secret:
                crud_organization.update(db, db_obj=org, obj_in={"webhook_secret": current_secret_to_use, "last_webhook_update": now})

        except Exception as e:
            logger.error(f"Error during webhook registration for org {org.id}: {e}", exc_info=True)
            org_stats["errors"] += 1

    # Polling logic
    projects = client.scan_projects(db, org)
    org_stats["projects"] = len(projects)
    for project in projects:
        issues, embeddings_updated = client.scan_issues(db, org, project, since, force_update)
        org_stats["issues"] += len(issues)
        org_stats["embeddings_updated"] += embeddings_updated

    crud_organization.update(db, db_obj=org, obj_in={"last_polling_update": now})
    return org_stats, False

def scan_tracker(
    db: Session, tracker: Tracker, force_update: bool = False, since: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    """Scan a single tracker."""
    logger.info(f"Scanning tracker {tracker.id} ({tracker.tracker_type})")
    stats = {"organizations": 0, "projects": 0, "issues": 0, "embeddings_updated": 0, "errors": 0}

    try:
        client = TrackerClient(tracker)
        organizations = client.scan_organizations(db)
        stats["organizations"] = len(organizations)

        for org in organizations:
            org_stats, skipped = _process_organization(db, client, org, since, force_update)
            for key in stats:
                stats[key] += org_stats.get(key, 0)
    except Exception as e:
        logger.error(f"Failed to scan tracker {tracker.id}: {e}", exc_info=True)
        stats["errors"] += 1

    return stats

def scan_account(
    db: Session, account_id: str, force_update: bool = False, since: Optional[datetime.datetime] = None
) -> Dict[str, Any]:
    """Scan all trackers for a given account."""
    account = crud_account.get(db, id=account_id)
    if not account:
        logger.error(f"Account with id {account_id} not found.")
        return {}

    total_stats = {"trackers": 0, "organizations": 0, "projects": 0, "issues": 0, "embeddings_updated": 0, "errors": 0}
    for tracker in account.trackers:
        if tracker.is_active:
            total_stats["trackers"] += 1
            tracker_stats = scan_tracker(db, tracker, force_update, since)
            for key in total_stats:
                total_stats[key] += tracker_stats.get(key, 0)
    return total_stats

def scan_all_accounts(db: Session, force_update: bool = False) -> Dict[str, Any]:
    """Scan all active accounts and their trackers."""
    accounts = crud_account.get_multi(db, skip=0, limit=1000)
    logger.info(f"Found {len(accounts)} accounts to scan.")
    overall_stats = {"accounts": 0, "trackers": 0, "organizations": 0, "projects": 0, "issues": 0, "embeddings_updated": 0, "errors": 0}
    for account in accounts:
        if account.is_active:
            overall_stats["accounts"] += 1
            account_stats = scan_account(db, account.id, force_update)
            for key in overall_stats:
                overall_stats[key] += account_stats.get(key, 0)

    logger.info(f"Finished scanning all accounts. Stats: {overall_stats}")
    return overall_stats
