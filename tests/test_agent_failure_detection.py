"""Tests for agent failure detection in container logs."""

import pytest
from spacebridge.agents.container import ContainerAgentExecutor
from spacebridge.agents.base import AgentStatus


class TestAgentFailureDetection:
    """Test suite for detecting agent failures from container logs."""

    def setup_method(self):
        """Set up test fixtures."""
        self.agent = ContainerAgentExecutor(
            agent_type="test", config={}, image="test-image:latest"
        )

    def test_detect_litellm_bad_request_error(self):
        """Test detection of litellm.BadRequestError in logs."""
        logs = """
        Starting agent execution...
        litellm.BadRequestError: OpenAIException - {
          "error": {
            "message": "Unsupported parameter: 'temperature' is not supported with this model.",
            "type": "invalid_request_error",
            "param": "temperature",
            "code": null
          }
        }
        """
        assert self.agent._detect_error_in_logs(logs) is True

    def test_detect_authentication_error(self):
        """Test detection of authentication errors."""
        logs = """
        Connecting to API...
        litellm.AuthenticationError: Invalid API key provided
        """
        assert self.agent._detect_error_in_logs(logs) is True

    def test_detect_traceback(self):
        """Test detection of Python tracebacks."""
        logs = """
        Running task...
        Traceback (most recent call last):
          File "main.py", line 42, in run
            result = do_something()
        ValueError: Invalid input
        """
        assert self.agent._detect_error_in_logs(logs) is True

    def test_no_error_in_success_logs(self):
        """Test that successful execution logs don't trigger false positives."""
        logs = """
        Starting agent execution...
        Processing task...
        Task completed successfully
        Agent finished with exit code 0
        """
        assert self.agent._detect_error_in_logs(logs) is False

    def test_extract_error_from_logs(self):
        """Test extraction of error messages from logs."""
        logs = """
        Starting execution
        Processing request
        litellm.BadRequestError: Unsupported parameter
        Additional context line
        More context
        """
        error_message = self.agent._extract_error_from_logs(logs)
        assert "litellm.BadRequestError" in error_message
        assert "Unsupported parameter" in error_message

    def test_extract_error_with_context(self):
        """Test that error extraction includes surrounding context."""
        logs = """
        Line 1
        Line 2
        Error occurred: Connection failed
        Line 4
        Line 5
        Line 6
        Line 7
        """
        error_message = self.agent._extract_error_from_logs(logs)
        # Should include lines around the error
        assert "Line 2" in error_message or "Line 1" in error_message
        assert "Error occurred" in error_message
        assert "Line 4" in error_message or "Line 5" in error_message

    def test_no_error_extraction_from_clean_logs(self):
        """Test that no error is extracted from clean logs."""
        logs = """
        Starting execution
        Processing task
        Task completed
        Finished successfully
        """
        error_message = self.agent._extract_error_from_logs(logs)
        assert error_message == ""

    def test_detect_openai_exception(self):
        """Test detection of OpenAI exceptions."""
        logs = """
        Making API call...
        OpenAIException: Rate limit exceeded
        """
        assert self.agent._detect_error_in_logs(logs) is True

    def test_detect_fatal_error(self):
        """Test detection of FATAL ERROR messages."""
        logs = """
        Initializing system...
        FATAL ERROR: Cannot connect to database
        """
        assert self.agent._detect_error_in_logs(logs) is True

    def test_detect_critical_error(self):
        """Test detection of CRITICAL log level errors."""
        logs = """
        Running checks...
        CRITICAL: System resource exhausted
        """
        assert self.agent._detect_error_in_logs(logs) is True


@pytest.mark.asyncio
class TestContainerFailureStatus:
    """Integration tests for container failure status detection."""

    async def test_exit_code_zero_with_errors_marks_failed(self, mocker):
        """Test that exit code 0 with error logs is marked as FAILED."""
        agent = ContainerAgentExecutor(
            agent_type="test", config={}, image="test-image:latest"
        )

        # Mock Docker container with exit code 0 but error logs
        mock_docker = mocker.AsyncMock()
        mock_container = mocker.AsyncMock()
        mock_container.show.return_value = {
            "State": {"ExitCode": 0, "Status": "exited"}
        }

        error_logs = [
            "Starting aider",
            "litellm.BadRequestError: Unsupported parameter: 'temperature'",
            "Failed to execute task",
        ]
        mock_container.log.return_value = error_logs

        mocker.patch.object(agent, "_get_docker_client", return_value=mock_docker)
        mock_docker.containers.get.return_value = mock_container

        # Mock get_logs to return error logs
        mocker.patch.object(agent, "get_logs", return_value=error_logs)

        # Mock get_status to return SUCCEEDED initially
        mocker.patch.object(agent, "get_status", return_value=AgentStatus.SUCCEEDED)

        result = await agent.get_result("test-container")

        # Should override SUCCEEDED to FAILED due to error logs
        assert result.status == AgentStatus.FAILED
        assert result.error_message is not None
        assert (
            "BadRequestError" in result.error_message
            or "Unsupported parameter" in result.error_message
        )
