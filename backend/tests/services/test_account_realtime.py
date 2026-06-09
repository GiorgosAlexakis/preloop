"""Tests for account-scoped realtime event encoding."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from preloop.services.account_realtime import encode_realtime_event_for_nats


def test_encode_realtime_event_serializes_datetime_payload() -> None:
    """Managed-agent summaries include datetime fields that must JSON-encode."""
    observed_at = datetime(2026, 6, 9, 12, 30, tzinfo=UTC)
    event = {
        "account_id": str(uuid4()),
        "topic": "managed_agents",
        "type": "managed_agent_updated",
        "timestamp": observed_at.isoformat(),
        "payload": {
            "id": str(uuid4()),
            "last_seen_at": observed_at,
            "lifecycle_updated_at": observed_at,
        },
    }

    payload_bytes = encode_realtime_event_for_nats(event, context="test account")
    assert payload_bytes is not None
    assert b"2026-06-09T12:30:00" in payload_bytes


def test_encode_realtime_event_serializes_uuid_values() -> None:
    """Nested UUID values should be converted to strings."""
    agent_id = uuid4()
    event = {
        "account_id": str(uuid4()),
        "topic": "managed_agents",
        "type": "managed_agent_updated",
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": {"agent_id": agent_id},
    }

    payload_bytes = encode_realtime_event_for_nats(event, context="test account")
    assert payload_bytes is not None
    assert str(agent_id).encode() in payload_bytes
    assert UUID(str(agent_id))
