"""Container-based agent executor for Docker and Kubernetes."""

import logging
import os
from typing import Any, Dict, Optional

import aiodocker
from aiodocker.exceptions import DockerError

from .base import AgentExecutionResult, AgentExecutor, AgentStatus

logger = logging.getLogger(__name__)


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

    async def _get_docker_client(self) -> aiodocker.Docker:
        """Get or create Docker client."""
        if self._docker_client is None:
            self._docker_client = aiodocker.Docker()
        return self._docker_client

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

        # Add MCP restrictions if specified
        if execution_context.get("allowed_mcp_servers"):
            env["ALLOWED_MCP_SERVERS"] = ",".join(
                execution_context["allowed_mcp_servers"]
            )
        if execution_context.get("allowed_mcp_tools"):
            env["ALLOWED_MCP_TOOLS"] = ",".join(execution_context["allowed_mcp_tools"])

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
        Start agent in a Kubernetes pod.

        Args:
            execution_context: Execution context

        Returns:
            Pod name
        """
        # TODO: Implement Kubernetes pod creation using kubernetes_asyncio
        # This is a placeholder for future K8s implementation
        self.logger.warning("Kubernetes execution not yet implemented, using Docker")
        return await self._start_docker_container(execution_context)

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

    async def _get_kubernetes_status(self, pod_name: str) -> AgentStatus:
        """Get status of a Kubernetes pod."""
        # TODO: Implement K8s status check
        self.logger.warning("Kubernetes status check not yet implemented")
        return AgentStatus.RUNNING

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

    async def _stop_kubernetes_pod(self, pod_name: str) -> None:
        """Stop a Kubernetes pod."""
        # TODO: Implement K8s pod deletion
        self.logger.warning("Kubernetes pod stop not yet implemented")

    async def get_logs(self, session_reference: str, tail: int = 100) -> list[str]:
        """
        Get logs from a container.

        Args:
            session_reference: Container ID
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
            return [line.decode("utf-8", errors="replace") for line in logs]

        except DockerError as e:
            self.logger.error(
                f"Failed to get logs for container {session_reference}: {e}"
            )
            return []

    async def _get_kubernetes_logs(self, pod_name: str, tail: int = 100) -> list[str]:
        """Get logs from a Kubernetes pod."""
        # TODO: Implement K8s log retrieval
        self.logger.warning("Kubernetes log retrieval not yet implemented")
        return []

    async def cleanup(self):
        """Cleanup resources (close Docker client, etc.)."""
        if self._docker_client:
            await self._docker_client.close()
            self._docker_client = None
