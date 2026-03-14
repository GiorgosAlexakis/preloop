from sqlalchemy.orm import Session

from preloop.models.crud import crud_account, crud_ai_model
from scripts.init_db import (
    _build_gateway_url,
    _merge_gateway_meta,
    reconcile_ai_model_gateway_settings,
)


def test_build_gateway_url_uses_public_preloop_base_url():
    assert (
        _build_gateway_url("https://review.preloop.ai/")
        == "https://review.preloop.ai/openai/v1"
    )


def test_merge_gateway_meta_preserves_existing_metadata():
    meta_data = {
        "label": "review",
        "gateway": {
            "model_alias": "custom/openai-gpt5",
        },
    }

    merged = _merge_gateway_meta(
        meta_data,
        provider_name="openai",
        model_identifier="gpt-5.4",
        gateway_url="https://review.preloop.ai/openai/v1",
    )

    assert merged["label"] == "review"
    assert merged["gateway"]["enabled"] is True
    assert merged["gateway"]["url"] == "https://review.preloop.ai/openai/v1"
    assert merged["gateway"]["provider_adapter"] == "preloop"
    assert merged["gateway"]["model_alias"] == "custom/openai-gpt5"


def test_reconcile_ai_model_gateway_settings_updates_credentialed_models(
    db_session: Session,
):
    account = crud_account.create(
        db_session,
        obj_in={
            "organization_name": "Gateway Bootstrap Org",
            "is_active": True,
        },
    )

    system_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "System Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5.4",
            "api_key": "system-secret",
            "is_default": True,
        },
        account_id=None,
    )
    account_model = crud_ai_model.create_with_account(
        db=db_session,
        obj_in={
            "name": "Account Model",
            "provider_name": "openai",
            "model_identifier": "gpt-5.4",
            "api_key": "account-secret",
            "meta_data": {"owner": "review"},
        },
        account_id=account.id,
    )

    updated_count = reconcile_ai_model_gateway_settings(
        db_session,
        gateway_url="https://review.preloop.ai/openai/v1",
    )

    db_session.refresh(system_model)
    db_session.refresh(account_model)

    assert updated_count >= 2
    assert system_model.meta_data["gateway"]["enabled"] is True
    assert (
        system_model.meta_data["gateway"]["url"]
        == "https://review.preloop.ai/openai/v1"
    )
    assert system_model.meta_data["gateway"]["model_alias"] == "openai/gpt-5.4"
    assert account_model.meta_data["owner"] == "review"
    assert account_model.meta_data["gateway"]["enabled"] is True
    assert (
        account_model.meta_data["gateway"]["url"]
        == "https://review.preloop.ai/openai/v1"
    )
