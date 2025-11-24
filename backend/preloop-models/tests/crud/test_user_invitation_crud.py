"""Tests for UserInvitation CRUD operations."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from preloop_models.crud.user_invitation import CRUDUserInvitation
from preloop_models.models.user_invitation import UserInvitation, UserInvitationStatus


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def crud_user_invitation():
    """Fixture for a CRUDUserInvitation instance."""
    return CRUDUserInvitation(UserInvitation)


def test_get_by_token(crud_user_invitation, mock_db_session):
    """Test retrieving invitation by token."""
    # Arrange
    token = "test-token-123"
    mock_invitation = UserInvitation(id=uuid4(), token=token)

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_invitation

    # Act
    result = crud_user_invitation.get_by_token(mock_db_session, token=token)

    # Assert
    assert result.token == token
    mock_db_session.query.assert_called_once_with(UserInvitation)


def test_get_by_token_not_found(crud_user_invitation, mock_db_session):
    """Test get_by_token when invitation doesn't exist."""
    # Arrange
    token = "non-existent-token"

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    # Act
    result = crud_user_invitation.get_by_token(mock_db_session, token=token)

    # Assert
    assert result is None


def test_get_by_email(crud_user_invitation, mock_db_session):
    """Test retrieving pending invitation by email."""
    # Arrange
    email = "test@example.com"
    account_id = str(uuid4())
    mock_invitation = UserInvitation(
        id=uuid4(),
        email=email,
        account_id=account_id,
        status=UserInvitationStatus.PENDING,
    )

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_invitation

    # Act
    result = crud_user_invitation.get_by_email(
        mock_db_session, email=email, account_id=account_id
    )

    # Assert
    assert result.email == email
    assert result.account_id == account_id
    assert result.status == UserInvitationStatus.PENDING


def test_get_by_email_not_found(crud_user_invitation, mock_db_session):
    """Test get_by_email when no pending invitation exists."""
    # Arrange
    email = "nonexistent@example.com"
    account_id = str(uuid4())

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    # Act
    result = crud_user_invitation.get_by_email(
        mock_db_session, email=email, account_id=account_id
    )

    # Assert
    assert result is None


