"""Tests for API key model and CRUD operations."""

from datetime import datetime, timedelta, timezone

from preloop.models.crud import crud_api_key
from preloop.models.models import ApiKey


def test_create_api_key(db_session, create_account, create_user):
    """Test creating an API key."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Create a key for the account
    key_data = {"name": "Test Key", "scopes": ["read:issues", "write:issues"]}
    key = crud_api_key.create_with_owner(
        db_session, obj_in=key_data, owner_username=user.username, expires_days=30
    )

    # Verify Key attributes
    assert key.name == "Test Key"
    assert key.user_id == user.id
    assert key.is_active is True
    assert key.scopes == ["read:issues", "write:issues"]
    assert key.expires_at is not None
    # Compare timezone-aware datetimes
    assert key.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
    assert key.expires_at.replace(tzinfo=timezone.utc) < datetime.now(
        timezone.utc
    ) + timedelta(days=31)


def test_get_by_key(db_session, create_account, create_user):
    """Test retrieving an API key by its value."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Create a key
    key_data = {"name": "Test Key"}
    key = crud_api_key.create_with_owner(
        db_session, obj_in=key_data, owner_username=user.username
    )

    # Retrieve the key by its value
    retrieved_key = crud_api_key.get_by_key(db_session, key=key.key)

    # Verify it's the same key
    assert retrieved_key is not None
    assert retrieved_key.id == key.id
    assert retrieved_key.key == key.key


def test_get_active_by_user(db_session, create_account, create_user):
    """Test retrieving active keys for a user."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Create two keys (one active, one inactive)
    key1 = crud_api_key.create_with_owner(
        db_session, obj_in={"name": "Active key"}, owner_username=user.username
    )
    key2 = crud_api_key.create_with_owner(
        db_session, obj_in={"name": "Inactive key"}, owner_username=user.username
    )

    # Deactivate the second key
    crud_api_key.deactivate(db_session, key_id=key2.id)

    # Get active keys
    active_keys = crud_api_key.get_active_by_user(db_session, username=user.username)

    # Should only have one active key
    assert len(active_keys) == 1
    assert active_keys[0].id == key1.id
    assert active_keys[0].name == "Active key"


def test_key_expiration(db_session, create_account, create_user):
    """Test key expiration checking."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Create an expired key (expires 1 day ago)
    expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    key = ApiKey(
        name="Expired key",
        key="test-expired-key",
        account_id=account.id,
        user_id=user.id,
        expires_at=expires_at,
        scopes=[],
        is_active=True,
    )
    db_session.add(key)
    db_session.commit()

    # Check if key is expired
    assert key.is_expired is True
    assert key.is_valid() is False

    # Create a valid key
    valid_key = crud_api_key.create_with_owner(
        db_session,
        obj_in={"name": "Valid key"},
        owner_username=user.username,
        expires_days=30,
    )

    # Check if key is valid
    assert valid_key.is_expired is False
    assert valid_key.is_valid() is True


def test_validate_key(db_session, create_account, create_user):
    """Test key validation with scopes."""
    # Create an account and user
    account = create_account()
    user = create_user(account=account)

    # Create a key with specific scopes
    key = crud_api_key.create_with_owner(
        db_session,
        obj_in={"name": "Scoped Key", "scopes": ["read:issues", "write:projects"]},
        owner_username=user.username,
    )

    # Validate with matching scopes
    valid_key = crud_api_key.validate_key(
        db_session, key=key.key, required_scopes=["read:issues"]
    )
    assert valid_key is not None
    assert valid_key.id == key.id

    # Validate with non-matching scopes
    invalid_key = crud_api_key.validate_key(
        db_session, key=key.key, required_scopes=["admin:system"]
    )
    assert invalid_key is None
