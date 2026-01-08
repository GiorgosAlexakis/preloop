"""Tests for the plugin system base classes and plugin manager."""

import pytest

from preloop.plugins.base import (
    ConditionEvaluatorPlugin,
    Plugin,
    PluginManager,
    PluginMetadata,
    reset_plugin_manager,
)


class DummyPlugin(Plugin):
    """Dummy plugin for testing."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="dummy",
            version="1.0.0",
            author="Test",
            description="Test plugin",
        )

    def get_services(self):
        return {"test_service": "service_instance"}


class DummyEvaluator(ConditionEvaluatorPlugin):
    """Dummy evaluator for testing."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="dummy_evaluator",
            version="1.0.0",
            author="Test",
            description="Test evaluator",
        )

    @property
    def condition_type(self):
        return "test"

    async def evaluate(self, condition_config, tool_args, context=None):
        return condition_config.get("return_value", False)

    async def validate_config(self, condition_config):
        if "error" in condition_config:
            return [condition_config["error"]]
        return []


class DummyPluginWithEvaluator(Plugin):
    """Plugin that provides an evaluator."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="dummy_with_evaluator",
            version="1.0.0",
            author="Test",
            description="Test plugin with evaluator",
        )

    def get_condition_evaluators(self):
        return [DummyEvaluator()]


@pytest.fixture(autouse=True)
def reset_manager():
    """Reset plugin manager before each test."""
    reset_plugin_manager()
    yield
    reset_plugin_manager()


class TestPluginManager:
    """Tests for PluginManager class."""

    def test_register_plugin(self):
        """Test registering a plugin."""
        manager = PluginManager()
        plugin = DummyPlugin()

        manager.register_plugin(plugin)

        assert "dummy" in manager._plugins
        assert manager._plugins["dummy"] == plugin

    def test_register_duplicate_plugin_raises_error(self):
        """Test that registering duplicate plugin raises error."""
        manager = PluginManager()
        plugin1 = DummyPlugin()
        plugin2 = DummyPlugin()

        manager.register_plugin(plugin1)

        with pytest.raises(ValueError, match="already registered"):
            manager.register_plugin(plugin2)

    def test_register_plugin_with_services(self):
        """Test registering plugin that provides services."""
        manager = PluginManager()
        plugin = DummyPlugin()

        manager.register_plugin(plugin)

        assert manager.get_service("test_service") == "service_instance"

    def test_register_plugin_with_evaluator(self):
        """Test registering plugin that provides evaluator."""
        manager = PluginManager()
        plugin = DummyPluginWithEvaluator()

        manager.register_plugin(plugin)

        evaluator = manager.get_condition_evaluator("test")
        assert evaluator is not None
        assert evaluator.condition_type == "test"

    def test_list_condition_evaluators(self):
        """Test listing registered condition evaluators."""
        manager = PluginManager()
        plugin = DummyPluginWithEvaluator()

        manager.register_plugin(plugin)

        evaluators = manager.list_condition_evaluators()
        assert "test" in evaluators

    def test_get_nonexistent_service(self):
        """Test getting non-existent service returns None."""
        manager = PluginManager()
        assert manager.get_service("nonexistent") is None

    def test_get_nonexistent_evaluator(self):
        """Test getting non-existent evaluator returns None."""
        manager = PluginManager()
        assert manager.get_condition_evaluator("nonexistent") is None

    @pytest.mark.asyncio
    async def test_startup_all(self):
        """Test calling startup on all plugins."""
        manager = PluginManager()

        startup_called = []

        class StartupPlugin(Plugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="startup_test",
                    version="1.0.0",
                    author="Test",
                    description="Test",
                )

            async def on_startup(self):
                startup_called.append(True)

        plugin = StartupPlugin()
        manager.register_plugin(plugin)

        await manager.startup_all()

        assert len(startup_called) == 1

    @pytest.mark.asyncio
    async def test_shutdown_all(self):
        """Test calling shutdown on all plugins."""
        manager = PluginManager()

        shutdown_called = []

        class ShutdownPlugin(Plugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="shutdown_test",
                    version="1.0.0",
                    author="Test",
                    description="Test",
                )

            async def on_shutdown(self):
                shutdown_called.append(True)

        plugin = ShutdownPlugin()
        manager.register_plugin(plugin)

        await manager.shutdown_all()

        assert len(shutdown_called) == 1

    @pytest.mark.asyncio
    async def test_startup_error_doesnt_crash(self):
        """Test that startup errors are logged but don't crash."""
        manager = PluginManager()

        class FailingPlugin(Plugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="failing",
                    version="1.0.0",
                    author="Test",
                    description="Test",
                )

            async def on_startup(self):
                raise RuntimeError("Startup failed")

        plugin = FailingPlugin()
        manager.register_plugin(plugin)

        # Should not raise
        await manager.startup_all()


class TestConditionEvaluatorPlugin:
    """Tests for ConditionEvaluatorPlugin abstract class."""

    @pytest.mark.asyncio
    async def test_evaluate(self):
        """Test evaluator evaluate method."""
        evaluator = DummyEvaluator()

        result = await evaluator.evaluate({"return_value": True}, {"arg": "value"})
        assert result is True

        result2 = await evaluator.evaluate({"return_value": False}, {"arg": "value"})
        assert result2 is False

    @pytest.mark.asyncio
    async def test_validate_config(self):
        """Test evaluator validate_config method."""
        evaluator = DummyEvaluator()

        errors = await evaluator.validate_config({})
        assert len(errors) == 0

        errors2 = await evaluator.validate_config({"error": "Test error"})
        assert len(errors2) == 1
        assert errors2[0] == "Test error"

    @pytest.mark.asyncio
    async def test_default_test_method(self):
        """Test default test method implementation."""
        evaluator = DummyEvaluator()

        result = await evaluator.test({"return_value": True}, {"arg": "value"})

        assert result["result"] is True
        assert len(result["errors"]) == 0
        assert len(result["trace"]) > 0

    @pytest.mark.asyncio
    async def test_test_method_with_error(self):
        """Test that test method handles errors gracefully."""

        class FailingEvaluator(ConditionEvaluatorPlugin):
            @property
            def metadata(self):
                return PluginMetadata(
                    name="failing", version="1.0.0", author="Test", description="Test"
                )

            @property
            def condition_type(self):
                return "failing"

            async def evaluate(self, condition_config, tool_args, context=None):
                raise ValueError("Evaluation failed")

            async def validate_config(self, condition_config):
                return []

        evaluator = FailingEvaluator()
        result = await evaluator.test({}, {})

        assert result["result"] is False
        assert len(result["errors"]) == 1
        assert "Evaluation failed" in result["errors"][0]

    def test_get_schema_default(self):
        """Test default get_schema returns empty dict."""
        evaluator = DummyEvaluator()
        schema = evaluator.get_schema()
        assert schema == {}

    def test_get_examples_default(self):
        """Test default get_examples returns empty list."""
        evaluator = DummyEvaluator()
        examples = evaluator.get_examples()
        assert examples == []
