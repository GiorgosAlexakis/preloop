"""Tests for invitation endpoints."""

from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from spacemodels.crud import crud_user, crud_user_invitation
from spacemodels.models.user import User


def test_get_invitation_public_info_invalid_token(
    client: TestClient, test_user: User, db_session: Session
):
    """Test getting public info with invalid token."""
    response = client.get("/api/v1/invitations/public/invalid-token")

    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert "Invalid" in data["error_message"]


def test_get_invitation_public_info_expired(
    client: TestClient, test_user: User, db_session: Session
):
    """Test getting public info for expired invitation."""
    invitation_dict = {
        "account_id": test_user.account_id,
        "email": "expired@example.com",
        "invited_by": test_user.id,
        "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    db_session.commit()

    response = client.get(f"/api/v1/invitations/public/{invitation.token}")

    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert "expired" in data["error_message"]


def test_get_invitation_public_info_accepted(
    client: TestClient, test_user: User, db_session: Session
):
    """Test getting public info for already accepted invitation."""
    invitation_dict = {
        "account_id": test_user.account_id,
        "email": "accepted@example.com",
        "invited_by": test_user.id,
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    crud_user_invitation.accept(
        db_session, invitation_id=invitation.id, user_id=test_user.id
    )
    db_session.commit()

    response = client.get(f"/api/v1/invitations/public/{invitation.token}")

    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert "already been accepted" in data["error_message"]


def test_get_invitation_public_info_cancelled(
    client: TestClient, test_user: User, db_session: Session
):
    """Test getting public info for cancelled invitation."""
    invitation_dict = {
        "account_id": test_user.account_id,
        "email": "cancelled@example.com",
        "invited_by": test_user.id,
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    crud_user_invitation.cancel(db_session, invitation_id=invitation.id)
    db_session.commit()

    response = client.get(f"/api/v1/invitations/public/{invitation.token}")

    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert "cancelled" in data["error_message"]


def test_get_invitation_public_info_valid(
    client: TestClient, test_user: User, db_session: Session
):
    """Test getting public info for valid invitation."""
    invitation_dict = {
        "account_id": test_user.account_id,
        "email": "valid@example.com",
        "invited_by": test_user.id,
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    db_session.commit()

    response = client.get(f"/api/v1/invitations/public/{invitation.token}")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "valid@example.com"
    assert data["is_valid"] is True
    assert data["organization_name"] == "Test Organization"
    assert data["error_message"] is None


def test_accept_invitation_invalid_token(
    client: TestClient, test_user: User, db_session: Session
):
    """Test accepting invitation with invalid token."""
    response = client.post(
        "/api/v1/invitations/accept",
        json={
            "token": "invalid-token",
            "username": "newuser",
            "password": "password123",
            "full_name": "New User",
        },
    )

    assert response.status_code == 404
    assert "Invalid" in response.json()["detail"]


def test_list_invitations_empty(
    client: TestClient, test_user: User, db_session: Session
):
    """Test listing invitations when none exist."""
    response = client.get("/api/v1/invitations")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["invitations"]) == 0
    assert data["skip"] == 0
    assert data["limit"] == 100


def test_list_invitations_with_data(
    client: TestClient, test_user: User, db_session: Session
):
    """Test listing invitations when some exist."""
    # Create invitations directly in database
    for i in range(2):
        invitation_dict = {
            "account_id": test_user.account_id,
            "email": f"user{i}@example.com",
            "invited_by": test_user.id,
        }
        crud_user_invitation.create(db_session, obj_in=invitation_dict)
    db_session.commit()

    response = client.get("/api/v1/invitations")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["invitations"]) == 2


def test_list_invitations_pagination(
    client: TestClient, test_user: User, db_session: Session
):
    """Test invitation list pagination."""
    # Create invitations
    for i in range(5):
        invitation_dict = {
            "account_id": test_user.account_id,
            "email": f"page{i}@example.com",
            "invited_by": test_user.id,
        }
        crud_user_invitation.create(db_session, obj_in=invitation_dict)
    db_session.commit()

    response = client.get("/api/v1/invitations?skip=1&limit=3")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["invitations"]) == 3
    assert data["skip"] == 1
    assert data["limit"] == 3


def test_get_invitation_success(
    client: TestClient, test_user: User, db_session: Session
):
    """Test getting a specific invitation."""
    invitation_dict = {
        "account_id": test_user.account_id,
        "email": "specific@example.com",
        "invited_by": test_user.id,
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    db_session.commit()

    response = client.get(f"/api/v1/invitations/{invitation.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(invitation.id)
    assert data["email"] == "specific@example.com"


def test_get_invitation_not_found(
    client: TestClient, test_user: User, db_session: Session
):
    """Test getting non-existent invitation."""
    fake_id = str(uuid4())
    response = client.get(f"/api/v1/invitations/{fake_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_invitation_different_account(
    client: TestClient, test_user: User, db_session: Session
):
    """Test accessing invitation from different account fails."""
    from spacemodels.crud import crud_account

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

    invitation_dict = {
        "account_id": other_account.id,
        "email": "invited@example.com",
        "invited_by": other_user.id,
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    db_session.commit()

    response = client.get(f"/api/v1/invitations/{invitation.id}")

    assert response.status_code == 403
    assert "different account" in response.json()["detail"]


def test_cancel_invitation_success(
    client: TestClient, test_user: User, db_session: Session
):
    """Test cancelling a pending invitation."""
    invitation_dict = {
        "account_id": test_user.account_id,
        "email": "cancel@example.com",
        "invited_by": test_user.id,
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    db_session.commit()

    response = client.delete(f"/api/v1/invitations/{invitation.id}")

    assert response.status_code == 204

    # Verify invitation is cancelled
    get_response = client.get(f"/api/v1/invitations/{invitation.id}")
    assert get_response.json()["status"] == "cancelled"


def test_cancel_invitation_not_found(
    client: TestClient, test_user: User, db_session: Session
):
    """Test cancelling non-existent invitation."""
    fake_id = str(uuid4())
    response = client.delete(f"/api/v1/invitations/{fake_id}")

    assert response.status_code == 404


def test_cancel_accepted_invitation(
    client: TestClient, test_user: User, db_session: Session
):
    """Test cancelling an already accepted invitation fails."""
    invitation_dict = {
        "account_id": test_user.account_id,
        "email": "accepted@example.com",
        "invited_by": test_user.id,
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    crud_user_invitation.accept(
        db_session, invitation_id=invitation.id, user_id=test_user.id
    )
    db_session.commit()

    response = client.delete(f"/api/v1/invitations/{invitation.id}")

    assert response.status_code == 400
    assert "accepted" in response.json()["detail"]


def test_resend_invitation_not_found(
    client: TestClient, test_user: User, db_session: Session
):
    """Test resending non-existent invitation."""
    fake_id = str(uuid4())
    response = client.post(f"/api/v1/invitations/{fake_id}/resend")

    assert response.status_code == 404


def test_resend_invitation_not_pending(
    client: TestClient, test_user: User, db_session: Session
):
    """Test resending non-pending invitation fails."""
    invitation_dict = {
        "account_id": test_user.account_id,
        "email": "cancelled@example.com",
        "invited_by": test_user.id,
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    crud_user_invitation.cancel(db_session, invitation_id=invitation.id)
    db_session.commit()

    response = client.post(f"/api/v1/invitations/{invitation.id}/resend")

    assert response.status_code == 400
    assert "status" in response.json()["detail"]


def test_resend_invitation_expired(
    client: TestClient, test_user: User, db_session: Session
):
    """Test resending expired invitation fails."""
    invitation_dict = {
        "account_id": test_user.account_id,
        "email": "expired@example.com",
        "invited_by": test_user.id,
        "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
    }
    invitation = crud_user_invitation.create(db_session, obj_in=invitation_dict)
    db_session.commit()

    response = client.post(f"/api/v1/invitations/{invitation.id}/resend")

    assert response.status_code == 400
    assert "expired" in response.json()["detail"]
