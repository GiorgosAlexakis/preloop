"""Tests for Aider agent gateway configuration."""

from unittest.mock import AsyncMock, patch

import pytest

from preloop.agents.aider import AiderAgent


class TestAiderGatewayConfiguration:
    """Gateway-specific Aider configuration behavior."""

    @pytest.mark.asyncio
    async def test_start_prefers_gateway_model_alias(self):
        """Gateway-enabled Aider flows should run through the gateway alias."""
        agent = AiderAgent({})
        context = {
            "model_gateway_enabled": True,
            "model_gateway_model_alias": "google/gemini-2.5-pro",
            "model_identifier": "gemini-2.5-pro",
            "execution_id": "exec-1",
            "flow_id": "flow-1",
            "prompt": "test",
            "agent_config": {},
        }

        with patch.object(
            agent, "_start_docker_container", new_callable=AsyncMock, return_value="cid"
        ) as mock_start:
            await agent.start(context)

        call_ctx = mock_start.call_args[0][0]
        assert call_ctx["aider_model"] == "google/gemini-2.5-pro"

    @pytest.mark.asyncio
    async def test_gateway_env_uses_openai_compatible_endpoint(self):
        """Aider/litellm should use the OpenAI-compatible gateway endpoint."""
        agent = AiderAgent({})
        env = await agent._prepare_environment(
            {
                "model_gateway_enabled": True,
                "model_gateway_token": "gw-token-123",
                "model_gateway_url": "https://review.preloop.ai/gemini/v1beta",
            }
        )

        assert env["OPENAI_API_KEY"] == "gw-token-123"
        assert env["OPENAI_API_BASE"] == "https://review.preloop.ai/openai/v1"
        assert env["PRELOOP_MODEL_GATEWAY_TOKEN"] == "gw-token-123"
