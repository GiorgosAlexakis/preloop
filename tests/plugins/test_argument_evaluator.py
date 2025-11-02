"""Tests for the ArgumentEvaluator plugin."""

import pytest

from spacebridge.plugins.builtin.argument_evaluator import ArgumentEvaluator


class TestArgumentEvaluator:
    """Tests for ArgumentEvaluator class."""

    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance."""
        return ArgumentEvaluator()

    def test_metadata(self, evaluator):
        """Test evaluator metadata."""
        metadata = evaluator.metadata
        assert metadata.name == "Argument Evaluator"
        assert metadata.version == "1.0.0"
        assert metadata.is_proprietary is False

    def test_condition_type(self, evaluator):
        """Test condition type."""
        assert evaluator.condition_type == "argument"

    @pytest.mark.asyncio
    async def test_numeric_comparison(self, evaluator):
        """Test numeric comparison expressions."""
        # Greater than
        config = {"expression": "args.amount > 1000"}
        assert await evaluator.evaluate(config, {"amount": 1500}) is True
        assert await evaluator.evaluate(config, {"amount": 500}) is False

        # Less than
        config2 = {"expression": "args.priority < 3"}
        assert await evaluator.evaluate(config2, {"priority": 1}) is True
        assert await evaluator.evaluate(config2, {"priority": 5}) is False

        # Greater than or equal
        config3 = {"expression": "args.score >= 90"}
        assert await evaluator.evaluate(config3, {"score": 90}) is True
        assert await evaluator.evaluate(config3, {"score": 95}) is True
        assert await evaluator.evaluate(config3, {"score": 85}) is False

    @pytest.mark.asyncio
    async def test_string_comparison(self, evaluator):
        """Test string comparison expressions."""
        config = {"expression": "args.status == 'active'"}
        assert await evaluator.evaluate(config, {"status": "active"}) is True
        assert await evaluator.evaluate(config, {"status": "inactive"}) is False

    @pytest.mark.asyncio
    async def test_logical_operators(self, evaluator):
        """Test logical AND/OR operators."""
        # AND
        config_and = {"expression": "args.amount > 1000 && args.currency == 'USD'"}
        assert (
            await evaluator.evaluate(config_and, {"amount": 1500, "currency": "USD"})
            is True
        )
        assert (
            await evaluator.evaluate(config_and, {"amount": 1500, "currency": "EUR"})
            is False
        )
        assert (
            await evaluator.evaluate(config_and, {"amount": 500, "currency": "USD"})
            is False
        )

        # OR
        config_or = {"expression": "args.urgent || args.critical"}
        assert (
            await evaluator.evaluate(config_or, {"urgent": True, "critical": False})
            is True
        )
        assert (
            await evaluator.evaluate(config_or, {"urgent": False, "critical": True})
            is True
        )
        assert (
            await evaluator.evaluate(config_or, {"urgent": False, "critical": False})
            is False
        )

    @pytest.mark.asyncio
    async def test_array_membership(self, evaluator):
        """Test array membership (in operator)."""
        config = {"expression": "'urgent' in args.labels"}
        assert await evaluator.evaluate(config, {"labels": ["urgent", "bug"]}) is True
        assert (
            await evaluator.evaluate(config, {"labels": ["feature", "enhancement"]})
            is False
        )

    @pytest.mark.asyncio
    async def test_nested_access(self, evaluator):
        """Test nested object access."""
        config = {
            "expression": "args.deployment.environment == 'production' && args.deployment.region == 'us-east-1'"
        }
        assert (
            await evaluator.evaluate(
                config,
                {"deployment": {"environment": "production", "region": "us-east-1"}},
            )
            is True
        )
        assert (
            await evaluator.evaluate(
                config,
                {"deployment": {"environment": "staging", "region": "us-east-1"}},
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_missing_expression_raises_error(self, evaluator):
        """Test that missing expression raises ValueError."""
        with pytest.raises(ValueError, match="Missing 'expression'"):
            await evaluator.evaluate({}, {"amount": 1500})

    @pytest.mark.asyncio
    async def test_invalid_cel_syntax_raises_error(self, evaluator):
        """Test that invalid CEL syntax raises ValueError."""
        config = {"expression": "args.amount >> 1000"}  # Invalid operator
        with pytest.raises(ValueError, match="Invalid CEL syntax"):
            await evaluator.evaluate(config, {"amount": 1500})

    @pytest.mark.asyncio
    async def test_validate_config_valid(self, evaluator):
        """Test validating valid configuration."""
        config = {"expression": "args.amount > 1000"}
        errors = await evaluator.validate_config(config)
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_config_missing_expression(self, evaluator):
        """Test validating config with missing expression."""
        errors = await evaluator.validate_config({})
        assert len(errors) == 1
        assert "Missing required field" in errors[0]

    @pytest.mark.asyncio
    async def test_validate_config_expression_too_long(self, evaluator):
        """Test validating config with too long expression."""
        config = {"expression": "a" * 501}
        errors = await evaluator.validate_config(config)
        assert len(errors) >= 1
        assert any("too long" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_config_invalid_syntax(self, evaluator):
        """Test validating config with invalid CEL syntax."""
        config = {"expression": "args.amount >> 1000"}
        errors = await evaluator.validate_config(config)
        assert len(errors) >= 1
        assert any("Invalid CEL syntax" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_config_non_string_expression(self, evaluator):
        """Test validating config with non-string expression."""
        config = {"expression": 12345}
        errors = await evaluator.validate_config(config)
        assert len(errors) == 1
        assert "must be a string" in errors[0]

    def test_get_schema(self, evaluator):
        """Test getting JSON schema."""
        schema = evaluator.get_schema()
        assert schema["type"] == "object"
        assert "expression" in schema["required"]
        assert "expression" in schema["properties"]
        assert schema["properties"]["expression"]["maxLength"] == 500

    def test_get_examples(self, evaluator):
        """Test getting example configurations."""
        examples = evaluator.get_examples()
        assert len(examples) > 0

        # Check first example structure
        example = examples[0]
        assert "name" in example
        assert "description" in example
        assert "config" in example
        assert "sample_args" in example
        assert "expected_result" in example
        assert "expression" in example["config"]

    @pytest.mark.asyncio
    async def test_complex_condition(self, evaluator):
        """Test complex real-world condition."""
        config = {
            "expression": "(args.amount > 1000 && args.currency == 'USD') || args.priority == 'critical'"
        }

        # High amount in USD
        assert (
            await evaluator.evaluate(config, {"amount": 1500, "currency": "USD"})
            is True
        )

        # Critical priority
        assert (
            await evaluator.evaluate(
                config, {"amount": 500, "currency": "EUR", "priority": "critical"}
            )
            is True
        )

        # Neither condition met
        assert (
            await evaluator.evaluate(
                config, {"amount": 500, "currency": "EUR", "priority": "low"}
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_evaluate_with_context(self, evaluator):
        """Test evaluate with context parameter (currently unused)."""
        config = {"expression": "args.amount > 1000"}
        context = {"account_id": "test-account", "user_id": "test-user"}

        # Context is passed but not used in argument evaluation
        result = await evaluator.evaluate(config, {"amount": 1500}, context)
        assert result is True


class TestArgumentEvaluatorPlugin:
    """Tests for BuiltinPlugin registration."""

    def test_plugin_registration(self):
        """Test that plugin can be imported and has register function."""
        from spacebridge.plugins.builtin import argument_evaluator

        assert hasattr(argument_evaluator, "register")
        assert callable(argument_evaluator.register)

    def test_builtin_plugin_metadata(self):
        """Test BuiltinPlugin metadata."""
        from spacebridge.plugins.builtin.argument_evaluator import BuiltinPlugin

        plugin = BuiltinPlugin()
        metadata = plugin.metadata

        assert metadata.name == "builtin"
        assert metadata.is_proprietary is False

    def test_builtin_plugin_provides_evaluator(self):
        """Test that BuiltinPlugin provides ArgumentEvaluator."""
        from spacebridge.plugins.builtin.argument_evaluator import BuiltinPlugin

        plugin = BuiltinPlugin()
        evaluators = plugin.get_condition_evaluators()

        assert len(evaluators) == 1
        assert isinstance(evaluators[0], ArgumentEvaluator)
