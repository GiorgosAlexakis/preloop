import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from spacemodels.models import Organization, Tracker
from spacesync.scanner.core import scan_tracker


@pytest.fixture
def mock_db_session():
    """Fixture for a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def mock_tracker():
    """Fixture for a mock tracker model instance."""
    tracker = MagicMock(spec=Tracker)
    tracker.id = 1
    tracker.is_deleted = False
    tracker.tracker_type = "github"
    return tracker


@pytest.fixture
def mock_organization():
    """Fixture for a mock organization model instance."""
    org = MagicMock(spec=Organization)
    org.id = 101
    org.last_webhook_update = None
    org.last_polling_update = None
    return org


@patch("spacesync.scanner.core._process_organization")
@patch("spacesync.scanner.core.TrackerClient")
def test_scan_tracker_happy_path(
    mock_tracker_client_class,
    mock_process_org,
    mock_db_session,
    mock_tracker,
    mock_organization,
):
    """
    Test that scan_tracker initializes TrackerClient, gets organizations,
    and processes them.
    """
    # Arrange
    mock_client_instance = MagicMock()
    mock_client_instance.scan_organizations.return_value = [mock_organization]
    mock_tracker_client_class.return_value = mock_client_instance
    mock_process_org.return_value = {
        "projects": 1,
        "issues": 5,
        "embeddings_updated": 5,
        "organizations": {"errors": 0},
    }

    # Act
    stats = scan_tracker(db=mock_db_session, tracker=mock_tracker)

    # Assert
    mock_tracker_client_class.assert_called_once_with(mock_tracker)
    mock_client_instance.scan_organizations.assert_called_once_with(mock_db_session)
    mock_process_org.assert_called_once_with(
        mock_db_session, mock_client_instance, mock_organization, None, False
    )
    assert stats["organizations"]["total"] == 1
    assert stats["organizations"]["processed"] == 1
    assert stats["projects"] == 1
    assert stats["issues"] == 5


def test_scan_tracker_skips_deleted_tracker(mock_db_session, mock_tracker):
    """Test that a deleted tracker is skipped."""
    # Arrange
    mock_tracker.is_deleted = True

    # Act
    stats = scan_tracker(db=mock_db_session, tracker=mock_tracker)

    # Assert
    assert stats["organizations"]["total"] == 0


@patch("spacesync.scanner.core._process_organization")
@patch("spacesync.scanner.core.TrackerClient")
def test_scan_tracker_skips_recently_polled_org(
    mock_tracker_client_class,
    mock_process_org,
    mock_db_session,
    mock_tracker,
    mock_organization,
):
    """Test that an organization that was recently polled is skipped."""
    # Arrange
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_organization.last_polling_update = now - datetime.timedelta(minutes=10)

    mock_client_instance = MagicMock()
    mock_client_instance.scan_organizations.return_value = [mock_organization]
    mock_tracker_client_class.return_value = mock_client_instance

    # Act
    stats = scan_tracker(db=mock_db_session, tracker=mock_tracker)

    # Assert
    mock_process_org.assert_not_called()
    assert stats["organizations"]["total"] == 1
    assert stats["organizations"]["processed"] == 0
    assert stats["organizations"]["skipped_polling"] == 1


@patch("spacesync.scanner.core.TrackerClient")
def test_scan_tracker_force_update_ignores_polling_time(
    mock_tracker_client_class,
    mock_db_session,
    mock_tracker,
    mock_organization,
):
    """Test that force_update=True processes an org regardless of polling time."""
    # Arrange
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_organization.last_polling_update = now - datetime.timedelta(minutes=10)

    mock_client_instance = MagicMock()
    mock_client_instance.scan_organizations.return_value = [mock_organization]
    mock_tracker_client_class.return_value = mock_client_instance

    with patch("spacesync.scanner.core._process_organization") as mock_process_org:
        mock_process_org.return_value = {
            "projects": 1,
            "issues": 5,
            "embeddings_updated": 5,
            "organizations": {"errors": 0},
        }
        # Act
        stats = scan_tracker(
            db=mock_db_session, tracker=mock_tracker, force_update=True
        )

        # Assert
        mock_process_org.assert_called_once()
        assert stats["organizations"]["processed"] == 1
        assert stats["organizations"]["skipped_polling"] == 0
