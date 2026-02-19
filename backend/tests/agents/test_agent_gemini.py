"""Tests for Gemini agent implementation."""

import os
from unittest.mock import patch, AsyncMock

import pytest

from preloop.agents.gemini import GeminiAgent


class TestGeminiAgentInit:
    """Test GeminiAgent initialization."""

    def test_default_image(self):
        """Default image is the official Gemini CLI sandbox."""
        agent = GeminiAgent({})
        assert agent.agent_type == "gemini"
        assert agent.image == "docker/sandbox-templates:gemini"

    def test_custom_image_from_env(self):
        """GEMINI_IMAGE env var overrides default image."""
        with patch.dict(os.environ, {"GEMINI_IMAGE": "custom/gemini:latest"}):
            agent = GeminiAgent({})
            assert agent.image == "custom/gemini:latest"

    def test_config_stored(self):
        """Configuration is stored on the agent."""
        config = {"model": "gemini-3-pro-preview", "custom": "value"}
        agent = GeminiAgent(config)
        assert agent.config == config


class TestGeminiKubernetesDetection:
    """Test Kubernetes environment detection."""

    def test_explicit_true(self):
        """USE_KUBERNETES=true forces Kubernetes mode."""
        with patch.dict(os.environ, {"USE_KUBERNETES": "true"}):
            agent = GeminiAgent({})
            assert agent._detect_kubernetes_environment() is True

    def test_explicit_false(self):
        """USE_KUBERNETES=false forces Docker mode."""
        with patch.dict(os.environ, {"USE_KUBERNETES": "false"}):
            agent = GeminiAgent({})
            assert agent._detect_kubernetes_environment() is False

    def test_no_k8s_indicators(self):
        """Defaults to Docker when no k8s indicators found."""
        env_clean = {
            "USE_KUBERNETES": "",
            "KUBERNETES_SERVICE_HOST": "",
        }
        with patch.dict(os.environ, env_clean, clear=False):
            with patch("os.path.exists", return_value=False):
                agent = GeminiAgent({})
                assert agent._detect_kubernetes_environment() is False


class TestGeminiModelResolution:
    """Test model resolution logic in start()."""

    @pytest.mark.asyncio
    async def test_model_identifier_takes_priority(self):
        """model_identifier from AIModel takes priority over agent_config."""
        agent = GeminiAgent({})
        context = {
            "model_identifier": "gemini-3-flash",
            "agent_config": {"model": "gemini-3-pro-preview"},
            "execution_id": "test-123",
            "flow_id": "flow-1",
        }
        with patch.object(
            agent, "_start_docker_container", new_callable=AsyncMock, return_value="cid"
        ) as mock_start:
            with patch.object(agent, "use_kubernetes", False):
                await agent.start(context)
                call_ctx = mock_start.call_args[0][0]
                assert call_ctx["gemini_model"] == "gemini-3-flash"

    @pytest.mark.asyncio
    async def test_agent_config_model_fallback(self):
        """Falls back to agent_config.model when model_identifier is absent."""
        agent = GeminiAgent({})
        context = {
            "agent_config": {"model": "custom-gemini"},
            "execution_id": "test-123",
            "flow_id": "flow-1",
        }
        with patch.object(
            agent, "_start_docker_container", new_callable=AsyncMock, return_value="cid"
        ) as mock_start:
            with patch.object(agent, "use_kubernetes", False):
                await agent.start(context)
                call_ctx = mock_start.call_args[0][0]
                assert call_ctx["gemini_model"] == "custom-gemini"


