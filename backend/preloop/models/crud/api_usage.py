"""CRUD operations for ApiUsage model."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.api_usage import ApiUsage
from ..models.flow import Flow
from ..models.flow_execution import FlowExecution
from ..models.runtime_session import RuntimeSession
from ..models.user import User
from .base import CRUDBase


class CRUDApiUsage(CRUDBase[ApiUsage]):
    """CRUD operations for API usage tracking."""

    def log_request(
        self,
        db: Session,
        *,
        username: Optional[str] = None,
        endpoint: str,
        method: str,
        status_code: int,
        duration: float,
        action_type: Optional[str] = None,
        create_user_if_missing: bool = False,
    ) -> Optional[ApiUsage]:
        """Log an API request.

        Args:
            db: Database session
            username: Username of the user making the request
            endpoint: API endpoint being accessed
            method: HTTP method used (GET, POST, etc.)
            status_code: HTTP status code of the response
            duration: Time taken to process the request in seconds
            action_type: Type of action (create_issue, update_issue, etc.)
            create_user_if_missing: Whether to create a user account if it doesn't exist (not supported)

        Returns:
            Created API usage record, or None if the user doesn't exist and create_user_if_missing is False
        """
        user_id = None

        # Only check for user existence if a username is provided
        if username:
            user = db.query(User).filter(User.username == username).first()

            if user:
                user_id = user.id
            elif not create_user_if_missing:
                # Set user_id to None for non-existent users
                user_id = None

        try:
            # Create the API usage record
            db_obj = ApiUsage(
                user_id=user_id,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration=duration,
                action_type=action_type,
                timestamp=datetime.now(timezone.utc),
            )

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            # If there's still an integrity error, roll back and return None
            db.rollback()
            return None

    def log_gateway_request(
        self,
        db: Session,
        *,
        endpoint: str,
        method: str,
        status_code: int,
        duration: float,
        user_id: Optional[str] = None,
        account_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        auth_subject_type: Optional[str] = None,
        ai_model_id: Optional[str] = None,
        flow_id: Optional[str] = None,
        flow_execution_id: Optional[str] = None,
        runtime_session_id: Optional[str] = None,
        model_alias: Optional[str] = None,
        provider_name: Optional[str] = None,
        upstream_request_id: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        runtime_principal_type: Optional[str] = None,
        runtime_principal_id: Optional[str] = None,
        runtime_principal_name: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None,
    ) -> ApiUsage:
        """Log a model gateway request with usage and attribution fields."""
        db_obj = ApiUsage(
            user_id=user_id,
            account_id=account_id,
            api_key_id=api_key_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration=duration,
            action_type="model_gateway",
            auth_subject_type=auth_subject_type,
            ai_model_id=ai_model_id,
            flow_id=flow_id,
            flow_execution_id=flow_execution_id,
            runtime_session_id=runtime_session_id,
            model_alias=model_alias,
            provider_name=provider_name,
            upstream_request_id=upstream_request_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            runtime_principal_type=runtime_principal_type,
            runtime_principal_id=runtime_principal_id,
            runtime_principal_name=runtime_principal_name,
            meta_data=meta_data,
            timestamp=datetime.now(timezone.utc),
        )

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_user_usage(
        self,
        db: Session,
        *,
        username: str,
        days: int = 30,
        account_id: Optional[str] = None,
    ) -> List[ApiUsage]:
        """Get API usage for a specific user within a time period."""
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = (
            db.query(ApiUsage)
            .join(User, ApiUsage.user_id == User.id)
            .filter(User.username == username, ApiUsage.timestamp >= start_date)
        )
        if account_id:
            query = query.filter(User.account_id == account_id)
        return query.order_by(ApiUsage.timestamp.desc()).all()

    def get_endpoint_stats(
        self, db: Session, *, days: int = 30, account_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get statistics for API endpoints."""
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = db.query(
            ApiUsage.endpoint,
            ApiUsage.method,
            func.count().label("request_count"),
            func.avg(ApiUsage.duration).label("avg_duration"),
            func.min(ApiUsage.duration).label("min_duration"),
            func.max(ApiUsage.duration).label("max_duration"),
        ).filter(ApiUsage.timestamp >= start_date)

        if account_id:
            query = query.join(User, ApiUsage.user_id == User.id).filter(
                User.account_id == account_id
            )

        result = (
            query.group_by(ApiUsage.endpoint, ApiUsage.method)
            .order_by(func.count().desc())
            .all()
        )

        return [
            {
                "endpoint": row.endpoint,
                "method": row.method,
                "request_count": row.request_count,
                "avg_duration": float(row.avg_duration),
                "min_duration": float(row.min_duration),
                "max_duration": float(row.max_duration),
            }
            for row in result
        ]

    def get_user_stats(
        self,
        db: Session,
        *,
        days: int = 30,
        limit: int = 10,
        account_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get statistics for API users."""
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = (
            db.query(
                User.username,
                func.count().label("request_count"),
                func.avg(ApiUsage.duration).label("avg_duration"),
            )
            .join(User, ApiUsage.user_id == User.id)
            .filter(ApiUsage.timestamp >= start_date)
        )

        if account_id:
            query = query.filter(User.account_id == account_id)

        result = (
            query.group_by(User.username)
            .order_by(func.count().desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "username": row.username,
                "request_count": row.request_count,
                "avg_duration": float(row.avg_duration),
            }
            for row in result
        ]

    def get_for_user_filtered(
        self,
        db: Session,
        *,
        username: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        account_id: Optional[str] = None,
    ) -> List[ApiUsage]:
        """Get API usage for a user with optional date filters."""
        query = (
            db.query(ApiUsage)
            .join(User, ApiUsage.user_id == User.id)
            .filter(User.username == username)
        )

        if start_date:
            query = query.filter(ApiUsage.timestamp >= start_date)
        if end_date:
            query = query.filter(ApiUsage.timestamp <= end_date)

        if account_id:
            query = query.filter(User.account_id == account_id)

        return query.all()

    def get_gateway_usage_summary(
        self,
        db: Session,
        *,
        account_id: str,
        start_date: datetime,
        end_date: datetime,
        flow_id: Optional[str] = None,
        runtime_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get aggregated gateway usage totals for an account or flow."""
        query = db.query(
            func.count(ApiUsage.id).label("request_count"),
            func.coalesce(
                func.sum(case((ApiUsage.status_code < 400, 1), else_=0)), 0
            ).label("success_count"),
            func.coalesce(
                func.sum(case((ApiUsage.status_code >= 400, 1), else_=0)), 0
            ).label("error_count"),
            func.coalesce(func.sum(ApiUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(ApiUsage.completion_tokens), 0).label(
                "completion_tokens"
            ),
            func.coalesce(func.sum(ApiUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0).label(
                "estimated_cost"
            ),
        ).filter(
            ApiUsage.action_type == "model_gateway",
            ApiUsage.account_id == account_id,
            ApiUsage.timestamp >= start_date,
            ApiUsage.timestamp < end_date,
        )

        if flow_id:
            query = query.filter(ApiUsage.flow_id == flow_id)
        if runtime_session_id:
            query = query.filter(ApiUsage.runtime_session_id == runtime_session_id)

        row = query.one()
        return {
            "request_count": int(row.request_count or 0),
            "success_count": int(row.success_count or 0),
            "error_count": int(row.error_count or 0),
            "prompt_tokens": int(row.prompt_tokens or 0),
            "completion_tokens": int(row.completion_tokens or 0),
            "total_tokens": int(row.total_tokens or 0),
            "estimated_cost": float(row.estimated_cost or 0.0),
        }

    def get_gateway_usage_by_model(
        self,
        db: Session,
        *,
        account_id: str,
        start_date: datetime,
        end_date: datetime,
        flow_id: Optional[str] = None,
        runtime_session_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Group gateway usage by model."""
        query = db.query(
            ApiUsage.ai_model_id,
            ApiUsage.model_alias,
            ApiUsage.provider_name,
            func.count(ApiUsage.id).label("request_count"),
            func.coalesce(func.sum(ApiUsage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(ApiUsage.completion_tokens), 0).label(
                "completion_tokens"
            ),
            func.coalesce(func.sum(ApiUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0).label(
                "estimated_cost"
            ),
        ).filter(
            ApiUsage.action_type == "model_gateway",
            ApiUsage.account_id == account_id,
            ApiUsage.timestamp >= start_date,
            ApiUsage.timestamp < end_date,
        )
        if flow_id:
            query = query.filter(ApiUsage.flow_id == flow_id)
        if runtime_session_id:
            query = query.filter(ApiUsage.runtime_session_id == runtime_session_id)

        rows = (
            query.group_by(
                ApiUsage.ai_model_id, ApiUsage.model_alias, ApiUsage.provider_name
            )
            .order_by(func.count(ApiUsage.id).desc())
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

    def get_gateway_usage_by_flow(
        self,
        db: Session,
        *,
        account_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Group gateway usage by flow."""
        from ..models.flow import Flow

        rows = (
            db.query(
                ApiUsage.flow_id,
                Flow.name.label("flow_name"),
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
            .outerjoin(Flow, ApiUsage.flow_id == Flow.id)
            .filter(
                ApiUsage.action_type == "model_gateway",
                ApiUsage.account_id == account_id,
                ApiUsage.timestamp >= start_date,
                ApiUsage.timestamp < end_date,
            )
            .group_by(ApiUsage.flow_id, Flow.name)
            .order_by(func.count(ApiUsage.id).desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "flow_id": str(row.flow_id) if row.flow_id else None,
                "flow_name": row.flow_name,
                "request_count": int(row.request_count or 0),
                "prompt_tokens": int(row.prompt_tokens or 0),
                "completion_tokens": int(row.completion_tokens or 0),
                "total_tokens": int(row.total_tokens or 0),
                "estimated_cost": float(row.estimated_cost or 0.0),
            }
            for row in rows
        ]

    def get_gateway_usage_by_execution(
        self,
        db: Session,
        *,
        account_id: str,
        flow_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Group gateway usage by flow execution."""
        rows = (
            db.query(
                ApiUsage.flow_execution_id,
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
                func.max(ApiUsage.timestamp).label("last_request_at"),
            )
            .filter(
                ApiUsage.action_type == "model_gateway",
                ApiUsage.account_id == account_id,
                ApiUsage.flow_id == flow_id,
                ApiUsage.timestamp >= start_date,
                ApiUsage.timestamp < end_date,
            )
            .group_by(ApiUsage.flow_execution_id)
            .order_by(func.max(ApiUsage.timestamp).desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "flow_execution_id": (
                    str(row.flow_execution_id) if row.flow_execution_id else None
                ),
                "request_count": int(row.request_count or 0),
                "prompt_tokens": int(row.prompt_tokens or 0),
                "completion_tokens": int(row.completion_tokens or 0),
                "total_tokens": int(row.total_tokens or 0),
                "estimated_cost": float(row.estimated_cost or 0.0),
                "last_request_at": row.last_request_at,
            }
            for row in rows
        ]

    def get_gateway_usage_by_session(
        self,
        db: Session,
        *,
        account_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Group recent execution-backed gateway usage into session slices."""
        legacy_session_source_type = case(
            (ApiUsage.flow_execution_id.isnot(None), "flow_execution"),
            else_=None,
        )
        legacy_session_source_id = cast(ApiUsage.flow_execution_id, String)
        session_source_type = func.coalesce(
            RuntimeSession.session_source_type, legacy_session_source_type
        )
        session_source_id = func.coalesce(
            RuntimeSession.session_source_id, legacy_session_source_id
        )
        session_reference = func.coalesce(
            RuntimeSession.session_reference, FlowExecution.agent_session_reference
        )
        rows = (
            db.query(
                RuntimeSession.id.label("runtime_session_id"),
                session_source_type.label("session_source_type"),
                session_source_id.label("session_source_id"),
                ApiUsage.flow_execution_id,
                ApiUsage.flow_id,
                Flow.name.label("flow_name"),
                session_reference.label("session_reference"),
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
                func.max(ApiUsage.timestamp).label("last_request_at"),
            )
            .outerjoin(Flow, ApiUsage.flow_id == Flow.id)
            .outerjoin(FlowExecution, ApiUsage.flow_execution_id == FlowExecution.id)
            .outerjoin(RuntimeSession, ApiUsage.runtime_session_id == RuntimeSession.id)
            .filter(
                ApiUsage.action_type == "model_gateway",
                ApiUsage.account_id == account_id,
                or_(
                    ApiUsage.runtime_session_id.isnot(None),
                    ApiUsage.flow_execution_id.isnot(None),
                ),
                ApiUsage.timestamp >= start_date,
                ApiUsage.timestamp < end_date,
            )
            .group_by(
                RuntimeSession.id,
                session_source_type,
                session_source_id,
                ApiUsage.flow_execution_id,
                ApiUsage.flow_id,
                Flow.name,
                session_reference,
                ApiUsage.model_alias,
                ApiUsage.provider_name,
            )
            .order_by(
                func.max(ApiUsage.timestamp).desc(), func.count(ApiUsage.id).desc()
            )
            .limit(limit)
            .all()
        )
        return [
            {
                "runtime_session_id": (
                    str(row.runtime_session_id) if row.runtime_session_id else None
                ),
                "session_source_type": row.session_source_type,
                "session_source_id": row.session_source_id,
                "flow_execution_id": (
                    str(row.flow_execution_id) if row.flow_execution_id else None
                ),
                "flow_id": str(row.flow_id) if row.flow_id else None,
                "flow_name": row.flow_name,
                "session_reference": row.session_reference,
                "model_alias": row.model_alias,
                "provider_name": row.provider_name,
                "request_count": int(row.request_count or 0),
                "prompt_tokens": int(row.prompt_tokens or 0),
                "completion_tokens": int(row.completion_tokens or 0),
                "total_tokens": int(row.total_tokens or 0),
                "estimated_cost": float(row.estimated_cost or 0.0),
                "last_request_at": row.last_request_at,
            }
            for row in rows
        ]

    def get_gateway_usage_timeseries(
        self,
        db: Session,
        *,
        account_id: str,
        start_date: datetime,
        end_date: datetime,
        flow_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Group gateway usage by day."""
        bucket = func.date_trunc("day", ApiUsage.timestamp)
        query = db.query(
            bucket.label("bucket"),
            func.count(ApiUsage.id).label("request_count"),
            func.coalesce(func.sum(ApiUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(ApiUsage.estimated_cost), 0.0).label(
                "estimated_cost"
            ),
        ).filter(
            ApiUsage.action_type == "model_gateway",
            ApiUsage.account_id == account_id,
            ApiUsage.timestamp >= start_date,
            ApiUsage.timestamp < end_date,
        )
        if flow_id:
            query = query.filter(ApiUsage.flow_id == flow_id)

        rows = query.group_by(bucket).order_by(bucket.asc()).all()
        return [
            {
                "date": row.bucket.date().isoformat(),
                "request_count": int(row.request_count or 0),
                "total_tokens": int(row.total_tokens or 0),
                "estimated_cost": float(row.estimated_cost or 0.0),
            }
            for row in rows
        ]
