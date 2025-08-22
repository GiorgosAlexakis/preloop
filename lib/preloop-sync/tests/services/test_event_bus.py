import pytest
import json
from unittest.mock import AsyncMock, patch, Mock

from nats.js.errors import APIError
from spacesync.services.event_bus import EventBus


@pytest.fixture
def event_bus():
    """Provides an EventBus instance for testing."""
    bus = EventBus()
    # Mock settings for the test environment
    bus.nats_url = "nats://test-server:4222"
    return bus


@pytest.mark.asyncio
@patch("spacesync.services.event_bus.nats.connect")
async def test_publish_task_success(mock_nats_connect, event_bus: EventBus):
    """
    Tests that a task is successfully published with the correct payload format.
    """
    # Arrange
    mock_nc = AsyncMock()
    mock_js = AsyncMock()
    mock_ack = AsyncMock()
    mock_ack.stream = "tasks"
    mock_ack.seq = 1

    # Configure the mock connect to return our NATS client mock
    mock_nats_connect.return_value = mock_nc

    # Configure jetstream() to be a regular method returning the jetstream mock
    mock_nc.jetstream = Mock(return_value=mock_js)

    # Mock stream interaction
    mock_js.stream_info.side_effect = APIError(err_code=10059)  # Stream not found
    mock_js.add_stream = AsyncMock()

    # Configure the async method on the jetstream mock
    mock_js.publish.return_value = mock_ack

    # Connect the publisher, which should now use our mocks
    await event_bus.connect()

    # Act
    task_name = "my_test_function"
    task_args = [1, "hello"]
    task_kwargs = {"test": True}

    result_ack = await event_bus.publish_task(task_name, *task_args, **task_kwargs)

    # Assert
    mock_js.publish.assert_called_once()
    call_args = mock_js.publish.call_args

    # Check subject and payload
    assert call_args.args[0] == f"spacesync.tasks.{task_name}"
    payload = json.loads(call_args.args[1].decode("utf-8"))

    assert payload["function"] == task_name
    assert payload["args"] == task_args
    assert payload["kwargs"] == task_kwargs

    assert result_ack is not None
    assert result_ack.stream == "tasks"
    assert result_ack.seq == 1


@pytest.mark.asyncio
@patch("spacesync.services.event_bus.nats.connect")
async def test_publish_task_reconnects_if_not_connected(
    mock_nats_connect, event_bus: EventBus
):
    """
    Tests that the publisher attempts to reconnect if publish is called without a connection.
    """
    # Arrange
    # Publisher is not connected initially
    assert event_bus.js is None

    # Set up mocks for a successful connection on the second attempt
    mock_nc = AsyncMock()
    mock_js = AsyncMock()
    mock_ack = AsyncMock()
    mock_ack.stream = "tasks"
    mock_ack.seq = 1
    mock_nats_connect.return_value = mock_nc
    mock_nc.jetstream = Mock(return_value=mock_js)
    mock_js.publish.return_value = mock_ack

    # Act
    result = await event_bus.publish_task("some_task")

    # Assert
    mock_nats_connect.assert_called_once()  # Should be called inside publish_task
    mock_js.stream_info.side_effect = APIError(err_code=10059)
    mock_js.publish.assert_called_once_with(
        "spacesync.tasks.some_task",
        b'{"function": "some_task", "args": [], "kwargs": {}}',
    )
    assert result is not None


@pytest.mark.asyncio
@patch("spacesync.services.event_bus.nats.connect")
async def test_publish_task_handles_publish_failure(
    mock_nats_connect, event_bus: EventBus
):
    """
    Tests that a failure during the publish call is handled gracefully.
    """
    # Arrange
    mock_nc = AsyncMock()
    mock_js = AsyncMock()
    mock_nats_connect.return_value = mock_nc
    mock_nc.jetstream = Mock(return_value=mock_js)

    # Configure publish to raise an exception
    mock_js.publish.side_effect = Exception("NATS publish error")
    mock_js.stream_info.side_effect = APIError(err_code=10059)

    await event_bus.connect()

    # Act
    result = await event_bus.publish_task("failing_task")

    # Assert
    assert result is None
    mock_js.publish.assert_called_once()
