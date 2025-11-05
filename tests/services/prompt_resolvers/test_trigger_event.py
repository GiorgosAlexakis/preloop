"""Tests for trigger event resolver."""

from unittest.mock import MagicMock

import pytest

from spacebridge.services.prompt_resolvers.base import ResolverContext
from spacebridge.services.prompt_resolvers.trigger_event import TriggerEventResolver


class TestTriggerEventResolver:
    """Test TriggerEventResolver class."""

    def test_prefix(self):
        """Test that prefix returns correct value."""
        resolver = TriggerEventResolver()
        assert resolver.prefix == "trigger_event"

    @pytest.mark.asyncio
    async def test_resolve_simple_field(self):
        """Test resolving a simple field from trigger event."""
        resolver = TriggerEventResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"source": "github", "action": "created"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        result = await resolver.resolve("source", context)
        assert result == "github"

        result = await resolver.resolve("action", context)
        assert result == "created"

    @pytest.mark.asyncio
    async def test_resolve_nested_field(self):
        """Test resolving a nested field from trigger event."""
        resolver = TriggerEventResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={
                "payload": {
                    "issue": {"title": "Test Issue", "number": 123},
                    "commit": {"sha": "abc123"},
                }
            },
            flow_id="flow-1",
            execution_id="exec-1",
        )

        result = await resolver.resolve("payload.issue.title", context)
        assert result == "Test Issue"

        result = await resolver.resolve("payload.commit.sha", context)
        assert result == "abc123"

    @pytest.mark.asyncio
    async def test_resolve_no_trigger_event_data(self):
        """Test resolving when no trigger event data is available."""
        resolver = TriggerEventResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data=None,
            flow_id="flow-1",
            execution_id="exec-1",
        )

        result = await resolver.resolve("source", context)
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_field(self):
        """Test resolving a field that doesn't exist."""
        resolver = TriggerEventResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={"source": "github"},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        result = await resolver.resolve("nonexistent.field", context)
        assert result is None

    @pytest.mark.asyncio
    async def test_resolve_empty_trigger_event_data(self):
        """Test resolving when trigger event data is empty."""
        resolver = TriggerEventResolver()

        mock_db = MagicMock()
        context = ResolverContext(
            db=mock_db,
            trigger_event_data={},
            flow_id="flow-1",
            execution_id="exec-1",
        )

        result = await resolver.resolve("source", context)
        assert result is None
