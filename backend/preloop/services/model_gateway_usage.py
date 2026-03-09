"""Reporting service for model gateway usage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from preloop.models.crud import crud_api_usage
from preloop.models.models.account import Account
from preloop.models.models.flow import Flow
from preloop.schemas.gateway_usage import (
    AccountGatewayUsageSummaryResponse,
    FlowGatewayUsageSummaryResponse,
    GatewayBudgetSummary,
    GatewayTokenUsage,
    GatewayUsageByDay,
    GatewayUsageByExecution,
    GatewayUsageByFlow,
    GatewayUsageByModel,
    GatewayUsageBySession,
)


class ModelGatewayUsageService:
    """Build product-facing summaries from gateway usage facts."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_account_summary(
        self,
        *,
        account: Account,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> AccountGatewayUsageSummaryResponse:
        start_date, end_date = self._normalize_period(start_date, end_date)
        totals = crud_api_usage.get_gateway_usage_summary(
            self.db,
            account_id=str(account.id),
            start_date=start_date,
            end_date=end_date,
        )
        usage_by_model = crud_api_usage.get_gateway_usage_by_model(
            self.db,
            account_id=str(account.id),
            start_date=start_date,
            end_date=end_date,
        )
        usage_by_flow = crud_api_usage.get_gateway_usage_by_flow(
            self.db,
            account_id=str(account.id),
            start_date=start_date,
            end_date=end_date,
        )
        usage_by_session = crud_api_usage.get_gateway_usage_by_session(
            self.db,
            account_id=str(account.id),
            start_date=start_date,
            end_date=end_date,
        )
        requests_by_day = crud_api_usage.get_gateway_usage_timeseries(
            self.db,
            account_id=str(account.id),
            start_date=start_date,
            end_date=end_date,
        )

        budget_cfg = self._normalize_budget_config(
            (account.meta_data or {}).get("model_gateway_budget")
        )
        budget = GatewayBudgetSummary(
            monthly_limit_usd=budget_cfg["monthly_usd_limit"],
            soft_limit_usd=budget_cfg["soft_limit_usd"],
            current_spend_usd=totals["estimated_cost"],
            soft_limit_exceeded=(
                budget_cfg["soft_limit_usd"] is not None
                and totals["estimated_cost"] > budget_cfg["soft_limit_usd"]
            ),
            hard_limit_exceeded=(
                budget_cfg["monthly_usd_limit"] is not None
                and totals["estimated_cost"] > budget_cfg["monthly_usd_limit"]
            ),
        )

        return AccountGatewayUsageSummaryResponse(
            period_start=start_date,
            period_end=end_date,
            total_requests=totals["request_count"],
            successful_requests=totals["success_count"],
            failed_requests=totals["error_count"],
            token_usage=GatewayTokenUsage(
                prompt_tokens=totals["prompt_tokens"],
                completion_tokens=totals["completion_tokens"],
                total_tokens=totals["total_tokens"],
            ),
            estimated_cost=totals["estimated_cost"],
            budget=budget,
            requests_by_day=[GatewayUsageByDay(**row) for row in requests_by_day],
            usage_by_model=[self._model_row_to_schema(row) for row in usage_by_model],
            usage_by_flow=[self._flow_row_to_schema(row) for row in usage_by_flow],
            usage_by_session=[
                self._session_row_to_schema(row) for row in usage_by_session
            ],
        )

    def get_flow_summary(
        self,
        *,
        account: Account,
        flow: Flow,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> FlowGatewayUsageSummaryResponse:
        start_date, end_date = self._normalize_period(start_date, end_date)
        totals = crud_api_usage.get_gateway_usage_summary(
            self.db,
            account_id=str(account.id),
            flow_id=str(flow.id),
            start_date=start_date,
            end_date=end_date,
        )
        usage_by_model = crud_api_usage.get_gateway_usage_by_model(
            self.db,
            account_id=str(account.id),
            flow_id=str(flow.id),
            start_date=start_date,
            end_date=end_date,
        )
        usage_by_execution = crud_api_usage.get_gateway_usage_by_execution(
            self.db,
            account_id=str(account.id),
            flow_id=str(flow.id),
            start_date=start_date,
            end_date=end_date,
        )
        budget_cfg = self._normalize_budget_config(
            (flow.agent_config or {}).get("model_gateway_budget")
        )
        budget = GatewayBudgetSummary(
            monthly_limit_usd=budget_cfg["monthly_usd_limit"],
            soft_limit_usd=budget_cfg["soft_limit_usd"],
            current_spend_usd=totals["estimated_cost"],
            soft_limit_exceeded=(
                budget_cfg["soft_limit_usd"] is not None
                and totals["estimated_cost"] > budget_cfg["soft_limit_usd"]
            ),
            hard_limit_exceeded=(
                budget_cfg["monthly_usd_limit"] is not None
                and totals["estimated_cost"] > budget_cfg["monthly_usd_limit"]
            ),
        )

        return FlowGatewayUsageSummaryResponse(
            flow_id=str(flow.id),
            flow_name=flow.name,
            period_start=start_date,
            period_end=end_date,
            total_requests=totals["request_count"],
            successful_requests=totals["success_count"],
            failed_requests=totals["error_count"],
            token_usage=GatewayTokenUsage(
                prompt_tokens=totals["prompt_tokens"],
                completion_tokens=totals["completion_tokens"],
                total_tokens=totals["total_tokens"],
            ),
            estimated_cost=totals["estimated_cost"],
            budget=budget,
            usage_by_model=[self._model_row_to_schema(row) for row in usage_by_model],
            usage_by_execution=[
                GatewayUsageByExecution(
                    flow_execution_id=row["flow_execution_id"],
                    request_count=row["request_count"],
                    token_usage=GatewayTokenUsage(
                        prompt_tokens=row["prompt_tokens"],
                        completion_tokens=row["completion_tokens"],
                        total_tokens=row["total_tokens"],
                    ),
                    estimated_cost=row["estimated_cost"],
                    last_request_at=row["last_request_at"],
                )
                for row in usage_by_execution
            ],
        )

    @staticmethod
    def _normalize_period(
        start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> tuple[datetime, datetime]:
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        elif end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        if start_date is None:
            start_date = end_date - timedelta(days=30)
        elif start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)

        return start_date, end_date

    @staticmethod
    def _normalize_budget_config(config):
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
    def _model_row_to_schema(row) -> GatewayUsageByModel:
        return GatewayUsageByModel(
            ai_model_id=row["ai_model_id"],
            model_alias=row["model_alias"],
            provider_name=row["provider_name"],
            request_count=row["request_count"],
            token_usage=GatewayTokenUsage(
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                total_tokens=row["total_tokens"],
            ),
            estimated_cost=row["estimated_cost"],
        )

    @staticmethod
    def _flow_row_to_schema(row) -> GatewayUsageByFlow:
        return GatewayUsageByFlow(
            flow_id=row["flow_id"],
            flow_name=row["flow_name"],
            request_count=row["request_count"],
            token_usage=GatewayTokenUsage(
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                total_tokens=row["total_tokens"],
            ),
            estimated_cost=row["estimated_cost"],
        )

    @staticmethod
    def _session_row_to_schema(row) -> GatewayUsageBySession:
        return GatewayUsageBySession(
            runtime_session_id=row["runtime_session_id"],
            session_source_type=row["session_source_type"],
            session_source_id=row["session_source_id"],
            flow_execution_id=row["flow_execution_id"],
            flow_id=row["flow_id"],
            flow_name=row["flow_name"],
            session_reference=row["session_reference"],
            model_alias=row["model_alias"],
            provider_name=row["provider_name"],
            request_count=row["request_count"],
            token_usage=GatewayTokenUsage(
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                total_tokens=row["total_tokens"],
            ),
            estimated_cost=row["estimated_cost"],
            last_request_at=row["last_request_at"],
        )
