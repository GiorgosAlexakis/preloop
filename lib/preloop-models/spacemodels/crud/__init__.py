"""CRUD operation implementations."""

# Create CRUD instances for each model
from ..models import (
    Account,
    ApiKey,
    ApiUsage,
    EmbeddingModel,
    Issue,
    IssueEmbedding,
    AIModel,
    Organization,
    Project,
    Tracker,
    TrackerScopeRule,
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
from .tracker_scope_rule import CRUDTrackerScopeRule
from .ai_model import CRUDAIModel
from .webhook import CRUDWebhook
from .issue_compliance_result import (
    CRUDIssueComplianceResult,
    issue_compliance_result,
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
crud_ai_model = CRUDAIModel(AIModel)
# crud_comment is already instantiated in its own file
crud_webhook = CRUDWebhook(Webhook)
crud_flow = CRUDFlow()  # Instantiate CRUDFlow
crud_tracker_scope_rule = CRUDTrackerScopeRule(TrackerScopeRule)

__all__ = [
    "CRUDBase",
    "CRUDAccount",
    "CRUDTracker",
    "CRUDTrackerScopeRule",
    "CRUDOrganization",
    # "crud_create_organization", # Removed export
    "CRUDProject",
    "CRUDIssue",
    "CRUDEmbeddingModel",
    "CRUDIssueEmbedding",
    "CRUDApiKey",
    "CRUDApiUsage",
    "CRUDComment",
    "CRUDAIModel",
    "CRUDFlow",
    "CRUDIssueComplianceResult",
    "crud_account",
    "crud_tracker",
    "crud_tracker_scope_rule",
    "crud_organization",
    "crud_project",
    "crud_issue",
    "crud_embedding_model",
    "crud_issue_embedding",
    "crud_api_key",
    "crud_api_usage",
    "crud_comment",
    "crud_ai_model",
    "crud_webhook",
    "crud_flow",
    "issue_compliance_result",
]
