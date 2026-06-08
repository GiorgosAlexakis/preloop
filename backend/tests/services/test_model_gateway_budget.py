"""Tests for model gateway budget enforcement."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from preloop.models.crud import crud_ai_model
from preloop.models.crud.plan import plan as crud_plan
from preloop.models.crud.plan import subscription as crud_subscription
from preloop.services.model_gateway_auth import ModelGatewayAuthContext
from preloop.services.model_gateway_budget import ModelGatewayBudgetService


def test_enforce_or_raise_reports_trial_hosted_model_limit(db_session, test_user):
    """Trial hosted-model hard caps should return the specific BYOK guidance."""
    now = datetime.now(timezone.utc)
    crud_plan.create(
        db_session,
        obj_in={
            "id": "teams",
            "name": "Teams",
            "price_monthly": 0.0,
            "price_annually": 0.0,
            "is_active": True,
            "features": {},
            "is_custom": False,
        },
    )
    crud_subscription.create(
        db_session,
        obj_in={
            "account_id": test_user.account_id,
            "plan_id": "teams",
            "status": "trialing",
            "current_period_start": now - timedelta(days=1),
            "current_period_end": now + timedelta(days=13),
        },
    )
    ai_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Hosted Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "meta_data": {
                "hosted": True,
                "pricing": {"price_per_1k": 100.0},
            },
        },
        account_id=test_user.account_id,
    )
    service = ModelGatewayBudgetService(
        db_session,
        ModelGatewayAuthContext(token="trial-token", user=test_user),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.enforce_or_raise(ai_model, {"model": "openai/gpt-5", "input": "Hi"})

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == (
        "Preloop trial limit for hosted model reached. Please configure your own "
        "OpenAI/Anthropic API key."
    )


def test_budget_preflight_uses_account_model_price_override(
    db_session, test_user, monkeypatch
):
    """Account-scoped pricing overrides should drive preflight cost estimates."""
    ai_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Negotiated GPT",
            "provider_name": "openai",
            "model_identifier": "gpt-4o",
            "meta_data": {"gateway": {"model_alias": "openai/gpt-4o"}},
        },
        account_id=test_user.account_id,
    )
    service = ModelGatewayBudgetService(
        db_session,
        ModelGatewayAuthContext(token="override-token", user=test_user),
    )
    monkeypatch.setattr(
        service,
        "_pricing_override_for_request",
        lambda *_args, **_kwargs: {
            "currency": "USD",
            "input_price_per_1k": 1.0,
            "output_price_per_1k": 2.0,
        },
    )

    result = service.preflight_check(
        ai_model,
        {"model": "openai/gpt-4o", "input": "hello", "max_tokens": 1000},
    )

    assert result.pricing_available is True
    assert result.estimated_request_cost_usd == 2.002
