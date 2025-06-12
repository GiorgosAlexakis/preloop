"""
Core scanning functionality for SpaceSync.
"""

import datetime
from datetime import timedelta
import os
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urljoin

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

POLLING_THRESHOLD = timedelta(seconds=os.getenv("POLLING_THRESHOLD", 3600))
RECHECK_PROJECT_WEBHOOK_INTERVAL = timedelta(days=1) # How often to re-check/register project webhooks

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
            xformed_issue_data = self.client.transform_issue(issue_data, project)

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
                    if i.external_id == xformed_issue_data.get("external_id")
                ),
                None,
            )

            issue_changed = False

            # Pop comments BEFORE creating or updating the issue to prevent AttributeError
            # The Issue model expects related Comment objects, not a list of dicts for 'comments' field
            comment_data: List[Dict] = xformed_issue_data.pop("comments", [])

            if current_issue_model:
                if (
                    current_issue_model.title != xformed_issue_data.get("title")
                    or current_issue_model.description != xformed_issue_data.get("description")
                    # Potentially add other fields that define an "update"
                ):
                    issue_changed = True
                # Ensure xformed_issue_data doesn't contain 'comments' when updating
                current_issue_model = crud_issue.update(db, db_obj=current_issue_model, obj_in=xformed_issue_data)
                logger.debug(f"Updated issue {current_issue_model.id} ({current_issue_model.title})")
            else:
                # Ensure xformed_issue_data doesn't contain 'comments' when creating
                current_issue_model = crud_issue.create(db, obj_in=xformed_issue_data)
                issue_changed = True
                logger.debug(f"Created issue {current_issue_model.id} ({current_issue_model.title})")

            issues_processed.append(current_issue_model)

            # Process comments after the issue has been created or retrieved
            if len(comment_data):
                logger.debug(f"Processing {len(comment_data)} comments for issue {current_issue_model.id}")

            db_comments_for_issue = crud_comment.get_multi_by_issue(db, issue_id=current_issue_model.id, limit=10000)
            db_comments_map_by_external_id = {
                c.external_id: c for c in db_comments_for_issue if c.external_id
            }

            for single_comment_data in comment_data:
                comment_changed = False
                xformed_comment_data = self.client.transform_comment(single_comment_data, current_issue_model.id)
                #Find if comment exists in db comparing commend_data id with db external_id
                db_comment = db_comments_map_by_external_id.get(xformed_comment_data.get("external_id"))
                if db_comment and db_comment.body != xformed_comment_data.get("body"):
                    # Check if comment needs update
                    db_comment = crud_comment.update(db, db_obj=db_comment, obj_in=xformed_comment_data)
                    comment_changed = True
                    logger.debug(f"Updated comment {db_comment.id} (external_id: {xformed_comment_data.get('external_id')})")
                elif not db_comment:
                    #Create comment
                    db_comment = crud_comment.create(db, obj_in=xformed_comment_data)
                    comment_changed = True
                    logger.debug(f"Created comment {db_comment.id} (external_id: {xformed_comment_data.get('external_id')})")
                # Generate comment embedding
                if comment_changed or force_update:
                    crud_issue_embedding.create_embeddings(
                                    db=db,
                                    issue_id=current_issue_model.id,
                                    comment_id=db_comment.id,
                                    force_update=force_update
                                )

            if issue_changed or force_update:
                embedding_updates += 1
                crud_issue_embedding.create_embeddings(db, issue_id=current_issue_model.id)
                logger.info(
                    f"Generated embeddings for issue {current_issue_model.id} - '{current_issue_model.title}'"
                )

        return issues_processed, embedding_updates

    def register_webhook(
        self, org_identifier: str, webhook_url: str, secret: str
    ) -> bool:
        """
        Register a webhook for the given organization/group.

        Args:
            org_identifier: The identifier of the organization/group.
            webhook_url: The target URL for the webhook.
            secret: The secret to use for the webhook.

        Returns:
            True if registration was successful, False otherwise.

        Raises:
            NotImplementedError: If the specific tracker client doesn't implement it.
        """
        # Delegate to the specific client implementation
        # For Jira, this method on the client itself is now more generic,
        # and the actual project-specific registration happens in _process_organization.
        # This base register_webhook on TrackerClient might need to be re-evaluated
        # or made more abstract if it's not directly used for group-level hooks by Jira.
        # For now, we assume it might be called by some generic logic, but Jira's
        # primary webhook setup is project-based within _process_organization.
        if self.tracker_type == "jira":
            # This generic org-level registration is not directly applicable to Jira's project-based webhooks.
            # The actual registration for Jira projects is handled in _process_organization.
            # However, to satisfy the interface, we can log a message or return a specific status.
            logger.warning(
                f"Org-level webhook registration via TrackerClient.register_webhook is not "
                f"the primary mechanism for Jira (tracker_id: {self.tracker.id}). "
                f"Project-specific webhooks are registered in _process_organization."
            )
            # Returning True to indicate it's not an error, but not a typical registration.
            # Or, raise NotImplementedError if this path should strictly not be taken for Jira.
            return True # Or False, or raise NotImplementedError

        return self.client.register_webhook(org_identifier=org_identifier, webhook_url=webhook_url, secret=secret)


