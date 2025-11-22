"""Initialize test data for SpaceBridge."""

import asyncio
import logging
import uuid

from passlib.context import CryptContext
from sqlalchemy.exc import SQLAlchemyError

from spacemodels.crud.account import CRUDAccount
from spacemodels.crud.organization import CRUDOrganization
from spacemodels.crud.project import CRUDProject
from spacemodels.crud.tracker import CRUDTracker
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.organization import Organization
from spacemodels.models.project import Project
from spacemodels.models.tracker import Tracker, TrackerType

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_test_data():
    """Create test data for the SpaceBridge server."""
    session_generator = get_db_session()
    db = next(session_generator)
    crud_account = CRUDAccount(Account)
    crud_tracker = CRUDTracker(Tracker)
    crud_organization = CRUDOrganization(Organization)
    crud_project = CRUDProject(Project)

    try:
        # Create a test account if it doesn't exist
        account = crud_account.get_by_email(db, email="admin@spacecode.ai")
        if account:
            logger.info(
                f"Account already exists: {account.username} (ID: {account.id})"
            )
        else:
            # Hash the password
            hashed_password = pwd_context.hash("admin")

            logger.info("Creating admin account...")
            account = crud_account.create(
                db,
                obj_in={
                    "id": str(uuid.uuid4()),
                    "username": "admin",
                    "email": "admin@spacecode.ai",
                    "full_name": "Admin User",
                    "hashed_password": hashed_password,
                    "is_active": True,
                    "is_superuser": True,
                    "meta_data": {"admin_account": True},
                },
            )
            logger.info(f"Created account: {account.username} (ID: {account.id})")

        # Create a tracker if it doesn't exist
        tracker = crud_tracker.get_for_account(db, account_id=account.id)
        if tracker and len(tracker) > 0:
            logger.info(
                f"Tracker already exists: {tracker[0].name} (ID: {tracker[0].id})"
            )
            tracker = tracker[0]
        else:
            logger.info("Creating GitHub tracker...")
            tracker = crud_tracker.create(
                db,
                obj_in={
                    "id": str(uuid.uuid4()),
                    "name": "GitHub Issues",
                    "tracker_type": TrackerType.GITHUB.value,
                    "account_id": account.id,
                    "is_active": True,
                    "url": "https://api.github.com",
                    "api_key": "github_pat_mock_token",
                    "connection_details": {"repository": "spacecode/astrobot"},
                    "meta_data": {"integration_type": "personal_access_token"},
                },
            )
            logger.info(f"Created tracker: {tracker.name} (ID: {tracker.id})")

        # Create an organization if it doesn't exist
        org = crud_organization.get_by_identifier(db, identifier="spacecode")
        if org:
            logger.info(f"Organization already exists: {org.name} (ID: {org.id})")
        else:
            # Create organization
            logger.info("Creating test organization...")
            org = crud_organization.create(
                db,
                obj_in={
                    "id": str(uuid.uuid4()),
                    "name": "Spacecode AI",
                    "identifier": "spacecode",
                    "description": "Spacecode AI organization for testing",
                    "tracker_id": tracker.id,
                    "is_active": True,
                    "settings": {"default_tracker": tracker.id},
                    "meta_data": {"industry": "Technology", "size": "Startup"},
                },
            )
            logger.info(f"Created organization: {org.name} (ID: {org.id})")

        # Create a project if it doesn't exist
        project = crud_project.get_by_identifier(
            db, organization_id=org.id, identifier="astrobot"
        )
        if project:
            logger.info(f"Project already exists: {project.name} (ID: {project.id})")
        else:
            # Create project
            logger.info("Creating test project...")
            project = crud_project.create(
                db,
                obj_in={
                    "id": str(uuid.uuid4()),
                    "name": "Astrobot",
                    "identifier": "astrobot",
                    "description": "Astrobot project for testing",
                    "organization_id": org.id,
                    "is_active": True,
                    "settings": {"visibility": "public"},
                    "tracker_settings": {
                        "github": {
                            "repository": "spacecode/astrobot",
                            "credentials": "github_pat_mock_token",
                        }
                    },
                    "meta_data": {"team": "Engineering"},
                },
            )
            logger.info(f"Created project: {project.name} (ID: {project.id})")

        logger.info("Test data setup complete")

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error creating test data: {e}")
        raise
    finally:
        db.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


def main():
    """Main function to create test data."""
    try:
        # First ensure the database tables exist using Alembic
        import os
        import subprocess

        # Get the SpaceModels directory path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        spacemodels_dir = os.path.join(os.path.dirname(script_dir), "SpaceModels")

        logger.info(
            "Running Alembic migrations to ensure database schema is up to date..."
        )

        # Run alembic upgrade head
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=spacemodels_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Alembic migration failed: {result.stderr}")
            raise RuntimeError(f"Failed to run database migrations: {result.stderr}")

        logger.info("Database schema initialized successfully via Alembic")

        # Now create the test data
        asyncio.run(create_test_data())
        logger.info("Test data creation completed successfully")
    except Exception as e:
        logger.error(f"Failed to create test data: {e}")
        raise


if __name__ == "__main__":
    main()
