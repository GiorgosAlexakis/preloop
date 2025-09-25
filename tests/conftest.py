"""Pytest configuration file for SpaceBridge tests."""

from typing import Generator

import pytest
import os
import fastapi
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from spacebridge.api.app import create_app
from spacebridge.api.auth import get_current_active_user
from spacemodels.db.session import get_db_session as get_db
from spacemodels.models import Account
import uuid
from spacemodels.models.base import Base


@pytest.fixture(autouse=True)
def mock_openai_client():
    """Mock the OpenAI client to avoid real API calls."""
    with patch("openai.Client") as mock_client:
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        mock_client.return_value.embeddings.create.return_value = mock_response
        yield mock_client


def pytest_configure(config):
    """
    Load environment variables from .env file before tests run.
    """
    # Construct the path to the .env file relative to the conftest.py file
    # Assuming .env is in the project root, and conftest.py is in tests/
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(dotenv_path)


@pytest.fixture(scope="session")
def db_engine():
    """Create a new database engine for the test session."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    yield engine


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create a database session for each test function, and clean up afterwards."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(autocommit=False, autoflush=False, bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> Account:
    """Create and persist a test user for authentication."""
    user = Account(
        id=str(uuid.uuid4()),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        is_active=True,
        email_verified=True,
        is_superuser=False,
        hashed_password="testpassword",
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def app(
    db_session: Session, test_user: Account
) -> Generator[fastapi.FastAPI, None, None]:
    """Create a FastAPI app for testing with dependency overrides."""

    def override_get_current_active_user():
        return test_user

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    yield app


@pytest.fixture(scope="function")
def client(app: fastapi.FastAPI) -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    with TestClient(app) as client:
        yield client
