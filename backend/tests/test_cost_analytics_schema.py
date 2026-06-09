"""Tests for cost analytics API schemas."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from preloop.models.models.budget import BudgetPeriod
from preloop.schemas.cost_analytics import (
    BudgetPolicyCreate,
    BudgetPolicyResponse,
    ModelPriceOverrideCreate,
)


def test_budget_policy_create_rejects_soft_limit_above_hard_limit() -> None:
    """Request payloads should reject contradictory budget thresholds."""
    with pytest.raises(ValidationError, match="Soft limit cannot exceed hard limit"):
        BudgetPolicyCreate(
            subject_type="account",
            period=BudgetPeriod.monthly,
            hard_limit_usd=100.0,
            soft_limit_usd=125.0,
        )


def test_budget_policy_response_allows_legacy_soft_limit_above_hard_limit() -> None:
    """Stored legacy/plugin rows should serialize instead of breaking list APIs."""
    response = BudgetPolicyResponse(
        id=uuid4(),
        subject_type="account",
        period=BudgetPeriod.monthly,
        hard_limit_usd=100.0,
        soft_limit_usd=125.0,
    )

    assert response.soft_limit_usd == 125.0


def test_model_price_override_create_accepts_adjustment_terms() -> None:
    """Pricing overrides should allow discounts, prepaid balances, and free usage."""
    override = ModelPriceOverrideCreate(
        model_alias="openai/gpt-4o",
        request_price=0.0,
        discount_percent=10.0,
        prepaid_token_balance=1000,
        prepaid_credit_balance_usd=25.0,
    )

    assert override.request_price == 0.0
    assert override.discount_percent == 10.0
    assert override.prepaid_token_balance == 1000
    assert override.prepaid_credit_balance_usd == 25.0
