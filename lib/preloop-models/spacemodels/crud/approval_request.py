"""CRUD operations for ApprovalRequest model."""

from typing import Optional
from sqlalchemy.orm import Session

from ..models.approval_request import ApprovalRequest
from .base import CRUDBase


class CRUDApprovalRequest(CRUDBase[ApprovalRequest]):
    """CRUD operations for ApprovalRequest model."""

    def get_by_token(
        self,
        db: Session,
        *,
        token: str,
    ) -> Optional[ApprovalRequest]:
        """Get approval request by approval token."""
        return db.query(self.model).filter(self.model.approval_token == token).first()

    def get_by_id_and_token(
        self,
        db: Session,
        *,
        request_id: str,
        token: str,
    ) -> Optional[ApprovalRequest]:
        """Get approval request by ID and token (for public token-based access).

        Args:
            db: Database session
            request_id: Approval request ID
            token: Approval token

        Returns:
            Approval request if found and token matches, None otherwise
        """
        return (
            db.query(self.model)
            .filter(
                self.model.id == request_id,
                self.model.approval_token == token,
            )
            .first()
        )

    def get_multi_by_execution(
        self,
        db: Session,
        *,
        execution_id: str,
        account_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ApprovalRequest]:
        """Get approval requests for a specific execution."""
        query = db.query(self.model).filter(self.model.execution_id == execution_id)

        if account_id:
            query = query.filter(self.model.account_id == account_id)

        if status:
            query = query.filter(self.model.status == status)

        return (
            query.order_by(self.model.requested_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


# Create instance
crud_approval_request = CRUDApprovalRequest(ApprovalRequest)
