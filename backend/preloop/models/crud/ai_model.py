"""CRUD operations for AIModel model."""

import uuid
from typing import Dict, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from preloop.models.models.ai_model import AIModel
from .base import CRUDBase


class CRUDAIModel(CRUDBase[AIModel]):
    """CRUD class for AIModel operations."""

    def get_default_active_model(
        self, db: Session, *, account_id: Optional[str] = None
    ) -> Optional[AIModel]:
        """
        Get the default, active AIModel for a given account.
        If account_id is None, gets the system-wide default.
        If account_id is provided, returns account-specific default or falls back to system-wide default.
        """
        query = db.query(self.model).filter(self.model.is_default)
        if account_id is not None:
            query = query.filter(
                or_(
                    self.model.account_id.is_(None), self.model.account_id == account_id
                )
            )
        else:
            query = query.filter(self.model.account_id.is_(None))

        return query.order_by(self.model.account_id).first()

    def create_with_account(
        self,
        db: Session,
        *,
        obj_in: Dict,
        account_id: Optional[str] = None,
    ) -> AIModel:
        """Create a new AIModel, assigning it to an account."""
        if obj_in.get("is_default"):
            db.query(self.model).filter(
                self.model.account_id == account_id, self.model.is_default
            ).update({"is_default": False})

        db_obj = self.model(**obj_in, account_id=account_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_account(self, db: Session, *, account_id: str) -> list[AIModel]:
        """Get all AIModels for a specific account."""
        return db.query(self.model).filter(self.model.account_id == account_id).all()

    def update(
        self,
        db: Session,
        *,
        db_obj: AIModel,
        obj_in: Dict,
    ) -> AIModel:
        """Update an AIModel. If setting a model as default, ensure others are not."""
        if obj_in.get("is_default") and not db_obj.is_default:
            # Set all other models for this account to not be default
            db.query(self.model).filter(
                self.model.account_id == db_obj.account_id,
                self.model.id != db_obj.id,
                self.model.is_default,
            ).update({"is_default": False})

        return super().update(db, db_obj=db_obj, obj_in=obj_in)

    def remove(self, db: Session, *, id: uuid.UUID) -> AIModel:
        """Delete an AIModel."""
        obj = db.get(self.model, id)
        db.delete(obj)
        db.commit()
        return obj

    def default_model_exists(self, db: Session) -> bool:
        """Check if a system-wide default model exists."""
        return (
            db.query(self.model.id)
            .filter(self.model.is_default, self.model.account_id.is_(None))
            .first()
            is not None
        )


ai_model = CRUDAIModel(AIModel)
