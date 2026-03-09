"""Schemas for model gateway usage summaries."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class GatewayTokenUsage(BaseModel):
    """Token usage totals."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class GatewayBudgetSummary(BaseModel):
    """Budget snapshot for gateway usage."""

    monthly_limit_usd: Optional[float] = None
    soft_limit_usd: Optional[float] = None
    current_spend_usd: float = 0.0
    soft_limit_exceeded: bool = False
    hard_limit_exceeded: bool = False


class GatewayUsageByDay(BaseModel):
    """Daily usage aggregate."""

    date: str
    request_count: int = 0
    estimated_cost: float = 0.0
    total_tokens: int = 0


class GatewayUsageByModel(BaseModel):
    """Usage aggregate grouped by model."""

    ai_model_id: Optional[str] = None
    model_alias: Optional[str] = None
    provider_name: Optional[str] = None
    request_count: int = 0
    token_usage: GatewayTokenUsage
    estimated_cost: float = 0.0


class GatewayUsageByFlow(BaseModel):
    """Usage aggregate grouped by flow."""

    flow_id: Optional[str] = None
    flow_name: Optional[str] = None
    request_count: int = 0
    token_usage: GatewayTokenUsage
    estimated_cost: float = 0.0


class GatewayUsageByExecution(BaseModel):
    """Usage aggregate grouped by flow execution."""

    flow_execution_id: Optional[str] = None
    request_count: int = 0
    token_usage: GatewayTokenUsage
    estimated_cost: float = 0.0
    last_request_at: Optional[datetime] = None


class GatewayUsageBySession(BaseModel):
    """Recent usage aggregate grouped by execution-backed session slices."""

    runtime_session_id: Optional[str] = None
    session_source_type: Optional[str] = None
    session_source_id: Optional[str] = None
    flow_execution_id: Optional[str] = None
    flow_id: Optional[str] = None
    flow_name: Optional[str] = None
    session_reference: Optional[str] = None
    model_alias: Optional[str] = None
    provider_name: Optional[str] = None
    request_count: int = 0
    token_usage: GatewayTokenUsage
    estimated_cost: float = 0.0
    last_request_at: Optional[datetime] = None


class GatewayUsageSearchResultItem(BaseModel):
    """One account-scoped gateway interaction search hit."""

    api_usage_id: str
    timestamp: datetime
    status_code: int
    outcome: str
    endpoint: str
    method: str
    provider_name: Optional[str] = None
    model_alias: Optional[str] = None
    flow_id: Optional[str] = None
    flow_name: Optional[str] = None
    flow_execution_id: Optional[str] = None
    runtime_session_id: Optional[str] = None
    session_source_type: Optional[str] = None
    session_source_id: Optional[str] = None
    session_reference: Optional[str] = None
    runtime_principal_type: Optional[str] = None
    runtime_principal_id: Optional[str] = None
    runtime_principal_name: Optional[str] = None
    estimated_cost: float = 0.0
    token_usage: GatewayTokenUsage
    excerpt: str
    meta_data: dict = Field(default_factory=dict)


class AccountGatewayUsageSearchResponse(BaseModel):
    """Account-scoped gateway interaction search results."""

    period_start: datetime
    period_end: datetime
    query: Optional[str] = None
    total: int = 0
    limit: int = 20
    offset: int = 0
    items: List[GatewayUsageSearchResultItem] = Field(default_factory=list)


class RuntimeSessionSummary(BaseModel):
    """Aggregated runtime session summary for explorer views."""

    id: str
    session_source_type: str
    session_source_id: str
    session_reference: Optional[str] = None
    runtime_principal_type: Optional[str] = None
    runtime_principal_id: Optional[str] = None
    runtime_principal_name: Optional[str] = None
    started_at: datetime
    last_activity_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    flow_id: Optional[str] = None
    flow_name: Optional[str] = None
    flow_execution_id: Optional[str] = None
    latest_model_alias: Optional[str] = None
    latest_provider_name: Optional[str] = None
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    token_usage: GatewayTokenUsage
    estimated_cost: float = 0.0
    last_request_at: Optional[datetime] = None


class AccountRuntimeSessionListResponse(BaseModel):
    """Account-scoped runtime session explorer list response."""

    period_start: datetime
    period_end: datetime
    query: Optional[str] = None
    session_source_type: Optional[str] = None
    status: str = "all"
    total: int = 0
    limit: int = 20
    offset: int = 0
    items: List[RuntimeSessionSummary] = Field(default_factory=list)


class AccountRuntimeSessionDetailResponse(BaseModel):
    """One runtime session plus captured interaction timeline."""

    period_start: datetime
    period_end: datetime
    session: RuntimeSessionSummary
    usage_by_model: List[GatewayUsageByModel] = Field(default_factory=list)
    interactions: AccountGatewayUsageSearchResponse


class AccountGatewayUsageSummaryResponse(BaseModel):
    """Account-scoped gateway usage summary."""

    period_start: datetime
    period_end: datetime
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    token_usage: GatewayTokenUsage
    estimated_cost: float = 0.0
    budget: GatewayBudgetSummary
    requests_by_day: List[GatewayUsageByDay] = Field(default_factory=list)
    usage_by_model: List[GatewayUsageByModel] = Field(default_factory=list)
    usage_by_flow: List[GatewayUsageByFlow] = Field(default_factory=list)
    usage_by_session: List[GatewayUsageBySession] = Field(default_factory=list)


class FlowGatewayUsageSummaryResponse(BaseModel):
    """Flow-scoped gateway usage summary."""

    flow_id: str
    flow_name: Optional[str] = None
    period_start: datetime
    period_end: datetime
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    token_usage: GatewayTokenUsage
    estimated_cost: float = 0.0
    budget: GatewayBudgetSummary
    usage_by_model: List[GatewayUsageByModel] = Field(default_factory=list)
    usage_by_execution: List[GatewayUsageByExecution] = Field(default_factory=list)
