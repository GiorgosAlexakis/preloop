"""Shared model pricing resolution and cost estimation helpers."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

import litellm

from preloop.models.models.ai_model import AIModel

logger = logging.getLogger(__name__)

_PROVIDER_PREFIX: Dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "gemini",
    "gemini": "gemini",
    "qwen": "openai",
    "deepseek": "deepseek",
}


def estimate_ai_model_usage_cost(
    ai_model: AIModel,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    usage_details: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    """Estimate usage cost using manual pricing overrides or LiteLLM pricing."""
    configured_pricing = _get_configured_pricing(ai_model)
    if configured_pricing:
        return _estimate_cost_from_pricing(
            configured_pricing,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            usage_details=usage_details,
        )

    if prompt_tokens <= 0 and completion_tokens <= 0:
        return None

    for candidate in _iter_litellm_model_candidates(ai_model):
        if usage_details:
            try:
                return round(
                    float(
                        litellm.completion_cost(
                            model=candidate,
                            completion_response={"usage": usage_details},
                        )
                    ),
                    6,
                )
            except Exception:
                logger.debug(
                    "LiteLLM detailed pricing unavailable for model candidate %s",
                    candidate,
                    exc_info=True,
                )
        try:
            prompt_cost, completion_cost = litellm.cost_per_token(
                model=candidate,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            return round(float(prompt_cost or 0.0) + float(completion_cost or 0.0), 6)
        except Exception:
            logger.debug(
                "LiteLLM pricing unavailable for model candidate %s",
                candidate,
                exc_info=True,
            )

    return None


def _get_configured_pricing(ai_model: AIModel) -> Optional[Dict[str, Any]]:
    """Return manually configured pricing metadata when present."""
    pricing = None
    if ai_model.meta_data and isinstance(ai_model.meta_data, dict):
        pricing = ai_model.meta_data.get("pricing")
    if (
        not pricing
        and ai_model.model_parameters
        and isinstance(ai_model.model_parameters, dict)
    ):
        pricing = ai_model.model_parameters.get("pricing")
    return pricing if isinstance(pricing, dict) else None


def _estimate_cost_from_pricing(
    pricing: Dict[str, Any],
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    usage_details: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    """Estimate cost from a normalized pricing configuration."""
    usage_details = usage_details or {}
    prompt_tokens_details = usage_details.get("prompt_tokens_details") or {}
    cached_tokens = int(prompt_tokens_details.get("cached_tokens") or 0)
    cache_creation_tokens = int(
        prompt_tokens_details.get("cache_creation_tokens")
        or usage_details.get("cache_creation_input_tokens")
        or 0
    )
    uncached_prompt_tokens = max(
        prompt_tokens - cached_tokens - cache_creation_tokens, 0
    )

    input_price_per_1k = pricing.get("input_price_per_1k")
    output_price_per_1k = pricing.get("output_price_per_1k")
    if input_price_per_1k is not None or output_price_per_1k is not None:
        input_cost = (uncached_prompt_tokens / 1000.0) * float(input_price_per_1k or 0)
        input_cost += (cached_tokens / 1000.0) * float(
            pricing.get("cache_read_input_price_per_1k") or input_price_per_1k or 0
        )
        input_cost += (cache_creation_tokens / 1000.0) * float(
            pricing.get("cache_creation_input_price_per_1k") or input_price_per_1k or 0
        )
        output_cost = (completion_tokens / 1000.0) * float(output_price_per_1k or 0)
        return round(input_cost + output_cost, 6)

    price_per_1k = pricing.get("price_per_1k")
    if price_per_1k is not None:
        return round((total_tokens / 1000.0) * float(price_per_1k), 6)

    return None


def _iter_litellm_model_candidates(ai_model: AIModel) -> Iterable[str]:
    """Yield likely LiteLLM model names for the configured AI model."""
    provider = (ai_model.provider_name or "openai").strip().lower()
    model_identifier = (ai_model.model_identifier or "").strip()
    meta_data = ai_model.meta_data if isinstance(ai_model.meta_data, dict) else {}
    gateway_config = (
        meta_data.get("gateway") if isinstance(meta_data.get("gateway"), dict) else {}
    )

    candidates = []
    gateway_alias = gateway_config.get("model_alias")
    if isinstance(gateway_alias, str) and gateway_alias.strip():
        candidates.append(gateway_alias.strip())

    if model_identifier:
        candidates.append(model_identifier)
        prefix = _PROVIDER_PREFIX.get(provider, provider)
        if "/" not in model_identifier:
            candidates.append(f"{prefix}/{model_identifier}")

    seen = set()
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        yield normalized
