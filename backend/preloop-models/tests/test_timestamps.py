"""Tests for timestamp fields in Account and Tracker models."""

from datetime import datetime
from time import sleep

from spacemodels.crud import crud_account, crud_tracker


def test_timestamp_fields(db_session, create_account, create_tracker):
    """Test that timestamp fields are properly set and updated."""
    # Create account and check timestamp fields
    account = create_account()
    assert hasattr(account, "created")
    assert hasattr(account, "last_updated")
    assert isinstance(account.created, datetime)
    assert isinstance(account.last_updated, datetime)

    # Create tracker and check timestamp fields
    tracker = create_tracker(account=account)
    assert hasattr(tracker, "created")
    assert hasattr(tracker, "last_updated")
    assert isinstance(tracker.created, datetime)
    assert isinstance(tracker.last_updated, datetime)

    # Remember initial timestamps
    account_created = account.created
    account_updated = account.last_updated
    tracker_created = tracker.created
    tracker_updated = tracker.last_updated

    # Wait a moment to ensure timestamps will be different
    sleep(0.1)

    # Update account and verify last_updated changes but created doesn't
    crud_account.update(
        db_session, db_obj=account, obj_in={"full_name": "Updated Name"}
    )
    assert account.created == account_created  # should not change
    assert account.last_updated > account_updated  # should be updated

    # Update tracker and verify last_updated changes but created doesn't
    crud_tracker.update(db_session, db_obj=tracker, obj_in={"name": "Updated Tracker"})
    assert tracker.created == tracker_created  # should not change
    assert tracker.last_updated > tracker_updated  # should be updated

    # Verify validate method also updates last_updated
    sleep(0.1)
    tracker_updated = tracker.last_updated
    crud_tracker.validate(db_session, id=tracker.id, is_valid=True, message="Validated")
    assert tracker.last_updated > tracker_updated  # should be updated
