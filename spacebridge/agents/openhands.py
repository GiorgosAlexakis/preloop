"""OpenHands agent implementation."""

import json
import logging
import os
from typing import Any, Dict

from aiodocker.exceptions import DockerError

from spacebridge.services.mcp_config_service import MCPConfigService

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
        # Use OpenHands Docker image (custom build with tmux for local runtime)
        image = os.getenv("OPENHANDS_IMAGE", "spacebridge/openhands:latest-tmux")

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

    async def _start_docker_container(self, execution_context: Dict[str, Any]) -> str:
        """
        Start OpenHands in a Docker container with headless mode configuration.

        Args:
            execution_context: Execution context

        Returns:
            Container ID
        """
        docker = await self._get_docker_client()
        execution_id = execution_context["execution_id"]

        # Prepare OpenHands-specific environment variables
        env = await self._prepare_environment(execution_context)

        # Add MCP configuration using MCP config service
        allowed_mcp_servers = execution_context.get("allowed_mcp_servers", [])
        allowed_mcp_tools = execution_context.get("allowed_mcp_tools", [])
        account_api_token = execution_context.get("account_api_token")

        if allowed_mcp_servers or allowed_mcp_tools:
            # Generate MCP environment variables
            mcp_env = MCPConfigService.generate_mcp_environment_vars(
                allowed_mcp_servers, allowed_mcp_tools
            )
            env.update(mcp_env)

            # Add account API token for SpaceBridge MCP authentication
            if account_api_token:
                env["SPACEBRIDGE_API_TOKEN"] = account_api_token
            else:
                self.logger.warning(
                    "No account API token provided for SpaceBridge MCP access"
                )

            # Generate MCP config file (will be used by agents that support config files)
            mcp_config = MCPConfigService.generate_mcp_config(
                allowed_mcp_servers,
                allowed_mcp_tools,
                account_api_token=account_api_token,
            )
            env["MCP_CONFIG_JSON"] = json.dumps(mcp_config)

        # Build the command to run OpenHands in headless mode
        # We need to completely bypass the entrypoint.sh script
        max_iterations = execution_context.get("max_iterations", 10)
        prompt = execution_context["prompt"]

        # Create the command that runs OpenHands directly
        # Using bash -c to ensure proper execution without entrypoint.sh
        cmd = [
            "bash",
            "-c",
            f'cd /app && /app/.venv/bin/python -m openhands.core.main -t "{prompt}" -i {max_iterations}',
        ]

        # Container configuration
        container_config = {
            "Image": self.image,
            "Env": [f"{k}={v}" for k, v in env.items()],
            # Override entrypoint completely - set to empty list to disable entrypoint.sh
            "Entrypoint": [],
            # Run OpenHands in headless mode
            "Cmd": cmd,
            "WorkingDir": "/app",
            "Labels": {
                "spacebridge.flow_id": execution_context["flow_id"],
                "spacebridge.execution_id": execution_id,
                "spacebridge.agent_type": self.agent_type,
            },
            "HostConfig": {
                "AutoRemove": False,  # Keep container for log retrieval
                "NetworkMode": os.getenv(
                    "AGENT_NETWORK_MODE", "bridge"
                ),  # Use bridge by default
                # Resource limits
                "Memory": int(os.getenv("AGENT_MEMORY_LIMIT", "2g").replace("g", ""))
                * 1024
                * 1024
                * 1024,
                "CpuQuota": int(os.getenv("AGENT_CPU_QUOTA", "100000")),
            },
        }

        try:
            # Pull image if not available
            try:
                await docker.images.inspect(self.image)
            except DockerError:
                self.logger.info(f"Pulling image {self.image}...")
                await docker.images.pull(self.image)

            # Create and start container
            container = await docker.containers.create(config=container_config)
            container_id = container.id

            await container.start()

            self._containers[container_id] = container

            self.logger.info(
                f"Started OpenHands container {container_id[:12]} in headless mode for execution {execution_id}"
            )
            return container_id

        except DockerError as e:
            self.logger.error(
                f"Failed to start OpenHands container for execution {execution_id}: {e}"
            )
            raise RuntimeError(f"Failed to start OpenHands container: {e}")

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
            "RUNTIME": "local",  # Use local runtime - runs directly in the container without Docker-in-Docker
            "WORKSPACE_BASE": "/workspace",  # Working directory for the agent
        }

        # Add AI model configuration
        if "model_identifier" in execution_context:
            env["LLM_MODEL"] = execution_context["model_identifier"]
        if "model_api_key" in execution_context:
            env["LLM_API_KEY"] = execution_context["model_api_key"]
        if "model_provider" in execution_context:
            env["LLM_PROVIDER"] = execution_context["model_provider"]

        # Add model parameters if specified
        model_params = execution_context.get("model_parameters") or {}
        if model_params and "temperature" in model_params:
            env["LLM_TEMPERATURE"] = str(model_params["temperature"])
        if model_params and "max_tokens" in model_params:
            env["LLM_MAX_TOKENS"] = str(model_params["max_tokens"])

        # MCP configuration is already added by ContainerAgentExecutor
        # OpenHands can access MCP tools via the environment variables:
        # - MCP_ALLOWED_SERVERS: comma-separated list of allowed servers
        # - MCP_ALLOWED_TOOLS: JSON map of server -> [tools]
        # - SPACEBRIDGE_MCP_URL: URL to SpaceBridge MCP endpoint

        return env
