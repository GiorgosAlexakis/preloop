"""Budget checks for model gateway requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from preloop.models.models.account import Account
from preloop.models.models.ai_model import AIModel
from preloop.models.models.api_usage import ApiUsage
from preloop.models.models.flow import Flow
from preloop.services.model_gateway_auth import ModelGatewayAuthContext
from preloop.services.model_pricing import estimate_ai_model_usage_cost


DEFAULT_ESTIMATED_OUTPUT_TOKENS = 1024


@dataclass
class BudgetCheckResult:
    """Outcome of a gateway budget check."""

    account_limit_usd: Optional[float]
    account_soft_limit_usd: Optional[float]
    account_current_spend_usd: float
    account_estimated_total_usd: Optional[float]
    flow_limit_usd: Optional[float]
    flow_soft_limit_usd: Optional[float]
    flow_current_spend_usd: float
    flow_estimated_total_usd: Optional[float]
    estimated_request_cost_usd: Optional[float]
    hard_limit_exceeded: bool
    soft_limit_exceeded: bool
    enforcement_reason: Optional[str]
    pricing_available: bool


class ModelGatewayBudgetService:
    """Budget checks and reconciliation for model gateway requests."""

    def __init__(self, db: Session, auth_context: ModelGatewayAuthContext) -> None:
        self.db = db
        self.auth_context = auth_context

    def preflight_check(
        self, ai_model: AIModel, payload: Dict[str, Any]
    ) -> BudgetCheckResult:
        """Check whether a gateway request can proceed within configured budgets."""
        account = (
            self.db.query(Account)
            .filter(Account.id == self.auth_context.user.account_id)
            .first()
        )
        runtime_context = (
            (self.auth_context.api_key.context_data or {})
            if self.auth_context.api_key
            else {}
        )
        flow = self._get_flow(runtime_context.get("flow_id"))

        account_budget = self._normalize_budget_config(
            (account.meta_data or {}).get("model_gateway_budget") if account else None
        )
        flow_budget = self._normalize_budget_config(
            (flow.agent_config or {}).get("model_gateway_budget") if flow else None
        )

        start = self._current_period_start()
        account_spend = self._get_gateway_spend(
            account_id=str(self.auth_context.user.account_id), start=start
        )
        flow_spend = (
            self._get_gateway_spend(
                account_id=str(self.auth_context.user.account_id),
                flow_id=str(flow.id),
                start=start,
            )
            if flow
            else 0.0
        )

        estimated_request_cost = self._estimate_request_cost(ai_model, payload)
        pricing_available = estimated_request_cost is not None
        account_estimated_total = (
            account_spend + estimated_request_cost
            if estimated_request_cost is not None
            else None
        )
        flow_estimated_total = (
            flow_spend + estimated_request_cost
            if flow and estimated_request_cost is not None
            else None
        )

        account_limit = account_budget.get("monthly_usd_limit")
        account_soft_limit = account_budget.get("soft_limit_usd")
        flow_limit = flow_budget.get("monthly_usd_limit")
        flow_soft_limit = flow_budget.get("soft_limit_usd")
        budget_configured = any(
            limit is not None
            for limit in (
                account_limit,
                account_soft_limit,
                flow_limit,
                flow_soft_limit,
            )
        )

        hard_limit_exceeded = False
        soft_limit_exceeded = False
        enforcement_reason = None

        if budget_configured and not pricing_available:
            hard_limit_exceeded = True
            enforcement_reason = "pricing_required_for_budget_enforcement"
        elif pricing_available:
            if (
                account_limit is not None
                and account_estimated_total is not None
                and account_estimated_total > account_limit
            ):
                hard_limit_exceeded = True
                enforcement_reason = "account_budget_exceeded"
            elif (
                flow_limit is not None
                and flow_estimated_total is not None
                and flow_estimated_total > flow_limit
            ):
                hard_limit_exceeded = True
                enforcement_reason = "flow_budget_exceeded"
            elif (
                account_soft_limit is not None
                and account_estimated_total is not None
                and account_estimated_total > account_soft_limit
            ):
                soft_limit_exceeded = True
                enforcement_reason = "account_soft_limit_exceeded"
            elif (
                flow_soft_limit is not None
                and flow_estimated_total is not None
                and flow_estimated_total > flow_soft_limit
            ):
                soft_limit_exceeded = True
                enforcement_reason = "flow_soft_limit_exceeded"

        return BudgetCheckResult(
            account_limit_usd=account_limit,
            account_soft_limit_usd=account_soft_limit,
            account_current_spend_usd=account_spend,
            account_estimated_total_usd=account_estimated_total,
            flow_limit_usd=flow_limit,
            flow_soft_limit_usd=flow_soft_limit,
            flow_current_spend_usd=flow_spend,
            flow_estimated_total_usd=flow_estimated_total,
            estimated_request_cost_usd=estimated_request_cost,
            hard_limit_exceeded=hard_limit_exceeded,
            soft_limit_exceeded=soft_limit_exceeded,
            enforcement_reason=enforcement_reason,
            pricing_available=pricing_available,
        )

    def enforce_or_raise(
        self, ai_model: AIModel, payload: Dict[str, Any]
    ) -> BudgetCheckResult:
        """Run the preflight check and raise if a hard limit is exceeded."""
        result = self.preflight_check(ai_model, payload)
        if result.hard_limit_exceeded:
            detail = "Model gateway budget exceeded"
            if result.enforcement_reason == "account_budget_exceeded":
                detail = "Model gateway budget exceeded: account monthly limit reached"
            elif result.enforcement_reason == "flow_budget_exceeded":
                detail = "Model gateway budget exceeded: flow monthly limit reached"
            elif result.enforcement_reason == "pricing_required_for_budget_enforcement":
                detail = (
                    "Model gateway budget enforcement requires pricing information for "
                    "the selected gateway model"
                )
            raise HTTPException(status_code=403, detail=detail)
        return result

    def _get_gateway_spend(
        self, *, account_id: str, start: datetime, flow_id: Optional[str] = None
    ) -> float:
        query = self.db.query(
            func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0)
        ).filter(
            ApiUsage.action_type == "model_gateway",
            ApiUsage.account_id == account_id,
            ApiUsage.timestamp >= start,
        )
        if flow_id:
            query = query.filter(ApiUsage.flow_id == flow_id)
        return float(query.scalar() or 0.0)

    @staticmethod
    def _normalize_budget_config(
        config: Optional[Dict[str, Any]],
    ) -> Dict[str, Optional[float]]:
        config = config or {}
        monthly_limit = config.get("monthly_usd_limit")
        soft_limit = config.get("soft_limit_usd")
        if (
            soft_limit is None
            and monthly_limit is not None
            and config.get("soft_limit_ratio") is not None
        ):
            soft_limit = float(monthly_limit) * float(config["soft_limit_ratio"])
        return {
            "monthly_usd_limit": float(monthly_limit)
            if monthly_limit is not None
            else None,
            "soft_limit_usd": float(soft_limit) if soft_limit is not None else None,
        }

    @staticmethod
    def _current_period_start() -> datetime:
        now = datetime.now(timezone.utc)
        return datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    def _get_flow(self, flow_id: Optional[str]) -> Optional[Flow]:
        if not flow_id:
            return None
        return self.db.query(Flow).filter(Flow.id == flow_id).first()

    @staticmethod
    def _estimate_request_cost(
        ai_model: AIModel, payload: Dict[str, Any]
    ) -> Optional[float]:
        estimated_input_tokens = ModelGatewayBudgetService._estimate_input_tokens(
            payload
        )
        estimated_output_tokens = int(
            payload.get("max_completion_tokens")
            or payload.get("max_output_tokens")
            or payload.get("max_tokens")
            or DEFAULT_ESTIMATED_OUTPUT_TOKENS
        )
        return estimate_ai_model_usage_cost(
            ai_model,
            prompt_tokens=estimated_input_tokens,
            completion_tokens=estimated_output_tokens,
            total_tokens=estimated_input_tokens + estimated_output_tokens,
        )

    @staticmethod
    def _estimate_input_tokens(payload: Dict[str, Any]) -> int:
        text_parts = []
        if isinstance(payload.get("messages"), list):
            for message in payload["messages"]:
                if isinstance(message, dict):
                    text_parts.append(
                        ModelGatewayBudgetService._content_to_text(
                            message.get("content", "")
                        )
                    )
        if payload.get("instructions"):
            text_parts.append(str(payload["instructions"]))
        raw_input = payload.get("input")
        if isinstance(raw_input, str):
            text_parts.append(raw_input)
        elif isinstance(raw_input, list):
            for item in raw_input:
                if isinstance(item, dict):
                    text_parts.append(
                        ModelGatewayBudgetService._content_to_text(
                            item.get("content", "")
                        )
                    )
        total_chars = sum(len(part) for part in text_parts if part)
        return max(1, math.ceil(total_chars / 4)) if total_chars else 0

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {
                    "input_text",
                    "text",
                    "output_text",
                }:
                    texts.append(item.get("text", ""))
            return "\n".join(filter(None, texts))
        return str(content)
