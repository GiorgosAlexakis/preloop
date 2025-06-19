"""CRUD operations for LLMModel model."""

from typing import Optional

from sqlalchemy.orm import Session

from spacemodels.models.llm_model import LLMModel
from .base import CRUDBase


class CRUDLLMModel(CRUDBase[LLMModel]):
    """CRUD class for LLMModel operations."""

    def get_default_active_model(self, db: Session) -> Optional[LLMModel]:
        """Get the default, active LLMModel for the system."""
        return db.query(self.model).filter(self.model.is_default).first()

    def create_with_account(
        self,
        db: Session,
        *,
        name: str,
        provider_name: str,
        api_key: str,
        api_url: str,
        model_name: str,
        model_version: Optional[str] = None,
        is_default: Optional[bool] = False,
        account_id: Optional[str] = None,
    ) -> LLMModel:
        """Create a new LLMModel linked to an account."""
        if is_default:
            db.query(self.model).filter(
                self.model.account_id == account_id, self.model.is_default
            ).update({"is_default": False})

        db_obj = self.model(
            name=name,
            provider_name=provider_name,
            api_key=api_key,
            api_url=api_url,
            model_name=model_name,
            model_version=model_version,
            is_default=is_default,
            account_id=account_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_by_account_id(
        self, db: Session, *, account_id: Optional[str] = None
    ) -> list[LLMModel]:
        """Get all LLMModels for a specific account."""
        return db.query(self.model).filter(self.model.account_id == account_id).all()

    def get_default_by_account_id(
        self, db: Session, *, account_id: Optional[str] = None
    ) -> Optional[LLMModel]:
        """Get the default LLMModel for a specific account."""
        return (
            db.query(self.model)
            .filter(self.model.account_id == account_id, self.model.is_default)
            .first()
        )

    def update(
        self,
        db: Session,
        *,
        db_obj: LLMModel,
        name: Optional[str] = None,
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> LLMModel:
        """Update an LLMModel. If setting a model as default, ensure others are not."""

        # Only populate non null update data
        update_data = {
            "name": name,
            "provider_name": provider_name,
            "api_key": api_key,
            "api_url": api_url,
            "model_name": model_name,
            "model_version": model_version,
            "is_default": is_default,
        }

        # Remove null values from update data
        update_data = {k: v for k, v in update_data.items() if v is not None}

        if update_data.get("is_default") and not db_obj.is_default:
            # Set all other models for this account to not be default
            db.query(self.model).filter(
                self.model.account_id == db_obj.account_id,
                self.model.id != db_obj.id,
                self.model.is_default,
            ).update({"is_default": False})

        return super().update(db, db_obj=db_obj, obj_in=update_data)


llm_model = CRUDLLMModel(LLMModel)
