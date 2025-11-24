import pytest
from unittest.mock import Mock, patch
import datetime

from preloop_sync.services.base import (
    BaseTrackerUpdateService,
    PollingTrackerUpdateService,
)


class ConcreteTrackerUpdateService(BaseTrackerUpdateService):
    def setup(self) -> bool:
        return True

    def update(self) -> int:
        return 5

    def cleanup(self) -> None:
        pass


class ConcretePollingTrackerUpdateService(PollingTrackerUpdateService):
    def setup(self) -> bool:
        return True

    def update(self) -> int:
        return 5

    def cleanup(self) -> None:
        pass


@pytest.fixture
def mock_db_session():
    return Mock()


@pytest.fixture
def mock_tracker():
    tracker = Mock()
    tracker.id = 1
    tracker.tracker_type = "jira"
    tracker.connection_details = {
        "url": "https://test.jira.com",
        "username": "testuser",
    }
    return tracker


@patch("preloop_sync.trackers.jira.JIRA")
def test_base_tracker_update_service_initialization(
    mock_jira, mock_db_session, mock_tracker
):
    service = ConcreteTrackerUpdateService(mock_db_session, mock_tracker)
    assert service.db == mock_db_session
    assert service.tracker == mock_tracker
    assert not service.running
    assert isinstance(service.last_check, datetime.datetime)


@patch("preloop_sync.trackers.jira.JIRA")
def test_base_tracker_update_service_start_stop(
    mock_jira, mock_db_session, mock_tracker
):
    service = ConcreteTrackerUpdateService(mock_db_session, mock_tracker)
    service.cleanup = Mock()

    service.start()
    assert service.running

    service.stop()
    assert not service.running
    service.cleanup.assert_called_once()


@patch("preloop_sync.trackers.jira.JIRA")
def test_polling_tracker_update_service_initialization(
    mock_jira, mock_db_session, mock_tracker
):
    service = ConcretePollingTrackerUpdateService(
        mock_db_session, mock_tracker, poll_interval=120
    )
    assert service.poll_interval == 120


@patch("preloop_sync.services.base.logger")
@patch("preloop_sync.trackers.jira.JIRA")
def test_polling_tracker_update_service_start_stop(
    mock_jira, mock_logger, mock_db_session, mock_tracker
):
    service = ConcretePollingTrackerUpdateService(mock_db_session, mock_tracker)
    service.start()
    mock_logger.info.assert_called_with(
        "Polling service for tracker 1 marked as started (scheduling handled externally)."
    )

    service.stop()
    mock_logger.info.assert_called_with(
        "Polling service for tracker 1 marked as stopped."
    )
