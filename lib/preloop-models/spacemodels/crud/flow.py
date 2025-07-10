import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from .. import models, schemas
from .base import CRUDBase


class CRUDFlow(CRUDBase[models.Flow]):
    """CRUD operations for Flow model."""

    def __init__(self):
        """Initialize with the Flow model."""
        super().__init__(model=models.Flow)

    def get(self, db: Session, id: uuid.UUID) -> Optional[models.Flow]:
        """
        Retrieve a flow by its ID.

        Args:
            db: The database session.
            id: The ID of the flow to retrieve.

        Returns:
            The flow object if found, otherwise None.
        """
        return db.query(self.model).filter(self.model.id == id).first()

    def get_by_organization(
        self,
        db: Session,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        account_id: Optional[str] = None,
    ) -> List[models.Flow]:
        """
        Retrieve flows for a specific organization with pagination.
        """
        query = db.query(self.model).filter(
            self.model.organization_id == organization_id
        )
        if account_id:
            query = query.filter(self.model.created_by_user_id == account_id)
        return query.offset(skip).limit(limit).all()

    def create(self, db: Session, *, flow_in: schemas.FlowCreate) -> models.Flow:
        """
        Create a new flow.

        Args:
            db: The database session.
            flow_in: The data for the new flow.

        Returns:
            The created flow object.
        """
        db_flow = self.model(**flow_in.model_dump())
        db.add(db_flow)
        db.commit()
        db.refresh(db_flow)
        return db_flow

    def update(
        self, db: Session, *, db_obj: models.Flow, flow_in: schemas.FlowUpdate
    ) -> models.Flow:
        """
        Update an existing flow.

        Args:
            db: The database session.
            db_obj: The existing flow object to update.
            flow_in: The new data for the flow.

        Returns:
            The updated flow object.
        """
        update_data = flow_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: uuid.UUID) -> Optional[models.Flow]:
        """
        Remove a flow by its ID.

        Args:
            db: The database session.
            id: The ID of the flow to remove.

        Returns:
            The removed flow object if found and deleted, otherwise None.
        """
        db_flow = db.query(self.model).filter(self.model.id == id).first()
        if db_flow:
            db.delete(db_flow)
            db.commit()
        return db_flow
