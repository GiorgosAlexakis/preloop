"""Trackers router for registering and managing issue trackers."""

import logging
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from spacebridge.api.auth.jwt import get_current_active_user
from spacebridge.schemas.auth import TrackerRegisterRequest, UserResponse
from spacebridge.trackers.factory import create_tracker_client
from spacebridge.utils.email import send_tracker_registered_email
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.tracker import Tracker

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/trackers", status_code=status.HTTP_201_CREATED)
async def register_tracker(
    tracker_data: TrackerRegisterRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_active_user),
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
    # Validate tracker type
    valid_types = ["github", "gitlab", "jira"]
    if tracker_data.type.lower() not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tracker type. Must be one of: {', '.join(valid_types)}",
        )

    # For Jira, ensure username is present in config
    if tracker_data.type.lower() == "jira" and (
        not tracker_data.config or "username" not in tracker_data.config
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Jira tracker requires 'username' in config",
        )

    # Create a tracker client to test the connection
    try:
        # Create the client
        client = await create_tracker_client(
            tracker_type=tracker_data.type,
            base_url=tracker_data.url,
            token=tracker_data.token,
            config=tracker_data.config or {},
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
    # Since get_db_session() doesn't support async with, we'll use a manual approach
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Find current user's account
        account_result = session.execute(
            select(Account).where(Account.username == current_user.username)
        )
        account = account_result.scalars().first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User account not found",
            )

        # Check if a tracker with the same name already exists for this account
        existing_tracker = (
            session.execute(
                select(Tracker).where(
                    Tracker.name == tracker_data.name, Tracker.account_id == account.id
                )
            )
            .scalars()
            .first()
        )

        if existing_tracker:
            logger.warning(
                f"Tracker with name '{tracker_data.name}' already exists for account {account.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A tracker with name '{tracker_data.name}' already exists for your account",
            )

        # Log information before attempting to create the tracker
        logger.info(
            f"Creating new tracker: name='{tracker_data.name}', "
            f"type={tracker_data.type.lower()}, account_id={account.id}"
        )

        # First create the tracker with the account reference
        new_tracker = Tracker(
            name=tracker_data.name,
            tracker_type=tracker_data.type.lower(),
            url=tracker_data.url,
            api_key=tracker_data.token,  # In production, this should be encrypted
            connection_details=tracker_data.config or {},
            account_id=account.id,
            is_active=True,
        )

        session.add(new_tracker)

        try:
            session.flush()  # Save to get the tracker ID
        except Exception as flush_error:
            logger.error(
                f"Error during session.flush() for new tracker: {str(flush_error)}"
            )
            raise

        # Then create or find organization for this tracker
        org_result = session.execute(
            select(Organization).where(Organization.tracker_id == new_tracker.id)
        )
        org = org_result.scalars().first()

        if not org:
            # Create a default organization for the user with a unique identifier
            # that includes the tracker type and a timestamp to ensure uniqueness
            import uuid
            import re

            # Create a safe version of the tracker name for use in the identifier
            safe_tracker_name = re.sub(r"[^a-zA-Z0-9]", "-", tracker_data.name.lower())
            safe_tracker_name = re.sub(
                r"-+", "-", safe_tracker_name
            )  # Replace multiple dashes with a single one
            safe_tracker_name = safe_tracker_name[:20]  # Limit length

            # Create a unique identifier by combining username, tracker type, and a unique part
            org_identifier = f"{current_user.username.lower()}-{tracker_data.type.lower()}-{safe_tracker_name}"

            # Check if this identifier already exists
            existing_org = (
                session.execute(
                    select(Organization).where(
                        Organization.identifier == org_identifier
                    )
                )
                .scalars()
                .first()
            )

            # If it exists, make it truly unique by adding a short UUID
            if existing_org:
                short_uuid = str(uuid.uuid4())[:8]
                org_identifier = f"{org_identifier}-{short_uuid}"

            logger.info(f"Creating organization with identifier: {org_identifier}")

            org = Organization(
                name=f"{tracker_data.name} Organization",
                identifier=org_identifier,
                tracker_id=new_tracker.id,
                is_active=True,
            )
            session.add(org)
            try:
                session.commit()
            except IntegrityError as e:
                session.rollback()
                logger.error(f"Error creating organization: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create organization due to database constraint",
                )
            except Exception as e:
                session.rollback()
                logger.error(f"Error creating organization: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error creating organization",
                )

        session.add(new_tracker)
        session.commit()
        session.refresh(new_tracker)

        # Send email notification
        if current_user.email and current_user.email_verified:
            background_tasks.add_task(
                send_tracker_registered_email,
                user_email=current_user.email,
                tracker_name=new_tracker.name,
                tracker_type=new_tracker.tracker_type,
            )

        return {
            "id": str(new_tracker.id),
            "message": f"Tracker '{new_tracker.name}' registered successfully",
        }
    except IntegrityError as e:
        session.rollback()
        # Log the detailed error message for debugging
        error_msg = str(e)
        constraint_info = ""

        # Try to provide more specific information based on the error
        if "unique constraint" in error_msg.lower():
            if "name" in error_msg.lower():
                constraint_info = "A tracker with this name already exists."
            elif "url" in error_msg.lower():
                constraint_info = "A tracker with this URL already exists."
            else:
                constraint_info = "A duplicate entry exists in the database."

        logger.error(f"IntegrityError during tracker registration: {error_msg}")

        # Provide a more helpful error message
        detail_msg = f"Database constraint violation: {constraint_info or error_msg}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail_msg,
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Error registering tracker: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering tracker: {str(e)}",
        )
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


