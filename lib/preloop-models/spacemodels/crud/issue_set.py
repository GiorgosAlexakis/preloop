"""CRUD operations for the IssueSet model."""

from typing import List, Dict, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..models.issue_set import IssueSet
from .base import CRUDBase


class CRUDIssueSet(CRUDBase[IssueSet]):
    """CRUD operations for IssueSet model."""

    def get_supersets_by_issues(
        self,
        db: Session,
        *,
        issue_ids: List[str],
        ai_model_id: uuid.UUID,
        account_id: str,
    ) -> List[IssueSet]:
        """
        Finds all IssueSets that are supersets of the given list of issue_ids
        for a specific ai_model_id and account_id.

        Args:
            db: The database session.
            issue_ids: A list of issue IDs to check for containment.
            ai_model_id: The ID of the AI model associated with the sets.
            account_id: The ID of the account owning the AI model.

        Returns:
            A list of matching IssueSet objects.
        """
        return (
            db.query(self.model)
            .join(self.model.ai_model)
            .filter(
                self.model.ai_model_id == ai_model_id,
                self.model.issue_ids.contains(issue_ids),
                or_(
                    self.model.ai_model.has(account_id=account_id),
                    self.model.ai_model.has(account_id=None),
                ),
            )
            .all()
        )

    def create_and_remove_subsets(
        self,
        db: Session,
        *,
        name: str,
        issue_ids: List[str],
        ai_model_id: uuid.UUID,
        account_id: str,
        meta_data: Optional[Dict] = None,
    ) -> IssueSet:
        """
        Creates a new IssueSet and removes any existing IssueSets that are subsets
        of the new set for the same AI model and account.

        Args:
            db: The database session.
            name: The name of the IssueSet to create.
            issue_ids: A list of issue IDs for the new set.
            ai_model_id: The ID of the AI model associated with the set.
            account_id: The ID of the account owning the AI model.
            meta_data: Additional metadata for the new set.

        Returns:
            The newly created IssueSet object.
        """
        # Find and delete all existing subsets for this AI model and account
        subsets = (
            db.query(self.model)
            .join(self.model.ai_model)
            .filter(
                self.model.ai_model_id == ai_model_id,
                self.model.issue_ids.contained_by(issue_ids),
                self.model.ai_model.has(account_id=account_id),
            )
            .all()
        )

        for subset in subsets:
            db.delete(subset)

        # Create the new superset
        new_issue_set = self.model(
            name=name,
            issue_ids=issue_ids,
            ai_model_id=ai_model_id,
            meta_data=meta_data,
        )
        db.add(new_issue_set)
        db.commit()
        db.refresh(new_issue_set)
        return new_issue_set


crud_issue_set = CRUDIssueSet(IssueSet)