class TestGeminiBuildScript:
    """Test _build_gemini_script method."""

    def test_script_contains_prompt(self):
        """Generated script contains the base64-encoded prompt."""
        import base64

        agent = GeminiAgent({})
        prompt = "Refactor the database module"
        context = {
            "prompt": prompt,
            "execution_id": "exec-1",
            "flow_name": "test-flow",
        }
        script = agent._build_gemini_script(context)
        # Prompt is base64-encoded for shell safety
        expected_b64 = base64.b64encode(prompt.encode()).decode()
        assert expected_b64 in script

    def test_script_contains_model(self):
        """Generated script uses the configured model."""
        agent = GeminiAgent({})
        context = {
            "prompt": "test",
            "gemini_model": "gemini-3-flash",
            "execution_id": "exec-1",
            "flow_name": "test-flow",
        }
        script = agent._build_gemini_script(context)
        assert "gemini-3-flash" in script

    def test_script_has_post_exec_sleep_trap(self):
        """Script includes the post-exec debug sleep trap (parity with Codex)."""
        agent = GeminiAgent({})
        context = {
            "prompt": "test",
            "execution_id": "exec-1",
            "flow_name": "test-flow",
        }
        script = agent._build_gemini_script(context)
        assert "_post_exec_sleep()" in script
        assert "trap _post_exec_sleep EXIT" in script

    def test_script_contains_gemini_command(self):
        """Script runs gemini CLI with correct flags."""
        agent = GeminiAgent({})
        context = {
            "prompt": "test",
            "execution_id": "exec-1",
            "flow_name": "test-flow",
        }
        script = agent._build_gemini_script(context)
        assert "gemini" in script
        assert "--yolo" in script

    def test_script_mcp_config(self):
        """Script registers MCP server via gemini mcp add CLI command."""
        agent = GeminiAgent({})
        context = {
            "prompt": "test",
            "execution_id": "exec-1",
            "flow_name": "test-flow",
            "_mcp_tool_timeout": 900,
        }
        script = agent._build_gemini_script(context)
        assert "gemini mcp add preloop" in script
        assert "-t http" in script
        assert "-s user" in script
        assert "--trust" in script
        assert "-H" in script
        assert "$PRELOOP_API_TOKEN" in script

    def test_prompt_with_single_quotes(self):
        """Prompt with single quotes is handled safely via base64 encoding."""
        import base64

        agent = GeminiAgent({})
        prompt = "Don't break the build"
        context = {
            "prompt": prompt,
            "execution_id": "exec-1",
            "flow_name": "test-flow",
        }
        script = agent._build_gemini_script(context)
        # Prompt is base64-encoded, so single quotes are safe
        expected_b64 = base64.b64encode(prompt.encode()).decode()
        assert expected_b64 in script


class TestGeminiPrepareEnvironment:
    """Test _prepare_environment method."""

    @pytest.mark.asyncio
    async def test_gemini_api_key(self):
        """Sets GEMINI_API_KEY from model_api_key."""
        agent = GeminiAgent({})
        context = {"model_api_key": "gemini-test-key"}
        env = await agent._prepare_environment(context)
        assert env["GEMINI_API_KEY"] == "gemini-test-key"

    @pytest.mark.asyncio
    async def test_no_hardcoded_home(self):
        """HOME should NOT be hardcoded (container.py handles it)."""
        agent = GeminiAgent({})
        context = {"model_api_key": "key"}
        env = await agent._prepare_environment(context)
        assert "HOME" not in env

    @pytest.mark.asyncio
    async def test_default_mcp_timeout(self):
        """Default MCP timeout is 600 seconds."""
        agent = GeminiAgent({})
        context = {}
        env = await agent._prepare_environment(context)
        assert env["MCP_TOOL_TIMEOUT"] == "600"
        assert context["_mcp_tool_timeout"] == 600

    @pytest.mark.asyncio
    async def test_no_api_key_when_missing(self):
        """No GEMINI_API_KEY set when model_api_key is absent."""
        agent = GeminiAgent({})
        context = {}
        env = await agent._prepare_environment(context)
        assert "GEMINI_API_KEY" not in env


class TestGeminiKubernetesStartup:
    """Test _start_kubernetes_pod sets correct command and args."""

    @pytest.mark.asyncio
    async def test_k8s_sets_container_command_and_args(self):
        """K8s path sets _container_command=['/bin/bash'] and _container_args=['-c', script]."""
        agent = GeminiAgent({})
        context = {
            "prompt": "test prompt",
            "gemini_model": "gemini-3-flash",
            "model_identifier": "gemini-3-flash",
            "model_api_key": "key-123",
            "execution_id": "exec-k8s-1",
            "flow_id": "flow-1",
            "flow_name": "test-flow",
        }
        with patch(
            "preloop.agents.container.ContainerAgentExecutor._start_kubernetes_pod",
            new_callable=AsyncMock,
            return_value="job-name",
        ) as mock_parent:
            await agent._start_kubernetes_pod(context)
            call_ctx = mock_parent.call_args[0][0]
            assert call_ctx["_container_command"] == ["/bin/bash"]
            assert call_ctx["_container_args"][0] == "-c"
            assert len(call_ctx["_container_args"]) == 2
