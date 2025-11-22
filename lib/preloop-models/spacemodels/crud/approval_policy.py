"""CRUD operations for ApprovalPolicy model."""

from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.future import select

from .. import models
from ..schemas.tool_configuration import ApprovalPolicyCreate, ApprovalPolicyUpdate
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

    def get_default(
        self, db: Session, account_id: str
    ) -> Optional[models.ApprovalPolicy]:
        """Retrieve the default approval policy for an account.

        Args:
            db: The database session.
            account_id: The ID of the account.

        Returns:
            The default approval policy if found, otherwise None.
        """
        return (
            db.query(self.model)
            .filter(
                self.model.account_id == account_id,
                self.model.is_default,
            )
            .first()
        )

    def create(
        self,
        db: Session,
        *,
        obj_in: Union[ApprovalPolicyCreate, Dict[str, Any]],
        account_id: str,
    ) -> models.ApprovalPolicy:
        """Create a new approval policy.

        If this is the first policy for the account, it will be marked as default.
        If is_default is explicitly set to True, any existing default will be unmarked.

        Args:
            db: The database session.
            obj_in: The approval policy data.
            account_id: The ID of the account.

        Returns:
            The created approval policy.
        """
        # Convert to dict if it's a Pydantic model
        if isinstance(obj_in, ApprovalPolicyCreate):
            obj_data = obj_in.model_dump(exclude_unset=True)
        else:
            obj_data = obj_in.copy()

        # Ensure account_id is set
        obj_data["account_id"] = account_id

        # Check if this is the first policy for the account
        existing_count = (
            db.query(self.model).filter(self.model.account_id == account_id).count()
        )

        # If no policies exist, make this one default
        if existing_count == 0:
            obj_data["is_default"] = True
        elif obj_data.get("is_default", False):
            # If explicitly setting as default, unmark existing default
            self._unmark_default(db, account_id)

        # Create the policy
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: models.ApprovalPolicy,
        obj_in: Union[ApprovalPolicyUpdate, Dict[str, Any]],
    ) -> models.ApprovalPolicy:
        """Update an approval policy.

        If is_default is set to True, any existing default will be unmarked.

        Args:
            db: The database session.
            db_obj: The existing approval policy object.
            obj_in: The update data.

        Returns:
            The updated approval policy.
        """
        # Convert to dict if it's a Pydantic model
        if isinstance(obj_in, ApprovalPolicyUpdate):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in.copy()

        # If setting as default, unmark existing default
        if update_data.get("is_default", False) and not db_obj.is_default:
            self._unmark_default(db, db_obj.account_id)

        # Update the object
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def _unmark_default(self, db: Session, account_id: str) -> None:
        """Unmark any existing default policy for the account.

        Args:
            db: The database session.
            account_id: The ID of the account.
        """
        existing_default = self.get_default(db, account_id)
        if existing_default:
            existing_default.is_default = False
            db.add(existing_default)
            db.flush()  # Flush but don't commit yet

    def remove(
        self, db: Session, *, id: UUID, account_id: str
    ) -> Optional[models.ApprovalPolicy]:
        """Remove an approval policy by its ID.

        If removing the default policy and other policies exist, the most recently
        created remaining policy will be marked as default.

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
            .order_by(self.model.created_at.desc())
            .first()
        )
        if db_policy:
            was_default = db_policy.is_default
            db.delete(db_policy)
            db.flush()

            # If we deleted the default policy, make another one default
            if was_default:
                replacement = (
                    db.query(self.model)
                    .filter(self.model.account_id == account_id)
                    .order_by(self.model.created_at.desc())
                    .first()
                )
                if replacement:
                    replacement.is_default = True
                    db.add(replacement)

            db.commit()
        return db_policy


# Async helper functions
async def get_approval_policy_async(
    db: Session, policy_id: UUID
) -> Optional[models.ApprovalPolicy]:
    """Async: Retrieve an approval policy by its ID.

    Args:
        db: The async database session.
        policy_id: The ID of the approval policy.

    Returns:
        The approval policy object if found, otherwise None.
    """
    result = await db.execute(
        select(models.ApprovalPolicy).where(models.ApprovalPolicy.id == policy_id)
    )
    return result.scalar_one_or_none()
