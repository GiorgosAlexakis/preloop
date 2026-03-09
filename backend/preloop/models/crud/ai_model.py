"""CRUD operations for AIModel model."""

import uuid
from typing import Dict, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from preloop.models.models.ai_model import AIModel
from preloop.models.crud.secret_reference import crud_secret_reference
from preloop.services.secret_service import get_secret_service
from .base import CRUDBase


class CRUDAIModel(CRUDBase[AIModel]):
    """CRUD class for AIModel operations."""

    @staticmethod
    def _apply_secret_reference_fields(
        db: Session,
        *,
        obj_data: Dict,
        account_id,
        secret_name: str,
        existing_secret_id=None,
    ) -> None:
        """Resolve incoming credential fields into a SecretReference."""
        api_key = obj_data.pop("api_key", None) if "api_key" in obj_data else None
        credentials_backend_type = obj_data.pop("credentials_backend_type", None)
        credentials_external_ref = obj_data.pop("credentials_external_ref", None)
        credentials_meta_data = obj_data.pop("credentials_meta_data", None)

        if api_key:
            secret_ref = get_secret_service().create_local_secret_reference(
                db,
                account_id=account_id,
                name=secret_name,
                secret_kind="ai_model_api_key",
                secret_value=api_key,
                existing_secret_id=existing_secret_id,
            )
            obj_data["credentials_secret_id"] = secret_ref.id
            obj_data["api_key"] = None
            return

        if (
            credentials_backend_type
            or credentials_external_ref
            or credentials_meta_data
        ):
            secret_ref = get_secret_service().create_external_secret_reference(
                db,
                account_id=account_id,
                name=secret_name,
                secret_kind="ai_model_api_key",
                backend_type=credentials_backend_type,
                external_ref=credentials_external_ref,
                meta_data=credentials_meta_data,
                existing_secret_id=existing_secret_id,
            )
            obj_data["credentials_secret_id"] = secret_ref.id
            obj_data["api_key"] = None

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
        obj_data = dict(obj_in)
        if obj_in.get("is_default"):
            db.query(self.model).filter(
                self.model.account_id == account_id, self.model.is_default
            ).update({"is_default": False})

        self._apply_secret_reference_fields(
            db,
            obj_data=obj_data,
            account_id=account_id,
            secret_name=f"AI Model Credential: {obj_data.get('name', 'Unnamed Model')}",
        )

        db_obj = self.model(**obj_data, account_id=account_id)
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

        obj_data = dict(obj_in)
        self._apply_secret_reference_fields(
            db,
            obj_data=obj_data,
            account_id=db_obj.account_id,
            secret_name=f"AI Model Credential: {obj_data.get('name', db_obj.name)}",
            existing_secret_id=db_obj.credentials_secret_id,
        )

        return super().update(db, db_obj=db_obj, obj_in=obj_data)

    def remove(self, db: Session, *, id: uuid.UUID) -> Optional[AIModel]:
        """Delete an AIModel and any unreferenced credential secret."""
        obj = db.get(self.model, id)
        if obj is None:
            return None

        secret_id = obj.credentials_secret_id
        db.delete(obj)
        db.flush()

        if secret_id is not None:
            remaining_reference = (
                db.query(self.model.id)
                .filter(self.model.credentials_secret_id == secret_id)
                .first()
            )
            if remaining_reference is None:
                secret_ref = crud_secret_reference.get(db, id=secret_id)
                if secret_ref is not None:
                    db.delete(secret_ref)

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
