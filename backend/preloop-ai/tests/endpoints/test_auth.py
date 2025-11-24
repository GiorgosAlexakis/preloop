import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid

from fastapi import FastAPI
from preloop_ai.api.auth.router import router as auth_router
from preloop_models.models.user import User

app = FastAPI()
app.include_router(auth_router, prefix="/auth")
client = TestClient(app)


@pytest.fixture
def db_session_mock():
    with patch("preloop_ai.api.auth.router.get_db_session") as mock_get_db:
        db_session = MagicMock(spec=Session)
        mock_execute = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_execute.scalars.return_value = mock_scalars
        db_session.execute.return_value = mock_execute

        # Mock the query chain for CRUD methods
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_query.all.return_value = []
        db_session.query.return_value = mock_query

        mock_get_db.return_value = iter([db_session])
        yield db_session


def test_register_user_success(db_session_mock):
    with (
        patch("preloop_ai.api.auth.router.send_verification_email"),
        patch("preloop_ai.api.auth.router.send_product_notification_email"),
    ):
        response = client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password",
                "full_name": "Test User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["full_name"] == "Test User"
        assert not data["email_verified"]


def test_register_user_username_exists(db_session_mock):
    # Mock query chain for username check (returns existing user)
    mock_user = MagicMock(spec=User)
    mock_user.username = "testuser"
    mock_user.email = "test@example.com"

    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_user
    db_session_mock.query.return_value = mock_query

    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "another@example.com",
            "password": "password",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Username already registered"


def test_register_user_email_exists(db_session_mock):
    # First query for username check (returns None), second for email check (returns user)
    mock_query_username = MagicMock()
    mock_query_username.filter.return_value = mock_query_username
    mock_query_username.first.return_value = None

    mock_user = MagicMock(spec=User)
    mock_user.username = "anotheruser"
    mock_user.email = "test@example.com"

    mock_query_email = MagicMock()
    mock_query_email.filter.return_value = mock_query_email
    mock_query_email.first.return_value = mock_user

    # Use side_effect to return different mocks for each query call
    db_session_mock.query.side_effect = [mock_query_username, mock_query_email]

    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_login_success():
    with patch(
        "preloop_ai.api.auth.router.authenticate_user"
    ) as mock_authenticate_user:
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid.uuid4()
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.hashed_password = "hashed_password"
        mock_authenticate_user.return_value = mock_user

        response = client.post(
            "/auth/token/json",
            json={"username": "testuser", "password": "password"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"


def test_login_failure():
    with patch(
        "preloop_ai.api.auth.router.authenticate_user"
    ) as mock_authenticate_user:
        mock_authenticate_user.return_value = None

        response = client.post(
            "/auth/token/json",
            json={"username": "wronguser", "password": "password"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"
