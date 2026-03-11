"""CRUD operations for durable managed-agent registry entries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from ..models.api_usage import ApiUsage
from ..models.managed_agent import ManagedAgent
from ..models.runtime_session import RuntimeSession
from ..models.user import User
from .base import CRUDBase

MANAGED_AGENT_ACTIVE_WINDOW = timedelta(minutes=10)


def _utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware timestamp."""
    return datetime.now(UTC)


def _coerce_utc(timestamp: Optional[datetime]) -> Optional[datetime]:
    """Normalize stored timestamps so freshness checks can compare safely."""
    if timestamp is None:
        return None
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


class CRUDManagedAgent(CRUDBase[ManagedAgent]):
    """CRUD helpers for account-scoped managed-agent registry entries."""

    def get_by_source(
        self,
        db: Session,
        *,
        account_id: str,
        session_source_type: str,
        session_source_id: str,
    ) -> Optional[ManagedAgent]:
        """Look up one agent by its durable source identity."""
        return (
            db.query(self.model)
            .filter(
                self.model.account_id == account_id,
                self.model.session_source_type == session_source_type,
                self.model.session_source_id == session_source_id,
            )
            .first()
        )

    def get_for_account(
        self, db: Session, *, account_id: str, agent_id: str
    ) -> Optional[ManagedAgent]:
        """Return one managed agent scoped to the given account."""
        return (
            db.query(self.model)
            .filter(self.model.account_id == account_id, self.model.id == agent_id)
            .first()
        )

    def touch_last_seen_for_principal(
        self,
        db: Session,
        *,
        account_id: Any,
        session_source_type: str,
        session_source_id: str,
        runtime_session_id: Optional[Any] = None,
        observed_at: datetime,
        commit: bool = False,
    ) -> Optional[ManagedAgent]:
        """Update last-seen timestamp for one durable managed agent."""
        db_obj = self.get_by_source(
            db,
            account_id=str(account_id),
            session_source_type=session_source_type,
            session_source_id=session_source_id,
        )
        if db_obj is None:
            return None
        db_obj.last_seen_at = observed_at
        if runtime_session_id is not None:
            db_obj.runtime_session_id = runtime_session_id
        db.add(db_obj)
        if commit:
            db.commit()
            db.refresh(db_obj)
        else:
            db.flush()
        return db_obj

    def update_operator_state(
        self,
        db: Session,
        *,
        account_id: str,
        agent_id: str,
        owner_user_id: Any = None,
        set_owner: bool = False,
        lifecycle_state: Optional[str] = None,
        lifecycle_reason: Optional[str] = None,
        commit: bool = True,
    ) -> Optional[ManagedAgent]:
        """Update ownership and lifecycle controls for one managed agent."""
        db_obj = self.get_for_account(db, account_id=account_id, agent_id=agent_id)
        if db_obj is None:
            return None
        now = _utc_now()
        if set_owner:
            db_obj.owner_user_id = owner_user_id
        if lifecycle_state is not None:
            db_obj.lifecycle_state = lifecycle_state
            db_obj.lifecycle_reason = lifecycle_reason
            db_obj.lifecycle_updated_at = now
            if lifecycle_state == "decommissioned":
                db_obj.runtime_session_id = None
        db.add(db_obj)
        if commit:
            db.commit()
            db.refresh(db_obj)
        else:
            db.flush()
        return db_obj

    def clear_runtime_session_binding(
        self,
        db: Session,
        *,
        account_id: str,
        session_source_type: str,
        session_source_id: str,
        runtime_session_id: Optional[Any] = None,
        commit: bool = False,
    ) -> Optional[ManagedAgent]:
        """Clear the active runtime-session binding for one managed agent."""
        db_obj = self.get_by_source(
            db,
            account_id=account_id,
            session_source_type=session_source_type,
            session_source_id=session_source_id,
        )
        if db_obj is None:
            return None
        if runtime_session_id is not None and str(db_obj.runtime_session_id) != str(
            runtime_session_id
        ):
            return db_obj
        db_obj.runtime_session_id = None
        db.add(db_obj)
        if commit:
            db.commit()
            db.refresh(db_obj)
        else:
            db.flush()
        return db_obj

    def upsert_from_runtime_session(
        self,
        db: Session,
        *,
        account_id: Any,
        runtime_session_id: Any,
        session_source_type: str,
        session_source_id: str,
        display_name: str,
        session_reference: Optional[str] = None,
        managed_mcp_servers: Optional[list[str]] = None,
        enrolled_via: str = "runtime_session_token",
        last_seen_at: Optional[datetime] = None,
    ) -> ManagedAgent:
        """Create or update one registry entry from a runtime-session token flow."""
        db_obj = self.get_by_source(
            db,
            account_id=str(account_id),
            session_source_type=session_source_type,
            session_source_id=session_source_id,
        )
        normalized_servers = list(dict.fromkeys(managed_mcp_servers or []))
        observed_at = last_seen_at or _utc_now()

        if db_obj is None:
            db_obj = ManagedAgent(
                account_id=account_id,
                runtime_session_id=runtime_session_id,
                session_source_type=session_source_type,
                session_source_id=session_source_id,
                session_reference=session_reference,
                display_name=display_name,
                enrolled_via=enrolled_via,
                managed_mcp_servers=normalized_servers,
                lifecycle_state="active",
                lifecycle_reason=None,
                lifecycle_updated_at=observed_at,
                last_seen_at=observed_at,
            )
            db.add(db_obj)
            db.flush()
            return db_obj

        db_obj.runtime_session_id = runtime_session_id
        db_obj.display_name = display_name
        db_obj.enrolled_via = enrolled_via
        db_obj.last_seen_at = observed_at
        if db_obj.lifecycle_state in {"suspended", "decommissioned"}:
            db_obj.lifecycle_state = "active"
            db_obj.lifecycle_reason = None
            db_obj.lifecycle_updated_at = observed_at
        if session_reference is not None:
            db_obj.session_reference = session_reference
        db_obj.managed_mcp_servers = normalized_servers
        db.add(db_obj)
        db.flush()
        return db_obj

    def list_for_account(
        self,
        db: Session,
        *,
        account_id: str,
        query: Optional[str] = None,
        session_source_type: Optional[str] = None,
        status: str = "all",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List managed agents with runtime-session and gateway usage summary."""
        base_query = (
            db.query(self.model)
            .outerjoin(
                RuntimeSession, self.model.runtime_session_id == RuntimeSession.id
            )
            .outerjoin(User, self.model.owner_user_id == User.id)
        )
        base_query = base_query.filter(self.model.account_id == account_id)

        if query:
            normalized_query = f"%{' '.join(query.strip().split())}%"
            base_query = base_query.filter(
                or_(
                    self.model.display_name.ilike(normalized_query),
                    self.model.session_source_type.ilike(normalized_query),
                    self.model.session_source_id.ilike(normalized_query),
                    self.model.session_reference.ilike(normalized_query),
                )
            )
        if session_source_type:
            base_query = base_query.filter(
                self.model.session_source_type == session_source_type
            )
        if status == "active":
            base_query = base_query.filter(
                self.model.lifecycle_state == "active",
                RuntimeSession.id.isnot(None),
                RuntimeSession.ended_at.is_(None),
            )
        elif status == "ended":
            base_query = base_query.filter(
                or_(
                    RuntimeSession.ended_at.isnot(None),
                    self.model.lifecycle_state.in_(["suspended", "decommissioned"]),
                )
            )

        total = base_query.count()

        rows = (
            base_query.outerjoin(
                ApiUsage,
                and_(
                    ApiUsage.runtime_session_id == self.model.runtime_session_id,
                    ApiUsage.action_type == "model_gateway",
                ),
            )
            .with_entities(
                self.model.id,
                self.model.runtime_session_id,
                self.model.owner_user_id,
                self.model.display_name,
                self.model.session_source_type,
                self.model.session_source_id,
                self.model.session_reference,
                self.model.enrolled_via,
                self.model.managed_mcp_servers,
                self.model.lifecycle_state,
                self.model.lifecycle_reason,
                self.model.lifecycle_updated_at,
                self.model.last_seen_at,
                User.username.label("owner_username"),
                User.email.label("owner_email"),
                RuntimeSession.started_at,
                RuntimeSession.last_activity_at,
                RuntimeSession.ended_at,
                func.count(ApiUsage.id).label("request_count"),
                func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0).label(
                    "estimated_cost"
                ),
                func.max(ApiUsage.model_alias).label("latest_model_alias"),
                func.max(ApiUsage.provider_name).label("latest_provider_name"),
                func.max(ApiUsage.timestamp).label("last_request_at"),
            )
            .group_by(
                self.model.id,
                self.model.runtime_session_id,
                self.model.owner_user_id,
                self.model.display_name,
                self.model.session_source_type,
                self.model.session_source_id,
                self.model.session_reference,
                self.model.enrolled_via,
                self.model.managed_mcp_servers,
                self.model.lifecycle_state,
                self.model.lifecycle_reason,
                self.model.lifecycle_updated_at,
                self.model.last_seen_at,
                User.username,
                User.email,
                RuntimeSession.started_at,
                RuntimeSession.last_activity_at,
                RuntimeSession.ended_at,
            )
            .order_by(
                func.coalesce(
                    func.max(ApiUsage.timestamp),
                    RuntimeSession.last_activity_at,
                    self.model.last_seen_at,
                    self.model.created_at,
                ).desc()
            )
            .limit(limit)
            .offset(offset)
            .all()
        )

        return {"total": total, "items": [self._row_to_summary(row) for row in rows]}

    def get_summary_for_account(
        self, db: Session, *, account_id: str, agent_id: str
    ) -> Optional[dict[str, Any]]:
        """Return one managed agent summary with runtime and usage aggregates."""
        row = (
            db.query(self.model)
            .outerjoin(
                RuntimeSession, self.model.runtime_session_id == RuntimeSession.id
            )
            .outerjoin(User, self.model.owner_user_id == User.id)
            .outerjoin(
                ApiUsage,
                and_(
                    ApiUsage.runtime_session_id == self.model.runtime_session_id,
                    ApiUsage.action_type == "model_gateway",
                ),
            )
            .filter(self.model.account_id == account_id, self.model.id == agent_id)
            .with_entities(
                self.model.id,
                self.model.runtime_session_id,
                self.model.owner_user_id,
                self.model.display_name,
                self.model.session_source_type,
                self.model.session_source_id,
                self.model.session_reference,
                self.model.enrolled_via,
                self.model.managed_mcp_servers,
                self.model.lifecycle_state,
                self.model.lifecycle_reason,
                self.model.lifecycle_updated_at,
                self.model.last_seen_at,
                User.username.label("owner_username"),
                User.email.label("owner_email"),
                RuntimeSession.started_at,
                RuntimeSession.last_activity_at,
                RuntimeSession.ended_at,
                func.count(ApiUsage.id).label("request_count"),
                func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0).label(
                    "estimated_cost"
                ),
                func.max(ApiUsage.model_alias).label("latest_model_alias"),
                func.max(ApiUsage.provider_name).label("latest_provider_name"),
                func.max(ApiUsage.timestamp).label("last_request_at"),
            )
            .group_by(
                self.model.id,
                self.model.runtime_session_id,
                self.model.owner_user_id,
                self.model.display_name,
                self.model.session_source_type,
                self.model.session_source_id,
                self.model.session_reference,
                self.model.enrolled_via,
                self.model.managed_mcp_servers,
                self.model.lifecycle_state,
                self.model.lifecycle_reason,
                self.model.lifecycle_updated_at,
                self.model.last_seen_at,
                User.username,
                User.email,
                RuntimeSession.started_at,
                RuntimeSession.last_activity_at,
                RuntimeSession.ended_at,
            )
            .first()
        )
        if row is None:
            return None
        return self._row_to_summary(row)

    def get_usage_aggregate_for_account(
        self, db: Session, *, account_id: str, agent_id: str
    ) -> Optional[dict[str, Any]]:
        """Return historical usage totals across all sessions for one agent."""
        agent = self.get_for_account(db, account_id=account_id, agent_id=agent_id)
        if agent is None:
            return None

        session_count = (
            db.query(func.count(RuntimeSession.id))
            .filter(
                RuntimeSession.account_id == account_id,
                RuntimeSession.runtime_principal_type == agent.session_source_type,
                RuntimeSession.runtime_principal_id == agent.session_source_id,
            )
            .scalar()
            or 0
        )

        usage_row = (
            db.query(
                func.count(ApiUsage.id).label("request_count"),
                func.coalesce(
                    func.sum(case((ApiUsage.status_code < 400, 1), else_=0)), 0
                ).label("success_count"),
                func.coalesce(
                    func.sum(case((ApiUsage.status_code >= 400, 1), else_=0)), 0
                ).label("error_count"),
                func.coalesce(func.sum(ApiUsage.prompt_tokens), 0).label(
                    "prompt_tokens"
                ),
                func.coalesce(func.sum(ApiUsage.completion_tokens), 0).label(
                    "completion_tokens"
                ),
                func.coalesce(func.sum(ApiUsage.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0).label(
                    "estimated_cost"
                ),
                func.max(ApiUsage.model_alias).label("latest_model_alias"),
                func.max(ApiUsage.provider_name).label("latest_provider_name"),
                func.max(ApiUsage.timestamp).label("last_request_at"),
            )
            .filter(
                ApiUsage.account_id == account_id,
                ApiUsage.action_type == "model_gateway",
                ApiUsage.runtime_principal_type == agent.session_source_type,
                ApiUsage.runtime_principal_id == agent.session_source_id,
            )
            .one()
        )

        return {
            "session_count": int(session_count or 0),
            "total_requests": int(usage_row.request_count or 0),
            "successful_requests": int(usage_row.success_count or 0),
            "failed_requests": int(usage_row.error_count or 0),
            "prompt_tokens": int(usage_row.prompt_tokens or 0),
            "completion_tokens": int(usage_row.completion_tokens or 0),
            "total_tokens": int(usage_row.total_tokens or 0),
            "estimated_cost": float(usage_row.estimated_cost or 0.0),
            "latest_model_alias": usage_row.latest_model_alias,
            "latest_provider_name": usage_row.latest_provider_name,
            "last_request_at": usage_row.last_request_at,
        }

    def get_usage_by_model_for_account(
        self, db: Session, *, account_id: str, agent_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return historical model usage grouped across all sessions for one agent."""
        agent = self.get_for_account(db, account_id=account_id, agent_id=agent_id)
        if agent is None:
            return []

        rows = (
            db.query(
                ApiUsage.ai_model_id,
                ApiUsage.model_alias,
                ApiUsage.provider_name,
                func.count(ApiUsage.id).label("request_count"),
                func.coalesce(func.sum(ApiUsage.prompt_tokens), 0).label(
                    "prompt_tokens"
                ),
                func.coalesce(func.sum(ApiUsage.completion_tokens), 0).label(
                    "completion_tokens"
                ),
                func.coalesce(func.sum(ApiUsage.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0).label(
                    "estimated_cost"
                ),
            )
            .filter(
                ApiUsage.account_id == account_id,
                ApiUsage.action_type == "model_gateway",
                ApiUsage.runtime_principal_type == agent.session_source_type,
                ApiUsage.runtime_principal_id == agent.session_source_id,
            )
            .group_by(
                ApiUsage.ai_model_id, ApiUsage.model_alias, ApiUsage.provider_name
            )
            .order_by(
                func.count(ApiUsage.id).desc(), func.sum(ApiUsage.total_tokens).desc()
            )
            .limit(limit)
            .all()
        )

        return [
            {
                "ai_model_id": str(row.ai_model_id) if row.ai_model_id else None,
                "model_alias": row.model_alias,
                "provider_name": row.provider_name,
                "request_count": int(row.request_count or 0),
                "prompt_tokens": int(row.prompt_tokens or 0),
                "completion_tokens": int(row.completion_tokens or 0),
                "total_tokens": int(row.total_tokens or 0),
                "estimated_cost": float(row.estimated_cost or 0.0),
            }
            for row in rows
        ]

    @staticmethod
    def _row_to_summary(row: Any) -> dict[str, Any]:
        """Normalize one list row into API response data."""
        now = _utc_now()
        last_activity = _coerce_utc(
            row.last_activity_at or row.last_request_at or row.last_seen_at
        )
        if row.lifecycle_state == "decommissioned":
            activity_status = "decommissioned"
            is_active_now = False
        elif row.lifecycle_state == "suspended":
            activity_status = "suspended"
            is_active_now = False
        elif row.ended_at is not None:
            activity_status = "ended"
            is_active_now = False
        elif (
            last_activity is not None
            and (now - last_activity) <= MANAGED_AGENT_ACTIVE_WINDOW
        ):
            activity_status = "active_now"
            is_active_now = True
        else:
            activity_status = "idle"
            is_active_now = False
        return {
            "id": str(row.id),
            "runtime_session_id": (
                str(row.runtime_session_id) if row.runtime_session_id else None
            ),
            "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None,
            "owner_username": row.owner_username,
            "owner_email": row.owner_email,
            "display_name": row.display_name,
            "session_source_type": row.session_source_type,
            "session_source_id": row.session_source_id,
            "session_reference": row.session_reference,
            "enrolled_via": row.enrolled_via,
            "managed_mcp_servers": row.managed_mcp_servers or [],
            "lifecycle_state": row.lifecycle_state,
            "lifecycle_reason": row.lifecycle_reason,
            "lifecycle_updated_at": row.lifecycle_updated_at,
            "is_active_now": is_active_now,
            "activity_status": activity_status,
            "last_seen_at": row.last_seen_at,
            "started_at": row.started_at,
            "last_activity_at": row.last_activity_at,
            "ended_at": row.ended_at,
            "total_requests": int(row.request_count or 0),
            "estimated_cost": float(row.estimated_cost or 0.0),
            "latest_model_alias": row.latest_model_alias,
            "latest_provider_name": row.latest_provider_name,
            "last_request_at": row.last_request_at,
        }


crud_managed_agent = CRUDManagedAgent(ManagedAgent)
