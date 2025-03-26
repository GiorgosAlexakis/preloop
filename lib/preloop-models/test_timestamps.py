import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from spacemodels.crud import crud_account, crud_tracker


def test_timestamp_fields(db_session: Session, create_account, create_tracker):
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

    # Update account and verify last_updated changes
    old_updated = account.last_updated
    crud_account.update(
        db_session, db_obj=account, obj_in={"full_name": "Updated Name"}
    )
    assert account.last_updated > old_updated

    # Update tracker and verify last_updated changes
    old_tracker_updated = tracker.last_updated
    crud_tracker.update(db_session, db_obj=tracker, obj_in={"name": "Updated Tracker"})
    assert tracker.last_updated > old_tracker_updated


# Run this test directly
if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
