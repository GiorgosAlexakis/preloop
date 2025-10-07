"""OpenHands agent implementation."""

import logging
import os
from typing import Any, Dict

from .container import ContainerAgentExecutor

logger = logging.getLogger(__name__)


class OpenHandsAgent(ContainerAgentExecutor):
    """
    OpenHands agent executor.

    Runs OpenHands (formerly OpenDevin) in a Docker container for
    autonomous software development tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OpenHands agent.

        Args:
            config: Agent configuration including:
                - agent_type: Specific OpenHands agent type (CodeActAgent, etc.)
                - max_iterations: Maximum number of agent iterations
                - custom settings for OpenHands
        """
        # Use OpenHands Docker image
        image = os.getenv("OPENHANDS_IMAGE", "ghcr.io/all-hands-ai/openhands:latest")

        super().__init__(
            agent_type="openhands",
            config=config,
            image=image,
            use_kubernetes=os.getenv("USE_KUBERNETES", "false").lower() == "true",
        )

    async def start(self, execution_context: Dict[str, Any]) -> str:
        """
        Start OpenHands agent with specialized configuration.

        Args:
            execution_context: Execution context

        Returns:
            Container ID or pod name
        """
        # Enhance execution context with OpenHands-specific settings
        openhands_context = execution_context.copy()

        # Extract OpenHands agent config
        agent_config = execution_context.get("agent_config", {})

        # Set OpenHands agent type (CodeActAgent, PlannerAgent, etc.)
        openhands_agent_type = agent_config.get("agent_type", "CodeActAgent")
        openhands_context["openhands_agent_type"] = openhands_agent_type

        # Set max iterations
        max_iterations = agent_config.get("max_iterations", 10)
        openhands_context["max_iterations"] = max_iterations

        self.logger.info(
            f"Starting OpenHands with agent_type={openhands_agent_type}, "
            f"max_iterations={max_iterations}"
        )

        # Start the container with enhanced context
        return await super().start(openhands_context)

    async def _prepare_environment(
        self, execution_context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Prepare OpenHands-specific environment variables.

        Args:
            execution_context: Execution context

        Returns:
            Environment variables dict
        """
        env = {
            "AGENT_TYPE": execution_context.get("openhands_agent_type", "CodeActAgent"),
            "MAX_ITERATIONS": str(execution_context.get("max_iterations", 10)),
            "PROMPT": execution_context["prompt"],
        }

        # Add AI model configuration
        if "model_identifier" in execution_context:
            env["LLM_MODEL"] = execution_context["model_identifier"]
        if "model_api_key" in execution_context:
            env["LLM_API_KEY"] = execution_context["model_api_key"]
        if "model_provider" in execution_context:
            env["LLM_PROVIDER"] = execution_context["model_provider"]

        # Add model parameters if specified
        model_params = execution_context.get("model_parameters", {})
        if "temperature" in model_params:
            env["LLM_TEMPERATURE"] = str(model_params["temperature"])
        if "max_tokens" in model_params:
            env["LLM_MAX_TOKENS"] = str(model_params["max_tokens"])

        # MCP configuration is already added by ContainerAgentExecutor
        # OpenHands can access MCP tools via the environment variables:
        # - MCP_ALLOWED_SERVERS: comma-separated list of allowed servers
        # - MCP_ALLOWED_TOOLS: JSON map of server -> [tools]
        # - SPACEBRIDGE_MCP_URL: URL to SpaceBridge MCP endpoint

        return env
