"""Google Gemini CLI agent implementation."""

import json
import logging
import os
from typing import Any, Dict

from aiodocker.exceptions import DockerError

from preloop.services.mcp_config_service import MCPConfigService

from .container import ContainerAgentExecutor

logger = logging.getLogger(__name__)


class GeminiAgent(ContainerAgentExecutor):
    """
    Google Gemini CLI agent executor.

    Runs Google's Gemini CLI tool (https://github.com/google-gemini/gemini-cli) in a Docker
    container for autonomous coding tasks.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Gemini agent.

        Args:
            config: Agent configuration including:
                - model: Gemini model to use (default: gemini-3-pro-preview)
                - custom settings for Gemini CLI
        """
        # Use the official Gemini CLI sandbox image
        image = os.getenv(
            "GEMINI_IMAGE",
            "registry.spacecode.ai/spacecode/preloop/gemini-cli/sandbox:0.16.0",
        )

        # Auto-detect Kubernetes environment or use explicit env var
        use_k8s = self._detect_kubernetes_environment()

        super().__init__(
            agent_type="gemini",
            config=config,
            image=image,
            use_kubernetes=use_k8s,
        )

    def _detect_kubernetes_environment(self) -> bool:
        """
        Auto-detect if running in Kubernetes environment.

        Checks for:
        1. Explicit USE_KUBERNETES environment variable
        2. Kubernetes service account token (in-cluster detection)
        3. KUBERNETES_SERVICE_HOST environment variable

        Returns:
            True if Kubernetes environment detected, False otherwise
        """
        # Check explicit environment variable first
        env_value = os.getenv("USE_KUBERNETES", "").lower()
        if env_value == "true":
            logger.info("Kubernetes mode enabled via USE_KUBERNETES=true")
            return True
        elif env_value == "false":
            logger.info("Kubernetes mode disabled via USE_KUBERNETES=false")
            return False

        # Auto-detect: Check for Kubernetes service account token (in-cluster)
        k8s_token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        if os.path.exists(k8s_token_path):
            logger.info(
                f"Kubernetes environment detected (found service account token at {k8s_token_path})"
            )
            return True

        # Auto-detect: Check for Kubernetes service host
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            logger.info(
                "Kubernetes environment detected (KUBERNETES_SERVICE_HOST present)"
            )
            return True

        # Default to Docker if no Kubernetes indicators found
        logger.info("No Kubernetes environment detected, defaulting to Docker mode")
        return False

    async def start(self, execution_context: Dict[str, Any]) -> str:
        """
        Start Gemini agent with specialized configuration.

        Args:
            execution_context: Execution context

        Returns:
            Container ID or pod name
        """
        # Enhance execution context with Gemini-specific settings
        gemini_context = execution_context.copy()

        # Extract Gemini config
        agent_config = execution_context.get("agent_config", {})

        # Set Gemini model - prefer model_identifier from AIModel, fall back to agent_config
        model_identifier = execution_context.get("model_identifier")
        agent_model = agent_config.get("model")

        self.logger.info(
            f"Gemini model resolution: model_identifier={model_identifier}, "
            f"agent_config.model={agent_model}"
        )

        model = model_identifier or agent_model or "gemini-3-pro-preview"
        gemini_context["gemini_model"] = model

        self.logger.info(f"Starting Gemini CLI with model={model}")

        # Start the container with enhanced context
        return await super().start(gemini_context)

    async def _start_docker_container(self, execution_context: Dict[str, Any]) -> str:
        """
        Start Gemini CLI in a Docker container.

        Args:
            execution_context: Execution context

        Returns:
            Container ID
        """
        docker = await self._get_docker_client()
        execution_id = execution_context["execution_id"]

        # Log execution context for debugging
        self.logger.info(
            f"_start_docker_container called with gemini_model={execution_context.get('gemini_model')}, "
            f"model_identifier={execution_context.get('model_identifier')}, "
            f"has_model_api_key={('model_api_key' in execution_context)}"
        )

        # Prepare Gemini-specific environment variables
        env = await self._prepare_environment(execution_context)

        # Add account API token for Preloop MCP authentication (always for Gemini)
        account_api_token = execution_context.get("account_api_token")
        if account_api_token:
            env["PRELOOP_API_TOKEN"] = account_api_token
        else:
            self.logger.warning("No account API token provided for Preloop MCP access")

        # Set Preloop MCP URL (defaults to host.docker.internal for container access)
        env["PRELOOP_MCP_URL"] = os.getenv(
            "PRELOOP_MCP_URL", "http://host.docker.internal:8000/mcp/v1"
        )

        # Add MCP_TOOL_TIMEOUT_SEC for config substitution
        mcp_timeout = execution_context.get("_mcp_tool_timeout", 600)
        env["MCP_TOOL_TIMEOUT_SEC"] = str(mcp_timeout)
        self.logger.info(f"Set MCP_TOOL_TIMEOUT_SEC={mcp_timeout} for Gemini config")

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

        # Build the Gemini script using shared method
        script = self._build_gemini_script(execution_context)

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
                    f"Setting Gemini working directory to git repository: {working_dir}"
                )

        # Extract model for logging
        model = (
            execution_context.get("gemini_model")
            or execution_context.get("model_identifier")
            or "gemini-3-pro-preview"
        )

        self.logger.info(
            f"Container config: model={model}, "
            f"has_api_key={'GEMINI_API_KEY' in env}, "
            f"env_vars={list(env.keys())}"
        )

        # Container configuration
        container_config = {
            "Image": self.image,
            "Env": [f"{k}={v}" for k, v in env.items()],
            "Cmd": ["/bin/bash", "-c", script],
            "WorkingDir": working_dir,
            "Labels": {
                "preloop.flow_id": execution_context["flow_id"],
                "preloop.execution_id": execution_id,
                "preloop.agent_type": self.agent_type,
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
                f"Started Gemini CLI container {container_id[:12]} for execution {execution_id}"
            )
            return container_id

        except DockerError as e:
            self.logger.error(
                f"Failed to start Gemini CLI container for execution {execution_id}: {e}"
            )
            raise RuntimeError(f"Failed to start Gemini CLI container: {e}")

    def _build_gemini_script(self, execution_context: Dict[str, Any]) -> str:
        """
        Build the Gemini initialization and execution script.

        This script is used by both Docker and Kubernetes modes.

        Args:
            execution_context: Execution context

        Returns:
            Shell script to execute
        """
        prompt = execution_context["prompt"]
        model = (
            execution_context.get("gemini_model")
            or execution_context.get("model_identifier")
            or "gemini-3-pro-preview"
        )

        # Escape prompt for shell - need to handle both single and double quotes carefully
        # We'll use a heredoc to pass the prompt safely
        prompt_safe = prompt.replace("'", "'\\''")  # Escape single quotes for heredoc

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
# Run post-execution commands (push, PR/MR) if gemini succeeded
if [ "$GEMINI_EXIT_CODE" -eq "0" ]; then
    echo "========================================="
    echo "Running post-execution git operations..."
    echo "========================================="
    {post_exec_commands}
fi
"""

        # Get execution details for logging
        execution_id = execution_context.get("execution_id", "unknown")
        flow_name = execution_context.get("flow_name", "unknown")

        # Convert timeout from seconds to milliseconds for Gemini CLI
        mcp_timeout_ms = execution_context.get("_mcp_tool_timeout", 600) * 1000

        # Create the full script
        script = f"""
set -e

# ============================================================
# Flow Execution Information
# ============================================================
echo "=================================================="
echo "Flow Execution Started"
echo "=================================================="
echo "Execution ID: {execution_id}"
echo "Flow Name: {flow_name}"
echo "Agent Type: Gemini"
echo "Model: {model}"
echo "Start Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=================================================="
echo ""

# Run initialization commands (git clone, custom commands) if any
{init_commands}

# Configure git to trust all directories (needed for cloned repos)
git config --global --add safe.directory '*'

# Verify API key is set
if [ -z "$GEMINI_API_KEY" ]; then
    echo "ERROR: GEMINI_API_KEY is not set"
    exit 1
fi

# Configure Gemini CLI MCP servers
mkdir -p ~/.gemini

# Create settings.json with MCP server configuration
# Using envsubst for variable substitution
cat > ~/.gemini/settings.json << 'SETTINGS_EOF'
{{
  "mcpServers": {{
    "preloop": {{
      "httpUrl": "$PRELOOP_MCP_URL",
      "headers": {{
        "Authorization": "Bearer $PRELOOP_API_TOKEN"
      }},
      "timeout": {mcp_timeout_ms},
      "trust": true
    }}
  }}
}}
SETTINGS_EOF

# Substitute environment variables in settings.json
export PRELOOP_MCP_URL
export PRELOOP_API_TOKEN
envsubst < ~/.gemini/settings.json > ~/.gemini/settings.json.tmp
mv ~/.gemini/settings.json.tmp ~/.gemini/settings.json

# Debug: Show config (with token masked)
echo "=== Gemini Configuration ==="
echo "Model: {model}"
echo "MCP Server: $PRELOOP_MCP_URL"
echo "MCP Timeout: {mcp_timeout_ms}ms ({execution_context.get("_mcp_tool_timeout", 600)}s)"
echo "Working Directory: $(pwd)"
echo "=========================="

# Create prompt file to avoid shell escaping issues
cat > /tmp/prompt.txt << 'PROMPT_EOF'
{prompt_safe}
PROMPT_EOF

# Run Gemini CLI with the prompt
# --output-format stream-json: Stream JSON output for real-time monitoring
# --yolo: Skip confirmation prompts for tool usage
# -m: Specify the model
# --prompt: Pass the prompt (read from file)
gemini --output-format stream-json --yolo -m "{model}" --prompt "$(cat /tmp/prompt.txt)"
GEMINI_EXIT_CODE=$?

echo ""
echo "=================================================="
echo "Gemini CLI exited with code: $GEMINI_EXIT_CODE"
echo "=================================================="
{post_exec_block}
# Exit with gemini's exit code
exit $GEMINI_EXIT_CODE
"""
        return script

    async def _start_kubernetes_pod(self, execution_context: Dict[str, Any]) -> str:
        """
        Override to add Gemini-specific command to Kubernetes pod.

        Similar to Codex, we only set args (not command) to preserve the
        image's entrypoint that sets up the environment.
        """
        # Get the script to execute
        script = self._build_gemini_script(execution_context)

        # Store script in execution context
        execution_context["_gemini_script"] = script

        # Set args for Kubernetes
        execution_context["_container_args"] = ["-c", script]

        # Prepare Gemini-specific environment variables
        gemini_env = await self._prepare_environment(execution_context)

        # Add account API token for Preloop MCP authentication
        account_api_token = execution_context.get("account_api_token")
        if account_api_token:
            gemini_env["PRELOOP_API_TOKEN"] = account_api_token
        else:
            self.logger.warning("No account API token provided for Preloop MCP access")

        # Set Preloop MCP URL (for Kubernetes)
        gemini_env["PRELOOP_MCP_URL"] = os.getenv(
            "PRELOOP_MCP_URL_K8S",
            os.getenv("PRELOOP_MCP_URL", "http://preloop-api:8000/mcp/v1"),
        )

        # Add MCP_TOOL_TIMEOUT_SEC
        mcp_timeout = execution_context.get("_mcp_tool_timeout", 600)
        gemini_env["MCP_TOOL_TIMEOUT_SEC"] = str(mcp_timeout)
        self.logger.info(
            f"Set MCP_TOOL_TIMEOUT_SEC={mcp_timeout} for Gemini (Kubernetes)"
        )

        # Add MCP configuration
        allowed_mcp_servers = execution_context.get("allowed_mcp_servers", [])
        allowed_mcp_tools = execution_context.get("allowed_mcp_tools", [])

        if allowed_mcp_servers or allowed_mcp_tools:
            mcp_env = MCPConfigService.generate_mcp_environment_vars(
                allowed_mcp_servers, allowed_mcp_tools
            )
            gemini_env.update(mcp_env)

            mcp_config = MCPConfigService.generate_mcp_config(
                allowed_mcp_servers,
                allowed_mcp_tools,
                account_api_token=account_api_token,
            )
            gemini_env["MCP_CONFIG_JSON"] = json.dumps(mcp_config)

        execution_context["_gemini_env"] = gemini_env

        # Call parent implementation
        return await super()._start_kubernetes_pod(execution_context)

    async def _prepare_environment(
        self, execution_context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Prepare Gemini-specific environment variables.

        Args:
            execution_context: Execution context

        Returns:
            Environment variables dict
        """
        env = {}

        # Add Gemini API key
        if "model_api_key" in execution_context:
            env["GEMINI_API_KEY"] = execution_context["model_api_key"]

        # Set home directory for config storage
        env["HOME"] = "/root"

        # Configure MCP tool timeout based on approval policies
        # Base timeout is 600 seconds (10 minutes)
        mcp_timeout = 600

        # Check if there are approval policies that may require longer timeouts
        account_id = execution_context.get("account_id")
        if account_id:
            try:
                from preloop.models.db.session import get_db_context
                from preloop.models.crud import tool_configuration as tool_config_crud
                from preloop.models.crud import approval_policy as approval_policy_crud

                with get_db_context() as db:
                    max_approval_timeout = 0
                    has_escalation = False

                    tool_configs = tool_config_crud.get_multi_by_account(
                        db, account_id=account_id, limit=1000
                    )

                    for config in tool_configs:
                        if config.approval_policy_id:
                            policy = approval_policy_crud.get(
                                db, id=config.approval_policy_id
                            )
                            if policy and policy.timeout_seconds:
                                max_approval_timeout = max(
                                    max_approval_timeout, policy.timeout_seconds
                                )
                                if policy.escalation_policy:
                                    has_escalation = True

                    if max_approval_timeout > 0:
                        if has_escalation:
                            mcp_timeout = max_approval_timeout * 2
                        else:
                            mcp_timeout = max_approval_timeout

                        self.logger.info(
                            f"Set MCP_TOOL_TIMEOUT to {mcp_timeout}s based on approval policies "
                            f"(max_approval_timeout={max_approval_timeout}, has_escalation={has_escalation})"
                        )
            except Exception as e:
                self.logger.warning(
                    f"Failed to query approval policies for MCP timeout calculation: {e}. "
                    f"Using default timeout of {mcp_timeout}s"
                )

        env["MCP_TOOL_TIMEOUT"] = str(mcp_timeout)
        # Store timeout in context for use in config generation
        execution_context["_mcp_tool_timeout"] = mcp_timeout
        self.logger.info(f"MCP_TOOL_TIMEOUT set to {mcp_timeout}s")

        return env
