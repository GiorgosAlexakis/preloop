"""Initialize test data for SpaceBridge."""

import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from spacebridge.db.session import get_db
from spacebridge.models.organization import Organization
from spacebridge.models.project import Project

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_test_data():
    """Create test data for the SpaceBridge server."""
    db = next(get_db())

    try:
        # Check if organization already exists
        org = (
            db.query(Organization)
            .filter(Organization.identifier == "spacecode")
            .first()
        )

        if org:
            logger.info(f"Organization already exists: {org.name} (ID: {org.id})")
        else:
            # Create organization
            logger.info("Creating test organization...")
            org = Organization(
                id=str(uuid.uuid4()),  # Generate a UUID for the organization
                name="SpaceCode",
                identifier="spacecode",
                description="SpaceCode organization for testing",
                settings={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(org)
            db.commit()
            db.refresh(org)
            logger.info(f"Created organization: {org.name} (ID: {org.id})")

        # Check if project already exists
        project = (
            db.query(Project)
            .filter(Project.identifier == "astrobot", Project.organization_id == org.id)
            .first()
        )

        if project:
            logger.info(f"Project already exists: {project.name} (ID: {project.id})")
        else:
            # Create project
            logger.info("Creating test project...")
            project = Project(
                id=str(uuid.uuid4()),  # Generate a UUID for the project
                name="Astrobot",
                identifier="astrobot",
                description="Astrobot project for testing",
                organization_id=org.id,
                settings={},
                tracker_configurations={
                    "github": {
                        "repository": "spacecode/astrobot",
                        "credentials": "dummy_credentials",
                    }
                },
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            logger.info(f"Created project: {project.name} (ID: {project.id})")

        logger.info("Test data setup complete")

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error creating test data: {e}")
        raise
    finally:
        db.close()


def main():
    """Main function to create test data."""
    try:
        asyncio.run(create_test_data())
    except Exception as e:
        logger.error(f"Failed to create test data: {e}")
        raise


if __name__ == "__main__":
    main()
