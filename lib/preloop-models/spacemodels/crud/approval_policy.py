"""CRUD operations for ApprovalPolicy model."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models
from .base import CRUDBase


class CRUDApprovalPolicy(CRUDBase[models.ApprovalPolicy]):
    """CRUD operations for ApprovalPolicy model."""

    def __init__(self):
        """Initialize with the ApprovalPolicy model."""
        super().__init__(model=models.ApprovalPolicy)

    def get(
        self, db: Session, id: UUID, account_id: str
    ) -> Optional[models.ApprovalPolicy]:
        """Retrieve an approval policy by its ID.

        Args:
            db: The database session.
            id: The ID of the approval policy to retrieve.
            account_id: The ID of the account associated with the policy.

        Returns:
            The approval policy object if found, otherwise None.
        """
        return (
            db.query(self.model)
            .filter(
                self.model.id == id,
                self.model.account_id == account_id,
            )
            .first()
        )

    def get_by_name(
        self, db: Session, account_id: str, name: str
    ) -> Optional[models.ApprovalPolicy]:
        """Retrieve an approval policy by name and account.

        Args:
            db: The database session.
            account_id: The ID of the account.
            name: The name of the approval policy.

        Returns:
            The approval policy object if found, otherwise None.
        """
        return (
            db.query(self.model)
            .filter(
                self.model.account_id == account_id,
                self.model.name == name,
            )
            .first()
        )

    def get_multi_by_account(
        self,
        db: Session,
        account_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[models.ApprovalPolicy]:
        """Retrieve approval policies for a specific account.

        Args:
            db: The database session.
            account_id: The ID of the account.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of approval policy objects.
        """
        return (
            db.query(self.model)
            .filter(self.model.account_id == account_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def remove(
        self, db: Session, *, id: UUID, account_id: str
    ) -> Optional[models.ApprovalPolicy]:
        """Remove an approval policy by its ID.

        Args:
            db: The database session.
            id: The ID of the approval policy to remove.
            account_id: The ID of the account.

        Returns:
            The removed approval policy object if found and deleted, otherwise None.
        """
        db_policy = (
            db.query(self.model)
            .filter(
                self.model.id == id,
                self.model.account_id == account_id,
            )
            .first()
        )
        if db_policy:
            db.delete(db_policy)
            db.commit()
        return db_policy
