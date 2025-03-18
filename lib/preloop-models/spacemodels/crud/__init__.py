"""CRUD operation implementations."""

from .base import CRUDBase
from .account import CRUDAccount
from .tracker import CRUDTracker
from .organization import CRUDOrganization
from .project import CRUDProject
from .issue import CRUDIssue
from .embedding import CRUDEmbeddingModel, CRUDIssueEmbedding

# Create CRUD instances for each model
from ..models import (
    Account,
    Tracker,
    Organization,
    Project,
    Issue,
    EmbeddingModel,
    IssueEmbedding,
)

crud_account = CRUDAccount(Account)
crud_tracker = CRUDTracker(Tracker)
crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)
crud_issue = CRUDIssue(Issue)
crud_embedding_model = CRUDEmbeddingModel(EmbeddingModel)
crud_issue_embedding = CRUDIssueEmbedding(IssueEmbedding)

__all__ = [
    "CRUDBase",
    "CRUDAccount",
    "CRUDTracker",
    "CRUDOrganization",
    "CRUDProject",
    "CRUDIssue",
    "CRUDEmbeddingModel",
    "CRUDIssueEmbedding",
    "crud_account",
    "crud_tracker",
    "crud_organization",
    "crud_project",
    "crud_issue",
    "crud_embedding_model",
    "crud_issue_embedding",
]
