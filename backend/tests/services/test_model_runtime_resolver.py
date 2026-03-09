"""Tests for model runtime resolution."""

from sqlalchemy.orm import Session

from preloop.models.crud import crud_account, crud_ai_model
from preloop.services.model_runtime_resolver import resolve_ai_model_runtime


def test_resolve_ai_model_runtime_for_gateway_enabled_model(db_session: Session):
    """Gateway-enabled models should resolve to gateway fields only."""
    account = crud_account.create(
        db_session,
        obj_in={
            "organization_name": "Gateway Runtime Resolver Org",
            "is_active": True,
        },
    )
    ai_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Gateway Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5",
            "api_key": "provider-secret",
            "meta_data": {
                "gateway": {
                    "enabled": True,
                    "url": "http://gateway.internal/openai/v1",
                    "model_alias": "openai/gpt-5",
                    "provider_adapter": "preloop",
                }
            },
        },
        account_id=account.id,
    )

    resolved = resolve_ai_model_runtime(ai_model)

    assert resolved.model_gateway_enabled is True
    assert resolved.model_transport_mode == "preloop_gateway"
    assert resolved.model_identifier == "openai/gpt-5"
    assert resolved.model_provider == "preloop"
    assert resolved.model_endpoint == "http://gateway.internal/openai/v1"
    assert resolved.model_api_key is None


def test_resolve_ai_model_runtime_for_direct_provider_model(db_session: Session):
    """Direct-provider models should still resolve a provider API key."""
    account = crud_account.create(
        db_session,
        obj_in={
            "organization_name": "Direct Runtime Resolver Org",
            "is_active": True,
        },
    )
    ai_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Direct Model",
            "provider_name": "anthropic",
            "model_identifier": "claude-sonnet-4-5",
            "api_endpoint": "https://api.anthropic.com/v1",
            "api_key": "provider-secret",
        },
        account_id=account.id,
    )

    resolved = resolve_ai_model_runtime(ai_model)

    assert resolved.model_gateway_enabled is False
    assert resolved.model_transport_mode == "direct_provider"
    assert resolved.model_identifier == "claude-sonnet-4-5"
    assert resolved.model_provider == "anthropic"
    assert resolved.model_endpoint == "https://api.anthropic.com/v1"
    assert resolved.model_api_key == "provider-secret"
