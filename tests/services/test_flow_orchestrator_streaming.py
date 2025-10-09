"""Tests for flow orchestrator streaming and command handling."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from spacebridge.services.flow_orchestrator import FlowExecutionOrchestrator


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_nats_client():
    """Mock NATS client."""
    client = AsyncMock()
    client.is_connected = True
    client.publish = AsyncMock()
    client.subscribe = AsyncMock()
    return client


@pytest.fixture
def orchestrator(mock_db, mock_nats_client):
    """Create orchestrator instance."""
    flow_id = "test-flow-id"
    trigger_event_data = {"event": "test"}

    orch = FlowExecutionOrchestrator(
        db=mock_db,
        flow_id=flow_id,
        trigger_event_data=trigger_event_data,
        nats_client=mock_nats_client,
    )

    # Mock execution log
    orch.execution_log = MagicMock()
    orch.execution_log.id = "test-execution-id"

    return orch


class TestLogStreaming:
    """Test real-time log streaming to NATS."""

    @pytest.mark.asyncio
    async def test_stream_logs_to_nats_success(self, orchestrator, mock_nats_client):
        """Test that logs are streamed to NATS."""
        mock_agent_executor = AsyncMock()

        # Mock log streaming
        async def mock_stream(session_reference):
            for line in ["Log line 1", "Log line 2", "Log line 3"]:
                yield line

        mock_agent_executor.stream_logs = mock_stream

        # Run streaming task
        task = asyncio.create_task(
            orchestrator._stream_logs_to_nats(mock_agent_executor, "session-123")
        )

        # Give it time to process
        await asyncio.sleep(0.1)

        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify NATS publish was called
        assert mock_nats_client.publish.call_count >= 3

        # Verify message format
        calls = mock_nats_client.publish.call_args_list
        for call in calls:
            subject, message = call[0]
            assert subject.startswith("flow-updates.")

            # Decode and verify message
            data = json.loads(message.decode())
            assert data["type"] == "agent_log_line"
            assert "timestamp" in data["payload"]
            assert "line" in data["payload"]

    @pytest.mark.asyncio
    async def test_stream_logs_handles_cancellation(self, orchestrator):
        """Test that log streaming handles cancellation gracefully."""
        mock_agent_executor = AsyncMock()

        async def mock_stream(session_reference):
            for i in range(100):
                yield f"Line {i}"
                await asyncio.sleep(0.01)

        mock_agent_executor.stream_logs = mock_stream

        # Start task
        task = asyncio.create_task(
            orchestrator._stream_logs_to_nats(mock_agent_executor, "session-123")
        )

        # Let it run briefly
        await asyncio.sleep(0.05)

        # Cancel
        task.cancel()

        # Should not raise
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

    @pytest.mark.asyncio
    async def test_stream_logs_handles_errors(self, orchestrator, mock_nats_client):
        """Test that streaming handles errors gracefully."""
        mock_agent_executor = AsyncMock()

        async def mock_stream(session_reference):
            yield "Line 1"
            raise RuntimeError("Test error")

        mock_agent_executor.stream_logs = mock_stream

        # Run streaming task
        task = asyncio.create_task(
            orchestrator._stream_logs_to_nats(mock_agent_executor, "session-123")
        )

        await asyncio.sleep(0.1)

        # Should complete without raising
        await task

        # Should have published error
        calls = [call for call in mock_nats_client.publish.call_args_list]
        error_messages = [
            call
            for call in calls
            if b"agent_log_error" in call[0][1] or b"error" in call[0][1].lower()
        ]
        assert len(error_messages) > 0


class TestCommandListener:
    """Test command listener for user intervention."""

    @pytest.mark.asyncio
    async def test_listen_for_commands_stop(self, orchestrator, mock_nats_client):
        """Test that stop command is handled."""
        command_subject = f"flow-commands.{orchestrator.execution_log.id}"

        # Capture the subscription callback
        callback = None

        async def mock_subscribe(subject, cb):
            nonlocal callback
            callback = cb
            return AsyncMock()

        mock_nats_client.subscribe = mock_subscribe

        # Start listening
        await orchestrator._listen_for_commands()

        # Verify subscription
        assert callback is not None

        # Simulate stop command
        mock_msg = MagicMock()
        mock_msg.data = json.dumps({"command": "stop"}).encode()

        await callback(mock_msg)

        # Verify stop was requested
        assert orchestrator._stop_requested.is_set()

    @pytest.mark.asyncio
    async def test_listen_for_commands_send_message(
        self, orchestrator, mock_nats_client
    ):
        """Test that send_message command is handled."""
        callback = None

        async def mock_subscribe(subject, cb):
            nonlocal callback
            callback = cb
            return AsyncMock()

        mock_nats_client.subscribe = mock_subscribe

        await orchestrator._listen_for_commands()

        # Simulate send_message command
        mock_msg = MagicMock()
        mock_msg.data = json.dumps(
            {"command": "send_message", "message": "Hello agent!"}
        ).encode()

        await callback(mock_msg)

        # Verify message was queued
        assert orchestrator._user_messages.qsize() == 1
        message = await orchestrator._user_messages.get()
        assert message == "Hello agent!"

    @pytest.mark.asyncio
    async def test_listen_for_commands_invalid_json(
        self, orchestrator, mock_nats_client
    ):
        """Test that invalid JSON is handled."""
        callback = None

        async def mock_subscribe(subject, cb):
            nonlocal callback
            callback = cb
            return AsyncMock()

        mock_nats_client.subscribe = mock_subscribe

        await orchestrator._listen_for_commands()

        # Simulate invalid JSON
        mock_msg = MagicMock()
        mock_msg.data = b"invalid json"

        # Should not raise
        await callback(mock_msg)

    @pytest.mark.asyncio
    async def test_listen_for_commands_unknown_command(
        self, orchestrator, mock_nats_client
    ):
        """Test that unknown commands are logged."""
        callback = None

        async def mock_subscribe(subject, cb):
            nonlocal callback
            callback = cb
            return AsyncMock()

        mock_nats_client.subscribe = mock_subscribe

        await orchestrator._listen_for_commands()

        # Simulate unknown command
        mock_msg = MagicMock()
        mock_msg.data = json.dumps({"command": "unknown"}).encode()

        # Should not raise
        await callback(mock_msg)


class TestCleanupMonitoring:
    """Test cleanup of monitoring resources."""

    @pytest.mark.asyncio
    async def test_cleanup_cancels_log_streaming(self, orchestrator):
        """Test that cleanup cancels log streaming task."""

        # Create a real async task that we can test with
        async def dummy_stream():
            try:
                await asyncio.sleep(10)  # Long sleep
            except asyncio.CancelledError:
                raise

        # Create actual task
        mock_task = asyncio.create_task(dummy_stream())

        orchestrator._log_streaming_task = mock_task

        # Run cleanup
        await orchestrator._cleanup_monitoring()

        # Verify task was cancelled
        assert mock_task.cancelled()

    @pytest.mark.asyncio
    async def test_cleanup_unsubscribes_from_commands(self, orchestrator):
        """Test that cleanup unsubscribes from commands."""
        mock_subscription = AsyncMock()
        orchestrator._command_subscription = mock_subscription

        await orchestrator._cleanup_monitoring()

        # Verify unsubscribe was called
        mock_subscription.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_handles_errors(self, orchestrator):
        """Test that cleanup handles errors gracefully."""
        # Create subscription that raises on unsubscribe
        mock_subscription = AsyncMock()
        mock_subscription.unsubscribe = AsyncMock(
            side_effect=RuntimeError("Test error")
        )
        orchestrator._command_subscription = mock_subscription

        # Should not raise
        await orchestrator._cleanup_monitoring()


class TestMonitoringIntegration:
    """Integration tests for monitoring with streaming."""

    @pytest.mark.asyncio
    async def test_monitor_starts_log_streaming(self, orchestrator, mock_nats_client):
        """Test that monitoring starts log streaming task."""
        from spacebridge.agents.base import AgentStatus, AgentExecutionResult

        with patch(
            "spacebridge.services.flow_orchestrator.create_agent_executor"
        ) as mock_create:
            mock_agent_executor = AsyncMock()
            mock_agent_executor.get_status = AsyncMock(
                return_value=AgentStatus.SUCCEEDED
            )
            mock_agent_executor.get_result = AsyncMock(
                return_value=AgentExecutionResult(
                    status=AgentStatus.SUCCEEDED,
                    session_reference="session-123",
                    exit_code=0,
                    output_summary="Done",
                    error_message=None,
                )
            )

            async def mock_stream(session_reference):
                yield "Test log"

            mock_agent_executor.stream_logs = mock_stream
            mock_create.return_value = mock_agent_executor

            # Mock flow
            orchestrator.flow = MagicMock()
            orchestrator.flow.agent_type = "test"
            orchestrator.flow.agent_config = {}

            # Mock execution logger
            orchestrator.execution_logger.get_actions_taken = MagicMock(return_value=[])
            orchestrator.execution_logger.get_mcp_usage_logs = MagicMock(
                return_value=[]
            )
            orchestrator.execution_logger.log_milestone = MagicMock()

            # Run monitoring (will complete quickly due to SUCCEEDED status)
            result = await orchestrator._monitor_agent_execution("session-123")

            # Verify log streaming task was created
            assert orchestrator._log_streaming_task is not None

    @pytest.mark.asyncio
    async def test_monitor_handles_stop_command(self, orchestrator, mock_nats_client):
        """Test that monitoring handles stop command."""
        from spacebridge.agents.base import AgentStatus

        with patch(
            "spacebridge.services.flow_orchestrator.create_agent_executor"
        ) as mock_create:
            mock_agent_executor = AsyncMock()
            mock_agent_executor.get_status = AsyncMock(return_value=AgentStatus.RUNNING)
            mock_agent_executor.stop = AsyncMock()

            async def mock_stream(session_reference):
                while True:
                    yield "Test log"
                    await asyncio.sleep(0.1)

            mock_agent_executor.stream_logs = mock_stream
            mock_create.return_value = mock_agent_executor

            orchestrator.flow = MagicMock()
            orchestrator.flow.agent_type = "test"
            orchestrator.flow.agent_config = {}

            # Set stop requested immediately
            orchestrator._stop_requested.set()

            # Start monitoring
            task = asyncio.create_task(
                orchestrator._monitor_agent_execution("session-123")
            )

            # Give it time to process
            await asyncio.sleep(0.2)

            # Should have called stop at least once
            assert mock_agent_executor.stop.call_count >= 1
            mock_agent_executor.stop.assert_any_call("session-123")

            # Cancel task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
