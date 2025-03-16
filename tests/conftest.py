"""Pytest configuration file for SpaceBridge tests."""

from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Try to import FastAPI, but don't fail if it's not available
try:
    import fastapi  # noqa: F401

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# These will be implemented as the project progresses
# from spacebridge.api.app import create_app
# from spacebridge.db.base import Base
# from spacebridge.db.session import get_db


@pytest.fixture(scope="session")
def db_engine():
    """Create a database engine for testing."""
    # Use an in-memory SQLite database for tests
    return create_engine("sqlite:///:memory:")


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    """Create a database session factory for testing."""
    # Create tables in the test database
    # Base.metadata.create_all(db_engine)

    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture(scope="function")
def db_session(db_session_factory) -> Generator[Session, None, None]:
    """Create a database session for each test function."""
    session = db_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def app(db_session):
    """Create a FastAPI app for testing."""
    # Dependency override for database session
    # app = create_app()
    # app.dependency_overrides[get_db] = lambda: db_session
    # return app
    pass


@pytest.fixture(scope="function")
def client(app):
    """Create a test client for the FastAPI app."""
    # return TestClient(app)
    pass
