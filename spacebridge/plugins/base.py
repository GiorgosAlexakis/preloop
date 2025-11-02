"""Base classes for SpaceBridge plugin system.

This module provides the core plugin architecture for extending SpaceBridge
functionality. Plugins can provide services, API routes, background tasks,
condition evaluators, and workflow orchestrators.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

logger = logging.getLogger(__name__)


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""

    name: str
    version: str
    author: str
    description: str
    is_proprietary: bool = False


class Plugin(ABC):
    """Base class for all SpaceBridge plugins.

    Plugins can provide:
    - Services (business logic, integrations)
    - API routes (additional endpoints, webhooks)
    - Background tasks (scheduled jobs, workers)
    - Condition evaluators (for approval rules)
    - Workflow orchestrators (for complex approvals)
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass

    def get_routers(self) -> List[tuple[APIRouter, str]]:
        """Return list of (router, prefix) tuples to register."""
        return []

    def get_services(self) -> Dict[str, Any]:
        """Return services to register (name -> instance)."""
        return {}

    def get_tasks(self) -> List[Dict[str, Any]]:
        """Return background tasks to register."""
        return []

    def get_condition_evaluators(self) -> List["ConditionEvaluatorPlugin"]:
        """Return condition evaluators for approval rules."""
        return []

    def get_workflow_orchestrators(self) -> List["WorkflowOrchestratorPlugin"]:
        """Return workflow orchestrators for complex approvals."""
        return []

    async def on_startup(self):
        """Called when application starts."""
        return

    async def on_shutdown(self):
        """Called when application shuts down."""
        return


