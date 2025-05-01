"""Trackers router for registering and managing issue trackers."""

import logging
import re
import uuid
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import UUID4
from sqlalchemy.exc import IntegrityError

from spacebridge.api.auth.jwt import get_current_active_user
from spacebridge.schemas.auth import UserResponse
from spacebridge.schemas.tracker import (
    TrackerResponse,
    TrackerUpdate,
    TrackerTestResponse,
    TrackerTestRequest,
)
from spacebridge.schemas.tracker import (
    OrganizationGroup,
    ProjectIdentifier,
)  # Corrected import location
from spacebridge.trackers.github.client import GitHubClient  # Added import
from spacebridge.trackers.gitlab.client import GitLabClient
from spacebridge.trackers.factory import create_tracker_client
from spacebridge.utils.email import send_tracker_registered_email
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.organization import Organization
from spacemodels.models.tracker import Tracker, TrackerType
from spacemodels.db.session import Session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/trackers/debug")
async def debug_tracker_request(request: Request):
    """Debug endpoint to see raw request data"""
    try:
        body = await request.json()
        print("DEBUG REQUEST BODY:", body)
        return {"received": body}
    except Exception as e:
        print("DEBUG ERROR:", str(e))
        return {"error": str(e)}


@router.post("/trackers", status_code=status.HTTP_201_CREATED)
async def register_tracker(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> Dict[str, str]:
    """Register a new issue tracker.

    Args:
        tracker_data: Tracker registration data.
        background_tasks: Background tasks for sending emails.
        current_user: The current authenticated user.

    Returns:
        The registered tracker ID.

    Raises:
        HTTPException: If registration fails.
    """
    # Parse request body manually
    try:
        data = await request.json()
        print("Raw request data:", data)

        # Extract fields from the raw data
        name = data.get("name")
        tracker_type_str = data.get("type")
        url_str = data.get("url")
        token = data.get("token")
        config = data.get("config")
        included_identifiers = data.get("included_project_identifiers", [])
        excluded_identifiers = data.get("excluded_project_identifiers", [])
        include_future = data.get(
            "include_future_projects", True
        )  # Default to True as per schema

        # Validate required fields
        if not name or not tracker_type_str or not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: name, type, token",
            )
    except Exception as e:
        logger.error(f"Error parsing request data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request format: {str(e)}",
        )

    # Convert tracker_type string to enum
    try:
        tracker_type = TrackerType(tracker_type_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tracker type: {tracker_type_str}",
        )

    # For Jira, ensure username is present in config
    if tracker_type == TrackerType.JIRA and (not config or "username" not in config):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jira tracker requires 'username' in connection_details",
        )

    # Create a tracker client to test the connection
    try:
        # Create the client
        client = await create_tracker_client(
            tracker_type=tracker_type.value,
            base_url=str(url_str) if url_str else None,
            token=token,
            config=config or {},
        )

        # Test the connection
        connection_result = await client.test_connection()

        if not connection_result.connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to connect to tracker: {connection_result.message}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing tracker connection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to tracker: {str(e)}",
        )

    # Create a new tracker in the database
    try:
        # Find current user's account
        account = (
            db.query(Account).filter(Account.username == current_user.username).first()
        )

        if not account:
            # This shouldn't happen if get_current_active_user works correctly
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found",
            )

        # Check if a tracker with the same name already exists for this account
        existing_tracker = (
            db.query(Tracker)
            .filter(Tracker.name == name, Tracker.account_id == account.id)
            .filter(Tracker.is_deleted.is_(False))  # Only check non-deleted trackers
            .first()
        )

        if existing_tracker:
            logger.warning(
                f"Tracker with name '{name}' already exists for account {account.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A tracker with name '{name}' already exists for your account",
            )

        # Log information before attempting to create the tracker
        logger.info(
            f"Creating new tracker: name='{name}', "
            f"type={tracker_type.value}, account_id={account.id}"
        )

        # Create the tracker with the account reference and project selection fields
        new_tracker = Tracker(
            name=name,
            tracker_type=tracker_type.value,
            url=str(url_str) if url_str else None,
            api_key=token,  # In production, this should be encrypted
            connection_details=config or {},
            account_id=account.id,
            is_active=True,
            meta_data={},
            included_project_identifiers=included_identifiers,
            excluded_project_identifiers=excluded_identifiers,
            include_future_projects=include_future,
        )

        db.add(new_tracker)
        db.flush()  # Get ID before creating org

        # Then create or find organization for this tracker
        # (Assuming one org per tracker for now, might need adjustment later)
        org = (
            db.query(Organization)
            .filter(Organization.tracker_id == new_tracker.id)
            .first()
        )

        if not org:
            # Create a default organization
            safe_tracker_name = re.sub(r"[^a-zA-Z0-9]", "-", name.lower())
            safe_tracker_name = re.sub(r"-+", "-", safe_tracker_name)[:20]
            org_identifier = f"{current_user.username.lower()}-{tracker_type.value}-{safe_tracker_name}"

            existing_org = (
                db.query(Organization)
                .filter(Organization.identifier == org_identifier)
                .first()
            )
            if existing_org:
                short_uuid = str(uuid.uuid4())[:8]
                org_identifier = f"{org_identifier}-{short_uuid}"

            logger.info(f"Creating organization with identifier: {org_identifier}")
            org = Organization(
                name=f"{name} Organization",
                identifier=org_identifier,
                tracker_id=new_tracker.id,
                is_active=True,
            )
            db.add(org)

        db.commit()
        db.refresh(new_tracker)

        # Send email notification
        if current_user.email and current_user.email_verified:
            background_tasks.add_task(
                send_tracker_registered_email,
                user_email=current_user.email,
                tracker_name=new_tracker.name,
                tracker_type=new_tracker.tracker_type,
            )

        return {"id": new_tracker.id}  # Return the tracker ID

    except IntegrityError as e:
        db.rollback()
        error_msg = str(e)
        constraint_info = ""
        if "unique constraint" in error_msg.lower():
            if "name" in error_msg.lower() and "account_id" in error_msg.lower():
                constraint_info = (
                    "A tracker with this name already exists for your account."
                )
            elif (
                "url" in error_msg.lower()
            ):  # Assuming URL might be unique per account too
                constraint_info = (
                    "A tracker with this URL already exists for your account."
                )
            else:
                constraint_info = (
                    "A duplicate entry exists (e.g., identifier conflict)."
                )
        logger.error(f"IntegrityError during tracker registration: {error_msg}")
        detail_msg = f"Database constraint violation: {constraint_info or error_msg}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail_msg,
        )
    except Exception as e:
        db.rollback()
        logger.exception(
            f"Error registering tracker: {str(e)}"
        )  # Use logger.exception for stack trace
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering tracker: {str(e)}",
        )


