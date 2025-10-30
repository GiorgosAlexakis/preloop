"""Container-based agent executor for Docker and Kubernetes."""

import json
import logging
import os
from typing import Any, Dict, Optional

import aiodocker
from aiodocker.exceptions import DockerError

from .base import AgentExecutionResult, AgentExecutor, AgentStatus
from spacebridge.services.mcp_config_service import MCPConfigService

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

            self._k8s_batch_api = client.BatchV1Api()
            self._k8s_core_api = client.CoreV1Api()
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

        # Container configuration
        container_config = {
            "Image": self.image,
            "Env": [f"{k}={v}" for k, v in env.items()],
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
        env = {
            "FLOW_ID": flow_id,
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

        # Convert env dict to list of V1EnvVar
        env_vars = [client.V1EnvVar(name=k, value=v) for k, v in env.items()]

        # Get resource limits from config or use defaults
        memory_limit = os.getenv("AGENT_MEMORY_LIMIT", "2Gi")
        cpu_limit = os.getenv("AGENT_CPU_LIMIT", "1")
        memory_request = os.getenv("AGENT_MEMORY_REQUEST", "512Mi")
        cpu_request = os.getenv("AGENT_CPU_REQUEST", "250m")

        # Container specification with security context
        container = client.V1Container(
            name="agent",
            image=self.image,
            env=env_vars,
            resources=client.V1ResourceRequirements(
                limits={"memory": memory_limit, "cpu": cpu_limit},
                requests={"memory": memory_request, "cpu": cpu_request},
            ),
            security_context=client.V1SecurityContext(
                run_as_non_root=True,
                run_as_user=10000,
                read_only_root_filesystem=False,  # Some agents need writable filesystem
                allow_privilege_escalation=False,
                capabilities=client.V1Capabilities(drop=["ALL"]),
            ),
        )

        # Pod template specification
        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "spacebridge.flow_id": flow_id,
                    "spacebridge.execution_id": execution_id,
                    "spacebridge.agent_type": self.agent_type,
                    "app": "agent-execution",
                }
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container],
                security_context=client.V1PodSecurityContext(
                    run_as_non_root=True,
                    run_as_user=10000,
                    fs_group=10000,
                ),
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
                    "spacebridge.flow_id": flow_id,
                    "spacebridge.execution_id": execution_id,
                    "spacebridge.agent_type": self.agent_type,
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
            session_reference: Container ID

        Returns:
            Execution result
        """
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

            error_message = None
            if status == AgentStatus.FAILED:
                error_message = (
                    info["State"].get("Error")
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
        try:
            docker = await self._get_docker_client()
            container = await docker.containers.get(container_id)

            # Stream logs with follow=True
            async for line in container.log(
                stdout=True, stderr=True, follow=True, stream=True
            ):
                # Handle both bytes and str (aiodocker API can return either)
                if isinstance(line, bytes):
                    decoded_line = line.decode("utf-8", errors="replace").rstrip()
                else:
                    decoded_line = line.rstrip()

                if decoded_line:  # Skip empty lines
                    yield decoded_line

        except DockerError as e:
            self.logger.error(
                f"Error streaming logs from container {container_id}: {e}"
            )
            yield f"[ERROR] Failed to stream logs: {e}"
        except Exception as e:
            self.logger.error(
                f"Unexpected error streaming Docker logs for {container_id}: {e}"
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
            # List pods for this Job
            label_selector = f"job-name={job_name}"
            pods = await self._k8s_core_api.list_namespaced_pod(
                namespace=self.agent_namespace, label_selector=label_selector
            )

            if not pods.items:
                self.logger.warning(f"No pods found for Job {job_name}")
                yield f"[WARN] No pods found for Job {job_name}"
                return

            # Get the first pod
            pod_name = pods.items[0].metadata.name

            # Stream logs with follow=True
            response = await self._k8s_core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.agent_namespace,
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

    async def cleanup(self):
        """Cleanup resources (close Docker client, etc.)."""
        if self._docker_client:
            await self._docker_client.close()
            self._docker_client = None
