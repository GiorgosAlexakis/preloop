import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nats.aio.client import Client as NATSClient

from spacebridge.schemas.events import StandardizedNatsEvent
from spacesync.services.event_bus import NatsPublisher


@pytest.fixture
def nats_publisher():
    """Fixture for NatsPublisher with a mocked NATS client."""
    publisher = NatsPublisher()
    publisher.nc = MagicMock(spec=NATSClient)
    publisher.nc.is_connected = True
    publisher.js = AsyncMock()
    return publisher


@pytest.mark.asyncio
async def test_publish_standardized_event(nats_publisher: NatsPublisher):
    """Test that a StandardizedNatsEvent is correctly serialized and published."""
    # Arrange
    event = StandardizedNatsEvent(
        event_source="github",
        event_type="issues.opened",
        tracker_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        data={"issue_id": 123, "title": "Test Issue"},
        source_event_id="gh-delivery-abc-123",
    )
    expected_subject = f"spacebridge.events.{event.event_source}.{event.event_type}"
    expected_payload_dict = event.model_dump(mode="json")

    # Act
    await nats_publisher.publish_event(event)

    # Assert
    # Check that JetStream publish was called
    nats_publisher.js.publish.assert_called_once()

    # Get the actual arguments passed to publish
    args, kwargs = nats_publisher.js.publish.call_args
    actual_subject = args[0]
    actual_payload_bytes = args[1]

    # Verify the subject
    assert actual_subject == expected_subject

    # Verify the payload
    actual_payload_dict = json.loads(actual_payload_bytes)

    # Pydantic v2 serializes UUIDs and datetimes to strings automatically.
    # We need to compare the dictionaries field by field to avoid issues with
    # object instances (like UUID and datetime objects) vs. their string representations.
    assert actual_payload_dict["event_id"] == str(event.event_id)
    assert actual_payload_dict["event_source"] == event.event_source
    assert actual_payload_dict["event_type"] == event.event_type
    assert actual_payload_dict["tracker_id"] == str(event.tracker_id)
    assert actual_payload_dict["organization_id"] == str(event.organization_id)
    assert "timestamp" in actual_payload_dict  # Check for presence
    assert actual_payload_dict["data"] == event.data
    assert actual_payload_dict["source_event_id"] == event.source_event_id


@pytest.mark.asyncio
async def test_publish_event_reconnects_if_not_connected(nats_publisher: NatsPublisher):
    """Test that the publisher attempts to reconnect if the client is not connected."""
    # Arrange
    nats_publisher.nc.is_connected = False
    event = StandardizedNatsEvent(event_source="test", event_type="test.event", data={})

    # Mock the connect method to simulate a successful reconnection
    async def mock_connect_impl():
        nats_publisher.nc.is_connected = True
        # Simulate that connect also sets up 'js'
        nats_publisher.js = AsyncMock()

    with patch.object(
        nats_publisher, "connect", side_effect=mock_connect_impl
    ) as mock_connect:
        # Act
        await nats_publisher.publish_event(event)

        # Assert
        mock_connect.assert_awaited_once()
        nats_publisher.js.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_event_handles_publish_failure(nats_publisher: NatsPublisher):
    """Test that a failure during the publish call is handled gracefully."""
    # Arrange
    event = StandardizedNatsEvent(event_source="test", event_type="test.event", data={})
    nats_publisher.js.publish.side_effect = Exception("NATS publish failed")

    # Act
    result = await nats_publisher.publish_event(event)

    # Assert
    assert result is None  # Or check for a specific failure indicator if you prefer
    nats_publisher.js.publish.assert_called_once()