@router.get("/trackers", response_model=List[TrackerResponse])
async def list_trackers(
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> List[Tracker]:
    """List all non-deleted trackers for the current user."""
    account = (
        db.query(Account).filter(Account.username == current_user.username).first()
    )
    if not account:
        return []  # Or raise 404 if user must exist

    trackers = (
        db.query(Tracker)
        .filter(Tracker.account_id == account.id)
        .filter(Tracker.is_deleted.is_(False))
        .all()
    )
    return trackers  # FastAPI handles conversion via response_model


@router.get("/trackers/{tracker_id}", response_model=TrackerResponse)
async def get_tracker(
    tracker_id: UUID4,
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> Tracker:
    """Get a non-deleted tracker by ID, ensuring it belongs to the current user."""
    account = (
        db.query(Account).filter(Account.username == current_user.username).first()
    )
    if not account:
        # This case should ideally be handled by get_current_active_user dependency
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    tracker = (
        db.query(Tracker)
        .filter(Tracker.id == str(tracker_id))
        .filter(Tracker.account_id == account.id)
        .filter(Tracker.is_deleted.is_(False))
        .first()
    )

    if not tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracker not found or access denied",
        )

    # Note: Projects are not included in TrackerResponse by default.
    # If needed, fetch projects separately or adjust the response model.
    return tracker  # FastAPI handles conversion via response_model


@router.put("/trackers/{tracker_id}", response_model=TrackerResponse)
async def update_tracker(
    tracker_id: UUID4,
    tracker_update: TrackerUpdate,  # Use new update schema
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> Tracker:
    """Update an existing tracker."""
    account = (
        db.query(Account).filter(Account.username == current_user.username).first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    tracker = (
        db.query(Tracker)
        .filter(Tracker.id == str(tracker_id))
        .filter(Tracker.account_id == account.id)
        .filter(Tracker.is_deleted.is_(False))  # Can only update non-deleted trackers
        .first()
    )

    if not tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracker not found or access denied",
        )

    update_data = tracker_update.dict(exclude_unset=True)

    # Update fields
    for field, value in update_data.items():
        setattr(tracker, field, value)

    # Special handling if api_key is updated - revalidate connection?
    if "api_key" in update_data:
        # Optionally re-test connection here or mark as unvalidated
        tracker.is_valid = False
        tracker.last_validation = None
        tracker.validation_message = "API key updated, revalidation needed."
        logger.info(
            f"API key updated for tracker {tracker.id}, marked for revalidation."
        )

    try:
        db.add(tracker)
        db.commit()
        db.refresh(tracker)
        return tracker
    except IntegrityError as e:
        db.rollback()
        logger.error(f"IntegrityError updating tracker {tracker_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Update failed due to database constraint.",
        )
    except Exception as e:
        db.rollback()
        logger.exception(f"Error updating tracker {tracker_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating tracker.",
        )


@router.delete("/trackers/{tracker_id}", status_code=status.HTTP_200_OK)
async def delete_tracker(
    tracker_id: UUID4,
    current_user: UserResponse = Depends(get_current_active_user),
    hard_delete: bool = False,
    db: Session = Depends(get_db_session),
) -> Dict[str, str]:
    """Delete a tracker by ID (soft delete by default, hard delete if specified)."""
    account = (
        db.query(Account).filter(Account.username == current_user.username).first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    # Find the tracker, including potentially soft-deleted ones if hard_delete is true
    query = (
        db.query(Tracker)
        .filter(Tracker.id == str(tracker_id))
        .filter(Tracker.account_id == account.id)
    )
    if not hard_delete:
        query = query.filter(Tracker.is_deleted.is_(False))

    tracker = query.first()

    if not tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracker not found or access denied",
        )

    if hard_delete:
        logger.warning(
            f"Performing hard delete for tracker ID: {tracker.id} for user: {current_user.username}"
        )
        # TODO: Consider implications - delete related orgs/projects/issues?
        # Cascade might handle this, but needs verification.
        db.delete(tracker)
        message = "Tracker hard deleted successfully"
    else:
        if tracker.is_deleted:
            # Already soft-deleted, maybe return 200 OK or 404? Let's return OK.
            message = "Tracker already soft deleted"
        else:
            logger.info(
                f"Performing soft delete for tracker ID: {tracker.id} for user: {current_user.username}"
            )
            tracker.is_deleted = True
            tracker.is_active = False  # Also mark as inactive
            db.add(tracker)
            message = "Tracker soft deleted successfully"

    try:
        db.commit()
        return {"message": message}
    except Exception as e:
        db.rollback()
        logger.exception(f"Error during tracker deletion (ID: {tracker_id}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting tracker.",
        )


@router.post("/trackers/test-and-list-projects", response_model=TrackerTestResponse)
async def test_connection_and_list_projects(
    test_data: TrackerTestRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    # db: Session = Depends(get_db_session), # Not strictly needed for this endpoint
) -> TrackerTestResponse:
    """
    Tests connection to a tracker with provided credentials and lists accessible projects.
    Does not save the tracker configuration.

    Args:
        test_data: Temporary tracker connection details.
        current_user: The authenticated user performing the test.

    Returns:
        TrackerTestResponse indicating success/failure and the project list if successful.
    """
    logger.info(
        f"User {current_user.username} testing tracker connection for type {test_data.tracker_type.value}"
    )

    # Create a temporary tracker client
    try:
        client = await create_tracker_client(
            tracker_type=test_data.tracker_type.value,
            base_url=str(test_data.url) if test_data.url else None,
            token=test_data.api_key,
            config=test_data.connection_details or {},
        )
        if not client:
            raise ValueError(
                f"Could not create client for type {test_data.tracker_type.value}"
            )

        # Test the connection
        connection_result = await client.test_connection()

        if not connection_result.connected:
            logger.warning(
                f"Connection test failed for user {current_user.username}: {connection_result.message}"
            )
            return TrackerTestResponse(
                success=False, message=connection_result.message, projects=None
            )

        logger.info(f"Connection test successful for user {current_user.username}")

        # Fetch projects based on tracker type
        project_tree: List[OrganizationGroup] = []

        if test_data.tracker_type == TrackerType.GITHUB:
            logger.debug(
                "Tracker type is GitHub, fetching repositories grouped by owner."
            )
            # Ensure client is GitHubClient for type hinting, though factory should guarantee this
            if isinstance(client, GitHubClient):
                grouped_repos = await client.get_repositories_grouped_by_owner()
                for owner_group_data in grouped_repos:
                    # Use owner_login as the group ID and name for GitHub
                    owner_login = owner_group_data["owner_login"]
                    org_group = OrganizationGroup(id=owner_login, name=owner_login)
                    logger.debug(f"Processing owner group: {owner_login}")

                    for repo_data in owner_group_data.get("repositories", []):
                        # Use full_name as the project identifier for GitHub repos
                        repo_identifier = repo_data.get("identifier")
                        repo_name = repo_data.get("name")
                        if repo_identifier and repo_name:
                            logger.debug(f"Adding repository: {repo_identifier}")
                            org_group.children.append(
                                ProjectIdentifier(
                                    id=repo_identifier,
                                    name=repo_name,
                                    identifier=repo_identifier,
                                )
                            )
                        else:
                            logger.warning(
                                f"Skipping repository with missing identifier or name in group {owner_login}: {repo_data}"
                            )

                    if (
                        org_group.children
                    ):  # Only add group if it has valid repositories
                        project_tree.append(org_group)
                    else:
                        logger.debug(f"Skipping empty owner group: {owner_login}")
            else:
                logger.error(
                    f"Client type mismatch: Expected GitHubClient, got {type(client)}"
                )
                # Handle error appropriately, maybe raise HTTPException

        elif test_data.tracker_type == TrackerType.GITLAB:
            logger.debug("Tracker type is GitLab, fetching groups and projects.")
            # Ensure client is GitLabClient for type hinting and access to the new method
            if isinstance(client, GitLabClient):
                grouped_data = await client.get_groups_and_projects()
                for group_data in grouped_data:
                    # Use group_path as the OrganizationGroup ID and group_name as name
                    group_id = group_data.get("group_path")  # Use path for ID
                    group_name = group_data.get("group_name")

                    if not group_id or not group_name:
                        logger.warning(
                            f"Skipping GitLab group/user entry with missing path or name: {group_data}"
                        )
                        continue

                    org_group = OrganizationGroup(
                        id=str(group_id), name=group_name
                    )  # Ensure ID is string
                    logger.debug(
                        f"Processing GitLab group/user: {group_name} (Path: {group_id})"
                    )

                    for proj_data in group_data.get("projects", []):
                        # Use project 'identifier' (which is the stringified project ID)
                        proj_identifier = proj_data.get("identifier")
                        proj_name = proj_data.get("name")

                        if proj_identifier and proj_name:
                            # ProjectIdentifier expects string IDs
                            logger.debug(
                                f"Adding GitLab project: {proj_name} (Identifier: {proj_identifier})"
                            )
                            org_group.children.append(
                                ProjectIdentifier(
                                    id=proj_identifier,
                                    name=proj_name,
                                    identifier=proj_identifier,
                                )
                            )
                        else:
                            logger.warning(
                                f"Skipping GitLab project with missing identifier or name in group {group_name}: {proj_data}"
                            )

                    if org_group.children:  # Only add group if it has valid projects
                        project_tree.append(org_group)
                    else:
                        logger.debug(
                            f"Skipping empty GitLab group/user entry: {group_name}"
                        )
            else:
                logger.error(
                    f"Client type mismatch: Expected GitLabClient, got {type(client)}"
                )
                # Handle error appropriately

        else:
            # Existing logic for other non-GitHub/non-GitLab trackers (e.g., Jira)
            logger.debug(
                f"Tracker type is {test_data.tracker_type.value}, using default organization/project fetching."
            )
            # Note: This block assumes get_organizations and get_projects exist for other types
            try:
                organizations_data = (
                    await client.get_organizations()
                )  # This might raise AttributeError for unsupported types

                for org_data in organizations_data:
                    # Use helper methods if available, otherwise access directly
                    # Ensure org_data is treated as a dictionary for consistent access
                    org_dict = (
                        org_data
                        if isinstance(org_data, dict)
                        else getattr(org_data, "__dict__", {})
                    )
                    org_identifier = getattr(
                        client, "transform_organization", lambda x: x
                    )(org_dict).get("identifier")
                    org_name = getattr(client, "transform_organization", lambda x: x)(
                        org_dict
                    ).get("name")

                    if not org_identifier or not org_name:
                        logger.warning(
                            f"Skipping organization with missing identifier or name: {org_dict}"
                        )
                        continue

                    # Ensure org_identifier is a string for the OrganizationGroup id
                    org_id_str = str(org_identifier)
                    org_group = OrganizationGroup(id=org_id_str, name=org_name)
                    logger.debug(f"Processing organization: {org_name} ({org_id_str})")

                    try:
                        # Pass identifier as string to get_projects
                        projects_data = await client.get_projects(
                            org_id_str
                        )  # This might raise AttributeError
                        for proj_data in projects_data:
                            # Ensure proj_data is treated as a dictionary
                            proj_dict = (
                                proj_data
                                if isinstance(proj_data, dict)
                                else getattr(proj_data, "__dict__", {})
                            )
                            # Use helper methods if available
                            proj_identifier = getattr(
                                client, "_get_project_identifier", lambda x: x.get("id")
                            )(proj_dict)
                            # Pass org_id_str to transform_project helper if it exists
                            proj_name = getattr(
                                client, "transform_project", lambda x, y: x
                            )(proj_dict, org_id_str).get("name")

                            if proj_identifier and proj_name:
                                # Ensure ID and identifier are strings for ProjectIdentifier
                                proj_id_str = str(proj_identifier)
                                logger.debug(
                                    f"Adding project: {proj_name} ({proj_id_str})"
                                )
                                org_group.children.append(
                                    ProjectIdentifier(
                                        id=proj_id_str,
                                        name=proj_name,
                                        identifier=proj_id_str,
                                    )
                                )
                            else:
                                logger.warning(
                                    f"Skipping project with missing identifier or name in org {org_id_str}: {proj_dict}"
                                )

                    except AttributeError as attr_err:
                        logger.error(
                            f"Client for {test_data.tracker_type.value} missing expected method (e.g., get_projects): {attr_err}"
                        )
                        # Skip project fetching for this org if method is missing
                        if (
                            org_group.children
                        ):  # Still add org if it had children somehow? Unlikely.
                            project_tree.append(org_group)
                    except Exception as proj_error:
                        # Log specific error fetching projects for this org, but continue with others
                        logger.error(
                            f"Error fetching projects for org {org_id_str} ({org_name}): {proj_error}",
                            exc_info=True,
                        )

                    if (
                        org_group.children
                    ):  # Only add org if it has projects we could identify
                        project_tree.append(org_group)
                    else:
                        logger.debug(f"Skipping empty organization group: {org_name}")

            except AttributeError as attr_err:
                logger.error(
                    f"Client for {test_data.tracker_type.value} missing expected method (e.g., get_organizations): {attr_err}"
                )
                # Cannot proceed if get_organizations is missing
            except Exception as org_err:
                logger.exception(
                    f"Error fetching organizations for tracker type {test_data.tracker_type.value}: {org_err}"
                )

        # Sort the final tree by organization/owner name
        project_tree.sort(key=lambda group: group.name.lower())

        return TrackerTestResponse(
            success=True,
            message="Connection successful. Projects listed.",
            projects=project_tree,
        )

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions from client creation/testing
        raise http_exc
    except Exception as e:
        logger.error(
            f"Error during tracker test/list for user {current_user.username}: {e}",
            exc_info=True,
        )
        return TrackerTestResponse(
            success=False, message=f"An error occurred: {str(e)}", projects=None
        )
