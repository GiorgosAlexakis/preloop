"""Tests for model pricing estimation."""

from preloop.models.models.ai_model import AIModel
from preloop.models.models.model_price_override import ModelPriceOverride
from preloop.services.model_pricing import estimate_ai_model_usage_cost


def test_pricing_override_applies_discount_and_prepaid_credit() -> None:
    """Pricing overrides should support negotiated discounts and credits."""
    ai_model = AIModel(provider_name="openai", model_identifier="gpt-4o")

    cost = estimate_ai_model_usage_cost(
        ai_model,
        prompt_tokens=1000,
        completion_tokens=1000,
        total_tokens=2000,
        pricing_override={
            "input_price_per_1k": 1.0,
            "output_price_per_1k": 3.0,
            "discount_percent": 50.0,
            "prepaid_credit_balance_usd": 1.0,
        },
    )

    assert cost == 1.0


def test_pricing_override_supports_prepaid_token_balance() -> None:
    """Prepaid token balances should reduce request cost proportionally."""
    ai_model = AIModel(provider_name="openai", model_identifier="gpt-4o")

    cost = estimate_ai_model_usage_cost(
        ai_model,
        prompt_tokens=1000,
        completion_tokens=1000,
        total_tokens=2000,
        pricing_override={
            "price_per_1k": 2.0,
            "prepaid_token_balance": 1000,
        },
    )

    assert cost == 2.0


def test_pricing_override_supports_zero_fixed_request_price() -> None:
    """A fixed request price of zero should make a model free for matching calls."""
    ai_model = AIModel(provider_name="openai", model_identifier="gpt-4o")

    cost = estimate_ai_model_usage_cost(
        ai_model,
        prompt_tokens=1000,
        completion_tokens=1000,
        total_tokens=2000,
        pricing_override={"request_price": 0.0},
    )

    assert cost == 0.0


def test_discount_only_override_applies_to_litellm_list_price(monkeypatch) -> None:
    """A discount-only override should resolve list price first, then discount it."""
    ai_model = AIModel(provider_name="openai", model_identifier="gpt-4o")

    monkeypatch.setattr(
        "preloop.services.model_pricing.litellm.cost_per_token",
        lambda **_kwargs: (0.01, 0.03),
    )

    cost = estimate_ai_model_usage_cost(
        ai_model,
        prompt_tokens=1000,
        completion_tokens=1000,
        total_tokens=2000,
        pricing_override={"discount_percent": 25.0},
    )

    assert cost == 0.03


def test_model_price_override_serializes_adjustment_terms() -> None:
    """Persisted overrides should expose all adjustment terms to estimators."""
    override = ModelPriceOverride(
        model_alias="openai/gpt-4o",
        request_price=0.0,
        discount_percent=10.0,
        prepaid_token_balance=2000,
        prepaid_credit_balance_usd=5.0,
    )

    pricing = override.to_pricing_dict()

    assert pricing["request_price"] == 0.0
    assert pricing["discount_percent"] == 10.0
    assert pricing["prepaid_token_balance"] == 2000
    assert pricing["prepaid_credit_balance_usd"] == 5.0