# Helper function to process a single organization with polling checks
def _process_organization(
    db: Session,
    client: TrackerClient, # Pass the client instance
    org: Organization,
    since: datetime.datetime,
    force_update: bool,
    polling_threshold: timedelta,
) -> Tuple[Dict[str, Any], bool]:
    """
    Processes a single organization: checks polling conditions, scans if necessary,
    and updates the polling timestamp.

    Args:
        db: Database session.
        client: Initialized TrackerClient.
        org: The Organization object to process.
        since: Datetime threshold for scanning issues.
        force_update: Force embedding updates.
        polling_threshold: Timedelta threshold for skipping polling.

    Returns:
        A tuple containing:
        - A dictionary with scan statistics for this organization (projects, issues, embeddings_updated, errors).
        - A boolean indicating if polling was skipped (True if skipped, False if polled).
    """
    org_stats = {"projects": 0, "issues": 0, "embeddings_updated": 0, "errors": 0}
    now = datetime.datetime.now(datetime.timezone.utc)
    should_poll = True
    skipped = False

    # --- Webhook Registration Logic ---
    spacebridge_url_str = os.getenv("SPACEBRIDGE_URL")
    # This flag will determine if we save/update the org.webhook_secret.
    # It's true if org already has a secret, or if we successfully register a group hook,
    # or if (for GitLab CE) we successfully register at least one project hook AND the org secret wasn't set before.
    org_webhook_secret_should_be_set = bool(org.webhook_secret)
    temp_webhook_secret = None # Will hold newly generated secret if org doesn't have one

    if spacebridge_url_str:
        try:
            parsed_url = urlparse(spacebridge_url_str)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError("Invalid SPACEBRIDGE_URL format")

            webhook_target_path = f"/api/v1/private/webhooks/{client.tracker_type}/{org.identifier}"
            webhook_target_url = urljoin(spacebridge_url_str, webhook_target_path)

            if not org.webhook_secret:
                logger.info(f"Organization {org.id} ({org.name}) has no webhook secret. Will attempt registration.")
                temp_webhook_secret = secrets.token_hex(32) # Generate a potential secret
                current_secret_to_use = temp_webhook_secret
            else:
                logger.debug(f"Org {org.id} ({org.name}) already has a webhook secret. Will verify/update project webhooks if GitLab CE.")
                current_secret_to_use = org.webhook_secret

            gitlab_group_hooks_unsupported = False

            # --- 1. Attempt Group Webhook Registration (for all tracker types initially) ---
            if not org.webhook_secret: # Only attempt group registration if org doesn't have a secret yet
                if hasattr(client.client, "register_group_webhook"):
                    logger.info(f"Attempting group webhook registration for new org {org.id} ({client.tracker_type}).")
                    try:
                        group_hook_status = client.client.register_group_webhook(
                            org_identifier=org.identifier, webhook_url=webhook_target_url, secret=current_secret_to_use
                        )
                        if group_hook_status is True:
                            logger.info(f"Successfully registered group webhook for org {org.id}.")
                            org_webhook_secret_should_be_set = True # Mark that secret should be saved
                        elif group_hook_status == "group_hooks_not_supported":
                            if client.tracker_type == "gitlab":
                                logger.info(f"Group hooks not supported for GitLab org {org.id}. Will attempt project-level webhooks.")
                                gitlab_group_hooks_unsupported = True
                                if temp_webhook_secret: # This implies org.webhook_secret was initially None
                                    logger.info(f"Marking org {org.id} for secret save due to GitLab CE fallback.")
                                    org_webhook_secret_should_be_set = True
                            # For non-GitLab, "not_supported" is like a failure for setting the org secret via group hook
                        else: # False (error)
                            logger.warning(f"Group webhook registration failed for org {org.id}.")
                            org_stats["errors"] += 1
                    except Exception as e:
                        logger.error(f"Error during group webhook registration for org {org.id}: {e}", exc_info=True)
                        org_stats["errors"] += 1
                elif hasattr(client.client, "register_webhook"): # Fallback for GitHub etc.
                    logger.info(f"Attempting generic webhook registration for new org {org.id} ({client.tracker_type}).")
                    try:
                        success = client.client.register_webhook(
                            org_identifier=org.identifier, webhook_url=webhook_target_url, secret=current_secret_to_use
                        )
                        if success:
                            logger.info(f"Successfully registered generic webhook for org {org.id}.")
                            org_webhook_secret_should_be_set = True
                        else:
                            logger.warning(f"Generic webhook registration failed for org {org.id}.")
                            org_stats["errors"] += 1
                    except Exception as e:
                        logger.error(f"Error registering generic webhook for org {org.id}: {e}", exc_info=True)
                        org_stats["errors"] += 1

            # --- 2. Handle GitLab CE Project-Level Webhooks ---
            # This runs if a) it's GitLab and group hooks were unsupported OR
            # b) it's GitLab, org already has a secret (implying CE setup), so we need to check projects.
            if client.tracker_type == "gitlab" and (gitlab_group_hooks_unsupported or org.webhook_secret):
                if not current_secret_to_use: # Should only happen if org had no secret and group reg failed before CE check
                     logger.error(f"Cannot proceed with GitLab project webhooks for org {org.id}: no secret available.")
                else:
                    logger.info(f"Processing project-level webhooks for GitLab org {org.id} ({org.name}). Using secret: {'existing' if org.webhook_secret else 'newly_generated'}")
                    projects_for_org = client.scan_projects(db, org)
                    if not projects_for_org:
                        logger.info(f"No projects found for GitLab org {org.id} to check/register project webhooks.")

                    project_hooks_newly_registered_count = 0
                    for project_to_hook in projects_for_org:
                        # Check if project model has 'webhook_last_verified_at' and if it's recent
                        needs_check = True
                        if hasattr(project_to_hook, "webhook_last_verified_at") and project_to_hook.webhook_last_verified_at:
                            if (now - project_to_hook.webhook_last_verified_at) <= RECHECK_PROJECT_WEBHOOK_INTERVAL:
                                logger.debug(f"Skipping webhook check for project {project_to_hook.identifier}, recently verified at {project_to_hook.webhook_last_verified_at}.")
                                needs_check = False

                        if needs_check:
                            logger.info(f"Checking/Registering project webhook for project {project_to_hook.identifier} in org {org.id}.")
                            try:
                                project_hook_success = client.client.register_project_webhook(
                                    project_id_or_path=project_to_hook.identifier,
                                    webhook_url=webhook_target_url,
                                    secret=current_secret_to_use
                                )
                                if project_hook_success:
                                    logger.info(f"Project webhook for project {project_to_hook.identifier} is active/registered.")
                                    if not org.webhook_secret: # If org secret wasn't set yet, this counts as a success to set it
                                        project_hooks_newly_registered_count += 1
                                else: # False from register_project_webhook
                                    logger.warning(f"Failed to ensure project webhook for project {project_to_hook.identifier} in org {org.id}.")
                                    org_stats["errors"] +=1

                                # Update verification timestamp on the project model
                                if hasattr(project_to_hook, "webhook_last_verified_at"):
                                    project_to_hook.webhook_last_verified_at = now
                                    db.add(project_to_hook) # Stage for commit
                                else:
                                    logger.warning(f"Project model for {project_to_hook.identifier} missing 'webhook_last_verified_at' attribute.")

                            except Exception as e:
                                logger.error(f"Error during project webhook processing for {project_to_hook.identifier}: {e}", exc_info=True)
                                org_stats["errors"] += 1

                    if project_hooks_newly_registered_count > 0 and not org.webhook_secret:
                        org_webhook_secret_should_be_set = True # Mark that the temp secret should be saved to org

            # --- 3. Handle Jira Project-Level Webhooks ---
            elif client.tracker_type == "jira":
                if not current_secret_to_use:
                    logger.error(f"Cannot proceed with Jira project webhooks for instance {org.identifier}: no secret available.")
                else:
                    logger.info(f"Processing project-level webhooks for Jira instance {org.identifier} (Org ID: {org.id}). Using secret: {'existing' if org.webhook_secret else 'newly_generated'}")
                    # For Jira, "organization" is the Jira instance. We need to scan its projects.
                    # Ensure projects are scanned/fetched first to iterate through them.
                    projects_for_jira_instance = client.scan_projects(db, org)
                    if not projects_for_jira_instance:
                        logger.info(f"No projects found for Jira instance {org.identifier} to register webhooks.")
                    else:
                        jira_project_hooks_registered_count = 0
                        for jira_project in projects_for_jira_instance:
                            # Check if this project needs a webhook update (e.g., based on last_webhook_check_at)
                            needs_hook_check = True # Default to true
                            # Ensure last_webhook_check_at is a datetime object if it exists
                            last_check_time = getattr(jira_project, 'last_webhook_check_at', None)
                            if last_check_time and isinstance(last_check_time, datetime.datetime):
                                if (now.replace(tzinfo=None) - last_check_time) < RECHECK_PROJECT_WEBHOOK_INTERVAL:
                                    logger.debug(f"Skipping webhook check for Jira project {jira_project.identifier}, recently checked at {last_check_time}.")
                                    needs_hook_check = False
                            elif last_check_time: # Exists but not a datetime, log warning
                                logger.warning(f"last_webhook_check_at for Jira project {jira_project.identifier} is not a datetime object: {last_check_time}. Proceeding with check.")


                            if needs_hook_check and hasattr(client.client, "register_webhook"): # JiraTracker has register_webhook
                                project_key_to_use = jira_project.slug or jira_project.identifier
                                if not project_key_to_use:
                                    logger.warning(f"Skipping Jira project {jira_project.name} as it has no slug or identifier for webhook registration.")
                                    continue

                                logger.info(f"Checking/Registering webhook for Jira project {project_key_to_use}.")
                                try:
                                    # Jira's register_webhook takes project_key, webhook_url, secret, events
                                    # webhook_target_url is generic for SpaceBridge. Jira client appends project_key & secret.
                                    jira_hook_status = client.client.register_webhook(
                                        project_key=project_key_to_use,
                                        webhook_url=webhook_target_url, # Base URL for SpaceBridge
                                        secret=current_secret_to_use,
                                        # events=None will use defaults in JiraTracker
                                    )
                                    if jira_hook_status is True: # True means registered or already exists correctly
                                        logger.info(f"Successfully registered/verified webhook for Jira project {project_key_to_use}.")
                                        jira_project_hooks_registered_count += 1
                                        # Update last_webhook_check_at for the project
                                        crud_project.update(db, db_obj=jira_project, obj_in={"last_webhook_check_at": now.replace(tzinfo=None)})
                                    else: # False (error)
                                        logger.warning(f"Jira project webhook registration failed for {project_key_to_use}.")
                                        org_stats["errors"] += 1
                                except Exception as e:
                                    logger.error(f"Error registering webhook for Jira project {project_key_to_use}: {e}", exc_info=True)
                                    org_stats["errors"] += 1
                            elif not hasattr(client.client, "register_webhook"):
                                logger.error(f"JiraTracker instance is missing 'register_webhook' method for project {jira_project.identifier}. This should not happen.")
                                break # Stop trying for other projects if method is missing on client

                        if jira_project_hooks_registered_count > 0 and not org.webhook_secret:
                            # If at least one Jira project hook was set up and the "org" (Jira instance)
                            # didn't have a secret before, then mark the org's secret as needing to be set.
                            org_webhook_secret_should_be_set = True
                            logger.info(f"Successfully registered {jira_project_hooks_registered_count} project webhooks for Jira instance {org.identifier}. Org secret will be set.")

            # --- 4. Save Organization's Webhook Secret if marked ---
            if org_webhook_secret_should_be_set and temp_webhook_secret and not org.webhook_secret:
                # temp_webhook_secret will exist if org didn't have a secret initially
                try:
                    logger.info(f"Saving newly generated webhook secret and updating last_webhook_update for org {org.id}.")
                    crud_organization.update(
                        db, db_obj=org, obj_in={"webhook_secret": temp_webhook_secret, "last_webhook_update": now}
                    )
                    # db.commit() will happen with project timestamp updates later or at end of _process_organization
                    org = db.merge(org) # Refresh org state with the new secret
                    logger.info(f"Successfully saved new webhook secret for org {org.id}.")
                except Exception as e:
                    logger.error(f"Failed to save webhook secret for org {org.id}: {e}", exc_info=True)
                    db.rollback() # Rollback only this attempt to save secret
                    org_stats["errors"] += 1
                    # If saving fails, subsequent runs will try to generate a new temp_secret and re-register.

        except ValueError as e: # For SPACEBRIDGE_URL format error
            logger.warning(f"SPACEBRIDGE_URL is invalid ({spacebridge_url_str}): {e}. Skipping webhook registration.")
        except Exception as e: # Catch-all for other setup errors
            logger.error(f"Unexpected error during webhook registration setup for org {org.id}: {e}", exc_info=True)
            org_stats["errors"] += 1
    else: # SPACEBRIDGE_URL not set
        logger.info("SPACEBRIDGE_URL not set. Skipping webhook registration.")

    # --- Polling Logic ---
    # Check polling conditions only if webhook wasn't just handled (or if handling failed but we still might poll)
    # Note: The original logic prioritizes skipping based on recent updates.

    # Ensure datetime objects are timezone-aware (UTC) for comparison
    last_webhook_update_aware: Optional[datetime.datetime] = None
    if org.last_webhook_update:
        if org.last_webhook_update.tzinfo is None:
            # Assume naive datetime from DB is UTC, as per DateTime(timezone=True) intention
            last_webhook_update_aware = org.last_webhook_update.replace(tzinfo=datetime.timezone.utc)
        else:
            # Convert to UTC if it's already aware but possibly different timezone
            last_webhook_update_aware = org.last_webhook_update.astimezone(datetime.timezone.utc)

    last_polling_update_aware: Optional[datetime.datetime] = None
    if org.last_polling_update:
        if org.last_polling_update.tzinfo is None:
            # Assume naive datetime from DB is UTC
            last_polling_update_aware = org.last_polling_update.replace(tzinfo=datetime.timezone.utc)
        else:
            # Convert to UTC if it's already aware
            last_polling_update_aware = org.last_polling_update.astimezone(datetime.timezone.utc)

    if last_webhook_update_aware and (now - last_webhook_update_aware) < polling_threshold:
        logger.info(f"Skipping polling for org {org.id} ({org.name}) due to recent webhook update at {org.last_webhook_update}")
        should_poll = False
        skipped = True
    elif last_polling_update_aware and (now - last_polling_update_aware) < polling_threshold:
        logger.info(f"Skipping polling for org {org.id} ({org.name}) due to recent polling at {org.last_polling_update}")
        should_poll = False
        skipped = True

    # Proceed with polling if conditions allow
    if should_poll:
        logger.info(f"Proceeding with polling for org {org.id} ({org.name})")
        try:
            # Scan projects for this organization
            projects = client.scan_projects(db, org)
            org_stats["projects"] = len(projects)

            # Scan issues for each project within this organization
            for project in projects:
                # Ensure the org object is available (it should be 'org' from the outer loop)
                issues, embedding_updates = client.scan_issues(
                    db, org, project, since, force_update
                )
                org_stats["issues"] += len(issues)
                org_stats["embeddings_updated"] += embedding_updates

            # Update last_polling_update timestamp for this organization
            try:
                crud_organization.update(
                    db, db_obj=org, obj_in={"last_polling_update": now}
                )
                # Commit immediately after processing one org successfully
                # This makes the update visible sooner for subsequent runs/checks
                db.commit()
                logger.info(f"Updated last_polling_update for org {org.id} to {now}")
            except Exception as e:
                logger.error(f"Failed to update last_polling_update for org {org.id}: {e}", exc_info=True)
                db.rollback() # Rollback timestamp update failure
                org_stats["errors"] += 1

        except Exception as e:
             logger.error(f"Error scanning projects/issues for org {org.id} ({org.name}): {e}", exc_info=True)
             org_stats["errors"] += 1
             db.rollback() # Rollback potential partial changes within the org scan

    return org_stats, skipped


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
    # Define the time threshold for skipping polling
    stats = {
        "organizations_scanned": 0, # Renamed for clarity
        "organizations_skipped_webhook": 0,
        "organizations_skipped_polling": 0,
        "projects": 0,
        "issues": 0,
        "embeddings_updated": 0,
        "errors": 0, # Note: Error tracking might need refinement
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
    # Scan organizations first to get the list
    try:
        orgs = client.scan_organizations(db)
        logger.info(f"Found {len(orgs)} organizations associated with tracker {tracker.id}")
    except Exception as e:
        logger.error(f"Failed to scan organizations for tracker {tracker.id}: {e}", exc_info=True)
        stats["errors"] += 1
        orgs = [] # Ensure orgs is an empty list if scanning fails

    # Process each organization using the helper function
    for org in orgs:
        org_stats, skipped = _process_organization(
            db=db,
            client=client,
            org=org,
            since=since,
            force_update=force_update,
            polling_threshold=POLLING_THRESHOLD,
        )

        # Aggregate stats
        if skipped:
            # Increment appropriate skipped counter (logic inside helper determines why)
            # We need to check the org object again as the helper doesn't return *why* it skipped
            now = datetime.datetime.now(datetime.timezone.utc) # Re-get current time for accurate check
            if org.last_webhook_update and (now - org.last_webhook_update) < POLLING_THRESHOLD:
                 stats["organizations_skipped_webhook"] += 1
            elif org.last_polling_update and (now - org.last_polling_update) < POLLING_THRESHOLD:
                 stats["organizations_skipped_polling"] += 1
            # Note: There's a slight edge case if the state changed between the helper check and here,
            # but it's acceptable for logging/stats purposes.
        else:
            stats["organizations_scanned"] += 1
            stats["projects"] += org_stats["projects"]
            stats["issues"] += org_stats["issues"]
            stats["embeddings_updated"] += org_stats["embeddings_updated"]
            stats["errors"] += org_stats["errors"]

    # Update tracker's last_scan_time (this is separate from org polling time)
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
        print(f"  Organizations Scanned: {stats['organizations_scanned']}")
        print(f"  Organizations Skipped (Webhook): {stats['organizations_skipped_webhook']}")
        print(f"  Organizations Skipped (Polling): {stats['organizations_skipped_polling']}")
        print(f"  Projects Scanned: {stats['projects']}")
        print(f"  Issues Scanned: {stats['issues']}")
        print(f"  Embeddings Updated: {stats['embeddings_updated']}")
        print(f"  Errors Encountered: {stats['errors']}")
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
        "organizations_scanned": 0,
        "organizations_skipped_webhook": 0,
        "organizations_skipped_polling": 0,
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
        account_stats["organizations_scanned"] += stats["organizations_scanned"]
        account_stats["organizations_skipped_webhook"] += stats["organizations_skipped_webhook"]
        account_stats["organizations_skipped_polling"] += stats["organizations_skipped_polling"]
        account_stats["projects"] += stats["projects"]
        account_stats["issues"] += stats["issues"]
        account_stats["embeddings_updated"] += stats["embeddings_updated"]

    account_stats["duration_seconds"] = time.time() - start_time

    if verbose:
        print(f"\nAccount {account_id} scan completed:")
        print(f"  Trackers scanned: {account_stats['trackers_scanned']}")
        print(f"  Trackers with errors: {account_stats['trackers_with_errors']}")
        print(f"  Total Organizations Scanned: {account_stats['organizations_scanned']}")
        print(f"  Total Organizations Skipped (Webhook): {account_stats['organizations_skipped_webhook']}")
        print(f"  Total Organizations Skipped (Polling): {account_stats['organizations_skipped_polling']}")
        print(f"  Total Projects Scanned: {account_stats['projects']}")
        print(f"  Total Issues Scanned: {account_stats['issues']}")
        print(f"  Total Embeddings Updated: {account_stats['embeddings_updated']}")
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
        overall_stats["total_organizations"] += account_stats["organizations_scanned"]
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
