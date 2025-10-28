"""CRUD operations for ApiUsage model."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.account import Account
from ..models.api_usage import ApiUsage
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
            create_user_if_missing: Whether to create a user account if it doesn't exist

        Returns:
            Created API usage record, or None if the user doesn't exist and create_user_if_missing is False
        """
        # Only check for user existence if a username is provided
        if username:
            user = db.query(Account).filter(Account.username == username).first()

            if not user:
                if create_user_if_missing:
                    # Create a placeholder user account
                    user = Account(
                        username=username,
                        email=f"{username}@example.com",  # Placeholder email
                        hashed_password="",  # Empty password since this is just for logging
                        is_active=True,
                    )
                    db.add(user)
                    db.commit()
                else:
                    # Set username to None for non-existent users to avoid foreign key constraint
                    username = None

        try:
            # Create the API usage record
            db_obj = ApiUsage(
                username=username,
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
        query = db.query(ApiUsage).filter(
            ApiUsage.username == username, ApiUsage.timestamp >= start_date
        )
        if account_id:
            query = query.join(Account, ApiUsage.username == Account.username).filter(
                Account.id == account_id
            )
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
            query = query.join(Account, ApiUsage.username == Account.username).filter(
                Account.id == account_id
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
        query = db.query(
            ApiUsage.username,
            func.count().label("request_count"),
            func.avg(ApiUsage.duration).label("avg_duration"),
        ).filter(ApiUsage.timestamp >= start_date)

        if account_id:
            query = query.join(Account, ApiUsage.username == Account.username).filter(
                Account.id == account_id
            )

        result = (
            query.group_by(ApiUsage.username)
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
        query = db.query(ApiUsage).filter(ApiUsage.username == username)

        if start_date:
            query = query.filter(ApiUsage.timestamp >= start_date)
        if end_date:
            query = query.filter(ApiUsage.timestamp <= end_date)

        if account_id:
            query = query.join(Account, ApiUsage.username == Account.username).filter(
                Account.id == account_id
            )

        return query.all()
