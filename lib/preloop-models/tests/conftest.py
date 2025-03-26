"""Test fixtures for SpaceModels."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from spacemodels.models.base import Base


@pytest.fixture(scope="session")
def db_engine():
    """Create a test database engine."""
    # Use SQLite in-memory database for testing
    engine = create_engine("sqlite:///:memory:")

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    # Clean up (drop all tables)
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a new database session for a test."""
    # Create a new session for each test
    connection = db_engine.connect()
    transaction = connection.begin()

    # Create session factory bound to the connection
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = session_factory()

    yield session

    # Roll back the transaction after the test completes
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def create_account(db_session):
    """Create a test account."""
    import uuid

    from spacemodels.crud import crud_account

    def _create_account(username=None, email=None, **kwargs):
        # Generate unique username and email if not provided
        unique_id = str(uuid.uuid4())[:8]
        username = username or f"testuser_{unique_id}"
        email = email or f"test_{unique_id}@example.com"

        account_data = {
            "username": username,
            "email": email,
            "hashed_password": "hashed_password",
            "is_active": True,
            **kwargs,
        }
        return crud_account.create(db_session, obj_in=account_data)

    return _create_account


@pytest.fixture
def create_tracker(db_session, create_account):
    """Create a test tracker."""
    from spacemodels.crud import crud_tracker

    def _create_tracker(
        account=None, tracker_type="github", name="Test Tracker", **kwargs
    ):
        if account is None:
            account = create_account()

        tracker_data = {
            "name": name,
            "tracker_type": tracker_type,
            "account_id": account.id,
            "api_key": "test_api_key",
            "url": "https://example.com",
            "is_active": True,
            **kwargs,
        }
        return crud_tracker.create(db_session, obj_in=tracker_data)

    return _create_tracker


@pytest.fixture
def create_organization(db_session, create_tracker):
    """Create a test organization."""
    import uuid

    from spacemodels.crud import crud_organization

    def _create_organization(tracker=None, name=None, identifier=None, **kwargs):
        # Generate unique values if not provided
        unique_id = str(uuid.uuid4())[:8]
        name = name or f"Test Organization {unique_id}"
        identifier = identifier or f"test-org-{unique_id}"

        if tracker is None:
            tracker = create_tracker()

        org_data = {
            "name": name,
            "identifier": identifier,
            "tracker_id": tracker.id,
            "is_active": True,
            **kwargs,
        }
        return crud_organization.create(db_session, obj_in=org_data)

    return _create_organization


@pytest.fixture
def create_project(db_session, create_organization):
    """Create a test project."""
    from spacemodels.crud import crud_project

    def _create_project(name="Test Project", identifier="test-project", **kwargs):
        # Create organization first if not provided
        organization = kwargs.pop("organization", create_organization())

        project_data = {
            "name": name,
            "identifier": identifier,
            "organization_id": organization.id,
            "is_active": True,
            **kwargs,
        }
        return crud_project.create(db_session, obj_in=project_data)

    return _create_project


@pytest.fixture
def create_issue(db_session, create_project, create_tracker):
    """Create a test issue."""
    from spacemodels.crud import crud_issue

    def _create_issue(title="Test Issue", description="Test description", **kwargs):
        # Create project and tracker first if not provided
        project = kwargs.pop("project", create_project())
        tracker = kwargs.pop("tracker", create_tracker())

        issue_data = {
            "title": title,
            "description": description,
            "status": "open",
            "issue_type": "task",
            "project_id": project.id,
            "tracker_id": tracker.id,
            **kwargs,
        }
        return crud_issue.create(db_session, obj_in=issue_data)

    return _create_issue


@pytest.fixture
def create_embedding_model(db_session):
    """Create a test embedding model."""
    from spacemodels.crud import crud_embedding_model

    def _create_embedding_model(
        name="test-embedding",
        provider="openai",
        version="text-embedding-ada-002",
        dimensions=1536,
        **kwargs,
    ):
        model_data = {
            "name": name,
            "provider": provider,
            "version": version,
            "dimensions": dimensions,
            "is_active": True,
            "meta_data": {"test_mode": True},
            **kwargs,
        }
        return crud_embedding_model.create(db_session, obj_in=model_data)

    return _create_embedding_model
