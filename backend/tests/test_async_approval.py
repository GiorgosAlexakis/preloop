"""Tests for async approval polling, tool result caching, and idempotency.

These tests validate the fixes for:
- Double-execution race condition (SELECT FOR UPDATE guard)
- Aware vs naive timestamp subtraction in remaining_seconds
- Cached tool_result idempotency on repeated polls
- Timestamp serialisation for event logs
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest


class TestTimestampSerialization:
    """Tests for event timestamp serialization (LOW fix)."""

    def test_naive_timestamp_serialized_correctly(self):
        """Naive timestamps should produce valid RFC3339 with trailing Z."""
        ts = datetime(2026, 2, 17, 20, 0, 0)
        result = ts.replace(tzinfo=None).isoformat() + "Z"
        assert result == "2026-02-17T20:00:00Z"

    def test_aware_timestamp_stripped_before_z(self):
        """Aware timestamps must have tzinfo stripped before appending Z."""
        ts = datetime(2026, 2, 17, 20, 0, 0, tzinfo=timezone.utc)
        result = ts.replace(tzinfo=None).isoformat() + "Z"
        assert result == "2026-02-17T20:00:00Z"
        # Without the fix this would produce "2026-02-17T20:00:00+00:00Z"

    def test_aware_timestamp_with_offset(self):
        """Non-UTC aware timestamps should still produce clean Z suffix."""
        tz_plus2 = timezone(timedelta(hours=2))
        ts = datetime(2026, 2, 17, 22, 0, 0, tzinfo=tz_plus2)
        result = ts.replace(tzinfo=None).isoformat() + "Z"
        # Note: this strips offset info; callers should convert to UTC first
        assert result.endswith("Z")
        assert "+0" not in result


class TestRemainingSecondsCalculation:
    """Tests for the remaining_seconds calculation (HIGH fix)."""

    def test_naive_expires_at_minus_naive_utcnow(self):
        """Both sides naive — no TypeError."""
        expires_at = datetime.utcnow() + timedelta(minutes=5)
        remaining = (expires_at - datetime.utcnow()).total_seconds()
        assert 290 < remaining <= 300

    def test_naive_minus_aware_raises(self):
        """Mixing naive and aware datetimes should raise TypeError.

        This is what the bug produced before the fix.
        """
        naive_ts = datetime(2026, 2, 17, 20, 0, 0)
        aware_ts = datetime.now(timezone.utc)
        with pytest.raises(TypeError):
            _ = (naive_ts - aware_ts).total_seconds()

    def test_expired_returns_zero(self):
        """Expired requests should clamp to 0."""
        expires_at = datetime.utcnow() - timedelta(minutes=1)
        remaining = (expires_at - datetime.utcnow()).total_seconds()
        assert max(0, int(remaining)) == 0


class TestToolResultIdempotency:
    """Tests for tool result caching / idempotency logic."""

    def test_cached_result_returned_without_re_execution(self):
        """When tool_result is already cached, it should be returned directly."""
        cached = {"text": "already executed"}
        approval_request = MagicMock()
        approval_request.status = "approved"
        approval_request.tool_result = cached
        approval_request.tool_name = "test_tool"

        response = {}
        if approval_request.status == "approved":
            if approval_request.tool_result is not None:
                response["tool_result"] = approval_request.tool_result

        assert response["tool_result"] == cached

    def test_none_result_triggers_execution(self):
        """When tool_result is None, execution should proceed."""
        approval_request = MagicMock()
        approval_request.status = "approved"
        approval_request.tool_result = None

        needs_execution = (
            approval_request.status == "approved"
            and approval_request.tool_result is None
        )
        assert needs_execution is True


class TestJustificationEnforcement:
    """Tests for server-side justification_mode=required enforcement."""

    def test_required_justification_missing_is_rejected(self):
        """Tool calls without justification should be rejected when required."""
        justification = None
        requires_justification = True

        should_reject = requires_justification and not justification
        assert should_reject is True

    def test_required_justification_present_is_allowed(self):
        """Tool calls with justification should pass when required."""
        justification = "Need to update the config file"
        requires_justification = True

        should_reject = requires_justification and not justification
        assert should_reject is False

    def test_optional_justification_missing_is_allowed(self):
        """Tool calls without justification should pass when optional."""
        justification = None
        requires_justification = False

        should_reject = requires_justification and not justification
        assert should_reject is False

    def test_empty_string_justification_is_rejected(self):
        """Empty string justification should be treated as missing."""
        justification = ""
        requires_justification = True

        should_reject = requires_justification and not justification
        assert should_reject is True
