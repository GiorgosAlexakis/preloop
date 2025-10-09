"""Claude Code agent implementation."""

import json
import logging
import os
from typing import Any, Dict

from aiodocker.exceptions import DockerError

from spacebridge.services.mcp_config_service import MCPConfigService

from .container import ContainerAgentExecutor

logger = logging.getLogger(__name__)


class ClaudeCodeAgent(ContainerAgentExecutor):
    """
    Claude Code agent executor.

    Runs a Claude-based coding agent in a Docker container using Anthropic's API.
    This uses a simple Python-based agent that leverages Claude for code generation
    and execution.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Claude Code agent.

        Args:
            config: Agent configuration including:
                - model: Claude model to use (default: claude-sonnet-4)
                - max_tokens: Maximum tokens for response (default: 4096)
        """
        # Use Python base image with Anthropic SDK
        image = os.getenv("CLAUDE_CODE_IMAGE", "python:3.11-slim")

        super().__init__(
            agent_type="claude-code",
            config=config,
            image=image,
            use_kubernetes=os.getenv("USE_KUBERNETES", "false").lower() == "true",
        )

    async def start(self, execution_context: Dict[str, Any]) -> str:
        """
        Start Claude Code agent with specialized configuration.

        Args:
            execution_context: Execution context

        Returns:
            Container ID or pod name
        """
        # Enhance execution context with Claude-specific settings
        claude_context = execution_context.copy()

        # Extract Claude config
        agent_config = execution_context.get("agent_config", {})

        # Set Claude model
        model = agent_config.get("model", "claude-sonnet-4")
        claude_context["claude_model"] = model

        # Set max tokens
        max_tokens = agent_config.get("max_tokens", 4096)
        claude_context["claude_max_tokens"] = max_tokens

        self.logger.info(f"Starting Claude Code agent with model={model}")

        # Start the container with enhanced context
        return await super().start(claude_context)

    async def _start_docker_container(self, execution_context: Dict[str, Any]) -> str:
        """
        Start Claude Code agent in a Docker container.

        Args:
            execution_context: Execution context

        Returns:
            Container ID
        """
        docker = await self._get_docker_client()
        execution_id = execution_context["execution_id"]

        # Prepare Claude-specific environment variables
        env = await self._prepare_environment(execution_context)

        # Add MCP configuration
        allowed_mcp_servers = execution_context.get("allowed_mcp_servers", [])
        allowed_mcp_tools = execution_context.get("allowed_mcp_tools", [])
        account_api_token = execution_context.get("account_api_token")

        if allowed_mcp_servers or allowed_mcp_tools:
            mcp_env = MCPConfigService.generate_mcp_environment_vars(
                allowed_mcp_servers, allowed_mcp_tools
            )
            env.update(mcp_env)

            if account_api_token:
                env["SPACEBRIDGE_API_TOKEN"] = account_api_token

            mcp_config = MCPConfigService.generate_mcp_config(
                allowed_mcp_servers,
                allowed_mcp_tools,
                account_api_token=account_api_token,
            )
            env["MCP_CONFIG_JSON"] = json.dumps(mcp_config)

        # Build the command - install anthropic SDK and run a simple agent
        prompt = execution_context["prompt"]
        model = execution_context.get("claude_model", "claude-sonnet-4")

        # Escape prompt for Python string
        escaped_prompt = prompt.replace("'", "\\'").replace('"', '\\"')

        # Create a simple Python script that uses Claude
        script = f"""
import os
import sys

# Install anthropic if not available
try:
    import anthropic
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic"])
    import anthropic

# Initialize Claude client
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Create message
message = client.messages.create(
    model="{model}",
    max_tokens={execution_context.get("claude_max_tokens", 4096)},
    messages=[
        {{
            "role": "user",
            "content": "{escaped_prompt}"
        }}
    ]
)

# Print response
print(message.content[0].text)
"""

        cmd = ["python", "-c", script]

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
                "AutoRemove": False,
                "NetworkMode": os.getenv("AGENT_NETWORK_MODE", "bridge"),
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
                f"Started Claude Code container {container_id[:12]} for execution {execution_id}"
            )
            return container_id

        except DockerError as e:
            self.logger.error(
                f"Failed to start Claude Code container for execution {execution_id}: {e}"
            )
            raise RuntimeError(f"Failed to start Claude Code container: {e}")

    async def _prepare_environment(
        self, execution_context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Prepare Claude-specific environment variables.

        Args:
            execution_context: Execution context

        Returns:
            Environment variables dict
        """
        env = {}

        # Add Anthropic API key
        if "model_api_key" in execution_context:
            env["ANTHROPIC_API_KEY"] = execution_context["model_api_key"]

        return env
