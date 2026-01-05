"""OpenHands agent implementation."""

import json
import logging
import os
from typing import Any, Dict

from aiodocker.exceptions import DockerError

from preloop.services.mcp_config_service import MCPConfigService

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

            # Add account API token for Preloop MCP authentication
            if account_api_token:
                env["PRELOOP_API_TOKEN"] = account_api_token
            else:
                self.logger.warning(
                    "No account API token provided for Preloop MCP access"
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

        # Prepare initialization commands (git clone, custom commands)
        init_commands = self._prepare_init_commands(execution_context)

        # Create the command that runs initialization then OpenHands
        # Using bash -c to ensure proper execution without entrypoint.sh
        if init_commands:
            # Run init commands, then OpenHands
            full_command = f'{init_commands} && cd /app && /app/.venv/bin/python -m openhands.core.main -t "{prompt}" -i {max_iterations}'
        else:
            # No init commands, run OpenHands directly
            full_command = f'cd /app && /app/.venv/bin/python -m openhands.core.main -t "{prompt}" -i {max_iterations}'

        cmd = [
            "bash",
            "-c",
            full_command,
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
        # - PRELOOP_MCP_URL: URL to Preloop MCP endpoint

        return env

    def _prepare_init_commands(self, execution_context: Dict[str, Any]) -> str:
        """
        Prepare initialization commands (git clone, custom commands).

        Args:
            execution_context: Execution context

        Returns:
            Shell command string to run before agent starts, or empty string if none
        """
        commands = []

        # Prepare git clone command if enabled
        git_clone_config = execution_context.get("git_clone_config")
        if git_clone_config and git_clone_config.get("enabled"):
            git_cmd = self._prepare_git_clone_command(execution_context)
            if git_cmd:
                commands.append(git_cmd)

        # Prepare custom commands if enabled
        custom_commands = execution_context.get("custom_commands")
        if custom_commands and custom_commands.get("enabled"):
            custom_cmds = custom_commands.get("commands", [])
            for cmd in custom_cmds:
                # Sanitize command to prevent shell injection
                # Note: These commands come from admin-only configuration
                commands.append(cmd)

        # Join all commands with &&
        if commands:
            return " && ".join(commands)
        return ""

    def _prepare_git_clone_command(self, execution_context: Dict[str, Any]) -> str:
        """
        Prepare git clone commands for multiple repositories.

        Args:
            execution_context: Execution context

        Returns:
            Git clone commands string (multiple commands joined with &&) or empty string
        """
        try:
            git_config = execution_context.get("git_clone_config", {})
            repositories = git_config.get("repositories", [])

            if not repositories:
                self.logger.warning("No repositories configured for git clone")
                return ""

            clone_commands = []
            trigger_data = execution_context.get("trigger_event_data", {})

            for idx, repo_config in enumerate(repositories):
                # Get repository URL
                repo_url = repo_config.get("repository_url")

                # If no URL, try to get from project or trigger event
                if not repo_url:
                    project_id = repo_config.get("project_id")
                    if project_id:
                        # TODO: Fetch project details and get repository URL
                        # For now, try trigger event if it matches
                        trigger_project_id = trigger_data.get("project", {}).get("id")
                        if str(project_id) == str(trigger_project_id):
                            repo_url = self._extract_repo_url_from_trigger(trigger_data)
                    else:
                        # Use trigger event
                        repo_url = self._extract_repo_url_from_trigger(trigger_data)

                if not repo_url:
                    self.logger.warning(f"No repository URL found for repo #{idx + 1}")
                    continue

                # Get tracker credentials from credentials map
                tracker_id = repo_config.get("tracker_id")
                git_credentials_map = execution_context.get("git_credentials_map", {})

                # Get credentials for this tracker
                tracker_creds = git_credentials_map.get(tracker_id)
                if tracker_creds:
                    token = tracker_creds.get("token")
                    tracker_type = tracker_creds.get("tracker_type")

                    if token:
                        # Inject token into URL
                        if "github.com" in repo_url or tracker_type == "github":
                            repo_url = repo_url.replace(
                                "https://", f"https://oauth2:{token}@"
                            )
                        elif "gitlab.com" in repo_url or tracker_type == "gitlab":
                            repo_url = repo_url.replace(
                                "https://", f"https://oauth2:{token}@"
                            )

                # Get clone path (relative to workspace)
                clone_path = repo_config.get("clone_path", f"workspace-{idx + 1}")
                full_path = f"/workspace/{clone_path}"

                # Get branch if specified
                branch = repo_config.get("branch")
                branch_arg = f" -b {branch}" if branch else ""

                # Build git clone command
                git_cmd = f"git clone{branch_arg} {repo_url} {full_path}"
                clone_commands.append(git_cmd)

                self.logger.info(f"Prepared git clone command for {full_path}")

            if not clone_commands:
                return ""

            # Create workspace directory first, then clone all repos
            all_commands = ["mkdir -p /workspace"] + clone_commands
            return " && ".join(all_commands)

        except Exception as e:
            self.logger.error(f"Error preparing git clone command: {e}", exc_info=True)
            return ""

    def _extract_repo_url_from_trigger(self, trigger_data: Dict[str, Any]) -> str:
        """Extract repository URL from trigger event data."""
        try:
            # GitHub structure
            if "repository" in trigger_data:
                repo = trigger_data["repository"]
                if isinstance(repo, dict):
                    return repo.get("clone_url") or repo.get("html_url") or ""

            # GitLab structure
            if "project" in trigger_data:
                project = trigger_data["project"]
                if isinstance(project, dict):
                    return (
                        project.get("http_url_to_repo") or project.get("web_url") or ""
                    )

            return ""
        except Exception as e:
            self.logger.error(f"Error extracting repo URL from trigger: {e}")
            return ""
