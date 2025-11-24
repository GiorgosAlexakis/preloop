"""Tests for Account model and CRUD operations.

Account now represents an organization, not individual users.
For user tests, see test_user_model.py
"""

from preloop_models.crud import crud_account


def test_create_account(db_session, create_account):
    """Test creating an account (organization)."""
    # Create a test account
    account = create_account(organization_name="Test Organization")

    # Check the account was created with correct values
    assert account.id is not None
    assert account.organization_name == "Test Organization"
    assert account.is_active is True
    assert account.is_superuser is False

    # Check account creation timestamp
    assert account.created is not None
    assert account.last_updated is not None


def test_get_account(db_session, create_account):
    """Test getting an account by ID."""
    # Create a test account
    account = create_account(organization_name="Get Test Org")

    # Get account by ID
    retrieved = crud_account.get(db_session, id=account.id)

    # Check retrieval
    assert retrieved is not None
    assert retrieved.id == account.id
    assert retrieved.organization_name == "Get Test Org"


def test_update_account(db_session, create_account):
    """Test updating an account."""
    # Create a test account
    account = create_account(organization_name="Original Name")

    # Update account
    updated = crud_account.update(
        db_session,
        db_obj=account,
        obj_in={
            "organization_name": "Updated Organization",
            "is_active": False,
            "meta_data": {"preferences": {"theme": "dark"}},
        },
    )

    # Check updates
    assert updated.organization_name == "Updated Organization"
    assert updated.is_active is False
    assert updated.meta_data == {"preferences": {"theme": "dark"}}


def test_account_with_users(db_session, create_account, create_user):
    """Test account with multiple users."""
    # Create account
    account = create_account(organization_name="Multi-User Org")

    # Create multiple users in the account
    user1 = create_user(username="user1", email="user1@example.com", account=account)
    user2 = create_user(username="user2", email="user2@example.com", account=account)

    # Verify users are associated with account
    assert user1.account_id == account.id
    assert user2.account_id == account.id

    # Verify account has users (through relationship)
    db_session.refresh(account)
    assert len(account.users) == 2
    assert user1 in account.users
    assert user2 in account.users


def test_account_primary_user(db_session, create_account, create_user):
    """Test account with primary user."""
    # Create account
    account = create_account(organization_name="Primary User Test")

    # Create a user
    user = create_user(
        username="primaryuser", email="primary@example.com", account=account
    )

    # Set as primary user
    account.primary_user_id = user.id
    db_session.commit()
    db_session.refresh(account)

    # Verify primary user is set
    assert account.primary_user_id == user.id
