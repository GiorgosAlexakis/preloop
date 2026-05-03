"""Tests for account-scoped realtime event publishing helpers."""

import json

from preloop.services.account_realtime import (
    MAX_NATS_PAYLOAD_BYTES,
    encode_realtime_event_for_nats,
)


def test_encode_realtime_event_for_nats_truncates_heavy_payload_fields():
    event = {
        "account_id": "account-1",
        "topic": "gateway_activity",
        "type": "model_gateway_call",
        "payload": {
            "request": "x" * (MAX_NATS_PAYLOAD_BYTES + 1),
            "response": "y" * (MAX_NATS_PAYLOAD_BYTES + 1),
            "conversation_preview": {
                "messages": [{"content": "z" * 1000}],
                "metadata": {"has_truncated_content": False},
            },
        },
    }

    payload_bytes = encode_realtime_event_for_nats(event, context="account account-1")

    assert payload_bytes is not None
    assert len(payload_bytes) <= MAX_NATS_PAYLOAD_BYTES
    encoded = json.loads(payload_bytes)
    assert "request" not in encoded["payload"]
    assert "response" not in encoded["payload"]
    assert encoded["payload"]["conversation_preview"]["messages"] == []
    assert (
        encoded["payload"]["conversation_preview"]["metadata"]["has_truncated_content"]
        is True
    )


def test_encode_realtime_event_for_nats_drops_payload_if_still_too_large():
    event = {
        "account_id": "account-1",
        "topic": "gateway_activity",
        "type": "model_gateway_call",
        "payload": {
            "already_minimal_but_huge": "x" * (MAX_NATS_PAYLOAD_BYTES + 1),
        },
    }

    assert encode_realtime_event_for_nats(event, context="account account-1") is None
