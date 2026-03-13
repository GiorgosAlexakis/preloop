"""CRUD operations for RuntimeSessionActivity."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..models.managed_agent import ManagedAgent
from ..models.runtime_session import RuntimeSession
from ..models.runtime_session_activity import RuntimeSessionActivity
from .base import CRUDBase


class CRUDRuntimeSessionActivity(CRUDBase[RuntimeSessionActivity]):
    """CRUD helpers for normalized runtime-session activity."""

    def log_tool_call(
        self,
        db: Session,
        *,
        account_id: Any,
        runtime_session_id: Any,
        server_name: Optional[str],
        tool_name: Optional[str],
        status: str,
        summary: Optional[str] = None,
        flow_execution_id: Optional[Any] = None,
        api_key_id: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        commit: bool = True,
    ) -> RuntimeSessionActivity:
        """Persist one normalized tool-call activity item."""
        activity_timestamp = timestamp or datetime.now(timezone.utc)
        db_obj = RuntimeSessionActivity(
            account_id=account_id,
            runtime_session_id=runtime_session_id,
            flow_execution_id=flow_execution_id,
            api_key_id=api_key_id,
            activity_type="tool_call",
            server_name=server_name,
            tool_name=tool_name,
            status=status,
            summary=summary,
            metadata_=metadata,
            timestamp=activity_timestamp,
        )
        db.add(db_obj)

        runtime_session = db.get(RuntimeSession, runtime_session_id)
        if runtime_session is not None:
            runtime_session.last_activity_at = activity_timestamp
            db.add(runtime_session)

            if (
                runtime_session.runtime_principal_type
                and runtime_session.runtime_principal_id
            ):
                managed_agent = (
                    db.query(ManagedAgent)
                    .filter(
                        ManagedAgent.account_id == account_id,
                        ManagedAgent.session_source_type
                        == runtime_session.runtime_principal_type,
                        ManagedAgent.session_source_id
                        == runtime_session.runtime_principal_id,
                    )
                    .first()
                )
                if managed_agent is not None:
                    if managed_agent.lifecycle_state == "active":
                        managed_agent.runtime_session_id = runtime_session.id
                        managed_agent.last_seen_at = activity_timestamp
                        db.add(managed_agent)

        if commit:
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def list_for_runtime_session(
        self,
        db: Session,
        *,
        account_id: str,
        runtime_session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RuntimeSessionActivity]:
        """Return recent normalized activity for one runtime session."""
        return (
            db.query(self.model)
            .filter(
                self.model.account_id == account_id,
                self.model.runtime_session_id == runtime_session_id,
            )
            .order_by(self.model.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_server_summary_for_principal(
        self,
        db: Session,
        *,
        account_id: str,
        runtime_principal_type: str,
        runtime_principal_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Aggregate tool-call activity by server for one durable runtime principal."""
        rows = (
            db.query(
                self.model.server_name,
                func.count(self.model.id).label("call_count"),
                func.coalesce(
                    func.sum(case((self.model.status == "success", 1), else_=0)), 0
                ).label("success_count"),
                func.coalesce(
                    func.sum(case((self.model.status != "success", 1), else_=0)), 0
                ).label("failure_count"),
                func.max(self.model.timestamp).label("last_activity_at"),
            )
            .join(RuntimeSession, self.model.runtime_session_id == RuntimeSession.id)
            .filter(
                self.model.account_id == account_id,
                RuntimeSession.runtime_principal_type == runtime_principal_type,
                RuntimeSession.runtime_principal_id == runtime_principal_id,
                self.model.activity_type == "tool_call",
            )
            .group_by(self.model.server_name)
            .order_by(
                func.count(self.model.id).desc(), func.max(self.model.timestamp).desc()
            )
            .limit(limit)
            .all()
        )
        return [
            {
                "server_name": row.server_name,
                "call_count": int(row.call_count or 0),
                "successful_calls": int(row.success_count or 0),
                "failed_calls": int(row.failure_count or 0),
                "last_activity_at": row.last_activity_at,
            }
            for row in rows
        ]

    def get_tool_summary_for_principal(
        self,
        db: Session,
        *,
        account_id: str,
        runtime_principal_type: str,
        runtime_principal_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Aggregate tool-call activity by server/tool for one durable runtime principal."""
        rows = (
            db.query(
                self.model.server_name,
                self.model.tool_name,
                func.count(self.model.id).label("call_count"),
                func.coalesce(
                    func.sum(case((self.model.status == "success", 1), else_=0)), 0
                ).label("success_count"),
                func.coalesce(
                    func.sum(case((self.model.status != "success", 1), else_=0)), 0
                ).label("failure_count"),
                func.max(self.model.timestamp).label("last_activity_at"),
            )
            .join(RuntimeSession, self.model.runtime_session_id == RuntimeSession.id)
            .filter(
                self.model.account_id == account_id,
                RuntimeSession.runtime_principal_type == runtime_principal_type,
                RuntimeSession.runtime_principal_id == runtime_principal_id,
                self.model.activity_type == "tool_call",
            )
            .group_by(self.model.server_name, self.model.tool_name)
            .order_by(
                func.count(self.model.id).desc(), func.max(self.model.timestamp).desc()
            )
            .limit(limit)
            .all()
        )
        return [
            {
                "server_name": row.server_name,
                "tool_name": row.tool_name,
                "call_count": int(row.call_count or 0),
                "successful_calls": int(row.success_count or 0),
                "failed_calls": int(row.failure_count or 0),
                "last_activity_at": row.last_activity_at,
            }
            for row in rows
        ]


crud_runtime_session_activity = CRUDRuntimeSessionActivity(RuntimeSessionActivity)
