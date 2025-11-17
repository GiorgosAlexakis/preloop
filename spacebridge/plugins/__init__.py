"""SpaceBridge plugin system.

This package provides the plugin architecture for extending SpaceBridge
with custom evaluators, workflows, and integrations.
"""

from .base import (
    ConditionEvaluatorPlugin,
    Plugin,
    PluginManager,
    PluginMetadata,
    WorkflowOrchestratorPlugin,
    get_plugin_manager,
    reset_plugin_manager,
)

__all__ = [
    "Plugin",
    "PluginMetadata",
    "ConditionEvaluatorPlugin",
    "WorkflowOrchestratorPlugin",
    "PluginManager",
    "get_plugin_manager",
    "reset_plugin_manager",
]
