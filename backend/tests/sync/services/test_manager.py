import pytest
from unittest.mock import Mock, patch, AsyncMock
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from preloop.sync.services import manager


@pytest.mark.asyncio
@patch("preloop.sync.services.manager.event_bus_service")
async def test_poll_tracker_success(mock_event_bus_service):
    mock_ack = AsyncMock()
    mock_ack.stream = "tasks"
    mock_ack.seq = 1
    mock_event_bus_service.publish_task.return_value = mock_ack

    await manager.poll_tracker("tracker-1")

    mock_event_bus_service.publish_task.assert_called_once_with(
        "poll_tracker", "tracker-1"
    )


@pytest.mark.asyncio
@patch("preloop.sync.services.manager.event_bus_service")
async def test_poll_tracker_failure(mock_event_bus_service):
    mock_event_bus_service.publish_task.return_value = None

    await manager.poll_tracker("tracker-1")

    mock_event_bus_service.publish_task.assert_called_once_with(
        "poll_tracker", "tracker-1"
    )


@patch("preloop.sync.services.manager.crud_tracker")
@patch("preloop.sync.services.manager.get_db_session")
def test_sync_scheduled_jobs(mock_get_db_session, mock_crud_tracker):
    mock_scheduler = Mock(spec=AsyncIOScheduler)
    mock_db_session = Mock()
    mock_get_db_session.return_value = iter([mock_db_session])

    # Mock existing jobs and active trackers
    mock_job = Mock()
    mock_job.id = f"{manager.TRACKER_JOB_PREFIX}tracker-1"
    mock_scheduler.get_jobs.return_value = [mock_job]

    mock_tracker = Mock()
    mock_tracker.id = "tracker-2"
    mock_crud_tracker.get_active.return_value = [mock_tracker]

    manager.sync_scheduled_jobs(mock_scheduler, mock_db_session)

    # Assert that the old job was removed and the new job was added
    mock_scheduler.remove_job.assert_called_once_with(
        f"{manager.TRACKER_JOB_PREFIX}tracker-1"
    )
    mock_scheduler.add_job.assert_called_once()
