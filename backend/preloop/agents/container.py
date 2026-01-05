"""Container-based agent executor for Docker and Kubernetes."""

import json
import logging
import os
from typing import Any, Dict, Optional

import aiodocker
from aiodocker.exceptions import DockerError

from .base import AgentExecutionResult, AgentExecutor, AgentStatus
from preloop.services.mcp_config_service import MCPConfigService

logger = logging.getLogger(__name__)

try:
    from kubernetes_asyncio import client, config
    from kubernetes_asyncio.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    logger.warning(
        "kubernetes_asyncio not available, Kubernetes execution will not be supported"
    )


class ContainerAgentExecutor(AgentExecutor):
    """
    Execute agents in isolated Docker containers or Kubernetes pods.

    This is the production-ready executor that runs agents in isolated
    environments with proper resource limits, networking, and security.
    """

    def __init__(
        self,
        agent_type: str,
        config: Dict[str, Any],
        image: str,
        use_kubernetes: bool = False,
    ):
        """
        Initialize the container agent executor.

        Args:
            agent_type: Type of agent
            config: Agent configuration
            image: Docker image to use for the agent
            use_kubernetes: Whether to use Kubernetes instead of Docker
        """
        super().__init__(agent_type, config)
        self.image = image
        self.use_kubernetes = use_kubernetes
        self._docker_client: Optional[aiodocker.Docker] = None
        self._containers: Dict[str, Any] = {}  # Track running containers
        self._k8s_initialized = False
        self._k8s_api_client: Optional[Any] = None  # Store ApiClient for proper cleanup
        self._k8s_batch_api: Optional[Any] = None
        self._k8s_core_api: Optional[Any] = None
        # Get agent namespace from environment or use default
        self.agent_namespace = os.getenv(
            "AGENT_EXECUTION_NAMESPACE", "agent-executions"
        )

    async def _get_docker_client(self) -> aiodocker.Docker:
        """Get or create Docker client."""
        if self._docker_client is None:
            self._docker_client = aiodocker.Docker()
        return self._docker_client

    async def _init_kubernetes_clients(self):
        """Initialize Kubernetes API clients."""
        if not KUBERNETES_AVAILABLE:
            raise RuntimeError("kubernetes_asyncio is not installed")

        if not self._k8s_initialized:
            # Load in-cluster config when running inside K8s, otherwise load from kubeconfig
            try:
                config.load_incluster_config()
                self.logger.info("Loaded in-cluster Kubernetes config")
            except config.ConfigException:
                await config.load_kube_config()
                self.logger.info("Loaded Kubernetes config from kubeconfig")

            # Create ApiClient for proper resource management
            self._k8s_api_client = client.ApiClient()
            self._k8s_batch_api = client.BatchV1Api(self._k8s_api_client)
            self._k8s_core_api = client.CoreV1Api(self._k8s_api_client)
            self._k8s_initialized = True

    async def start(self, execution_context: Dict[str, Any]) -> str:
        """
        Start the agent in a Docker container or K8s pod.

        Args:
            execution_context: Execution context with prompt, config, etc.

        Returns:
            Container ID or K8s pod name as session reference
        """
        flow_id = execution_context["flow_id"]
        execution_id = execution_context["execution_id"]

        self.logger.info(
            f"Starting {self.agent_type} agent in container for execution {execution_id}"
        )

        # Check if Kubernetes is requested but not available - fall back to Docker
        if self.use_kubernetes and not KUBERNETES_AVAILABLE:
            self.logger.warning(
                "Kubernetes execution requested but kubernetes_asyncio is not available. "
                "Falling back to Docker execution."
            )
            return await self._start_docker_container(execution_context)

        if self.use_kubernetes:
            return await self._start_kubernetes_pod(execution_context)
        else:
            return await self._start_docker_container(execution_context)

    async def _start_docker_container(self, execution_context: Dict[str, Any]) -> str:
        """
        Start agent in a Docker container.

        Args:
            execution_context: Execution context

        Returns:
            Container ID
        """
        docker = await self._get_docker_client()
        execution_id = execution_context["execution_id"]

        # Prepare environment variables
        env = {
            "FLOW_ID": execution_context["flow_id"],
            "EXECUTION_ID": execution_id,
            "AGENT_PROMPT": execution_context["prompt"],
            "AGENT_CONFIG": str(execution_context.get("agent_config", {})),
        }

        # Add AI model credentials if available
        if "model_api_key" in execution_context:
            env["AI_MODEL_API_KEY"] = execution_context["model_api_key"]
        if "model_identifier" in execution_context:
            env["AI_MODEL"] = execution_context["model_identifier"]
        if "model_provider" in execution_context:
            env["AI_MODEL_PROVIDER"] = execution_context["model_provider"]

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

        # Create a writable workspace volume for the container
        # This ensures the agent has write permissions
        workspace_volume = f"agent-workspace-{execution_id}"

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
                    f"Setting container working directory to git repository: {working_dir}"
                )

        # Container configuration
        container_config = {
            "Image": self.image,
            "Env": [f"{k}={v}" for k, v in env.items()],
            "User": "10000:10000",  # Explicitly set user and group
            "WorkingDir": working_dir,  # Set working directory to git repo if configured
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
                # Mount workspace volume with proper permissions
                "Binds": [f"{workspace_volume}:/workspace:rw"],
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
                f"Started container {container_id[:12]} for execution {execution_id}"
            )
            return container_id

        except DockerError as e:
            self.logger.error(
                f"Failed to start container for execution {execution_id}: {e}"
            )
            raise RuntimeError(f"Failed to start agent container: {e}")

    async def _start_kubernetes_pod(self, execution_context: Dict[str, Any]) -> str:
        """
        Start agent in a Kubernetes Job.

        Args:
            execution_context: Execution context

        Returns:
            Job name (used as session reference)
        """
        await self._init_kubernetes_clients()

        execution_id = execution_context["execution_id"]
        flow_id = execution_context["flow_id"]

        # Generate unique job name (K8s names must be DNS-1123 compliant)
        job_name = f"agent-{execution_id}".replace("_", "-").lower()

        # Prepare environment variables
        # Start with agent-specific env if provided (e.g., from CodexAgent)
        env = execution_context.get("_codex_env", {}).copy()

        # Add base environment variables
        env.update(
            {
                "FLOW_ID": flow_id,
                "EXECUTION_ID": execution_id,
                "AGENT_PROMPT": execution_context["prompt"],
                "AGENT_CONFIG": str(execution_context.get("agent_config", {})),
            }
        )

        # Add AI model credentials if available (only if not already set by agent-specific env)
        if "model_api_key" in execution_context and "OPENAI_API_KEY" not in env:
            env["AI_MODEL_API_KEY"] = execution_context["model_api_key"]
        if "model_identifier" in execution_context:
            env["AI_MODEL"] = execution_context["model_identifier"]
        if "model_provider" in execution_context:
            env["AI_MODEL_PROVIDER"] = execution_context["model_provider"]

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
                env["PRELOOP_API_TOKEN"] = account_api_token

            mcp_config = MCPConfigService.generate_mcp_config(
                allowed_mcp_servers,
                allowed_mcp_tools,
                account_api_token=account_api_token,
            )
            env["MCP_CONFIG_JSON"] = json.dumps(mcp_config)

        # Convert env dict to list of V1EnvVar
        env_vars = [client.V1EnvVar(name=k, value=v) for k, v in env.items()]

        # Get resource limits from config or use defaults
        memory_limit = os.getenv("AGENT_MEMORY_LIMIT", "2Gi")
        cpu_limit = os.getenv("AGENT_CPU_LIMIT", "1")
        memory_request = os.getenv("AGENT_MEMORY_REQUEST", "512Mi")
        cpu_request = os.getenv("AGENT_CPU_REQUEST", "250m")

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
                    f"Setting pod working directory to git repository: {working_dir}"
                )

        # Check if subclass provided custom command/args (e.g., CodexAgent)
        command = execution_context.get("_container_command")
        args = execution_context.get("_container_args")

        # Container specification with security context and volume mounts
        # NOTE: Currently running as root for compatibility with agent images (codex-universal).
        # TODO: Harden security by running as non-root user in the future.
        container = client.V1Container(
            name="agent",
            image=self.image,
            env=env_vars,
            command=command,  # Optional: set by subclasses like CodexAgent
            args=args,  # Optional: set by subclasses like CodexAgent
            working_dir=working_dir,  # Set working directory to git repo if configured
            resources=client.V1ResourceRequirements(
                limits={"memory": memory_limit, "cpu": cpu_limit},
                requests={"memory": memory_request, "cpu": cpu_request},
            ),
            security_context=client.V1SecurityContext(
                run_as_user=0,  # Run as root (UID 0) for compatibility with codex-universal
                read_only_root_filesystem=False,
                allow_privilege_escalation=False,
                capabilities=client.V1Capabilities(drop=["ALL"]),
            ),
            volume_mounts=[
                client.V1VolumeMount(
                    name="workspace", mount_path="/workspace", sub_path=None
                ),
                client.V1VolumeMount(
                    name="root-home", mount_path="/root", sub_path=None
                ),
            ],
        )

        # Init container to copy /root contents to writable volume
        # This preserves pre-installed files (nvm, node, npm, etc.) while making /root writable
        # Uses --reflink=auto for copy-on-write optimization when supported by filesystem
        init_container = client.V1Container(
            name="copy-root",
            image=self.image,
            command=["/bin/sh", "-c"],
            args=[
                # Use --reflink=auto for CoW copies (much faster on supporting filesystems)
                # Then ensure proper permissions for npm and other tools
                "cp -a --reflink=auto /root/. /root-volume/ && "
                "chown -R 0:0 /root-volume && "
                "chmod -R u+w /root-volume && "
                "echo 'Copied /root to writable volume with proper permissions'"
            ],
            volume_mounts=[
                client.V1VolumeMount(
                    name="root-home", mount_path="/root-volume", sub_path=None
                ),
            ],
            security_context=client.V1SecurityContext(
                run_as_user=0,  # Run as root
            ),
        )

        # Pod template specification with volumes
        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "preloop.flow_id": flow_id,
                    "preloop.execution_id": execution_id,
                    "preloop.agent_type": self.agent_type,
                    "app": "agent-execution",
                }
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                init_containers=[
                    init_container
                ],  # Copy /root before main container starts
                containers=[container],
                # No pod-level security context - allows running as root
                volumes=[
                    client.V1Volume(
                        name="workspace",
                        empty_dir=client.V1EmptyDirVolumeSource(),
                    ),
                    client.V1Volume(
                        name="root-home",
                        empty_dir=client.V1EmptyDirVolumeSource(),
                    ),
                ],
            ),
        )

        # Job specification with TTL for auto-cleanup
        ttl_seconds = int(os.getenv("AGENT_JOB_TTL_SECONDS", "3600"))
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace=self.agent_namespace,
                labels={
                    "preloop.flow_id": flow_id,
                    "preloop.execution_id": execution_id,
                    "preloop.agent_type": self.agent_type,
                },
            ),
            spec=client.V1JobSpec(
                template=pod_template,
                backoff_limit=0,  # Don't retry failed jobs
                ttl_seconds_after_finished=ttl_seconds,  # Auto-cleanup after completion
            ),
        )

        try:
            # Create the Job
            await self._k8s_batch_api.create_namespaced_job(
                namespace=self.agent_namespace, body=job
            )

            self.logger.info(
                f"Started Kubernetes Job {job_name} in namespace {self.agent_namespace} "
                f"for execution {execution_id}"
            )
            return job_name

        except ApiException as e:
            self.logger.error(
                f"Failed to create Kubernetes Job for execution {execution_id}: {e}"
            )
            raise RuntimeError(f"Failed to start agent Job: {e}")

    async def get_status(self, session_reference: str) -> AgentStatus:
        """
        Get the status of a container.

        Args:
            session_reference: Container ID

        Returns:
            Agent status
        """
        if self.use_kubernetes:
            return await self._get_kubernetes_status(session_reference)

        try:
            docker = await self._get_docker_client()
            container = await docker.containers.get(session_reference)
            info = await container.show()

            state = info["State"]
            if state["Running"]:
                return AgentStatus.RUNNING
            elif state["Status"] == "created":
                return AgentStatus.STARTING
            elif state["Status"] == "exited":
                if state["ExitCode"] == 0:
                    return AgentStatus.SUCCEEDED
                else:
                    return AgentStatus.FAILED
            else:
                return AgentStatus.STOPPED

        except DockerError as e:
            self.logger.error(
                f"Failed to get status for container {session_reference}: {e}"
            )
            return AgentStatus.FAILED

    async def _get_kubernetes_status(self, job_name: str) -> AgentStatus:
        """
        Get status of a Kubernetes Job.

        Args:
            job_name: Name of the Job

        Returns:
            Agent status based on Job/Pod state
        """
        await self._init_kubernetes_clients()

        try:
            # Get Job status
            job = await self._k8s_batch_api.read_namespaced_job_status(
                name=job_name, namespace=self.agent_namespace
            )

            # Check Job conditions
            if job.status.active and job.status.active > 0:
                return AgentStatus.RUNNING

            if job.status.succeeded and job.status.succeeded > 0:
                return AgentStatus.SUCCEEDED

            if job.status.failed and job.status.failed > 0:
                return AgentStatus.FAILED

            # If no pods have started yet, it's starting
            if (
                not job.status.active
                and not job.status.succeeded
                and not job.status.failed
            ):
                return AgentStatus.STARTING

            return AgentStatus.RUNNING

        except ApiException as e:
            if e.status == 404:
                self.logger.warning(f"Job {job_name} not found")
                return AgentStatus.FAILED
            self.logger.error(f"Failed to get status for Job {job_name}: {e}")
            return AgentStatus.FAILED

    async def get_result(self, session_reference: str) -> AgentExecutionResult:
        """
        Get the result of a container execution.

        Args:
            session_reference: Container ID or Job name

        Returns:
            Execution result
        """
        if self.use_kubernetes:
            return await self._get_kubernetes_result(session_reference)

        status = await self.get_status(session_reference)

        try:
            docker = await self._get_docker_client()
            container = await docker.containers.get(session_reference)
            info = await container.show()

            # Get exit code
            exit_code = info["State"].get("ExitCode")

            # Get logs
            logs = await self.get_logs(session_reference, tail=1000)
            output_summary = "\n".join(logs[-50:]) if logs else None

            # Check for error patterns in logs even if exit code is 0
            error_message = None
            logs_text = "\n".join(logs) if logs else ""
            has_error_pattern = self._detect_error_in_logs(logs_text)

            # Override status if we detect errors in logs
            if has_error_pattern and status == AgentStatus.SUCCEEDED:
                self.logger.warning(
                    f"Container {session_reference[:12]} exited with code 0 but logs contain critical errors. "
                    "Marking as FAILED."
                )
                status = AgentStatus.FAILED
            elif not has_error_pattern and status == AgentStatus.SUCCEEDED:
                # Log when we successfully ignore benign error patterns
                if "error" in logs_text.lower() or "no commits" in logs_text.lower():
                    self.logger.info(
                        f"Container {session_reference[:12]} exited with code 0. "
                        "Logs contain benign messages (e.g., 'no commits'), not marking as failed."
                    )

            if status == AgentStatus.FAILED:
                error_message = (
                    info["State"].get("Error")
                    or self._extract_error_from_logs(logs_text)
                    or f"Container exited with code {exit_code}"
                )

            return AgentExecutionResult(
                status=status,
                session_reference=session_reference,
                output_summary=output_summary,
                error_message=error_message,
                exit_code=exit_code,
            )

        except DockerError as e:
            self.logger.error(
                f"Failed to get result for container {session_reference}: {e}"
            )
            return AgentExecutionResult(
                status=AgentStatus.FAILED,
                session_reference=session_reference,
                error_message=str(e),
            )

    async def _get_kubernetes_result(self, job_name: str) -> AgentExecutionResult:
        """
        Get the result of a Kubernetes Job execution.

        Args:
            job_name: Name of the Job

        Returns:
            Execution result
        """
        status = await self.get_status(job_name)

        try:
            await self._init_kubernetes_clients()

            # Get logs
            logs = await self.get_logs(job_name, tail=1000)
            output_summary = "\n".join(logs[-50:]) if logs else None

            # Check for error patterns in logs
            error_message = None
            logs_text = "\n".join(logs) if logs else ""
            has_error_pattern = self._detect_error_in_logs(logs_text)

            # Override status if we detect errors in logs
            if has_error_pattern and status == AgentStatus.SUCCEEDED:
                self.logger.warning(
                    f"Job {job_name} succeeded but logs contain critical errors. "
                    "Marking as FAILED."
                )
                status = AgentStatus.FAILED
            elif not has_error_pattern and status == AgentStatus.SUCCEEDED:
                # Log when we successfully ignore benign error patterns
                if "error" in logs_text.lower() or "no commits" in logs_text.lower():
                    self.logger.info(
                        f"Job {job_name} succeeded. "
                        "Logs contain benign messages (e.g., 'no commits'), not marking as failed."
                    )

            # Try to get exit code from pod
            exit_code = None
            try:
                label_selector = f"job-name={job_name}"
                pods = await self._k8s_core_api.list_namespaced_pod(
                    namespace=self.agent_namespace, label_selector=label_selector
                )
                if pods.items:
                    pod = pods.items[0]
                    if pod.status.container_statuses:
                        container_status = pod.status.container_statuses[0]
                        if container_status.state.terminated:
                            exit_code = container_status.state.terminated.exit_code
            except Exception as e:
                self.logger.warning(f"Could not get exit code for Job {job_name}: {e}")

            if status == AgentStatus.FAILED:
                error_message = (
                    self._extract_error_from_logs(logs_text)
                    or f"Job exited with code {exit_code}"
                    if exit_code is not None
                    else "Job failed"
                )

            return AgentExecutionResult(
                status=status,
                session_reference=job_name,
                output_summary=output_summary,
                error_message=error_message,
                exit_code=exit_code,
            )

        except ApiException as e:
            self.logger.error(f"Failed to get result for Job {job_name}: {e}")
            return AgentExecutionResult(
                status=AgentStatus.FAILED,
                session_reference=job_name,
                error_message=str(e),
            )

    def _detect_error_in_logs(self, logs_text: str) -> bool:
        """
        Detect if logs contain error patterns that indicate failure.

        Args:
            logs_text: Full log text

        Returns:
            True if error patterns detected
        """
        # Benign patterns that should NOT trigger failure detection
        # These are informational messages that contain "error" but don't indicate failure
        benign_patterns = [
            "no commits",
            "skipping push",
            "nothing to commit",
            "no changes",
            "up to date",
            "up-to-date",
            "already up to date",
            "everything up-to-date",
            "failed to create pr (may already exist)",  # PR/MR creation failure is not critical
            "failed to create mr (may already exist)",
        ]

        logs_lower = logs_text.lower()

        # Check for benign patterns first - if found, don't mark as error
        for benign_pattern in benign_patterns:
            if benign_pattern in logs_lower:
                return False

        # Critical error patterns that always indicate failure
        critical_error_patterns = [
            "litellm.BadRequestError",
            "litellm.AuthenticationError",
            "litellm.RateLimitError",
            "OpenAIException",
            "AnthropicException",
            "Traceback (most recent call last)",
            "FATAL ERROR",
            "CRITICAL:",
        ]

        for pattern in critical_error_patterns:
            if pattern.lower() in logs_lower:
                return True

        # Check for "ERROR:" but only if it's not a benign git-related message
        # and if it appears multiple times (suggesting a real error, not just logging)
        if "error:" in logs_lower:
            # Count occurrences to filter out single informational errors
            error_count = logs_lower.count("error:")
            if error_count >= 3:  # Multiple errors suggest real failure
                return True

        return False

    def _extract_error_from_logs(self, logs_text: str) -> str:
        """
        Extract error message from logs.

        Args:
            logs_text: Full log text

        Returns:
            Extracted error message or empty string
        """
        lines = logs_text.split("\n")
        error_lines = []

        # Look for exception or error messages
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(
                pattern in line_lower
                for pattern in ["error", "exception", "failed", "fatal"]
            ):
                # Include some context around the error
                start = max(0, i - 2)
                end = min(len(lines), i + 5)
                error_lines = lines[start:end]
                break

        if error_lines:
            return "\n".join(error_lines)
        return ""

    async def stop(self, session_reference: str) -> None:
        """
        Stop a running container.

        Args:
            session_reference: Container ID
        """
        if self.use_kubernetes:
            await self._stop_kubernetes_pod(session_reference)
            return

        try:
            docker = await self._get_docker_client()
            container = await docker.containers.get(session_reference)

            self.logger.info(f"Stopping container {session_reference[:12]}")
            await container.stop(t=30)  # 30 second grace period

            # Remove from tracking
            if session_reference in self._containers:
                del self._containers[session_reference]

        except DockerError as e:
            self.logger.error(f"Failed to stop container {session_reference}: {e}")
            raise

    async def _stop_kubernetes_pod(self, job_name: str) -> None:
        """
        Stop a Kubernetes Job by deleting it.

        Args:
            job_name: Name of the Job to delete
        """
        await self._init_kubernetes_clients()

        try:
            self.logger.info(f"Deleting Kubernetes Job {job_name}")

            # Delete the Job (this will also delete associated Pods)
            await self._k8s_batch_api.delete_namespaced_job(
                name=job_name,
                namespace=self.agent_namespace,
                propagation_policy="Foreground",  # Delete pods before deleting the job
            )

            self.logger.info(f"Successfully deleted Job {job_name}")

        except ApiException as e:
            if e.status == 404:
                self.logger.warning(f"Job {job_name} not found, already deleted")
            else:
                self.logger.error(f"Failed to delete Job {job_name}: {e}")
                raise

    async def get_logs(self, session_reference: str, tail: int = 100) -> list[str]:
        """
        Get logs from a container (batch mode).

        Args:
            session_reference: Container ID or Job name
            tail: Number of recent log lines

        Returns:
            List of log lines
        """
        if self.use_kubernetes:
            return await self._get_kubernetes_logs(session_reference, tail)

        try:
            docker = await self._get_docker_client()
            container = await docker.containers.get(session_reference)

            logs = await container.log(stdout=True, stderr=True, tail=tail)
            # Handle both bytes and str (aiodocker API can return either)
            decoded_logs = []
            for line in logs:
                if isinstance(line, bytes):
                    decoded_logs.append(line.decode("utf-8", errors="replace"))
                else:
                    decoded_logs.append(line)
            return decoded_logs

        except DockerError as e:
            self.logger.error(
                f"Failed to get logs for container {session_reference}: {e}"
            )
            return []

    async def stream_logs(self, session_reference: str):
        """
        Stream logs from a container in real-time.

        Args:
            session_reference: Container ID or Job name

        Yields:
            Log lines as they are produced
        """
        if self.use_kubernetes:
            async for line in self._stream_kubernetes_logs(session_reference):
                yield line
        else:
            async for line in self._stream_docker_logs(session_reference):
                yield line

    async def _stream_docker_logs(self, container_id: str):
        """
        Stream logs from a Docker container.

        Args:
            container_id: Container ID

        Yields:
            Log lines in real-time
        """
        self.logger.info(
            f"Starting Docker log stream for container {container_id[:12]}"
        )
        line_count = 0

        try:
            docker = await self._get_docker_client()
            container = await docker.containers.get(container_id)

            self.logger.info(
                f"Got container object, starting log follow for {container_id[:12]}"
            )

            # Stream logs with follow=True
            async for line in container.log(
                stdout=True, stderr=True, follow=True, stream=True
            ):
                line_count += 1
                # Handle both bytes and str (aiodocker API can return either)
                if isinstance(line, bytes):
                    decoded_line = line.decode("utf-8", errors="replace").rstrip()
                else:
                    decoded_line = line.rstrip()

                if decoded_line:  # Skip empty lines
                    if line_count <= 5:  # Log first 5 lines for debugging
                        self.logger.debug(
                            f"Docker log line #{line_count}: {decoded_line[:100]}"
                        )
                    yield decoded_line

            self.logger.info(
                f"Docker log stream ended for {container_id[:12]}, total lines: {line_count}"
            )

        except DockerError as e:
            self.logger.error(
                f"Error streaming logs from container {container_id}: {e}"
            )
            yield f"[ERROR] Failed to stream logs: {e}"
        except Exception as e:
            self.logger.error(
                f"Unexpected error streaming Docker logs for {container_id}: {e}",
                exc_info=True,
            )
            yield f"[ERROR] Unexpected error: {e}"

    async def _get_kubernetes_logs(self, job_name: str, tail: int = 100) -> list[str]:
        """
        Get logs from the Pod associated with a Kubernetes Job.

        Args:
            job_name: Name of the Job
            tail: Number of recent log lines

        Returns:
            List of log lines
        """
        await self._init_kubernetes_clients()

        try:
            # List pods for this Job
            label_selector = f"job-name={job_name}"
            pods = await self._k8s_core_api.list_namespaced_pod(
                namespace=self.agent_namespace, label_selector=label_selector
            )

            if not pods.items:
                self.logger.warning(f"No pods found for Job {job_name}")
                return []

            # Get logs from the first pod (Jobs typically have one pod)
            pod_name = pods.items[0].metadata.name

            logs = await self._k8s_core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.agent_namespace,
                tail_lines=tail,
                _preload_content=False,  # Get raw response
            )

            # Read and decode the logs
            log_data = await logs.read()
            log_text = log_data.decode("utf-8", errors="replace")

            # Split into lines
            return log_text.strip().split("\n") if log_text.strip() else []

        except ApiException as e:
            if e.status == 404:
                self.logger.warning(f"Job or Pod for {job_name} not found")
                return []
            self.logger.error(f"Failed to get logs for Job {job_name}: {e}")
            return []

    async def _stream_kubernetes_logs(self, job_name: str):
        """
        Stream logs from a Kubernetes Job's Pod in real-time.

        Args:
            job_name: Name of the Job

        Yields:
            Log lines as they are produced
        """
        await self._init_kubernetes_clients()

        try:
            # Wait for pod to be created (may take time after Job creation + init container)
            label_selector = f"job-name={job_name}"
            pod_name = None

            # Retry for up to 60 seconds to find the pod
            import asyncio

            for attempt in range(60):
                pods = await self._k8s_core_api.list_namespaced_pod(
                    namespace=self.agent_namespace, label_selector=label_selector
                )

                if pods.items:
                    pod_name = pods.items[0].metadata.name
                    self.logger.info(f"Found pod {pod_name} for Job {job_name}")
                    break

                if attempt < 59:
                    await asyncio.sleep(1)

            if not pod_name:
                self.logger.warning(
                    f"No pods found for Job {job_name} after 60 seconds"
                )
                yield f"[WARN] No pods found for Job {job_name}"
                return

            # Wait for main container to start (after init container completes)
            # Poll pod status until the main container is running or terminated
            for attempt in range(60):
                pod = await self._k8s_core_api.read_namespaced_pod(
                    name=pod_name, namespace=self.agent_namespace
                )

                # Check if pod has container statuses
                if pod.status.container_statuses:
                    container_status = pod.status.container_statuses[0]
                    # Container is running or terminated - logs are available
                    if (
                        container_status.state.running
                        or container_status.state.terminated
                    ):
                        self.logger.info(f"Main container ready for {pod_name}")
                        break

                if attempt < 59:
                    await asyncio.sleep(1)

            # Stream logs with follow=True
            response = await self._k8s_core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.agent_namespace,
                container="agent",  # Specify the main container (not init container)
                follow=True,
                _preload_content=False,  # Required for streaming
            )

            # Read lines from the stream
            async for line in response.content:
                decoded_line = line.decode("utf-8", errors="replace").rstrip()
                if decoded_line:  # Skip empty lines
                    yield decoded_line

        except ApiException as e:
            if e.status == 404:
                self.logger.warning(f"Job or Pod for {job_name} not found")
                yield "[WARN] Job or Pod not found"
            else:
                self.logger.error(f"Error streaming logs for Job {job_name}: {e}")
                yield f"[ERROR] Failed to stream logs: {e}"
        except Exception as e:
            self.logger.error(
                f"Unexpected error streaming Kubernetes logs for {job_name}: {e}"
            )
            yield f"[ERROR] Unexpected error: {e}"

    def _prepare_init_commands(self, execution_context: Dict[str, Any]) -> str:
        """
        Prepare initialization commands (git clone, custom commands).

        Args:
            execution_context: Execution context

        Returns:
            Shell command string to run before agent starts, or empty string if none
        """
        commands = []

        # Prepare git clone command if repositories are configured
        # Check for repositories existence rather than just enabled flag
        git_clone_config = execution_context.get("git_clone_config")
        if git_clone_config:
            repositories = git_clone_config.get("repositories", [])
            # If repositories exist, attempt to clone them
            if repositories:
                self.logger.info(
                    f"Git clone configured with {len(repositories)} repositories"
                )
                git_cmd = self._prepare_git_clone_command(execution_context)
                if git_cmd:
                    commands.append(git_cmd)
                    self.logger.info("Git clone commands added to init")
                else:
                    self.logger.warning(
                        "Git clone was configured but no commands were generated"
                    )
            else:
                self.logger.debug("No repositories configured for git clone")
        else:
            self.logger.debug("No git_clone_config in execution context")

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
        Prepare git clone commands for multiple repositories with branch management.

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

            # Get git user configuration (defaults)
            git_user_name = git_config.get("git_user_name", "Preloop")
            git_user_email = git_config.get("git_user_email", "git@preloop.ai")
            source_branch = git_config.get("source_branch", "main")
            target_branch = git_config.get("target_branch")

            # Auto-generate target branch if not specified
            if not target_branch:
                flow_name = execution_context.get("flow_name", "flow")
                execution_id = execution_context.get("execution_id", "exec")
                # Create a branch name like "preloop/fix-bug-abc123"
                safe_flow_name = flow_name.lower().replace(" ", "-")[:30]
                target_branch = f"preloop/{safe_flow_name}-{execution_id[:8]}"

            clone_commands = []
            trigger_data = execution_context.get("trigger_event_data", {})

            # Track if we successfully configured any repositories
            configured_repos_count = 0

            # Configure git user globally (do this once at the start)
            git_setup_commands = [
                "mkdir -p /workspace",
                f'git config --global user.name "{git_user_name}"',
                f'git config --global user.email "{git_user_email}"',
            ]

            for idx, repo_config in enumerate(repositories):
                # Get repository URL
                repo_url = repo_config.get("repository_url")

                # If no URL, try to get from project_id (in repo config) or trigger_project_id
                if not repo_url:
                    project_id = repo_config.get("project_id")

                    # If no project_id in repo config, use trigger_project_id
                    if not project_id:
                        project_id = execution_context.get("trigger_project_id")
                        if project_id:
                            self.logger.info(
                                f"Using trigger project {project_id} for repository #{idx + 1}"
                            )

                    if project_id:
                        # Fetch project details from database to construct repository URL
                        repo_url = self._get_repo_url_from_project(
                            project_id, execution_context.get("account_id")
                        )
                        if repo_url:
                            self.logger.info(
                                f"Resolved repository URL from project {project_id}"
                            )
                        else:
                            self.logger.warning(
                                f"Could not construct repository URL from project {project_id}"
                            )

                    # Final fallback: try to extract from trigger event data
                    if not repo_url:
                        repo_url = self._extract_repo_url_from_trigger(trigger_data)
                        if repo_url:
                            self.logger.info(
                                "Extracted repository URL from trigger event data"
                            )

                if not repo_url:
                    self.logger.error(
                        f"No repository URL found for repo #{idx + 1}. "
                        f"Please add 'repository_url' field to git_clone_config.repositories, "
                        f"or select a project in the trigger configuration. "
                        f"Repo config: {repo_config}, "
                        f"Trigger project ID: {execution_context.get('trigger_project_id')}"
                    )
                    continue

                # For manually specified URLs, inject token from credentials map
                if repo_url and "@" not in repo_url:
                    # URL doesn't have credentials, need to inject
                    tracker_id = repo_config.get("tracker_id")
                    git_credentials_map = execution_context.get(
                        "git_credentials_map", {}
                    )
                    tracker_creds = git_credentials_map.get(tracker_id)

                    if tracker_creds:
                        token = tracker_creds.get("token")
                        tracker_type = tracker_creds.get("tracker_type")

                        if token:
                            # Inject token into manually specified URL
                            if "github.com" in repo_url or tracker_type == "github":
                                repo_url = repo_url.replace(
                                    "https://", f"https://{token}@"
                                )
                            elif "gitlab" in repo_url or tracker_type == "gitlab":
                                repo_url = repo_url.replace(
                                    "https://", f"https://gitlab-ci-token:{token}@"
                                )
                            self.logger.info(
                                f"Injected token into manually specified URL (tracker type: {tracker_type})"
                            )

                # Get clone path - if it starts with /, use as-is (absolute), otherwise make it relative to /workspace
                clone_path = repo_config.get("clone_path", f"/workspace-{idx + 1}")
                if clone_path.startswith("/"):
                    # Absolute path
                    full_path = clone_path
                else:
                    # Relative path - prepend /workspace/
                    full_path = f"/workspace/{clone_path}"

                # Get branch - prioritize source_branch from config, fall back to repo-specific branch
                repo_branch = repo_config.get("branch")
                clone_branch = repo_branch if repo_branch else source_branch
                branch_arg = f" -b {clone_branch}" if clone_branch else ""

                # Build repository setup commands
                repo_commands = [
                    # Clone the repository
                    f"git clone{branch_arg} {repo_url} {full_path}",
                    # Navigate to repo
                    f"cd {full_path}",
                    # Ensure we're on the source branch
                    f"git checkout {source_branch} 2>/dev/null || git checkout -b {source_branch}",
                    # Create and checkout target branch for commits
                    f"git checkout -b {target_branch}",
                    # Return to workspace root
                    "cd /workspace",
                ]

                clone_commands.extend(repo_commands)

                # Add validation check - FAIL IMMEDIATELY if clone didn't work
                # This prevents wasting tokens if we can't actually update the repo
                validation_cmd = f"""
if [ ! -d "{full_path}" ] || [ ! -d "{full_path}/.git" ]; then
    echo "========================================="
    echo "FATAL ERROR: Git clone failed!"
    echo "Repository directory '{full_path}' does not exist or is not a git repository."
    echo "Flow execution cannot continue without repository access."
    echo "========================================="
    exit 1
fi
echo "✓ Repository successfully cloned to {full_path}"
""".strip()
                clone_commands.append(validation_cmd)

                configured_repos_count += 1
                self.logger.info(
                    f"Prepared git clone for {full_path}: "
                    f"source={source_branch}, target={target_branch}"
                )

            # Check if any repositories were successfully configured
            if configured_repos_count == 0:
                error_msg = (
                    f"FATAL: Git clone configured with {len(repositories)} repositories "
                    f"but could not resolve repository URLs for any of them. "
                    f"Please ensure 'repository_url' is set in git_clone_config.repositories, "
                    f"or that the flow is triggered by a webhook with repository information."
                )
                self.logger.error(error_msg)
                # Return a command that will fail immediately with clear error
                return f'echo "{error_msg}" && exit 1'

            # Store for later use in post-execution (only if we have valid repos)
            execution_context["_git_target_branch"] = target_branch
            execution_context["_git_source_branch"] = source_branch

            # Combine setup and clone commands
            all_commands = git_setup_commands + clone_commands
            return " && ".join(all_commands)

        except Exception as e:
            self.logger.error(f"Error preparing git clone command: {e}", exc_info=True)
            return ""

    def _prepare_git_post_execution_commands(
        self, execution_context: Dict[str, Any]
    ) -> str:
        """
        Prepare git commands to run after agent execution (push, PR/MR creation).

        Args:
            execution_context: Execution context

        Returns:
            Shell command string for post-execution git operations
        """
        try:
            git_config = execution_context.get("git_clone_config", {})

            if not git_config:
                self.logger.debug("No git_clone_config in execution context")
                return ""

            # Check for repositories - if they exist, we should have cloned them
            repositories = git_config.get("repositories", [])
            if not repositories:
                self.logger.debug("No repositories in git_clone_config")
                return ""

            target_branch = execution_context.get("_git_target_branch")
            source_branch = execution_context.get("_git_source_branch", "main")
            create_pr = git_config.get("create_pull_request", False)

            self.logger.info(
                f"Preparing post-execution git commands: "
                f"target_branch={target_branch}, source_branch={source_branch}, "
                f"create_pr={create_pr}, repos={len(repositories)}"
            )

            if not target_branch:
                return ""

            post_commands = []

            for idx, repo_config in enumerate(repositories):
                # Get clone path - handle absolute vs relative paths
                clone_path = repo_config.get("clone_path", f"/workspace-{idx + 1}")
                if clone_path.startswith("/"):
                    # Absolute path
                    full_path = clone_path
                else:
                    # Relative path - prepend /workspace/
                    full_path = f"/workspace/{clone_path}"

                # Get tracker info for PR/MR creation
                tracker_id = repo_config.get("tracker_id")
                git_credentials_map = execution_context.get("git_credentials_map", {})
                tracker_creds = git_credentials_map.get(tracker_id)

                if not tracker_creds:
                    continue

                tracker_type = tracker_creds.get("tracker_type")
                token = tracker_creds.get("token")

                # Commands to check for commits and push
                # Note: Directory is guaranteed to exist because git clone validation would have failed earlier
                repo_post_commands = [
                    f"cd {full_path}",
                    # Check if there are any commits on target branch vs source
                    f'COMMIT_COUNT=$(git rev-list --count {source_branch}..{target_branch} 2>/dev/null || echo "0")',
                    'if [ "$COMMIT_COUNT" -gt "0" ]; then',
                    f'  echo "Found $COMMIT_COUNT commits on {target_branch}, pushing..."',
                    f"  git push origin {target_branch}",
                ]

                # Add PR/MR creation if enabled
                if create_pr and token:
                    # Get Preloop URL for execution link
                    import os

                    preloop_url = os.getenv("PRELOOP_URL", "http://localhost:8000")
                    execution_id = execution_context.get("execution_id", "")
                    flow_name = execution_context.get("flow_name", "Automated changes")

                    # Check if user provided custom title/description
                    custom_pr_title = git_config.get("pull_request_title")
                    custom_pr_description = git_config.get("pull_request_description")

                    # Only use custom values if they're actually set (not None or empty)
                    use_custom = custom_pr_title and custom_pr_title.strip()

                    if tracker_type == "github":
                        # Extract owner/repo from URL
                        repo_url = self._extract_repo_url_from_trigger(
                            execution_context.get("trigger_event_data", {})
                        )

                        # If no URL from trigger, try to get from project configuration
                        if not repo_url:
                            project_id = repo_config.get("project_id")
                            if not project_id:
                                project_id = execution_context.get("trigger_project_id")
                            if project_id:
                                repo_url = self._get_repo_url_from_project(
                                    project_id, execution_context.get("account_id")
                                )
                                if repo_url:
                                    self.logger.info(
                                        f"Using repo URL from project {project_id} for PR creation"
                                    )

                        if repo_url:
                            # Parse owner/repo from URL like https://github.com/owner/repo
                            repo_parts = repo_url.rstrip("/").split("/")
                            if len(repo_parts) >= 2:
                                owner = repo_parts[-2]
                                repo = repo_parts[-1].replace(".git", "")

                                # Build PR creation command with dynamic title/description
                                if use_custom:
                                    # Use custom title and description
                                    pr_create_cmd = f"""
    curl -X POST \\
      -H "Authorization: token {token}" \\
      -H "Accept: application/vnd.github.v3+json" \\
      https://api.github.com/repos/{owner}/{repo}/pulls \\
      -d "$(cat <<'PREOF'
{{
  "title": "{custom_pr_title}",
  "body": "{custom_pr_description or ""}",
  "head": "{target_branch}",
  "base": "{source_branch}"
}}
PREOF
)" \\
      || echo "Failed to create PR (may already exist)"
"""
                                else:
                                    # Build title and description from commits
                                    execution_link = f"{preloop_url}/console/flows/executions/{execution_id}"
                                    pr_create_cmd = f"""
    # Build PR title and description based on commit count
    if [ "$COMMIT_COUNT" -eq "1" ]; then
      # Single commit - use commit message
      PR_TITLE=$(git log -1 --format=%s {source_branch}..{target_branch})
      COMMIT_BODY=$(git log -1 --format=%b {source_branch}..{target_branch})
      PR_BODY="Automated changes from Preloop flow: [{flow_name}]({execution_link})\\n\\n$COMMIT_BODY"
    else
      # Multiple commits - use flow name and list commits
      PR_TITLE="[Preloop] {flow_name}"
      COMMIT_LIST=$(git log --format="- %s" {source_branch}..{target_branch})
      PR_BODY="Automated changes from Preloop flow: [{flow_name}]({execution_link})\\n\\n**Commits:**\\n$COMMIT_LIST"
    fi

    # Create PR with dynamic title/body
    curl -X POST \\
      -H "Authorization: token {token}" \\
      -H "Accept: application/vnd.github.v3+json" \\
      https://api.github.com/repos/{owner}/{repo}/pulls \\
      -d "$(cat <<PREOF
{{
  "title": "$PR_TITLE",
  "body": "$PR_BODY",
  "head": "{target_branch}",
  "base": "{source_branch}"
}}
PREOF
)" \\
      || echo "Failed to create PR (may already exist)"
"""
                                repo_post_commands.append(pr_create_cmd)

                    elif tracker_type == "gitlab":
                        # Extract project path and GitLab host from URL
                        repo_url = self._extract_repo_url_from_trigger(
                            execution_context.get("trigger_event_data", {})
                        )

                        # If no URL from trigger, try to get from project configuration
                        if not repo_url:
                            project_id = repo_config.get("project_id")
                            if not project_id:
                                project_id = execution_context.get("trigger_project_id")
                            if project_id:
                                repo_url = self._get_repo_url_from_project(
                                    project_id, execution_context.get("account_id")
                                )
                                if repo_url:
                                    self.logger.info(
                                        f"Using repo URL from project {project_id} for MR creation"
                                    )

                        if repo_url:
                            # Parse GitLab host from URL (e.g., gitlab.spacecode.ai or gitlab.com)
                            from urllib.parse import urlparse

                            parsed_url = urlparse(repo_url)
                            gitlab_host = parsed_url.netloc
                            # Remove credentials if present (e.g., gitlab-ci-token:xxx@host)
                            if "@" in gitlab_host:
                                gitlab_host = gitlab_host.split("@")[-1]

                            # Parse project path from URL
                            repo_path = repo_url.rstrip("/").split("://")[-1]
                            repo_path = repo_path.split("/", 1)[-1].replace(".git", "")
                            # Remove credentials from path if present
                            if "@" in repo_path:
                                repo_path = repo_path.split("@", 1)[-1]

                            # URL encode the project path
                            import urllib.parse

                            encoded_path = urllib.parse.quote(repo_path, safe="")

                            self.logger.info(
                                f"Creating GitLab MR: host={gitlab_host}, path={encoded_path}, create_pr={create_pr}"
                            )

                            # Build MR creation command with dynamic title/description
                            if use_custom:
                                # Use custom title and description
                                mr_create_cmd = f"""
    echo "Creating Merge Request on {gitlab_host}..."
    curl -X POST \\
      -H "PRIVATE-TOKEN: {token}" \\
      -H "Content-Type: application/json" \\
      https://{gitlab_host}/api/v4/projects/{encoded_path}/merge_requests \\
      -d "$(cat <<'MREOF'
{{
  "source_branch": "{target_branch}",
  "target_branch": "{source_branch}",
  "title": "{custom_pr_title}",
  "description": "{custom_pr_description or ""}"
}}
MREOF
)" \\
      || echo "Failed to create MR (may already exist)"
"""
                            else:
                                # Build title and description from commits
                                execution_link = f"{preloop_url}/console/flows/executions/{execution_id}"
                                mr_create_cmd = f"""
    # Build MR title and description based on commit count
    if [ "$COMMIT_COUNT" -eq "1" ]; then
      # Single commit - use commit message
      MR_TITLE=$(git log -1 --format=%s {source_branch}..{target_branch})
      COMMIT_BODY=$(git log -1 --format=%b {source_branch}..{target_branch})
      MR_DESCRIPTION="Automated changes from Preloop flow: [{flow_name}]({execution_link})\\n\\n$COMMIT_BODY"
    else
      # Multiple commits - use flow name and list commits
      MR_TITLE="[Preloop] {flow_name}"
      COMMIT_LIST=$(git log --format="- %s" {source_branch}..{target_branch})
      MR_DESCRIPTION="Automated changes from Preloop flow: [{flow_name}]({execution_link})\\n\\n**Commits:**\\n$COMMIT_LIST"
    fi

    echo "Creating Merge Request on {gitlab_host}..."
    curl -X POST \\
      -H "PRIVATE-TOKEN: {token}" \\
      -H "Content-Type: application/json" \\
      https://{gitlab_host}/api/v4/projects/{encoded_path}/merge_requests \\
      -d "$(cat <<MREOF
{{
  "source_branch": "{target_branch}",
  "target_branch": "{source_branch}",
  "title": "$MR_TITLE",
  "description": "$MR_DESCRIPTION"
}}
MREOF
)" \\
      || echo "Failed to create MR (may already exist)"
"""
                            repo_post_commands.append(mr_create_cmd)

                repo_post_commands.extend(
                    [
                        "else",
                        f'  echo "No commits on {target_branch}, skipping push"',
                        "fi",
                        "cd /workspace",
                    ]
                )

                post_commands.extend(repo_post_commands)

            if not post_commands:
                return ""

            # Join commands with newlines instead of && to properly handle if-else-fi blocks
            return "\n".join(post_commands)

        except Exception as e:
            self.logger.error(
                f"Error preparing git post-execution commands: {e}", exc_info=True
            )
            return ""

    def _get_repo_url_from_project(
        self, project_id: str, account_id: str
    ) -> Optional[str]:
        """Construct repository URL from project and tracker information.

        Uses the tracker URL, project slug, and authentication token to construct
        a complete clone URL in the format:
        - GitLab: https://gitlab-ci-token:{token}@{host}/{slug}.git
        - GitHub: https://{token}@github.com/{slug}.git

        Args:
            project_id: Project ID
            account_id: Account ID

        Returns:
            Repository clone URL with token injected, or None if not found
        """
        try:
            from preloop.models.crud import crud_project, crud_tracker
            from preloop.models.db.session import get_db_session

            db = next(get_db_session())
            try:
                # Get project from database
                project = crud_project.get(db, id=project_id, account_id=account_id)
                if not project:
                    self.logger.warning(
                        f"Project {project_id} not found for account {account_id}"
                    )
                    return None

                if not project.slug:
                    self.logger.warning(
                        f"Project {project_id} has no slug, cannot construct repository URL"
                    )
                    return None

                # Get the organization to find the tracker
                organization = project.organization
                if not organization:
                    self.logger.warning(
                        f"Project {project_id} has no organization, cannot get tracker"
                    )
                    return None

                # Get the tracker
                tracker = crud_tracker.get(
                    db, id=organization.tracker_id, account_id=account_id
                )
                if not tracker:
                    self.logger.warning(
                        f"Tracker {organization.tracker_id} not found for account {account_id}"
                    )
                    return None

                # Get token from tracker (we always have tokens for GitHub/GitLab)
                token = tracker.api_key
                if not token:
                    self.logger.warning(
                        f"Tracker {tracker.id} has no API key configured"
                    )
                    return None

                # Construct the clone URL based on tracker type
                tracker_type = tracker.tracker_type.lower()
                slug = project.slug

                if tracker_type == "gitlab":
                    # GitLab format: https://gitlab-ci-token:{token}@{host}/{slug}.git
                    if not tracker.url:
                        self.logger.warning(
                            f"GitLab tracker {tracker.id} has no URL configured"
                        )
                        return None

                    # Parse the host from tracker URL
                    # tracker.url might be like "https://gitlab.spacecode.ai" or "https://gitlab.com"
                    from urllib.parse import urlparse

                    parsed = urlparse(tracker.url)
                    host = parsed.netloc or parsed.path

                    # Ensure slug ends with .git
                    if not slug.endswith(".git"):
                        slug = f"{slug}.git"

                    clone_url = f"https://gitlab-ci-token:{token}@{host}/{slug}"
                    self.logger.info(
                        f"Constructed GitLab clone URL for {slug} on {host}"
                    )
                    return clone_url

                elif tracker_type == "github":
                    # GitHub format: https://{token}@github.com/{slug}.git
                    # Ensure slug ends with .git
                    if not slug.endswith(".git"):
                        slug = f"{slug}.git"

                    clone_url = f"https://{token}@github.com/{slug}"
                    self.logger.info(f"Constructed GitHub clone URL for {slug}")
                    return clone_url

                else:
                    self.logger.warning(
                        f"Tracker type '{tracker_type}' not supported for git clone"
                    )
                    return None

            finally:
                db.close()

        except Exception as e:
            self.logger.error(
                f"Error constructing repository URL from project {project_id}: {e}",
                exc_info=True,
            )
            return None

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

    async def cleanup(self):
        """Cleanup resources (close Docker client, Kubernetes client, etc.)."""
        if self._docker_client:
            await self._docker_client.close()
            self._docker_client = None

        if self._k8s_api_client:
            await self._k8s_api_client.close()
            self._k8s_api_client = None
            self._k8s_batch_api = None
            self._k8s_core_api = None
            self._k8s_initialized = False
