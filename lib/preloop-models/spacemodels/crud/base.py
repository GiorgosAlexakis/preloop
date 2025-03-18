"""Base CRUD class for all models."""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from ..models.base import Base

# Define a generic type variable for models that inherit from Base
ModelType = TypeVar("ModelType", bound=Base)


class CRUDBase(Generic[ModelType]):
    """Base class for CRUD operations on models."""

    def __init__(self, model: Type[ModelType]):
        """Initialize with a model class."""
        self.model = model

    def get(self, db: Session, id: str) -> Optional[ModelType]:
        """Get entity by ID."""
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100, **filters
    ) -> List[ModelType]:
        """Get multiple entities with optional filtering."""
        query = db.query(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> ModelType:
        """Create new entity."""
        if "id" not in obj_in:
            obj_in["id"] = self.model.generate_id()

        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: ModelType, obj_in: Dict[str, Any]
    ) -> ModelType:
        """Update an entity."""
        # Update model attributes from obj_in
        obj_data = db_obj.to_dict()
        for field in obj_data:
            if field in obj_in:
                setattr(db_obj, field, obj_in[field])

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, id: str) -> Optional[ModelType]:
        """Delete an entity by ID."""
        obj = db.query(self.model).get(id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
