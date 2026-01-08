"""CRUD operations for AuditLog model."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.audit_log import AuditLog
from ..models.user import User
from .base import CRUDBase


class CRUDAuditLog(CRUDBase[AuditLog]):
    """CRUD operations for audit logging."""

    def log_action(
        self,
        db: Session,
        *,
        account_id: Union[UUID, str],
        user_id: Optional[UUID] = None,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log a security-sensitive action.

        Args:
            db: Database session
            account_id: The account this action belongs to (UUID or str)
            user_id: The user who performed the action (None for system actions)
            action: The action performed (e.g., 'permission_check', 'role_assigned')
            resource_type: The type of resource affected (e.g., 'issue', 'user', 'team')
            resource_id: The ID of the specific resource affected
            status: The result ('success', 'denied', 'failure')
            ip_address: The IP address of the request
            user_agent: The user agent string
            details: Additional context as JSON

        Returns:
            Created audit log record
        """
        # Convert UUID to string if needed
        account_id_str = str(account_id) if isinstance(account_id, UUID) else account_id

        db_obj = AuditLog(
            account_id=account_id_str,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            timestamp=datetime.now(timezone.utc),
        )

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_account(
        self,
        db: Session,
        *,
        account_id: Union[UUID, str],
        skip: int = 0,
        limit: int = 100,
        action: Optional[str] = None,
        status: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditLog]:
        """Get audit logs for an account with optional filters.

        Args:
            db: Database session
            account_id: The account to filter by (UUID or str)
            skip: Number of records to skip
            limit: Maximum number of records to return
            action: Filter by action type
            status: Filter by status
            resource_type: Filter by resource type
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of audit logs matching the criteria
        """
        account_id_str = str(account_id) if isinstance(account_id, UUID) else account_id
        query = db.query(AuditLog).filter(AuditLog.account_id == account_id_str)

        if action:
            query = query.filter(AuditLog.action == action)
        if status:
            query = query.filter(AuditLog.status == status)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        return query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

    def get_by_user(
        self,
        db: Session,
        *,
        user_id: UUID,
        account_id: Union[UUID, str],
        skip: int = 0,
        limit: int = 100,
        days: int = 30,
    ) -> List[AuditLog]:
        """Get audit logs for a specific user.

        Args:
            db: Database session
            user_id: The user to filter by
            account_id: The account to filter by (for isolation, UUID or str)
            skip: Number of records to skip
            limit: Maximum number of records to return
            days: Number of days to look back

        Returns:
            List of audit logs for the user
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        account_id_str = str(account_id) if isinstance(account_id, UUID) else account_id

        return (
            db.query(AuditLog)
            .filter(
                AuditLog.user_id == user_id,
                AuditLog.account_id == account_id_str,
                AuditLog.timestamp >= start_date,
            )
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_permission_denials(
        self,
        db: Session,
        *,
        account_id: Union[UUID, str],
        days: int = 7,
        limit: int = 100,
    ) -> List[AuditLog]:
        """Get recent permission denial events.

        Args:
            db: Database session
            account_id: The account to filter by (UUID or str)
            days: Number of days to look back
            limit: Maximum number of records to return

        Returns:
            List of permission denial audit logs
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        account_id_str = str(account_id) if isinstance(account_id, UUID) else account_id

        return (
            db.query(AuditLog)
            .filter(
                AuditLog.account_id == account_id_str,
                AuditLog.action == "permission_check",
                AuditLog.status == "denied",
                AuditLog.timestamp >= start_date,
            )
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_action_stats(
        self,
        db: Session,
        *,
        account_id: Union[UUID, str],
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get statistics for audit actions.

        Args:
            db: Database session
            account_id: The account to filter by (UUID or str)
            days: Number of days to look back

        Returns:
            List of action statistics
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        account_id_str = str(account_id) if isinstance(account_id, UUID) else account_id

        result = (
            db.query(
                AuditLog.action,
                AuditLog.status,
                func.count().label("count"),
            )
            .filter(
                AuditLog.account_id == account_id_str,
                AuditLog.timestamp >= start_date,
            )
            .group_by(AuditLog.action, AuditLog.status)
            .order_by(func.count().desc())
            .all()
        )

        return [
            {
                "action": row.action,
                "status": row.status,
                "count": row.count,
            }
            for row in result
        ]

    def get_user_activity(
        self,
        db: Session,
        *,
        account_id: Union[UUID, str],
        days: int = 30,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get user activity statistics.

        Args:
            db: Database session
            account_id: The account to filter by (UUID or str)
            days: Number of days to look back
            limit: Maximum number of users to return

        Returns:
            List of user activity statistics
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        account_id_str = str(account_id) if isinstance(account_id, UUID) else account_id

        result = (
            db.query(
                User.username,
                User.email,
                func.count().label("action_count"),
            )
            .join(AuditLog, AuditLog.user_id == User.id)
            .filter(
                AuditLog.account_id == account_id_str,
                AuditLog.timestamp >= start_date,
            )
            .group_by(User.username, User.email)
            .order_by(func.count().desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "username": row.username,
                "email": row.email,
                "action_count": row.action_count,
            }
            for row in result
        ]

    def count_by_account(
        self,
        db: Session,
        *,
        account_id: Union[UUID, str],
        action: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Count audit logs for an account with optional filters.

        Args:
            db: Database session
            account_id: The account to filter by (UUID or str)
            action: Filter by action type
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Count of matching audit logs
        """
        account_id_str = str(account_id) if isinstance(account_id, UUID) else account_id
        query = db.query(func.count(AuditLog.id)).filter(
            AuditLog.account_id == account_id_str
        )

        if action:
            query = query.filter(AuditLog.action == action)
        if status:
            query = query.filter(AuditLog.status == status)
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        return query.scalar()


# Global instance
crud_audit_log = CRUDAuditLog(AuditLog)