class ConditionEvaluatorPlugin(ABC):
    """Abstract base for condition evaluator plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return evaluator metadata."""
        pass

    @property
    @abstractmethod
    def condition_type(self) -> str:
        """Unique identifier for this condition type (e.g., 'argument', 'team', 'external')."""
        pass

    @abstractmethod
    async def evaluate(
        self,
        condition_config: Dict[str, Any],
        tool_args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Evaluate condition and return True if approval is required.

        Args:
            condition_config: Configuration from ApprovalRule.condition_config
            tool_args: Arguments passed to the tool
            context: Additional context (account_id, user_id, etc.)

        Returns:
            True if condition matches (approval required), False otherwise
        """
        pass

    @abstractmethod
    async def validate_config(self, condition_config: Dict[str, Any]) -> List[str]:
        """Validate condition configuration.

        Returns:
            List of error messages (empty if valid)
        """
        pass

    async def test(
        self, condition_config: Dict[str, Any], tool_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Test condition with sample data (returns debug info)."""
        try:
            result = await self.evaluate(condition_config, tool_args)
            return {
                "result": result,
                "trace": [f"Evaluation result: {result}"],
                "errors": [],
            }
        except Exception as e:
            return {"result": False, "trace": [], "errors": [str(e)]}

    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for condition_config (for UI validation)."""
        return {}

    def get_examples(self) -> List[Dict[str, Any]]:
        """Return example configurations."""
        return []


class WorkflowOrchestratorPlugin(ABC):
    """Abstract base for approval workflow orchestrators (Phase 3)."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return orchestrator metadata."""
        pass

    @property
    @abstractmethod
    def workflow_type(self) -> str:
        """Unique identifier for this workflow type (e.g., 'escalation', 'quorum')."""
        pass

    @abstractmethod
    async def execute_workflow(
        self,
        approval_request_id: str,
        workflow_config: Dict[str, Any],
        policy_config: Dict[str, Any],
    ) -> str:
        """Execute approval workflow.

        Returns:
            Final approval status: "approved", "declined", "expired"
        """
        pass

    @abstractmethod
    async def get_status(self, approval_request_id: str) -> Dict[str, Any]:
        """Get current workflow status."""
        pass


class PluginManager:
    """Manages plugin lifecycle and registration."""

    def __init__(self):
        """Initialize plugin manager."""
        self._plugins: Dict[str, Plugin] = {}
        self._services: Dict[str, Any] = {}
        self._condition_evaluators: Dict[str, ConditionEvaluatorPlugin] = {}
        self._workflow_orchestrators: Dict[str, WorkflowOrchestratorPlugin] = {}
        self._discovered_modules: set = (
            set()
        )  # Track discovered modules to prevent infinite recursion

    def register_plugin(self, plugin: Plugin):
        """Register a plugin and all its components."""
        if plugin.metadata.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.metadata.name}' already registered")

        self._plugins[plugin.metadata.name] = plugin

        # Register services
        for service_name, service in plugin.get_services().items():
            self._services[service_name] = service

        # Register condition evaluators
        for evaluator in plugin.get_condition_evaluators():
            self._condition_evaluators[evaluator.condition_type] = evaluator

        # Register workflow orchestrators
        for orchestrator in plugin.get_workflow_orchestrators():
            self._workflow_orchestrators[orchestrator.workflow_type] = orchestrator

        logger.info(
            f"Registered plugin: {plugin.metadata.name} v{plugin.metadata.version} "
            f"(proprietary: {plugin.metadata.is_proprietary})"
        )

    def get_service(self, name: str) -> Any:
        """Get registered service by name."""
        return self._services.get(name)

    def get_condition_evaluator(
        self, condition_type: str
    ) -> Optional[ConditionEvaluatorPlugin]:
        """Get condition evaluator by type."""
        return self._condition_evaluators.get(condition_type)

    def get_workflow_orchestrator(
        self, workflow_type: str
    ) -> Optional[WorkflowOrchestratorPlugin]:
        """Get workflow orchestrator by type."""
        return self._workflow_orchestrators.get(workflow_type)

    def list_condition_evaluators(self) -> List[str]:
        """List all registered condition evaluator types."""
        return list(self._condition_evaluators.keys())

    def list_workflow_orchestrators(self) -> List[str]:
        """List all registered workflow orchestrator types."""
        return list(self._workflow_orchestrators.keys())

    def get_enabled_features(self) -> Dict[str, Any]:
        """Get list of enabled features/plugins for frontend consumption."""
        features = {"plugins": [], "features": {}}

        for _plugin_name, plugin in self._plugins.items():
            features["plugins"].append(
                {
                    "name": plugin.metadata.name,
                    "version": plugin.metadata.version,
                    "description": plugin.metadata.description,
                    "is_proprietary": plugin.metadata.is_proprietary,
                }
            )

            # Add specific feature flags based on plugin name
            if plugin.metadata.name == "rbac":
                features["features"]["rbac"] = True
                features["features"]["user_management"] = True
                features["features"]["team_management"] = True
                features["features"]["role_management"] = True
            elif plugin.metadata.name == "audit":
                features["features"]["audit_logs"] = True

        return features

    async def startup_all(self):
        """Call on_startup for all plugins."""
        for plugin in self._plugins.values():
            try:
                await plugin.on_startup()
            except Exception as e:
                logger.error(
                    f"Error starting plugin '{plugin.metadata.name}': {e}",
                    exc_info=True,
                )

    async def shutdown_all(self):
        """Call on_shutdown for all plugins."""
        for plugin in self._plugins.values():
            try:
                await plugin.on_shutdown()
            except Exception as e:
                logger.error(
                    f"Error shutting down plugin '{plugin.metadata.name}': {e}",
                    exc_info=True,
                )

    def register_routes(self, app):
        """Register all plugin routes with FastAPI app."""
        for plugin in self._plugins.values():
            for router, prefix in plugin.get_routers():
                app.include_router(router, prefix=prefix)
                logger.info(
                    f"Registered routes from plugin '{plugin.metadata.name}' at {prefix}"
                )

    def discover_plugins(self, plugin_module: str = "plugins"):
        """Discover and load plugins from a Python package.

        Args:
            plugin_module: Dotted module path (e.g. "spacebridge.plugins.builtin")
        """
        import importlib
        import pkgutil

        # Prevent infinite recursion
        if plugin_module in self._discovered_modules:
            return
        self._discovered_modules.add(plugin_module)

        try:
            # Import the plugin package
            package = importlib.import_module(plugin_module)

            # Get the package's path for pkgutil
            if not hasattr(package, "__path__"):
                logger.warning(f"Plugin module '{plugin_module}' is not a package")
                return

            # Iterate through submodules and sub-packages
            for _finder, name, ispkg in pkgutil.iter_modules(package.__path__):
                full_module_name = f"{plugin_module}.{name}"

                # Skip if already discovered
                if full_module_name in self._discovered_modules:
                    continue

                try:
                    # Import the submodule or sub-package
                    module = importlib.import_module(full_module_name)
                    # Check if it has a register function
                    if hasattr(module, "register"):
                        module.register(self)
                        logger.info(f"Loaded plugin module: {full_module_name}")
                    elif ispkg:
                        # If it's a package without a register function, try to discover plugins within it
                        self.discover_plugins(full_module_name)
                except Exception as e:
                    logger.error(
                        f"Failed to load plugin '{full_module_name}': {e}",
                        exc_info=True,
                    )
        except ImportError as e:
            logger.warning(f"Plugin module not found: {plugin_module} - {e}")


# Global singleton
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get global plugin manager (singleton)."""
    import os

    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        _plugin_manager.discover_plugins("spacebridge.plugins.builtin")

        # Only load proprietary plugins if not explicitly disabled
        # Check both DISABLE_RBAC (for permission checks) and DISABLE_PROPRIETARY_PLUGINS (for plugin loading)
        if (
            os.getenv("DISABLE_RBAC", "false").lower() != "true"
            and os.getenv("DISABLE_PROPRIETARY_PLUGINS", "false").lower() != "true"
        ):
            _plugin_manager.discover_plugins("spacebridge.plugins.proprietary")
    return _plugin_manager


def reset_plugin_manager():
    """Reset global plugin manager (for testing)."""
    global _plugin_manager
    _plugin_manager = None
