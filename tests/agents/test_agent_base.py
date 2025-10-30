"""Tests for agent base classes and enums."""

import pytest
from spacebridge.agents.base import AgentStatus, AgentExecutionResult, AgentExecutor


class TestAgentStatus:
    """Test AgentStatus enum."""

    def test_agent_status_values(self):
        """Test that all expected status values exist."""
        assert AgentStatus.PENDING == "PENDING"
        assert AgentStatus.STARTING == "STARTING"
        assert AgentStatus.RUNNING == "RUNNING"
        assert AgentStatus.SUCCEEDED == "SUCCEEDED"
        assert AgentStatus.FAILED == "FAILED"
        assert AgentStatus.STOPPED == "STOPPED"

    def test_agent_status_is_string_enum(self):
        """Test that AgentStatus values are strings."""
        assert isinstance(AgentStatus.PENDING.value, str)
        assert isinstance(AgentStatus.RUNNING.value, str)


class TestAgentExecutionResult:
    """Test AgentExecutionResult dataclass."""

    def test_result_creation_minimal(self):
        """Test creating result with minimal required fields."""
        result = AgentExecutionResult(
            status=AgentStatus.SUCCEEDED,
            session_reference="test-session-123",
        )
        assert result.status == AgentStatus.SUCCEEDED
        assert result.session_reference == "test-session-123"
        assert result.output_summary is None
        assert result.error_message is None
        assert result.actions_taken is None
        assert result.artifacts is None
        assert result.exit_code is None

    def test_result_creation_full(self):
        """Test creating result with all fields."""
        actions = ["action1", "action2"]
        artifacts = {"file1.txt": "content", "logs": ["log1", "log2"]}

        result = AgentExecutionResult(
            status=AgentStatus.SUCCEEDED,
            session_reference="test-session-456",
            output_summary="Task completed successfully",
            error_message=None,
            actions_taken=actions,
            artifacts=artifacts,
            exit_code=0,
        )

        assert result.status == AgentStatus.SUCCEEDED
        assert result.session_reference == "test-session-456"
        assert result.output_summary == "Task completed successfully"
        assert result.error_message is None
        assert result.actions_taken == actions
        assert result.artifacts == artifacts
        assert result.exit_code == 0

    def test_result_with_error(self):
        """Test creating result with error information."""
        result = AgentExecutionResult(
            status=AgentStatus.FAILED,
            session_reference="test-session-error",
            error_message="Container failed to start",
            exit_code=1,
        )

        assert result.status == AgentStatus.FAILED
        assert result.error_message == "Container failed to start"
        assert result.exit_code == 1


class TestAgentExecutor:
    """Test AgentExecutor abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that AgentExecutor cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AgentExecutor("test", {})  # type: ignore

    def test_concrete_implementation_required(self):
        """Test that concrete implementations must implement all abstract methods."""

        class IncompleteAgent(AgentExecutor):
            """Agent missing required method implementations."""

            pass

        with pytest.raises(TypeError):
            IncompleteAgent("test", {})  # type: ignore

    @pytest.mark.asyncio
    async def test_concrete_implementation_works(self):
        """Test that a complete concrete implementation can be instantiated."""

        class CompleteAgent(AgentExecutor):
            """Fully implemented agent."""

            async def start(self, execution_context):
                return "session-123"

            async def get_status(self, session_reference):
                return AgentStatus.RUNNING

            async def get_result(self, session_reference):
                return AgentExecutionResult(
                    status=AgentStatus.SUCCEEDED,
                    session_reference=session_reference,
                )

            async def stop(self, session_reference):
                pass

            async def get_logs(self, session_reference, tail=100):
                return ["log line 1", "log line 2"]

        agent = CompleteAgent("test-agent", {"key": "value"})
        assert agent.agent_type == "test-agent"
        assert agent.config == {"key": "value"}

        # Test that methods work
        session = await agent.start({"prompt": "test"})
        assert session == "session-123"

        status = await agent.get_status("session-123")
        assert status == AgentStatus.RUNNING

        result = await agent.get_result("session-123")
        assert result.status == AgentStatus.SUCCEEDED
        assert result.session_reference == "session-123"

        await agent.stop("session-123")

        logs = await agent.get_logs("session-123")
        assert len(logs) == 2
        assert logs[0] == "log line 1"
