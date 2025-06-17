"""CRUD operations for LLMProvider model."""

from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from spacemodels.models.llm_provider import LLMProvider
from spacebridge.schemas.llm_provider import LLMProviderCreate, LLMProviderUpdate
from .base import CRUDBase


class CRUDLLMProvider(CRUDBase[LLMProvider]):
    """CRUD class for LLMProvider operations."""

    def get_default_active_provider(self, db: Session) -> Optional[LLMProvider]:
        """Get the default, active LLMProvider for the system."""
        return db.query(self.model).filter(self.model.is_default is True).first()

    def create_with_account(
        self,
        db: Session,
        *,
        obj_in: LLMProviderCreate,
        account_id: int,
    ) -> LLMProvider:
        """Create a new LLMProvider linked to an account."""
        if obj_in.is_default:
            db.query(self.model).filter(
                self.model.account_id == account_id, self.model.is_default is True
            ).update({"is_default": False})

        db_obj = self.model(**obj_in.model_dump(), account_id=account_id)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_account_id(self, db: Session, *, account_id: int) -> list[LLMProvider]:
        """Get all LLMProviders for a specific account."""
        return db.query(self.model).filter(self.model.account_id == account_id).all()

    def get_default_by_account_id(
        self, db: Session, *, account_id: int
    ) -> Optional[LLMProvider]:
        """Get the default LLMProvider for a specific account."""
        return (
            db.query(self.model)
            .filter(self.model.account_id == account_id, self.model.is_default is True)
            .first()
        )

    def update(
        self,
        db: Session,
        *,
        db_obj: LLMProvider,
        obj_in: Union[LLMProviderUpdate, Dict[str, Any]],
    ) -> LLMProvider:
        """Update an LLMProvider. If setting a provider as default, ensure others are not."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        if update_data.get("is_default") is True and db_obj.is_default is False:
            # Set all other providers for this account to not be default
            db.query(self.model).filter(
                self.model.account_id == db_obj.account_id,
                self.model.id != db_obj.id,
                self.model.is_default is True,
            ).update({"is_default": False})

        return super().update(db, db_obj=db_obj, obj_in=update_data)


llm_provider = CRUDLLMProvider(LLMProvider)
