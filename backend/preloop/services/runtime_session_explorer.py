"""Product-facing runtime session explorer service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from preloop.models.crud import (
    crud_api_usage,
    crud_gateway_usage_search_document,
    crud_runtime_session,
)
from preloop.models.models.account import Account
from preloop.schemas.gateway_usage import (
    AccountGatewayUsageSearchResponse,
    AccountRuntimeSessionDetailResponse,
    AccountRuntimeSessionListResponse,
    GatewayTokenUsage,
    RuntimeSessionSummary,
)
from preloop.services.model_gateway_usage import ModelGatewayUsageService


class RuntimeSessionExplorerService:
    """Build runtime session explorer responses."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_account_sessions(
        self,
        *,
        account: Account,
        query: Optional[str] = None,
        session_source_type: Optional[str] = None,
        status: str = "all",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> AccountRuntimeSessionListResponse:
        start_date, end_date = self._normalize_period(start_date, end_date)
        results = crud_runtime_session.list_account_sessions(
            self.db,
            account_id=str(account.id),
            start_date=start_date,
            end_date=end_date,
            query=query,
            session_source_type=session_source_type,
            status=status,
            limit=limit,
            offset=offset,
        )
        return AccountRuntimeSessionListResponse(
            period_start=start_date,
            period_end=end_date,
            query=query,
            session_source_type=session_source_type,
            status=status,
            total=results["total"],
            limit=limit,
            offset=offset,
            items=[self._summary_row_to_schema(item) for item in results["items"]],
        )

    def get_account_session_detail(
        self,
        *,
        account: Account,
        runtime_session_id: str,
        interaction_query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        interaction_limit: int = 50,
        interaction_offset: int = 0,
    ) -> AccountRuntimeSessionDetailResponse:
        start_date, end_date = self._normalize_period(start_date, end_date)
        summary_row = crud_runtime_session.get_account_session_summary(
            self.db,
            account_id=str(account.id),
            runtime_session_id=runtime_session_id,
            start_date=start_date,
            end_date=end_date,
        )
        if summary_row is None:
            raise HTTPException(status_code=404, detail="Runtime session not found")

        usage_by_model = crud_api_usage.get_gateway_usage_by_model(
            self.db,
            account_id=str(account.id),
            runtime_session_id=runtime_session_id,
            start_date=start_date,
            end_date=end_date,
            limit=20,
        )
        interactions = crud_gateway_usage_search_document.search_account_documents(
            self.db,
            account_id=str(account.id),
            start_date=start_date,
            end_date=end_date,
            runtime_session_id=runtime_session_id,
            query=interaction_query,
            limit=interaction_limit,
            offset=interaction_offset,
        )

        return AccountRuntimeSessionDetailResponse(
            period_start=start_date,
            period_end=end_date,
            session=self._summary_row_to_schema(summary_row),
            usage_by_model=[
                ModelGatewayUsageService._model_row_to_schema(row)
                for row in usage_by_model
            ],
            interactions=AccountGatewayUsageSearchResponse(
                period_start=start_date,
                period_end=end_date,
                query=interaction_query,
                total=interactions["total"],
                limit=interaction_limit,
                offset=interaction_offset,
                items=[
                    ModelGatewayUsageService._search_row_to_schema(item)
                    for item in interactions["items"]
                ],
            ),
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
    def _summary_row_to_schema(row: dict) -> RuntimeSessionSummary:
        return RuntimeSessionSummary(
            id=row["id"],
            session_source_type=row["session_source_type"],
            session_source_id=row["session_source_id"],
            session_reference=row["session_reference"],
            runtime_principal_type=row["runtime_principal_type"],
            runtime_principal_id=row["runtime_principal_id"],
            runtime_principal_name=row["runtime_principal_name"],
            started_at=row["started_at"],
            last_activity_at=row["last_activity_at"],
            ended_at=row["ended_at"],
            flow_id=row["flow_id"],
            flow_name=row["flow_name"],
            flow_execution_id=row["flow_execution_id"],
            latest_model_alias=row["latest_model_alias"],
            latest_provider_name=row["latest_provider_name"],
            total_requests=row["total_requests"],
            successful_requests=row["successful_requests"],
            failed_requests=row["failed_requests"],
            token_usage=GatewayTokenUsage(
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                total_tokens=row["total_tokens"],
            ),
            estimated_cost=row["estimated_cost"],
            last_request_at=row["last_request_at"],
        )
