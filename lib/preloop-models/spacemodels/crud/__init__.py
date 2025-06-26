"""CRUD operation implementations."""

# Create CRUD instances for each model
from ..models import (
    Account,
    ApiKey,
    ApiUsage,
    EmbeddingModel,
    Issue,
    IssueEmbedding,
    LLMModel,  # Add LLMModel model import
    Organization,
    Project,
    Tracker,
    Webhook,
)
from .account import CRUDAccount
from .api_key import CRUDApiKey
from .api_usage import CRUDApiUsage
from .base import CRUDBase
from .comment import CRUDComment, crud_comment
from .embedding import CRUDEmbeddingModel, CRUDIssueEmbedding
from .flow import CRUDFlow  # Import CRUDFlow class
from .issue import CRUDIssue
from .organization import CRUDOrganization  # Removed create_organization import
from .project import CRUDProject
from .tracker import CRUDTracker
from .llm_model import CRUDLLMModel
from .webhook import CRUDWebhook

crud_account = CRUDAccount(Account)
crud_tracker = CRUDTracker(Tracker)
crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)
crud_issue = CRUDIssue(Issue)
crud_embedding_model = CRUDEmbeddingModel(EmbeddingModel)
crud_issue_embedding = CRUDIssueEmbedding(IssueEmbedding)
crud_api_key = CRUDApiKey(ApiKey)
crud_api_usage = CRUDApiUsage(ApiUsage)
crud_llm_model = CRUDLLMModel(LLMModel)  # Instantiate crud_llm_model
# crud_comment is already instantiated in its own file
crud_webhook = CRUDWebhook(Webhook)
crud_flow = CRUDFlow()  # Instantiate CRUDFlow

__all__ = [
    "CRUDBase",
    "CRUDAccount",
    "CRUDTracker",
    "CRUDOrganization",
    # "crud_create_organization", # Removed export
    "CRUDProject",
    "CRUDIssue",
    "CRUDEmbeddingModel",
    "CRUDIssueEmbedding",
    "CRUDApiKey",
    "CRUDApiUsage",
    "CRUDComment",
    "CRUDLLMModel",
    "CRUDFlow",
    "crud_account",
    "crud_tracker",
    "crud_organization",
    "crud_project",
    "crud_issue",
    "crud_embedding_model",
    "crud_issue_embedding",
    "crud_api_key",
    "crud_api_usage",
    "crud_comment",
    "crud_llm_model",
    "crud_webhook",
    "crud_flow",
]
