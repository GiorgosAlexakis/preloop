"""Trackers router for registering and managing issue trackers."""

import logging
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from spacebridge.api.auth.jwt import get_current_active_user
from spacebridge.schemas.auth import UserResponse
from spacebridge.schemas.tracker import (
    TrackerResponse,
    TrackerUpdate,
    TrackerTestResponse,
    TrackerTestRequest,
)
from spacebridge.schemas.tracker import (
    ProjectIdentifier,
)  # Corrected import location
from spacebridge.trackers.factory import create_tracker_client
from spacebridge.utils.email import send_tracker_registered_email
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.tracker import Tracker, TrackerType, TrackerScopeRule

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
        scope_rules_data = data.get("scope_rules", [])

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
        scope_rules = [TrackerScopeRule(**rule) for rule in scope_rules_data]

        new_tracker = Tracker(
            name=name,
            tracker_type=tracker_type.value,
            url=str(url_str) if url_str else None,
            api_key=token,  # In production, this should be encrypted
            connection_details=config or {},
            account_id=account.id,
            is_active=True,
            meta_data={},
            scope_rules=scope_rules,
        )

        db.add(new_tracker)
        db.flush()  # Get ID before creating org

        # Then create or find organization for this tracker
        # (Assuming one org per tracker for now, might need adjustment later)
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
    update_data = tracker_update.model_dump(exclude_unset=True)

    # Handle scope_rules separately
    if "scope_rules" in update_data:
        # Delete existing scope rules
        db.query(TrackerScopeRule).filter(
            TrackerScopeRule.tracker_id == tracker.id
        ).delete(synchronize_session=False)

        # Create new scope rules from the payload
        new_scope_rules_data = update_data.pop("scope_rules")
        if new_scope_rules_data is not None:
            new_scope_rules = [
                TrackerScopeRule(**rule_data) for rule_data in new_scope_rules_data
            ]
            tracker.scope_rules = new_scope_rules

    # Update other fields
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
        logger.info(f"Updating tracker {tracker_id} with data: {update_data}")
        db.merge(tracker)
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
        logger.exception(
            f"Error during tracker deletion (ID: {tracker_id}): {e}"
        )  # Use logger.exception for stack trace
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting tracker.",
        )


@router.post("/trackers/test-and-list-orgs", response_model=TrackerTestResponse)
async def test_connection_and_list_orgs(
    test_data: TrackerTestRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> TrackerTestResponse:
    """
    Tests connection to a tracker and lists accessible organizations/groups.
    This endpoint does not fetch the projects within each organization.
    """
    logger.info(
        f"User {current_user.username} testing tracker connection for type {test_data.tracker_type.value}"
    )
    if test_data.tracker_id:
        tracker = (
            db.query(Tracker)
            .filter(Tracker.account_id == current_user.id)
            .filter(Tracker.id == test_data.tracker_id)
            .first()
        )
        if not tracker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracker not found or access denied",
            )
        test_data.api_key = tracker.api_key
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

        connection_result = await client.test_connection()
        if not connection_result.connected:
            logger.warning(
                f"Connection test failed for user {current_user.username}: {connection_result.message}"
            )
            return TrackerTestResponse(
                success=False, message=connection_result.message, orgs=[]
            )

        logger.info(f"Connection test successful for user {current_user.username}")

        orgs = await client.get_organizations()
        if len(orgs) == 1:
            projects = await client.list_projects(orgs[0].id)
            orgs[0].children = [
                ProjectIdentifier(id=p.id, name=p.name, identifier=p.id, type="project")
                for p in projects
            ]
        return TrackerTestResponse(
            success=True,
            message="Connection successful!",
            orgs=orgs,
        )

    except Exception as e:
        logger.exception(
            f"Error during tracker org list for user {current_user.username}: {e}"
        )
        return TrackerTestResponse(
            success=False, message=f"An unexpected error occurred: {e}", orgs=[]
        )


@router.post("/trackers/list-projects-for-org", response_model=List[ProjectIdentifier])
async def list_projects_for_org(
    test_data: TrackerTestRequest,
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
) -> List[ProjectIdentifier]:
    """
    Lists projects for a specific organization/group within a tracker.
    """
    logger.info(
        f"User {current_user.username} listing projects for org {test_data.organization_identifier} "
        f"in tracker type {test_data.tracker_type.value}"
    )
    if test_data.tracker_id:
        tracker = (
            db.query(Tracker)
            .filter(Tracker.account_id == current_user.id)
            .filter(Tracker.id == test_data.tracker_id)
            .first()
        )
        if not tracker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracker not found or access denied",
            )
        test_data.api_key = tracker.api_key

    try:
        if test_data.url and not test_data.url.endswith("/"):
            test_data.url = test_data.url + "/"
        client = await create_tracker_client(
            tracker_type=test_data.tracker_type.value,
            base_url=str(test_data.url) if test_data.url else None,
            token=test_data.api_key,
            config=test_data.connection_details or {},
        )
        if not client:
            raise HTTPException(
                status_code=400, detail="Could not create tracker client"
            )
        return await client.list_projects(test_data.organization_identifier)

    except Exception as e:
        logger.exception(
            f"Error listing projects for org for user {current_user.username}: {e}"
        )
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )
