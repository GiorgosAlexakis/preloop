import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fastapi import FastAPI
from spacebridge.api.auth.router import router as auth_router
from spacemodels.models.account import Account

app = FastAPI()
app.include_router(auth_router, prefix="/auth")
client = TestClient(app)


@pytest.fixture
def db_session_mock():
    with patch("spacebridge.api.auth.router.get_db_session") as mock_get_db:
        db_session = MagicMock(spec=Session)
        mock_execute = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_execute.scalars.return_value = mock_scalars
        db_session.execute.return_value = mock_execute
        mock_get_db.return_value = iter([db_session])
        yield db_session


def test_register_user_success(db_session_mock):
    with (
        patch("spacebridge.api.auth.router.send_verification_email"),
        patch("spacebridge.api.auth.router.send_product_notification_email"),
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
    mock_execute = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = Account(
        username="testuser", email="test@example.com"
    )
    mock_execute.scalars.return_value = mock_scalars
    db_session_mock.execute.return_value = mock_execute

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
    # First call to execute is for username, second is for email
    mock_execute = MagicMock()
    mock_scalars_user = MagicMock()
    mock_scalars_user.first.return_value = None
    mock_scalars_email = MagicMock()
    mock_scalars_email.first.return_value = Account(
        username="anotheruser", email="test@example.com"
    )

    # This setup is a bit more complex to handle the two separate checks
    results = [
        MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(first=MagicMock(return_value=None))
            )
        ),
        MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(
                    first=MagicMock(
                        return_value=Account(
                            username="anotheruser", email="test@example.com"
                        )
                    )
                )
            )
        ),
    ]
    db_session_mock.execute.side_effect = results

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
        "spacebridge.api.auth.router.authenticate_user"
    ) as mock_authenticate_user:
        mock_user = Account(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password",
        )
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
        "spacebridge.api.auth.router.authenticate_user"
    ) as mock_authenticate_user:
        mock_authenticate_user.return_value = None

        response = client.post(
            "/auth/token/json",
            json={"username": "wronguser", "password": "password"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"
