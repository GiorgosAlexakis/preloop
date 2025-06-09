"""CRUD operation implementations."""

# Create CRUD instances for each model
from ..models import (
    Account,
    ApiKey,
    ApiUsage,
    EmbeddingModel,
    Issue,
    IssueEmbedding,
    Organization,
    Project,
    Tracker,
)
from .account import CRUDAccount
from .api_key import CRUDApiKey
from .api_usage import CRUDApiUsage
from .base import CRUDBase
from .comment import CRUDComment, crud_comment  # Add this import
from .embedding import CRUDEmbeddingModel, CRUDIssueEmbedding
from .issue import CRUDIssue
from .organization import CRUDOrganization
from .project import CRUDProject
from .tracker import CRUDTracker

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
    "CRUDComment",  # Add this
    "crud_account",
    "crud_tracker",
    "crud_organization",
    "crud_project",
    "crud_issue",
    "crud_embedding_model",
    "crud_issue_embedding",
    "crud_api_key",
    "crud_api_usage",
    "crud_comment",  # Add this
]
