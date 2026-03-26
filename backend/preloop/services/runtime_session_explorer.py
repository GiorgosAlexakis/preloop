"""Product-facing runtime session explorer service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from preloop.models.crud import (
    crud_api_usage,
    crud_gateway_usage_search_document,
    crud_runtime_session,
    crud_runtime_session_activity,
)
from preloop.models.models.account import Account
from preloop.schemas.gateway_usage import (
    AccountGatewayUsageSearchResponse,
    AccountRuntimeSessionDetailResponse,
    AccountRuntimeSessionListResponse,
    GatewayTokenUsage,
    RuntimeSessionActivityItem,
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
        ai_model_id: Optional[str] = None,
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
            ai_model_id=ai_model_id,
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

        flow_execution_id = summary_row.get("flow_execution_id")
        usage_by_model = crud_api_usage.get_gateway_usage_by_model(
            self.db,
            account_id=str(account.id),
            runtime_session_id=runtime_session_id,
            flow_execution_id=flow_execution_id,
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
            flow_execution_id=flow_execution_id,
            query=interaction_query,
            limit=interaction_limit,
            offset=interaction_offset,
        )
        interaction_items = [
            ModelGatewayUsageService._search_row_to_schema(item)
            for item in interactions["items"]
        ]

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
                items=interaction_items,
            ),
            activity_timeline=self._build_activity_timeline(
                summary_row=summary_row,
                interactions=interaction_items,
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
            is_active_now=row.get("is_active_now", False),
            activity_status=row.get("activity_status", "idle"),
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

    def _build_activity_timeline(
        self,
        *,
        summary_row: dict,
        interactions,
    ) -> list[RuntimeSessionActivityItem]:
        items: list[RuntimeSessionActivityItem] = []

        started_at = summary_row.get("started_at")
        if started_at is not None:
            items.append(
                RuntimeSessionActivityItem(
                    activity_type="session_started",
                    timestamp=self._normalize_timestamp(started_at),
                    title="Session started",
                    summary=summary_row.get("session_reference")
                    or summary_row.get("runtime_principal_name")
                    or summary_row.get("session_source_id"),
                    status="info",
                )
            )

        items.extend(
            RuntimeSessionActivityItem(
                activity_type="model_interaction",
                timestamp=self._normalize_timestamp(interaction.timestamp),
                title=interaction.model_alias or "Model interaction",
                summary=f"{interaction.method} {interaction.endpoint}",
                status=interaction.outcome,
                api_usage_id=interaction.api_usage_id,
                auth_subject_type=interaction.auth_subject_type,
                api_key_id=interaction.api_key_id,
                api_key_name=interaction.api_key_name,
                estimated_cost=interaction.estimated_cost,
                total_tokens=interaction.token_usage.total_tokens,
            )
            for interaction in interactions
        )

        activity_rows = crud_runtime_session_activity.list_for_runtime_session(
            self.db,
            account_id=summary_row["account_id"],
            runtime_session_id=summary_row["id"],
            limit=100,
        )
        if activity_rows:
            items.extend(
                RuntimeSessionActivityItem(
                    activity_type=activity.activity_type,
                    timestamp=self._normalize_timestamp(activity.timestamp),
                    title=activity.tool_name or "Tool call",
                    summary=activity.summary or activity.server_name,
                    status=activity.status,
                    tool_name=activity.tool_name,
                    server_name=activity.server_name,
                    api_key_id=str(activity.api_key_id)
                    if activity.api_key_id
                    else None,
                )
                for activity in activity_rows
            )

        flow_execution_id = summary_row.get("flow_execution_id")
        if flow_execution_id and not activity_rows:
            from preloop.models.crud.flow_execution import CRUDFlowExecution

            crud_flow_execution = CRUDFlowExecution()
            execution = crud_flow_execution.get(self.db, id=UUID(flow_execution_id))
            if execution and isinstance(execution.mcp_usage_logs, list):
                for log in execution.mcp_usage_logs:
                    timestamp = self._parse_timestamp(log.get("timestamp"))
                    if timestamp is None:
                        continue
                    items.append(
                        RuntimeSessionActivityItem(
                            activity_type="tool_call",
                            timestamp=self._normalize_timestamp(timestamp),
                            title=log.get("tool_name") or "Tool call",
                            summary=log.get("result_summary")
                            or log.get("error")
                            or log.get("server_name"),
                            status=log.get("status"),
                            tool_name=log.get("tool_name"),
                            server_name=log.get("server_name"),
                        )
                    )

        ended_at = summary_row.get("ended_at")
        if ended_at is not None:
            items.append(
                RuntimeSessionActivityItem(
                    activity_type="session_ended",
                    timestamp=self._normalize_timestamp(ended_at),
                    title="Session ended",
                    summary=summary_row.get("session_reference")
                    or summary_row.get("runtime_principal_name")
                    or summary_row.get("session_source_id"),
                    status="completed",
                )
            )

        return sorted(items, key=lambda item: item.timestamp, reverse=True)

    @staticmethod
    def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
