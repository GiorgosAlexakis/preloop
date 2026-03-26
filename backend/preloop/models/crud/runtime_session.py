"""CRUD operations for RuntimeSession."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import String, and_, case, cast, func, or_
from sqlalchemy.orm import Session

from ..models.api_usage import ApiUsage
from ..models.flow import Flow
from ..models.runtime_session import RuntimeSession
from .base import CRUDBase


class CRUDRuntimeSession(CRUDBase[RuntimeSession]):
    """CRUD helpers for shared runtime session identities."""

    ACTIVE_WINDOW = timedelta(minutes=10)

    def get_by_source(
        self,
        db: Session,
        *,
        account_id: Any,
        session_source_type: str,
        session_source_id: str,
    ) -> Optional[RuntimeSession]:
        """Look up a runtime session by its source identity."""
        return (
            db.query(self.model)
            .filter(
                self.model.account_id == account_id,
                self.model.session_source_type == session_source_type,
                self.model.session_source_id == session_source_id,
            )
            .first()
        )

    def touch_activity(
        self,
        db: Session,
        *,
        account_id: Any,
        runtime_session_id: Any,
        observed_at: datetime,
        commit: bool = False,
    ) -> Optional[RuntimeSession]:
        """Update last activity for one runtime session."""
        db_obj = (
            db.query(self.model)
            .filter(
                self.model.account_id == account_id,
                self.model.id == runtime_session_id,
            )
            .first()
        )
        if db_obj is None:
            return None
        db_obj.last_activity_at = observed_at
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
        runtime_session_id: str,
        ended_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> Optional[RuntimeSession]:
        """Update operator-managed lifecycle state for one runtime session."""
        db_obj = self.get_account_session(
            db, account_id=account_id, runtime_session_id=runtime_session_id
        )
        if db_obj is None:
            return None
        if ended_at is not None:
            db_obj.ended_at = ended_at
            db_obj.last_activity_at = ended_at
        db.add(db_obj)
        if commit:
            db.commit()
            db.refresh(db_obj)
        else:
            db.flush()
        return db_obj

    def upsert_by_source(
        self,
        db: Session,
        *,
        account_id: Any,
        session_source_type: str,
        session_source_id: str,
        session_reference: Optional[str] = None,
        runtime_principal_type: Optional[str] = None,
        runtime_principal_id: Optional[str] = None,
        runtime_principal_name: Optional[str] = None,
        started_at: Optional[datetime] = None,
        last_activity_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        reopen_if_ended: bool = False,
    ) -> RuntimeSession:
        """Create or update a runtime session keyed by source identity."""
        db_obj = self.get_by_source(
            db,
            account_id=account_id,
            session_source_type=session_source_type,
            session_source_id=session_source_id,
        )
        if db_obj is None:
            db_obj = RuntimeSession(
                account_id=account_id,
                session_source_type=session_source_type,
                session_source_id=session_source_id,
                session_reference=session_reference,
                runtime_principal_type=runtime_principal_type,
                runtime_principal_id=runtime_principal_id,
                runtime_principal_name=runtime_principal_name,
                started_at=started_at or last_activity_at,
                last_activity_at=last_activity_at,
                ended_at=ended_at,
            )
            db.add(db_obj)
            db.flush()
            return db_obj

        if session_reference is not None:
            db_obj.session_reference = session_reference
        if runtime_principal_type is not None:
            db_obj.runtime_principal_type = runtime_principal_type
        if runtime_principal_id is not None:
            db_obj.runtime_principal_id = runtime_principal_id
        if runtime_principal_name is not None:
            db_obj.runtime_principal_name = runtime_principal_name
        if reopen_if_ended and db_obj.ended_at is not None and ended_at is None:
            db_obj.ended_at = None
            db_obj.started_at = started_at or last_activity_at
        elif started_at is not None and db_obj.started_at is None:
            db_obj.started_at = started_at
        if last_activity_at is not None:
            db_obj.last_activity_at = last_activity_at
        if ended_at is not None:
            db_obj.ended_at = ended_at

        db.add(db_obj)
        db.flush()
        return db_obj

    def list_account_sessions(
        self,
        db: Session,
        *,
        account_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        query: Optional[str] = None,
        ai_model_id: Optional[str] = None,
        session_source_type: Optional[str] = None,
        runtime_principal_type: Optional[str] = None,
        runtime_principal_id: Optional[str] = None,
        status: str = "all",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List runtime sessions with aggregated gateway usage."""
        session_query = db.query(self.model).filter(self.model.account_id == account_id)

        if query:
            normalized_query = f"%{' '.join(query.strip().split())}%"
            session_query = session_query.filter(
                or_(
                    self.model.session_source_type.ilike(normalized_query),
                    self.model.session_source_id.ilike(normalized_query),
                    self.model.session_reference.ilike(normalized_query),
                    self.model.runtime_principal_name.ilike(normalized_query),
                )
            )
        if ai_model_id:
            matching_session_ids = db.query(ApiUsage.runtime_session_id).filter(
                ApiUsage.runtime_session_id.isnot(None),
                ApiUsage.action_type == "model_gateway",
                ApiUsage.ai_model_id == ai_model_id,
            )
            if start_date is not None:
                matching_session_ids = matching_session_ids.filter(
                    ApiUsage.timestamp >= start_date
                )
            if end_date is not None:
                matching_session_ids = matching_session_ids.filter(
                    ApiUsage.timestamp < end_date
                )
            session_query = session_query.filter(
                self.model.id.in_(matching_session_ids.distinct())
            )
        if session_source_type:
            session_query = session_query.filter(
                self.model.session_source_type == session_source_type
            )
        if runtime_principal_type:
            session_query = session_query.filter(
                self.model.runtime_principal_type == runtime_principal_type
            )
        if runtime_principal_id:
            session_query = session_query.filter(
                self.model.runtime_principal_id == runtime_principal_id
            )
        if status == "active":
            session_query = session_query.filter(self.model.ended_at.is_(None))
        elif status == "ended":
            session_query = session_query.filter(self.model.ended_at.isnot(None))

        total = session_query.count()
        usage_join = self._usage_join_conditions(
            start_date=start_date, end_date=end_date, ai_model_id=ai_model_id
        )

        rows = (
            session_query.outerjoin(ApiUsage, usage_join)
            .outerjoin(Flow, ApiUsage.flow_id == Flow.id)
            .with_entities(
                self.model.account_id,
                self.model.id,
                self.model.session_source_type,
                self.model.session_source_id,
                self.model.session_reference,
                self.model.runtime_principal_type,
                self.model.runtime_principal_id,
                self.model.runtime_principal_name,
                self.model.started_at,
                self.model.last_activity_at,
                self.model.ended_at,
                func.max(cast(ApiUsage.flow_id, String)).label("flow_id"),
                func.max(Flow.name).label("flow_name"),
                func.max(cast(ApiUsage.flow_execution_id, String)).label(
                    "flow_execution_id"
                ),
                func.max(ApiUsage.model_alias).label("latest_model_alias"),
                func.max(ApiUsage.provider_name).label("latest_provider_name"),
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
                func.max(ApiUsage.timestamp).label("last_request_at"),
            )
            .group_by(
                self.model.account_id,
                self.model.id,
                self.model.session_source_type,
                self.model.session_source_id,
                self.model.session_reference,
                self.model.runtime_principal_type,
                self.model.runtime_principal_id,
                self.model.runtime_principal_name,
                self.model.started_at,
                self.model.last_activity_at,
                self.model.ended_at,
            )
            .order_by(
                func.coalesce(
                    func.max(ApiUsage.timestamp),
                    self.model.last_activity_at,
                    self.model.started_at,
                ).desc()
            )
            .limit(limit)
            .offset(offset)
            .all()
        )

        return {"total": total, "items": [self._row_to_summary(row) for row in rows]}

    def get_account_session(
        self, db: Session, *, account_id: str, runtime_session_id: str
    ) -> Optional[RuntimeSession]:
        """Return one runtime session for an account."""
        return (
            db.query(self.model)
            .filter(
                self.model.account_id == account_id, self.model.id == runtime_session_id
            )
            .first()
        )

    def get_latest_by_principal(
        self,
        db: Session,
        *,
        principal_type: str,
        principal_id: str,
    ) -> Optional[RuntimeSession]:
        """Return the most recent runtime session for a given principal."""
        return (
            db.query(self.model)
            .filter(
                self.model.session_source_type == principal_type,
                self.model.session_source_id.startswith(f"{principal_id}-")
                | (self.model.session_source_id == principal_id),
            )
            .order_by(self.model.created_at.desc())
            .first()
        )

    def get_account_session_summary(
        self,
        db: Session,
        *,
        account_id: str,
        runtime_session_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        ai_model_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Return one runtime session with aggregated gateway usage."""
        usage_join = self._usage_join_conditions(
            start_date=start_date, end_date=end_date, ai_model_id=ai_model_id
        )
        row = (
            db.query(
                self.model.account_id,
                self.model.id,
                self.model.session_source_type,
                self.model.session_source_id,
                self.model.session_reference,
                self.model.runtime_principal_type,
                self.model.runtime_principal_id,
                self.model.runtime_principal_name,
                self.model.started_at,
                self.model.last_activity_at,
                self.model.ended_at,
                func.max(cast(ApiUsage.flow_id, String)).label("flow_id"),
                func.max(Flow.name).label("flow_name"),
                func.max(cast(ApiUsage.flow_execution_id, String)).label(
                    "flow_execution_id"
                ),
                func.max(ApiUsage.model_alias).label("latest_model_alias"),
                func.max(ApiUsage.provider_name).label("latest_provider_name"),
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
                func.max(ApiUsage.timestamp).label("last_request_at"),
            )
            .outerjoin(ApiUsage, usage_join)
            .outerjoin(Flow, ApiUsage.flow_id == Flow.id)
            .filter(
                self.model.account_id == account_id, self.model.id == runtime_session_id
            )
            .group_by(
                self.model.account_id,
                self.model.id,
                self.model.session_source_type,
                self.model.session_source_id,
                self.model.session_reference,
                self.model.runtime_principal_type,
                self.model.runtime_principal_id,
                self.model.runtime_principal_name,
                self.model.started_at,
                self.model.last_activity_at,
                self.model.ended_at,
            )
            .first()
        )
        return self._row_to_summary(row) if row is not None else None

    @staticmethod
    def _usage_join_conditions(
        *,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        ai_model_id: Optional[str] = None,
    ):
        legacy_flow_execution_match = and_(
            RuntimeSession.session_source_type == "flow_execution",
            ApiUsage.flow_execution_id.isnot(None),
            cast(ApiUsage.flow_execution_id, String)
            == RuntimeSession.session_source_id,
        )
        conditions = [
            ApiUsage.action_type == "model_gateway",
            or_(
                ApiUsage.runtime_session_id == RuntimeSession.id,
                legacy_flow_execution_match,
            ),
        ]
        if start_date is not None:
            conditions.append(ApiUsage.timestamp >= start_date)
        if end_date is not None:
            conditions.append(ApiUsage.timestamp < end_date)
        if ai_model_id is not None:
            conditions.append(ApiUsage.ai_model_id == ai_model_id)
        return and_(*conditions)

    @staticmethod
    def _row_to_summary(row) -> dict[str, Any]:
        now = datetime.now(UTC)
        last_observed_at = row.last_request_at or row.last_activity_at or row.started_at
        if last_observed_at is not None and last_observed_at.tzinfo is None:
            last_observed_at = last_observed_at.replace(tzinfo=UTC)
        elif last_observed_at is not None:
            last_observed_at = last_observed_at.astimezone(UTC)

        if row.ended_at is not None:
            activity_status = "ended"
            is_active_now = False
        elif (
            last_observed_at is not None
            and (now - last_observed_at) <= CRUDRuntimeSession.ACTIVE_WINDOW
        ):
            activity_status = "active_now"
            is_active_now = True
        else:
            activity_status = "idle"
            is_active_now = False

        return {
            "account_id": str(row.account_id),
            "id": str(row.id),
            "session_source_type": row.session_source_type,
            "session_source_id": row.session_source_id,
            "session_reference": row.session_reference,
            "runtime_principal_type": row.runtime_principal_type,
            "runtime_principal_id": row.runtime_principal_id,
            "runtime_principal_name": row.runtime_principal_name,
            "started_at": row.started_at,
            "last_activity_at": row.last_activity_at,
            "ended_at": row.ended_at,
            "flow_id": row.flow_id,
            "flow_name": row.flow_name,
            "flow_execution_id": row.flow_execution_id,
            "latest_model_alias": row.latest_model_alias,
            "latest_provider_name": row.latest_provider_name,
            "is_active_now": is_active_now,
            "activity_status": activity_status,
            "total_requests": int(row.request_count or 0),
            "successful_requests": int(row.success_count or 0),
            "failed_requests": int(row.error_count or 0),
            "prompt_tokens": int(row.prompt_tokens or 0),
            "completion_tokens": int(row.completion_tokens or 0),
            "total_tokens": int(row.total_tokens or 0),
            "estimated_cost": float(row.estimated_cost or 0.0),
            "last_request_at": row.last_request_at,
        }


crud_runtime_session = CRUDRuntimeSession(RuntimeSession)
