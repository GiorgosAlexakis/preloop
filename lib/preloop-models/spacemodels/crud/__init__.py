"""CRUD operation implementations."""

from .base import CRUDBase
from .account import CRUDAccount
from .tracker import CRUDTracker
from .organization import CRUDOrganization
from .project import CRUDProject
from .issue import CRUDIssue
from .embedding import CRUDEmbeddingModel, CRUDIssueEmbedding
from .api_key import CRUDApiKey
from .api_usage import CRUDApiUsage

# Create CRUD instances for each model
from ..models import (
    Account,
    Tracker,
    Organization,
    Project,
    Issue,
    EmbeddingModel,
    IssueEmbedding,
    ApiKey,
    ApiUsage,
)

crud_account = CRUDAccount(Account)
crud_tracker = CRUDTracker(Tracker)
crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)
crud_issue = CRUDIssue(Issue)
crud_embedding_model = CRUDEmbeddingModel(EmbeddingModel)
crud_issue_embedding = CRUDIssueEmbedding(IssueEmbedding)
crud_api_key = CRUDApiKey(ApiKey)
crud_api_usage = CRUDApiUsage(ApiUsage)

__all__ = [
    "CRUDBase",
    "CRUDAccount",
    "CRUDTracker",
    "CRUDOrganization",
    "CRUDProject",
    "CRUDIssue",
    "CRUDEmbeddingModel",
    "CRUDIssueEmbedding",
    "CRUDApiKey",
    "CRUDApiUsage",
    "crud_account",
    "crud_tracker",
    "crud_organization",
    "crud_project",
    "crud_issue",
    "crud_embedding_model",
    "crud_issue_embedding",
    "crud_api_key",
    "crud_api_usage",
]
