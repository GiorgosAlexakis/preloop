"""OpenAI Codex CLI agent implementation."""

import json
import logging
import os
from typing import Any, Dict

from aiodocker.exceptions import DockerError

from spacebridge.services.mcp_config_service import MCPConfigService

from .container import ContainerAgentExecutor

logger = logging.getLogger(__name__)


class CodexAgent(ContainerAgentExecutor):
    """
    OpenAI Codex CLI agent executor.

    Runs OpenAI's Codex CLI tool (https://github.com/openai/codex) in a Docker
    container for autonomous coding tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Codex agent.

        Args:
            config: Agent configuration including:
                - model: OpenAI model to use (default: gpt-4)
                - custom settings for Codex CLI
        """
        # Use Node.js base image for Codex CLI
        image = os.getenv("CODEX_IMAGE", "node:20-slim")

        super().__init__(
            agent_type="codex",
            config=config,
            image=image,
            use_kubernetes=os.getenv("USE_KUBERNETES", "false").lower() == "true",
        )

    async def start(self, execution_context: Dict[str, Any]) -> str:
        """
        Start Codex agent with specialized configuration.

        Args:
            execution_context: Execution context

        Returns:
            Container ID or pod name
        """
        # Enhance execution context with Codex-specific settings
        codex_context = execution_context.copy()

        # Extract Codex config
        agent_config = execution_context.get("agent_config", {})

        # Set Codex model - prefer model_identifier from AIModel, fall back to agent_config
        model_identifier = execution_context.get("model_identifier")
        agent_model = agent_config.get("model")

        self.logger.info(
            f"Codex model resolution: model_identifier={model_identifier}, "
            f"agent_config.model={agent_model}"
        )

        model = model_identifier or agent_model or "gpt-4"
        codex_context["codex_model"] = model

        self.logger.info(f"Starting Codex CLI with model={model}")

        # Start the container with enhanced context
        return await super().start(codex_context)

    async def _start_docker_container(self, execution_context: Dict[str, Any]) -> str:
        """
        Start Codex CLI in a Docker container.

        Args:
            execution_context: Execution context

        Returns:
            Container ID
        """
        docker = await self._get_docker_client()
        execution_id = execution_context["execution_id"]

        # Log execution context for debugging
        self.logger.info(
            f"_start_docker_container called with codex_model={execution_context.get('codex_model')}, "
            f"model_identifier={execution_context.get('model_identifier')}, "
            f"has_model_api_key={('model_api_key' in execution_context)}"
        )

        # Prepare Codex-specific environment variables
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

            # Generate MCP config file
            mcp_config = MCPConfigService.generate_mcp_config(
                allowed_mcp_servers,
                allowed_mcp_tools,
                account_api_token=account_api_token,
            )
            env["MCP_CONFIG_JSON"] = json.dumps(mcp_config)

        # Build the command to run Codex CLI with the prompt
        prompt = execution_context["prompt"]
        # Try codex_model first (set by start()), then model_identifier, then default
        model = (
            execution_context.get("codex_model")
            or execution_context.get("model_identifier")
            or "gpt-4"
        )

        self.logger.info(f"Using model for Codex CLI: {model}")

        # Escape prompt for shell
        escaped_prompt = prompt.replace('"', '\\"').replace("'", "\\'")

        # Create a script that installs codex and runs it
        script = f"""
set -e

# Install Codex CLI globally
npm install -g @openai/codex

# Create config directory
mkdir -p ~/.codex

# Debug: Print environment variables
echo "=== DEBUG: Environment variables ==="
echo "OPENAI_API_KEY: ${{OPENAI_API_KEY:0:10}}..." || echo "OPENAI_API_KEY: NOT SET"
echo "Model being configured: {model}"
echo "==================================="

# Create config file with API key and model
cat > ~/.codex/config.toml << EOF
[ai]
api_key = "$OPENAI_API_KEY"
model = "{model}"

[settings]
zero_data_retention = true
EOF

# Debug: Show config file
echo "=== DEBUG: Config file content ==="
cat ~/.codex/config.toml
echo "==================================="

# Run codex in non-interactive mode with the prompt
echo "{escaped_prompt}" | codex exec --model "{model}" --skip-git-repo-check
"""

        self.logger.info(
            f"Container config: model={model}, "
            f"has_api_key={'OPENAI_API_KEY' in env}, "
            f"env_vars={list(env.keys())}"
        )

        cmd = ["bash", "-c", script]

        # Container configuration
        container_config = {
            "Image": self.image,
            "Env": [f"{k}={v}" for k, v in env.items()],
            "Cmd": cmd,
            "WorkingDir": "/workspace",
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
                f"Started Codex CLI container {container_id[:12]} for execution {execution_id}"
            )
            return container_id

        except DockerError as e:
            self.logger.error(
                f"Failed to start Codex CLI container for execution {execution_id}: {e}"
            )
            raise RuntimeError(f"Failed to start Codex CLI container: {e}")

    async def _prepare_environment(
        self, execution_context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Prepare Codex-specific environment variables.

        Args:
            execution_context: Execution context

        Returns:
            Environment variables dict
        """
        env = {}

        # Add OpenAI API key
        if "model_api_key" in execution_context:
            env["OPENAI_API_KEY"] = execution_context["model_api_key"]

        # Set home directory for config storage
        env["HOME"] = "/root"

        return env