def test_get_by_account(crud_user_invitation, mock_db_session):
    """Test retrieving invitations by account."""
    # Arrange
    account_id = str(uuid4())
    mock_invitations = [
        UserInvitation(id=uuid4(), account_id=account_id),
        UserInvitation(id=uuid4(), account_id=account_id),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_invitations

    # Act
    result = crud_user_invitation.get_by_account(mock_db_session, account_id=account_id)

    # Assert
    assert len(result) == 2
    assert all(inv.account_id == account_id for inv in result)


def test_get_by_account_with_status_filter(crud_user_invitation, mock_db_session):
    """Test retrieving invitations by account with status filter."""
    # Arrange
    account_id = str(uuid4())
    status = UserInvitationStatus.PENDING
    mock_invitations = [
        UserInvitation(id=uuid4(), account_id=account_id, status=status),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_invitations

    # Act
    result = crud_user_invitation.get_by_account(
        mock_db_session, account_id=account_id, status=status
    )

    # Assert
    assert len(result) == 1
    assert result[0].status == status


def test_get_by_account_with_pagination(crud_user_invitation, mock_db_session):
    """Test retrieving invitations with pagination."""
    # Arrange
    account_id = str(uuid4())
    skip = 10
    limit = 5
    mock_invitations = [UserInvitation(id=uuid4()) for _ in range(5)]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_invitations

    # Act
    result = crud_user_invitation.get_by_account(
        mock_db_session, account_id=account_id, skip=skip, limit=limit
    )

    # Assert
    mock_query.offset.assert_called_once_with(skip)
    mock_query.limit.assert_called_once_with(limit)
    assert len(result) == 5


def test_get_pending(crud_user_invitation, mock_db_session):
    """Test retrieving pending invitations."""
    # Arrange
    account_id = str(uuid4())
    mock_invitations = [
        UserInvitation(id=uuid4(), status=UserInvitationStatus.PENDING),
        UserInvitation(id=uuid4(), status=UserInvitationStatus.PENDING),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = mock_invitations

    # Act
    result = crud_user_invitation.get_pending(mock_db_session, account_id=account_id)

    # Assert
    assert len(result) == 2
    assert all(inv.status == UserInvitationStatus.PENDING for inv in result)


def test_accept(crud_user_invitation, mock_db_session):
    """Test accepting an invitation."""
    # Arrange
    invitation_id = uuid4()
    user_id = uuid4()
    mock_invitation = UserInvitation(
        id=invitation_id, status=UserInvitationStatus.PENDING
    )

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_invitation

    # Act
    result = crud_user_invitation.accept(
        mock_db_session, invitation_id=invitation_id, user_id=user_id
    )

    # Assert
    assert result.status == UserInvitationStatus.ACCEPTED
    assert result.accepted_by == user_id
    assert result.accepted_at is not None
    mock_db_session.add.assert_called_once_with(mock_invitation)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_invitation)


def test_accept_not_found(crud_user_invitation, mock_db_session):
    """Test accepting non-existent invitation."""
    # Arrange
    invitation_id = uuid4()
    user_id = uuid4()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    # Act
    result = crud_user_invitation.accept(
        mock_db_session, invitation_id=invitation_id, user_id=user_id
    )

    # Assert
    assert result is None
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


def test_cancel(crud_user_invitation, mock_db_session):
    """Test cancelling an invitation."""
    # Arrange
    invitation_id = uuid4()
    mock_invitation = UserInvitation(
        id=invitation_id, status=UserInvitationStatus.PENDING
    )

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_invitation

    # Act
    result = crud_user_invitation.cancel(mock_db_session, invitation_id=invitation_id)

    # Assert
    assert result.status == UserInvitationStatus.CANCELLED
    mock_db_session.add.assert_called_once_with(mock_invitation)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_invitation)


def test_cancel_not_found(crud_user_invitation, mock_db_session):
    """Test cancelling non-existent invitation."""
    # Arrange
    invitation_id = uuid4()

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None

    # Act
    result = crud_user_invitation.cancel(mock_db_session, invitation_id=invitation_id)

    # Assert
    assert result is None
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()


def test_expire_old_invitations(crud_user_invitation, mock_db_session):
    """Test expiring old pending invitations."""
    # Arrange
    now = datetime.now(timezone.utc)
    past_time = now - timedelta(days=7)
    mock_invitations = [
        UserInvitation(
            id=uuid4(), status=UserInvitationStatus.PENDING, expires_at=past_time
        ),
        UserInvitation(
            id=uuid4(), status=UserInvitationStatus.PENDING, expires_at=past_time
        ),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_invitations

    # Act
    count = crud_user_invitation.expire_old_invitations(mock_db_session)

    # Assert
    assert count == 2
    assert all(inv.status == UserInvitationStatus.EXPIRED for inv in mock_invitations)
    assert mock_db_session.add.call_count == 2
    mock_db_session.commit.assert_called_once()


def test_expire_old_invitations_none_found(crud_user_invitation, mock_db_session):
    """Test expiring invitations when none are expired."""
    # Arrange
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = []

    # Act
    count = crud_user_invitation.expire_old_invitations(mock_db_session)

    # Assert
    assert count == 0
    mock_db_session.commit.assert_not_called()


def test_cleanup_expired(crud_user_invitation, mock_db_session):
    """Test deleting old expired invitations."""
    # Arrange
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=40)
    mock_invitations = [
        UserInvitation(
            id=uuid4(), status=UserInvitationStatus.EXPIRED, expires_at=old_time
        ),
        UserInvitation(
            id=uuid4(), status=UserInvitationStatus.CANCELLED, expires_at=old_time
        ),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_invitations

    # Act
    count = crud_user_invitation.cleanup_expired(mock_db_session, days_old=30)

    # Assert
    assert count == 2
    assert mock_db_session.delete.call_count == 2
    mock_db_session.commit.assert_called_once()


def test_cleanup_expired_none_found(crud_user_invitation, mock_db_session):
    """Test cleanup when no old expired invitations exist."""
    # Arrange
    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = []

    # Act
    count = crud_user_invitation.cleanup_expired(mock_db_session, days_old=30)

    # Assert
    assert count == 0
    mock_db_session.delete.assert_not_called()
    mock_db_session.commit.assert_not_called()


def test_cleanup_expired_custom_days(crud_user_invitation, mock_db_session):
    """Test cleanup with custom days_old parameter."""
    # Arrange
    days_old = 60
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=70)
    mock_invitations = [
        UserInvitation(
            id=uuid4(), status=UserInvitationStatus.EXPIRED, expires_at=old_time
        ),
    ]

    mock_query = MagicMock()
    mock_db_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = mock_invitations

    # Act
    count = crud_user_invitation.cleanup_expired(mock_db_session, days_old=days_old)

    # Assert
    assert count == 1
    mock_db_session.delete.assert_called_once()
