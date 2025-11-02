"""Tests for user management endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from spacemodels.crud import crud_user, crud_account
from spacemodels.models.user import User


def test_get_current_user_info(
    client: TestClient, test_user: User, db_session: Session
):
    """Test getting current user's information."""
    response = client.get("/api/v1/users/me")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email
    assert data["account_id"] == str(test_user.account_id)


def test_update_current_user(client: TestClient, test_user: User, db_session: Session):
    """Test updating current user's profile."""
    response = client.patch(
        "/api/v1/users/me",
        json={
            "full_name": "Updated Name",
            "email": "updated@example.com",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert data["email"] == "updated@example.com"

    # Verify database was updated
    db_session.refresh(test_user)
    assert test_user.full_name == "Updated Name"
    assert test_user.email == "updated@example.com"


def test_update_current_user_partial(
    client: TestClient, test_user: User, db_session: Session
):
    """Test partial update of current user's profile."""
    original_email = test_user.email

    response = client.patch(
        "/api/v1/users/me",
        json={"full_name": "New Name Only"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "New Name Only"
    assert data["email"] == original_email  # Email unchanged


def test_change_password_success(
    client: TestClient, test_user: User, db_session: Session
):
    """Test changing password successfully."""
    from spacebridge.api.auth.jwt import get_password_hash, verify_password

    # Set a known password
    test_user.hashed_password = get_password_hash("oldpassword123")
    test_user.user_source = "local"
    db_session.commit()

    response = client.post(
        "/api/v1/users/me/change-password",
        json={
            "current_password": "oldpassword123",
            "new_password": "newpassword456",
        },
    )

    assert response.status_code == 204

    # Verify password was changed
    db_session.refresh(test_user)
    assert verify_password("newpassword456", test_user.hashed_password)
    assert not verify_password("oldpassword123", test_user.hashed_password)


def test_change_password_wrong_current(
    client: TestClient, test_user: User, db_session: Session
):
    """Test changing password with wrong current password."""
    from spacebridge.api.auth.jwt import get_password_hash

    test_user.hashed_password = get_password_hash("correctpassword")
    test_user.user_source = "local"
    db_session.commit()

    response = client.post(
        "/api/v1/users/me/change-password",
        json={
            "current_password": "wrongpassword",
            "new_password": "newpassword456",
        },
    )

    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_change_password_external_auth(
    client: TestClient, test_user: User, db_session: Session
):
    """Test changing password for external auth user fails."""
    test_user.user_source = "oauth"
    test_user.oauth_provider = "google"
    db_session.commit()

    response = client.post(
        "/api/v1/users/me/change-password",
        json={
            "current_password": "anything",
            "new_password": "newpassword456",
        },
    )

    assert response.status_code == 400
    assert "external authentication" in response.json()["detail"]


def test_list_users(client: TestClient, test_user: User, db_session: Session):
    """Test listing users in account."""
    # Create additional users
    for i in range(3):
        user_data = {
            "account_id": test_user.account_id,
            "email": f"user{i}@example.com",
            "username": f"user{i}",
            "is_active": True,
            "email_verified": True,
            "hashed_password": "testpassword",
            "user_source": "local",
        }
        crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    response = client.get("/api/v1/users")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4  # test_user + 3 new users
    assert len(data["users"]) == 4
    assert data["skip"] == 0
    assert data["limit"] == 100


def test_list_users_pagination(
    client: TestClient, test_user: User, db_session: Session
):
    """Test user list pagination."""
    # Create additional users
    for i in range(5):
        user_data = {
            "account_id": test_user.account_id,
            "email": f"page{i}@example.com",
            "username": f"page{i}",
            "is_active": True,
            "email_verified": True,
            "hashed_password": "testpassword",
            "user_source": "local",
        }
        crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    response = client.get("/api/v1/users?skip=2&limit=3")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 6  # test_user + 5 new users
    assert len(data["users"]) == 3
    assert data["skip"] == 2
    assert data["limit"] == 3


def test_list_users_multi_tenancy(
    client: TestClient, test_user: User, db_session: Session
):
    """Test that users from other accounts are not listed."""
    # Create another account and user
    other_account_data = {
        "organization_name": "Other Organization",
        "is_active": True,
    }
    other_account = crud_account.create(db_session, obj_in=other_account_data)

    other_user_data = {
        "account_id": other_account.id,
        "email": "other@example.com",
        "username": "otheruser",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    crud_user.create(db_session, obj_in=other_user_data)
    db_session.commit()

    response = client.get("/api/v1/users")

    assert response.status_code == 200
    data = response.json()
    # Should only see test_user, not other_user
    assert data["total"] == 1
    assert all(
        user["account_id"] == str(test_user.account_id) for user in data["users"]
    )


def test_get_user_success(client: TestClient, test_user: User, db_session: Session):
    """Test getting a specific user."""
    # Create another user in same account
    user_data = {
        "account_id": test_user.account_id,
        "email": "specific@example.com",
        "username": "specificuser",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    specific_user = crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    response = client.get(f"/api/v1/users/{specific_user.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(specific_user.id)
    assert data["username"] == "specificuser"
    assert data["email"] == "specific@example.com"


def test_get_user_not_found(client: TestClient, test_user: User, db_session: Session):
    """Test getting non-existent user."""
    fake_id = str(uuid4())
    response = client.get(f"/api/v1/users/{fake_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_user_different_account(
    client: TestClient, test_user: User, db_session: Session
):
    """Test getting user from different account fails."""
    # Create another account and user
    other_account_data = {
        "organization_name": "Other Organization",
        "is_active": True,
    }
    other_account = crud_account.create(db_session, obj_in=other_account_data)

    other_user_data = {
        "account_id": other_account.id,
        "email": "other@example.com",
        "username": "otheruser",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    other_user = crud_user.create(db_session, obj_in=other_user_data)
    db_session.commit()

    response = client.get(f"/api/v1/users/{other_user.id}")

    assert response.status_code == 403
    assert "different account" in response.json()["detail"]


def test_update_user_success(client: TestClient, test_user: User, db_session: Session):
    """Test updating another user's profile."""
    # Create another user
    user_data = {
        "account_id": test_user.account_id,
        "email": "toupdate@example.com",
        "username": "toupdateuser",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    target_user = crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    response = client.patch(
        f"/api/v1/users/{target_user.id}",
        json={
            "full_name": "Updated User Name",
            "email": "newemail@example.com",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated User Name"
    assert data["email"] == "newemail@example.com"


def test_update_user_not_found(
    client: TestClient, test_user: User, db_session: Session
):
    """Test updating non-existent user."""
    fake_id = str(uuid4())
    response = client.patch(
        f"/api/v1/users/{fake_id}",
        json={"full_name": "New Name"},
    )

    assert response.status_code == 404


def test_update_user_different_account(
    client: TestClient, test_user: User, db_session: Session
):
    """Test updating user from different account fails."""
    # Create another account and user
    other_account_data = {
        "organization_name": "Other Organization",
        "is_active": True,
    }
    other_account = crud_account.create(db_session, obj_in=other_account_data)

    other_user_data = {
        "account_id": other_account.id,
        "email": "other@example.com",
        "username": "otheruser",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    other_user = crud_user.create(db_session, obj_in=other_user_data)
    db_session.commit()

    response = client.patch(
        f"/api/v1/users/{other_user.id}",
        json={"full_name": "Hacked Name"},
    )

    assert response.status_code == 403
    assert "different account" in response.json()["detail"]


def test_deactivate_user_success(
    client: TestClient, test_user: User, db_session: Session
):
    """Test deactivating a user."""
    # Create another user
    user_data = {
        "account_id": test_user.account_id,
        "email": "todeactivate@example.com",
        "username": "todeactivate",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    target_user = crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    response = client.post(f"/api/v1/users/{target_user.id}/deactivate")

    assert response.status_code == 204

    # Verify user is deactivated
    db_session.refresh(target_user)
    assert target_user.is_active is False


def test_deactivate_self_fails(
    client: TestClient, test_user: User, db_session: Session
):
    """Test that users cannot deactivate their own account."""
    response = client.post(f"/api/v1/users/{test_user.id}/deactivate")

    assert response.status_code == 400
    assert "your own account" in response.json()["detail"]


def test_deactivate_user_not_found(
    client: TestClient, test_user: User, db_session: Session
):
    """Test deactivating non-existent user."""
    fake_id = str(uuid4())
    response = client.post(f"/api/v1/users/{fake_id}/deactivate")

    assert response.status_code == 404


def test_deactivate_user_different_account(
    client: TestClient, test_user: User, db_session: Session
):
    """Test deactivating user from different account fails."""
    # Create another account and user
    other_account_data = {
        "organization_name": "Other Organization",
        "is_active": True,
    }
    other_account = crud_account.create(db_session, obj_in=other_account_data)

    other_user_data = {
        "account_id": other_account.id,
        "email": "other@example.com",
        "username": "otheruser",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    other_user = crud_user.create(db_session, obj_in=other_user_data)
    db_session.commit()

    response = client.post(f"/api/v1/users/{other_user.id}/deactivate")

    assert response.status_code == 403
    assert "different account" in response.json()["detail"]


def test_search_users_by_username(
    client: TestClient, test_user: User, db_session: Session
):
    """Test searching users by username."""
    # Create users with different usernames
    usernames = ["alice_smith", "alice_jones", "bob_alice", "charlie"]
    for username in usernames:
        user_data = {
            "account_id": test_user.account_id,
            "email": f"{username}@example.com",
            "username": username,
            "is_active": True,
            "email_verified": True,
            "hashed_password": "testpassword",
            "user_source": "local",
        }
        crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    response = client.get("/api/v1/users/search/alice")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3  # alice_smith, alice_jones, bob_alice
    assert all("alice" in user["username"].lower() for user in data)


def test_search_users_case_insensitive(
    client: TestClient, test_user: User, db_session: Session
):
    """Test that user search is case-insensitive."""
    user_data = {
        "account_id": test_user.account_id,
        "email": "john@example.com",
        "username": "JohnDoe",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    response = client.get("/api/v1/users/search/john")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(user["username"] == "JohnDoe" for user in data)


def test_search_users_limit(client: TestClient, test_user: User, db_session: Session):
    """Test search users with limit parameter."""
    # Create many users
    for i in range(15):
        user_data = {
            "account_id": test_user.account_id,
            "email": f"search{i}@example.com",
            "username": f"search{i}",
            "is_active": True,
            "email_verified": True,
            "hashed_password": "testpassword",
            "user_source": "local",
        }
        crud_user.create(db_session, obj_in=user_data)
    db_session.commit()

    response = client.get("/api/v1/users/search/search?limit=5")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


def test_search_users_only_active(
    client: TestClient, test_user: User, db_session: Session
):
    """Test that search only returns active users."""
    # Create active and inactive users
    active_user_data = {
        "account_id": test_user.account_id,
        "email": "active@example.com",
        "username": "activeuser",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    crud_user.create(db_session, obj_in=active_user_data)

    inactive_user_data = {
        "account_id": test_user.account_id,
        "email": "inactive@example.com",
        "username": "inactiveuser",
        "is_active": False,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    crud_user.create(db_session, obj_in=inactive_user_data)
    db_session.commit()

    response = client.get("/api/v1/users/search/user")

    assert response.status_code == 200
    data = response.json()
    # Should include activeuser and testuser, but not inactiveuser
    usernames = [user["username"] for user in data]
    assert "activeuser" in usernames
    assert "inactiveuser" not in usernames


def test_search_users_different_account(
    client: TestClient, test_user: User, db_session: Session
):
    """Test that search doesn't return users from other accounts."""
    # Create another account and user
    other_account_data = {
        "organization_name": "Other Organization",
        "is_active": True,
    }
    other_account = crud_account.create(db_session, obj_in=other_account_data)

    other_user_data = {
        "account_id": other_account.id,
        "email": "other@example.com",
        "username": "othersearch",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    crud_user.create(db_session, obj_in=other_user_data)

    # Create user in test account
    same_account_data = {
        "account_id": test_user.account_id,
        "email": "same@example.com",
        "username": "samesearch",
        "is_active": True,
        "email_verified": True,
        "hashed_password": "testpassword",
        "user_source": "local",
    }
    crud_user.create(db_session, obj_in=same_account_data)
    db_session.commit()

    response = client.get("/api/v1/users/search/search")

    assert response.status_code == 200
    data = response.json()
    usernames = [user["username"] for user in data]
    assert "samesearch" in usernames
    assert "othersearch" not in usernames
