"""CRUD operations for RuntimeSession."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models.runtime_session import RuntimeSession
from .base import CRUDBase


class CRUDRuntimeSession(CRUDBase[RuntimeSession]):
    """CRUD helpers for shared runtime session identities."""

    def get_by_source(
        self,
        db: Session,
        *,
        session_source_type: str,
        session_source_id: str,
    ) -> Optional[RuntimeSession]:
        """Look up a runtime session by its source identity."""
        return (
            db.query(self.model)
            .filter(
                self.model.session_source_type == session_source_type,
                self.model.session_source_id == session_source_id,
            )
            .first()
        )

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
    ) -> RuntimeSession:
        """Create or update a runtime session keyed by source identity."""
        db_obj = self.get_by_source(
            db,
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
        if started_at is not None and db_obj.started_at is None:
            db_obj.started_at = started_at
        if last_activity_at is not None:
            db_obj.last_activity_at = last_activity_at
        if ended_at is not None:
            db_obj.ended_at = ended_at

        db.add(db_obj)
        db.flush()
        return db_obj


crud_runtime_session = CRUDRuntimeSession(RuntimeSession)
