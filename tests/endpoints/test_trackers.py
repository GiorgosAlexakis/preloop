import pytest
from fastapi.testclient import TestClient

from spacebridge.api.app import create_app
from spacebridge.schemas.auth import UserResponse
from spacebridge.api.auth.jwt import get_current_active_user

app = create_app()
client = TestClient(app)


@pytest.fixture
def db_session():
    """Fixture for a database session."""
    from spacemodels.db.session import get_engine
    from spacemodels.models.base import Base
    from sqlalchemy.orm import sessionmaker
    import os

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not in env")
    engine = get_engine(db_url)
    Base.metadata.create_all(engine)
    sessionmaker_ = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = sessionmaker_()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def mock_current_user():
    """Fixture for a mock current user."""
    return UserResponse(
        username="testuser", email="test@example.com", email_verified=True
    )


@pytest.fixture
def mock_get_current_active_user(mock_current_user):
    """Fixture to mock the get_current_active_user dependency."""
    app.dependency_overrides[get_current_active_user] = lambda: mock_current_user
    yield
    app.dependency_overrides = {}


def test_list_trackers_empty(db_session, mock_get_current_active_user):
    """Test listing trackers when none exist."""
    from spacemodels.models.account import Account

    user = Account(
        username="testuser", email="test@example.com", hashed_password="password"
    )
    db_session.add(user)
    db_session.commit()
    response = client.get("/api/v1/trackers")
    assert response.status_code == 200
    assert response.json() == []


def test_list_trackers_with_data(db_session, mock_get_current_active_user):
    """Test listing trackers with existing data."""
    from spacemodels.models.tracker import Tracker
    from spacemodels.models.account import Account

    user = Account(
        username="testuser", email="test@example.com", hashed_password="password"
    )
    db_session.add(user)
    db_session.commit()
    tracker = Tracker(
        name="Test Tracker",
        tracker_type="jira",
        url="https://test.jira.com",
        account_id=user.id,
        api_key="dummy_key",
    )
    db_session.add(tracker)
    db_session.commit()

    response = client.get("/api/v1/trackers")
    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["name"] == "Test Tracker"


def test_get_tracker_not_found(db_session, mock_get_current_active_user):
    """Test getting a tracker that does not exist."""
    from spacemodels.models.account import Account
    import uuid

    user = Account(
        username="testuser", email="test@example.com", hashed_password="password"
    )
    db_session.add(user)
    db_session.commit()
    response = client.get(f"/api/v1/trackers/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_tracker_success(db_session, mock_get_current_active_user):
    """Test getting a tracker successfully."""
    from spacemodels.models.tracker import Tracker
    from spacemodels.models.account import Account

    user = Account(
        username="testuser", email="test@example.com", hashed_password="password"
    )
    db_session.add(user)
    db_session.commit()
    tracker = Tracker(
        name="Test Tracker",
        tracker_type="jira",
        url="https://test.jira.com",
        account_id=user.id,
        api_key="dummy_key",
    )
    db_session.add(tracker)
    db_session.commit()

    response = client.get(f"/api/v1/trackers/{tracker.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Test Tracker"


def test_delete_tracker(db_session, mock_get_current_active_user):
    """Test deleting a tracker."""
    from spacemodels.models.tracker import Tracker
    from spacemodels.models.account import Account

    user = Account(
        username="testuser", email="test@example.com", hashed_password="password"
    )
    db_session.add(user)
    db_session.commit()
    tracker = Tracker(
        name="Test Tracker",
        tracker_type="jira",
        url="https://test.jira.com",
        account_id=user.id,
        api_key="dummy_key",
    )
    db_session.add(tracker)
    db_session.commit()

    response = client.delete(f"/api/v1/trackers/{tracker.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Tracker soft deleted successfully"

    # Verify the tracker is marked as deleted
    db_session.refresh(tracker)
    deleted_tracker = db_session.query(Tracker).filter(Tracker.id == tracker.id).first()
    assert deleted_tracker.is_deleted is True