@router.get("/trackers", response_model=List[Dict])
async def list_trackers(
    current_user: UserResponse = Depends(get_current_active_user),
) -> List[Dict]:
    """List all trackers for the current user.

    Args:
        current_user: The current authenticated user.

    Returns:
        List of trackers.
    """
    # Since get_db_session() doesn't support async with, we'll use a manual approach
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Find the user's account
        account_result = session.execute(
            select(Account).where(Account.username == current_user.username)
        )
        account = account_result.scalars().first()

        if not account:
            return []

        # Get all trackers for the account
        tracker_result = session.execute(
            select(Tracker).where(Tracker.account_id == account.id)
        )
        trackers = tracker_result.scalars().all()

        return [
            {
                "id": str(tracker.id),
                "name": tracker.name,
                "type": tracker.tracker_type,
                "url": tracker.url,
                "created_at": tracker.created_at,
                "updated_at": tracker.updated_at,
            }
            for tracker in trackers
        ]
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


@router.get("/trackers/{tracker_id}", response_model=Dict)
async def get_tracker(
    tracker_id: UUID4,
    current_user: UserResponse = Depends(get_current_active_user),
) -> Dict:
    """Get a tracker by ID.

    Args:
        tracker_id: The tracker ID.
        current_user: The current authenticated user.

    Returns:
        The tracker details.

    Raises:
        HTTPException: If the tracker does not exist or the user does not have access.
    """
    # Since get_db_session() doesn't support async with, we'll use a manual approach
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Find the user's account
        account_result = session.execute(
            select(Account).where(Account.username == current_user.username)
        )
        account = account_result.scalars().first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracker not found",
            )

        # Get the tracker
        tracker_result = session.execute(
            select(Tracker)
            .where(Tracker.id == tracker_id)
            .where(Tracker.account_id == account.id)
        )
        tracker = tracker_result.scalars().first()

        if not tracker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracker not found",
            )

        # Get projects using this tracker
        projects_result = session.execute(
            select(Project).where(Project.tracker_id == tracker.id)
        )
        projects = projects_result.scalars().all()

        return {
            "id": str(tracker.id),
            "name": tracker.name,
            "type": tracker.tracker_type,
            "url": tracker.url,
            "config": tracker.config,
            "created_at": tracker.created_at,
            "updated_at": tracker.updated_at,
            "projects": [
                {
                    "id": str(project.id),
                    "name": project.name,
                    "external_id": project.external_id,
                }
                for project in projects
            ],
        }
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


@router.delete("/trackers/{tracker_id}", status_code=status.HTTP_200_OK)
async def delete_tracker(
    tracker_id: UUID4,
    current_user: UserResponse = Depends(get_current_active_user),
) -> Dict[str, str]:
    """Delete a tracker by ID.

    Args:
        tracker_id: The tracker ID.
        current_user: The current authenticated user.

    Returns:
        Success message.

    Raises:
        HTTPException: If the tracker does not exist or the user does not have access.
    """
    # Since get_db_session() doesn't support async with, we'll use a manual approach
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Find the user's account
        account_result = session.execute(
            select(Account).where(Account.username == current_user.username)
        )
        account = account_result.scalars().first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracker not found",
            )

        # Get the tracker
        tracker_result = session.execute(
            select(Tracker)
            .where(Tracker.id == tracker_id)
            .where(Tracker.account_id == account.id)
        )
        tracker = tracker_result.scalars().first()

        if not tracker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracker not found",
            )

        # Check if any projects are using this tracker
        projects_result = session.execute(
            select(Project).where(Project.tracker_id == tracker.id)
        )
        if projects_result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete tracker with associated projects",
            )

        # Delete the tracker
        session.delete(tracker)
        session.commit()

        return {"message": "Tracker deleted successfully"}
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass
