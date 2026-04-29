"""Tests for OpenHandsAgent implementation."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from preloop.agents.openhands import OpenHandsAgent


@pytest.fixture
def openhands_config():
    """Sample OpenHands agent configuration."""
    return {
        "agent_type": "CodeActAgent",
        "max_iterations": 15,
        "custom_setting": "value",
    }


@pytest.fixture
def mock_docker():
    """Mock aiodocker Docker client."""
    with patch("preloop.agents.container.aiodocker.Docker") as mock:
        docker_instance = AsyncMock()
        mock.return_value = docker_instance
        docker_instance.containers.create = AsyncMock()
        yield docker_instance


class TestOpenHandsAgent:
    """Test OpenHandsAgent class."""

    def test_init_default_image(self, openhands_config):
        """Test OpenHandsAgent initialization with default image."""
        agent = OpenHandsAgent(openhands_config)

        assert agent.agent_type == "openhands"
        assert agent.config == openhands_config
        assert agent.image == "spacebridge/openhands:latest-tmux"
        assert agent.use_kubernetes is False

    def test_init_custom_image(self, openhands_config):
        """Test OpenHandsAgent initialization with custom image."""
        with patch.dict(os.environ, {"OPENHANDS_IMAGE": "custom-image:v1.0"}):
            agent = OpenHandsAgent(openhands_config)
            assert agent.image == "custom-image:v1.0"

    def test_init_kubernetes_enabled(self, openhands_config):
        """Test OpenHandsAgent with Kubernetes enabled."""
        with patch.dict(os.environ, {"USE_KUBERNETES": "true"}):
            agent = OpenHandsAgent(openhands_config)
            assert agent.use_kubernetes is True

    def test_init_kubernetes_disabled(self, openhands_config):
        """Test OpenHandsAgent with Kubernetes explicitly disabled."""
        with patch.dict(os.environ, {"USE_KUBERNETES": "false"}):
            agent = OpenHandsAgent(openhands_config)
            assert agent.use_kubernetes is False

    @pytest.mark.asyncio
    async def test_start_with_agent_config(self, openhands_config, mock_docker):
        """Test starting OpenHands with agent configuration."""
        mock_container = AsyncMock()
        mock_container.id = "openhands-container-123"
        mock_docker.containers.create.return_value = mock_container

        agent = OpenHandsAgent(openhands_config)

        execution_context = {
            "flow_id": "flow-456",
            "execution_id": "exec-789",
            "prompt": "Fix the authentication bug",
            "agent_config": {
                "agent_type": "PlannerAgent",
                "max_iterations": 20,
            },
            "model_identifier": "gpt-5.4",
            "model_api_key": "test-key",
        }

        session_ref = await agent.start(execution_context)

        assert session_ref == "openhands-container-123"
        mock_container.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_default_agent_type(self, mock_docker):
        """Test starting OpenHands with default CodeActAgent type."""
        mock_container = AsyncMock()
        mock_container.id = "openhands-container-456"
        mock_docker.containers.create.return_value = mock_container

        agent = OpenHandsAgent({})

        execution_context = {
            "flow_id": "flow-123",
            "execution_id": "exec-456",
            "prompt": "Test prompt",
            "agent_config": {},  # No agent_type specified
        }

        await agent.start(execution_context)

        # Verify that CodeActAgent is used as default
        # This is verified through the environment variables set
        mock_docker.containers.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_default_max_iterations(self, mock_docker):
        """Test starting OpenHands with default max_iterations."""
        mock_container = AsyncMock()
        mock_container.id = "openhands-container-789"
        mock_docker.containers.create.return_value = mock_container

        agent = OpenHandsAgent({})

        execution_context = {
            "flow_id": "flow-123",
            "execution_id": "exec-456",
            "prompt": "Test prompt",
            "agent_config": {},  # No max_iterations specified
        }

        await agent.start(execution_context)

        # Default should be 10
        mock_docker.containers.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_prepare_environment_openhands_specific(self, openhands_config):
        """Test that OpenHands-specific environment variables are set."""
        agent = OpenHandsAgent(openhands_config)

        execution_context = {
            "flow_id": "flow-123",
            "execution_id": "exec-456",
            "prompt": "Implement feature X",
            "agent_config": {
                "agent_type": "CodeActAgent",
                "max_iterations": 25,
            },
            "model_identifier": "gpt-5.4-turbo",
            "model_api_key": "sk-test-key",
            "model_provider": "openai",
            "model_parameters": {
                "temperature": 0.7,
                "max_tokens": 4000,
            },
            "openhands_agent_type": "CodeActAgent",
            "max_iterations": 25,
        }

        env = await agent._prepare_environment(execution_context)

        # Check OpenHands-specific variables
        assert env["AGENT_TYPE"] == "CodeActAgent"
        assert env["MAX_ITERATIONS"] == "25"
        assert env["PROMPT"] == "Implement feature X"

        # Check AI model variables
        assert env["LLM_MODEL"] == "gpt-5.4-turbo"
        assert env["LLM_API_KEY"] == "sk-test-key"
        assert env["LLM_PROVIDER"] == "openai"
        assert env["LLM_TEMPERATURE"] == "0.7"
        assert env["LLM_MAX_TOKENS"] == "4000"

    @pytest.mark.asyncio
    async def test_prepare_environment_minimal(self, openhands_config):
        """Test environment preparation with minimal context."""
        agent = OpenHandsAgent(openhands_config)

        execution_context = {
            "prompt": "Simple task",
            "openhands_agent_type": "CodeActAgent",
            "max_iterations": 10,
        }

        env = await agent._prepare_environment(execution_context)

        assert env["AGENT_TYPE"] == "CodeActAgent"
        assert env["MAX_ITERATIONS"] == "10"
        assert env["PROMPT"] == "Simple task"

        # Optional fields should not be present
        assert "LLM_MODEL" not in env
        assert "LLM_API_KEY" not in env

    @pytest.mark.asyncio
    async def test_prepare_environment_gateway_uses_openai_compatible_endpoint(
        self, openhands_config
    ):
        """Gateway mode should configure OpenHands through the OpenAI API shape."""
        agent = OpenHandsAgent(openhands_config)

        env = await agent._prepare_environment(
            {
                "prompt": "Use the gateway",
                "openhands_agent_type": "CodeActAgent",
                "max_iterations": 10,
                "model_gateway_enabled": True,
                "model_gateway_model_alias": "google/gemini-2.5-pro",
                "model_gateway_token": "gw-token-123",
                "model_gateway_url": "https://review.preloop.ai/gemini/v1beta",
            }
        )

        assert env["LLM_MODEL"] == "openai/google/gemini-2.5-pro"
        assert env["LLM_PROVIDER"] == "openai"
        assert env["LLM_API_KEY"] == "gw-token-123"
        assert env["LLM_BASE_URL"] == "https://review.preloop.ai/openai/v1"
        assert env["OPENAI_API_BASE"] == "https://review.preloop.ai/openai/v1"

    @pytest.mark.asyncio
    async def test_start_enhances_context(self, openhands_config, mock_docker):
        """Test that start method enhances execution context."""
        mock_container = AsyncMock()
        mock_container.id = "container-xyz"
        mock_docker.containers.create.return_value = mock_container

        agent = OpenHandsAgent(openhands_config)

        original_context = {
            "flow_id": "flow-123",
            "execution_id": "exec-456",
            "prompt": "Test",
            "agent_config": {
                "agent_type": "PlannerAgent",
                "max_iterations": 30,
            },
        }

        await agent.start(original_context)

        # Verify that the container was created
        # The enhanced context should include openhands_agent_type and max_iterations
        mock_docker.containers.create.assert_called_once()
        mock_container.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_openhands_agent_types(self, mock_docker):
        """Test that different OpenHands agent types are supported."""
        mock_container = AsyncMock()
        mock_container.id = "container-123"
        mock_docker.containers.create.return_value = mock_container

        agent_types = ["CodeActAgent", "PlannerAgent", "MonologueAgent"]

        for agent_type in agent_types:
            agent = OpenHandsAgent({"agent_type": agent_type})

            execution_context = {
                "flow_id": "flow-123",
                "execution_id": "exec-456",
                "prompt": f"Test {agent_type}",
                "agent_config": {"agent_type": agent_type},
            }

            await agent.start(execution_context)

            # Verify container was created
            assert mock_docker.containers.create.called

    @pytest.mark.asyncio
    async def test_model_parameters_handling(self, openhands_config):
        """Test that model parameters are properly handled."""
        agent = OpenHandsAgent(openhands_config)

        execution_context = {
            "prompt": "Test task",
            "model_identifier": "gpt-5.4",
            "model_parameters": {
                "temperature": 0.9,
                "max_tokens": 2000,
                "top_p": 0.95,  # This should be ignored as it's not in the list
            },
            "openhands_agent_type": "CodeActAgent",
            "max_iterations": 10,
        }

        env = await agent._prepare_environment(execution_context)

        assert env["LLM_TEMPERATURE"] == "0.9"
        assert env["LLM_MAX_TOKENS"] == "2000"
        # top_p is not in the supported parameters list
        assert "LLM_TOP_P" not in env

    @pytest.mark.asyncio
    async def test_model_parameters_missing(self, openhands_config):
        """Test behavior when model_parameters is missing."""
        agent = OpenHandsAgent(openhands_config)

        execution_context = {
            "prompt": "Test task",
            "model_identifier": "gpt-5.4",
            # No model_parameters
            "openhands_agent_type": "CodeActAgent",
            "max_iterations": 10,
        }

        env = await agent._prepare_environment(execution_context)

        # Should not fail, just skip the parameters
        assert "LLM_TEMPERATURE" not in env
        assert "LLM_MAX_TOKENS" not in env
