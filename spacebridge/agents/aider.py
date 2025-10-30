"""Aider agent implementation."""

import json
import logging
import os
from typing import Any, Dict

from aiodocker.exceptions import DockerError

from spacebridge.services.mcp_config_service import MCPConfigService

from .container import ContainerAgentExecutor

logger = logging.getLogger(__name__)


class AiderAgent(ContainerAgentExecutor):
    """
    Aider agent executor.

    Runs Aider (AI pair programming in your terminal) in a Docker container
    for autonomous coding tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Aider agent.

        Args:
            config: Agent configuration including:
                - model: AI model to use (default: gpt-4)
                - edit_format: Edit format (default: whole)
                - custom settings for Aider
        """
        # Use Aider Docker image
        image = os.getenv("AIDER_IMAGE", "paulgauthier/aider:latest")

        super().__init__(
            agent_type="aider",
            config=config,
            image=image,
            use_kubernetes=os.getenv("USE_KUBERNETES", "false").lower() == "true",
        )

    async def start(self, execution_context: Dict[str, Any]) -> str:
        """
        Start Aider agent with specialized configuration.

        Args:
            execution_context: Execution context

        Returns:
            Container ID or pod name
        """
        # Enhance execution context with Aider-specific settings
        aider_context = execution_context.copy()

        # Extract Aider config
        agent_config = execution_context.get("agent_config", {})

        # Set Aider model - prefer model_identifier from AIModel, fall back to agent_config
        model = (
            execution_context.get("model_identifier")
            or agent_config.get("model")
            or "gpt-4"
        )
        aider_context["aider_model"] = model

        # Set edit format
        edit_format = agent_config.get("edit_format", "whole")
        aider_context["aider_edit_format"] = edit_format

        self.logger.info(
            f"Starting Aider with model={model}, edit_format={edit_format}"
        )

        # Start the container with enhanced context
        return await super().start(aider_context)

    async def _start_docker_container(self, execution_context: Dict[str, Any]) -> str:
        """
        Start Aider in a Docker container.

        Args:
            execution_context: Execution context

        Returns:
            Container ID
        """
        docker = await self._get_docker_client()
        execution_id = execution_context["execution_id"]

        # Prepare Aider-specific environment variables
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

        # Build the command to run Aider with the prompt
        prompt = execution_context["prompt"]
        model = execution_context.get("aider_model", "gpt-4")
        edit_format = execution_context.get("aider_edit_format", "whole")

        # Escape prompt for shell (use single quotes to avoid escaping issues)
        escaped_prompt = prompt.replace("'", "'\\''")

        # Use direct command array instead of bash -c for better argument handling
        cmd = [
            "aider",
            "--model",
            model,
            "--edit-format",
            edit_format,
            "--yes",
            "--message",
            prompt,
        ]

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
                f"Started Aider container {container_id[:12]} for execution {execution_id}"
            )
            return container_id

        except DockerError as e:
            self.logger.error(
                f"Failed to start Aider container for execution {execution_id}: {e}"
            )
            raise RuntimeError(f"Failed to start Aider container: {e}")

    async def _prepare_environment(
        self, execution_context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Prepare Aider-specific environment variables.

        Args:
            execution_context: Execution context

        Returns:
            Environment variables dict
        """
        env = {}

        # Add AI model configuration
        if "model_api_key" in execution_context:
            # Aider uses OPENAI_API_KEY by default
            env["OPENAI_API_KEY"] = execution_context["model_api_key"]

        # Add model provider-specific keys
        model_provider = execution_context.get("model_provider", "").lower()
        if model_provider == "anthropic" and "model_api_key" in execution_context:
            env["ANTHROPIC_API_KEY"] = execution_context["model_api_key"]
        elif model_provider == "openai" and "model_api_key" in execution_context:
            env["OPENAI_API_KEY"] = execution_context["model_api_key"]

        return env
