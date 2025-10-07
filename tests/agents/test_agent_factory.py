"""Tests for agent factory."""

import pytest

from spacebridge.agents.factory import create_agent_executor
from spacebridge.agents.openhands import OpenHandsAgent


class TestAgentFactory:
    """Test agent factory functionality."""

    def test_create_openhands_agent(self):
        """Test creating an OpenHands agent."""
        config = {
            "agent_type": "CodeActAgent",
            "max_iterations": 10,
        }

        agent = create_agent_executor("openhands", config)

        assert isinstance(agent, OpenHandsAgent)
        assert agent.agent_type == "openhands"
        assert agent.config == config

    def test_create_openhands_agent_case_insensitive(self):
        """Test that agent type is case-insensitive."""
        config = {"agent_type": "CodeActAgent"}

        # Test various cases
        for agent_type in ["openhands", "OpenHands", "OPENHANDS", "OpEnHaNdS"]:
            agent = create_agent_executor(agent_type, config)
            assert isinstance(agent, OpenHandsAgent)

    def test_create_claude_code_agent_not_implemented(self):
        """Test that Claude Code agent raises NotImplementedError."""
        config = {}

        with pytest.raises(NotImplementedError, match="Claude Code agent"):
            create_agent_executor("claude-code", config)

    def test_create_aider_agent_not_implemented(self):
        """Test that Aider agent raises NotImplementedError."""
        config = {}

        with pytest.raises(NotImplementedError, match="Aider agent"):
            create_agent_executor("aider", config)

    def test_unsupported_agent_type(self):
        """Test that unsupported agent type raises ValueError."""
        config = {}

        with pytest.raises(ValueError, match="Unsupported agent type"):
            create_agent_executor("unknown-agent", config)

    def test_unsupported_agent_type_message(self):
        """Test that error message lists supported types."""
        config = {}

        try:
            create_agent_executor("invalid", config)
        except ValueError as e:
            error_msg = str(e)
            assert "invalid" in error_msg
            assert "openhands" in error_msg
            assert "claude-code" in error_msg
            assert "aider" in error_msg

    def test_config_passed_to_agent(self):
        """Test that configuration is passed to the agent."""
        config = {
            "agent_type": "PlannerAgent",
            "max_iterations": 20,
            "custom_setting": "test_value",
        }

        agent = create_agent_executor("openhands", config)

        assert agent.config == config
        assert agent.config["agent_type"] == "PlannerAgent"
        assert agent.config["max_iterations"] == 20
        assert agent.config["custom_setting"] == "test_value"

    def test_empty_config(self):
        """Test creating agent with empty configuration."""
        agent = create_agent_executor("openhands", {})

        assert isinstance(agent, OpenHandsAgent)
        assert agent.config == {}

    def test_create_multiple_agents(self):
        """Test creating multiple agent instances."""
        config1 = {"agent_type": "CodeActAgent"}
        config2 = {"agent_type": "PlannerAgent"}

        agent1 = create_agent_executor("openhands", config1)
        agent2 = create_agent_executor("openhands", config2)

        # Should be different instances
        assert agent1 is not agent2
        assert agent1.config != agent2.config

    def test_agent_type_validation(self):
        """Test that agent type validation works correctly."""
        valid_types = ["openhands", "OPENHANDS", "OpenHands"]
        invalid_types = ["open hands", "open-hands-v2", "", "  ", "123"]

        # Valid types should work
        for agent_type in valid_types:
            agent = create_agent_executor(agent_type, {})
            assert isinstance(agent, OpenHandsAgent)

        # Invalid types should raise ValueError
        for agent_type in invalid_types:
            with pytest.raises((ValueError, NotImplementedError)):
                create_agent_executor(agent_type, {})
