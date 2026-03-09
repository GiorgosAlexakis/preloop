"""Tests for RegistrationToken CRUD operations."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from preloop.models.crud import crud_registration_token


class TestRegistrationTokenCRUD:
    """Test CRUD operations for RegistrationToken."""

    def test_create_token(self, db_session: Session, create_user):
        """Test creating a registration token."""
        user = create_user()
        token = crud_registration_token.create_token(
            db_session, user_id=user.id, expiry_minutes=15
        )

        assert token.id is not None
        assert token.token is not None
        assert len(token.token) > 0
        assert token.user_id == user.id
        assert token.is_consumed is False
        assert token.expires_at is not None
        now = datetime.now(timezone.utc)
        expires_aware = (
            token.expires_at
            if token.expires_at.tzinfo
            else token.expires_at.replace(tzinfo=timezone.utc)
        )
        assert expires_aware > now

    def test_create_token_custom_expiry(self, db_session: Session, create_user):
        """Test creating token with custom expiry."""
        user = create_user()
        token = crud_registration_token.create_token(
            db_session, user_id=user.id, expiry_minutes=60
        )

        expires_aware = (
            token.expires_at
            if token.expires_at.tzinfo
            else token.expires_at.replace(tzinfo=timezone.utc)
        )
        expected_min = datetime.now(timezone.utc) + timedelta(minutes=55)
        expected_max = datetime.now(timezone.utc) + timedelta(minutes=65)
        assert expected_min <= expires_aware <= expected_max

    def test_get_by_token(self, db_session: Session, create_user):
        """Test retrieving token by token value."""
        user = create_user()
        created = crud_registration_token.create_token(db_session, user_id=user.id)
        db_session.flush()

        found = crud_registration_token.get_by_token(db_session, token=created.token)
        assert found is not None
        assert found.id == created.id
        assert found.token == created.token

    def test_get_by_token_not_found(self, db_session: Session):
        """Test get_by_token returns None for non-existent token."""
        result = crud_registration_token.get_by_token(
            db_session, token="nonexistent-token-value-xyz"
        )
        assert result is None

    def test_validate_and_consume_success(self, db_session: Session, create_user):
        """Test validate_and_consume with valid token."""
        user = create_user()
        created = crud_registration_token.create_token(
            db_session, user_id=user.id, expiry_minutes=15
        )
        db_session.flush()

        result = crud_registration_token.validate_and_consume(
            db_session, token=created.token
        )
        assert result is not None
        assert result.id == created.id
        assert result.is_consumed is True
        assert result.used_at is not None

    def test_validate_and_consume_invalid_token(self, db_session: Session):
        """Test validate_and_consume returns None for invalid token."""
        result = crud_registration_token.validate_and_consume(
            db_session, token="invalid-token"
        )
        assert result is None

    def test_validate_and_consume_already_consumed(
        self, db_session: Session, create_user
    ):
        """Test validate_and_consume returns None for consumed token."""
        user = create_user()
        created = crud_registration_token.create_token(
            db_session, user_id=user.id, expiry_minutes=15
        )
        db_session.flush()

        # Consume first time
        crud_registration_token.validate_and_consume(db_session, token=created.token)

        # Second consume should fail
        result = crud_registration_token.validate_and_consume(
            db_session, token=created.token
        )
        assert result is None

    def test_validate_and_consume_expired_token(self, db_session: Session, create_user):
        """Test validate_and_consume returns None for expired token."""
        user = create_user()
        created = crud_registration_token.create_token(
            db_session, user_id=user.id, expiry_minutes=15
        )
        db_session.flush()

        # Manually expire the token by setting expires_at in the past
        created.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.add(created)
        db_session.commit()
        db_session.refresh(created)

        result = crud_registration_token.validate_and_consume(
            db_session, token=created.token
        )
        assert result is None

    def test_cleanup_expired(self, db_session: Session, create_user):
        """Test cleanup_expired removes expired tokens."""
        user = create_user()
        token1 = crud_registration_token.create_token(
            db_session, user_id=user.id, expiry_minutes=15
        )
        token2 = crud_registration_token.create_token(
            db_session, user_id=user.id, expiry_minutes=15
        )
        token1_value = token1.token
        token2_value = token2.token
        db_session.flush()

        # Expire both tokens
        token1.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        token2.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.add(token1)
        db_session.add(token2)
        db_session.commit()

        deleted = crud_registration_token.cleanup_expired(db_session)
        assert deleted == 2

        # Verify tokens are gone (use saved values; objects are detached after delete)
        assert (
            crud_registration_token.get_by_token(db_session, token=token1_value) is None
        )
        assert (
            crud_registration_token.get_by_token(db_session, token=token2_value) is None
        )

    def test_cleanup_expired_none(self, db_session: Session, create_user):
        """Test cleanup_expired when no expired tokens exist."""
        user = create_user()
        crud_registration_token.create_token(
            db_session, user_id=user.id, expiry_minutes=15
        )
        db_session.flush()

        deleted = crud_registration_token.cleanup_expired(db_session)
        assert deleted == 0
