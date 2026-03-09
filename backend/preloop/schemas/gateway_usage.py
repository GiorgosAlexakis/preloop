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
