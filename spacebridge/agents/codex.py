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
        # Use official Codex Universal image
        image = os.getenv("CODEX_IMAGE", "ghcr.io/openai/codex-universal:latest")

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

        # Add account API token for SpaceBridge MCP authentication (always for Codex)
        account_api_token = execution_context.get("account_api_token")
        if account_api_token:
            env["SPACEBRIDGE_API_TOKEN"] = account_api_token
        else:
            self.logger.warning(
                "No account API token provided for SpaceBridge MCP access"
            )

        # Set SpaceBridge MCP URL (defaults to host.docker.internal for container access)
        env["SPACEBRIDGE_MCP_URL"] = os.getenv(
            "SPACEBRIDGE_MCP_URL", "http://host.docker.internal:8000/mcp/v1"
        )

        # Add MCP configuration using MCP config service
        allowed_mcp_servers = execution_context.get("allowed_mcp_servers", [])
        allowed_mcp_tools = execution_context.get("allowed_mcp_tools", [])

        if allowed_mcp_servers or allowed_mcp_tools:
            # Generate MCP environment variables
            mcp_env = MCPConfigService.generate_mcp_environment_vars(
                allowed_mcp_servers, allowed_mcp_tools
            )
            env.update(mcp_env)

            # Generate MCP config file
            mcp_config = MCPConfigService.generate_mcp_config(
                allowed_mcp_servers,
                allowed_mcp_tools,
                account_api_token=account_api_token,
            )
            env["MCP_CONFIG_JSON"] = json.dumps(mcp_config)

        # Build the Codex script using shared method
        script = self._build_codex_script(execution_context)

        # Determine working directory based on git clone configuration
        working_dir = "/workspace"
        git_clone_config = execution_context.get("git_clone_config")
        if git_clone_config:
            repositories = git_clone_config.get("repositories", [])
            if repositories:
                # Use the first repository's clone path as working directory
                clone_path = repositories[0].get("clone_path", "/workspace")
                if clone_path.startswith("/"):
                    # Absolute path
                    working_dir = clone_path
                else:
                    # Relative path - prepend /workspace/
                    working_dir = f"/workspace/{clone_path}"
                self.logger.info(
                    f"Setting Codex working directory to git repository: {working_dir}"
                )

        # Extract model for logging
        model = (
            execution_context.get("codex_model")
            or execution_context.get("model_identifier")
            or "gpt-4"
        )

        self.logger.info(
            f"Container config: model={model}, "
            f"has_api_key={'OPENAI_API_KEY' in env}, "
            f"env_vars={list(env.keys())}"
        )

        # Container configuration
        container_config = {
            "Image": self.image,
            "Env": [f"{k}={v}" for k, v in env.items()],
            # Don't override entrypoint - let codex-universal image configure environment
            # The entrypoint drops into bash, so pass -c and script as arguments to bash
            "Cmd": ["-c", script],
            "WorkingDir": working_dir,  # Set to git repo if configured, otherwise /workspace
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

    def _build_codex_script(self, execution_context: Dict[str, Any]) -> str:
        """
        Build the Codex initialization and execution script.

        This script is used by both Docker and Kubernetes modes.

        Args:
            execution_context: Execution context

        Returns:
            Shell script to execute
        """
        prompt = execution_context["prompt"]
        model = (
            execution_context.get("codex_model")
            or execution_context.get("model_identifier")
            or "gpt-4"
        )

        # Escape prompt for shell
        escaped_prompt = prompt.replace('"', '\\"').replace("'", "\\'")

        # Prepare initialization commands (git clone, custom commands)
        init_commands = self._prepare_init_commands(execution_context)

        # Prepare post-execution commands (push, PR/MR creation)
        post_exec_commands = self._prepare_git_post_execution_commands(
            execution_context
        )

        # Build post-execution block if there are commands
        post_exec_block = ""
        if post_exec_commands:
            post_exec_block = f"""
# Run post-execution commands (push, PR/MR) if codex succeeded
if [ "$CODEX_EXIT_CODE" -eq "0" ]; then
    echo "========================================="
    echo "Running post-execution git operations..."
    echo "========================================="
    {post_exec_commands}
fi
"""

        # Create the full script
        script = f"""
set -e

# Run initialization commands (git clone, custom commands) if any
{init_commands}

# Configure git to trust all directories (needed for cloned repos)
git config --global --add safe.directory '*'

# Configure Codex CLI in the universal image
npm install -g @openai/codex

# Verify API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: OPENAI_API_KEY is not set"
    exit 1
fi

# Configure Codex CLI authentication
mkdir -p ~/.codex

# Create auth.json with OpenAI API key
# Use unquoted heredoc to allow variable substitution (safer than sed with special chars)
cat > ~/.codex/auth.json << EOF
{{
  "OPENAI_API_KEY": "$OPENAI_API_KEY"
}}
EOF

# Create config.toml with model and MCP server configuration
# Use unquoted heredoc to allow variable substitution
cat > ~/.codex/config.toml << EOF
model = "{model}"

rmcp_client = true

[mcp_servers.spacebridge]
url = "$SPACEBRIDGE_MCP_URL"
bearer_token_env_var = "SPACEBRIDGE_API_TOKEN"
EOF

# Debug: Show config files (with API key masked)
echo "=== Codex Configuration ==="
echo "Model: {model}"
echo "MCP Server: $SPACEBRIDGE_MCP_URL"
echo "=========================="

# Run codex in non-interactive mode with the prompt
echo "{escaped_prompt}" | codex exec --model "{model}" --sandbox workspace-write --yolo
CODEX_EXIT_CODE=$?
{post_exec_block}
# Exit with codex's exit code
exit $CODEX_EXIT_CODE
"""
        return script

    async def _start_kubernetes_pod(self, execution_context: Dict[str, Any]) -> str:
        """
        Override to add Codex-specific command to Kubernetes pod.

        The base class creates the pod but doesn't set command/args, which causes
        codex-universal to drop into a bash shell. We need to override this to
        provide the script as command arguments.

        IMPORTANT: We only set args, NOT command. Setting command would override
        the image's ENTRYPOINT, which sets up PATH and other environment variables.
        By only setting args, the entrypoint runs first (sets up environment), then
        passes our args to bash for execution.
        """
        # Get the script to execute
        script = self._build_codex_script(execution_context)

        # Store script in execution context so base class can access it if needed
        execution_context["_codex_script"] = script

        # Set args for Kubernetes - these will be passed to the image's entrypoint
        # The entrypoint sets up the environment and then executes: bash "$@"
        # So our args become: bash -c "script"
        execution_context["_container_args"] = ["-c", script]
        # Don't set _container_command - let the image's entrypoint run

        # Prepare Codex-specific environment variables and store in context
        # The base class will merge these with its default env vars
        codex_env = await self._prepare_environment(execution_context)

        # Add account API token for SpaceBridge MCP authentication (always for Codex)
        account_api_token = execution_context.get("account_api_token")
        if account_api_token:
            codex_env["SPACEBRIDGE_API_TOKEN"] = account_api_token
        else:
            self.logger.warning(
                "No account API token provided for SpaceBridge MCP access"
            )

        # Set SpaceBridge MCP URL (for Kubernetes, use the service DNS name or external URL)
        codex_env["SPACEBRIDGE_MCP_URL"] = os.getenv(
            "SPACEBRIDGE_MCP_URL_K8S",
            os.getenv("SPACEBRIDGE_MCP_URL", "http://spacebridge-api:8000/mcp/v1"),
        )

        # Add MCP configuration using MCP config service
        allowed_mcp_servers = execution_context.get("allowed_mcp_servers", [])
        allowed_mcp_tools = execution_context.get("allowed_mcp_tools", [])

        if allowed_mcp_servers or allowed_mcp_tools:
            # Generate MCP environment variables
            mcp_env = MCPConfigService.generate_mcp_environment_vars(
                allowed_mcp_servers, allowed_mcp_tools
            )
            codex_env.update(mcp_env)

            # Generate MCP config file
            mcp_config = MCPConfigService.generate_mcp_config(
                allowed_mcp_servers,
                allowed_mcp_tools,
                account_api_token=account_api_token,
            )
            codex_env["MCP_CONFIG_JSON"] = json.dumps(mcp_config)

        execution_context["_codex_env"] = codex_env

        # Call parent implementation which will use the args and env
        return await super()._start_kubernetes_pod(execution_context)

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
        # Note: This is overridden to /home/agent in Kubernetes mode
        env["HOME"] = "/root"

        # Configure language runtimes for codex-universal image
        # These env vars tell the image which versions to set up
        env["CODEX_ENV_PYTHON_VERSION"] = os.getenv("CODEX_ENV_PYTHON_VERSION", "3.12")
        env["CODEX_ENV_NODE_VERSION"] = os.getenv("CODEX_ENV_NODE_VERSION", "20")
        env["CODEX_ENV_RUST_VERSION"] = os.getenv("CODEX_ENV_RUST_VERSION", "1.87.0")
        env["CODEX_ENV_GO_VERSION"] = os.getenv("CODEX_ENV_GO_VERSION", "1.23.8")
        env["CODEX_ENV_SWIFT_VERSION"] = os.getenv("CODEX_ENV_SWIFT_VERSION", "6.2")
        env["CODEX_ENV_RUBY_VERSION"] = os.getenv("CODEX_ENV_RUBY_VERSION", "3.4.4")
        env["CODEX_ENV_PHP_VERSION"] = os.getenv("CODEX_ENV_PHP_VERSION", "8.4")

        return env
