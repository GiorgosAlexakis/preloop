"""CRUD operation implementations."""

# Create CRUD instances for each model
from ..models import (
    Account,
    ApiKey,
    ApiUsage,
    AuditLog,
    EmbeddingModel,
    Issue,
    IssueEmbedding,
    AIModel,
    Organization,
    Project,
    TrackerScopeRule,
    Webhook,
    IssueRelationship,
    IssueSet,
)
from .account import CRUDAccount
from .api_key import CRUDApiKey
from .api_usage import CRUDApiUsage
from .audit_log import CRUDAuditLog
from .base import CRUDBase
from .comment import CRUDComment, crud_comment
from .embedding import CRUDEmbeddingModel, CRUDIssueEmbedding
from .flow import CRUDFlow  # Import CRUDFlow class
from .flow_execution import CRUDFlowExecution
from .issue import CRUDIssue
from .organization import CRUDOrganization  # Removed create_organization import
from .project import CRUDProject
from .tracker import CRUDTracker, crud_tracker
from .tracker_scope_rule import CRUDTrackerScopeRule
from .ai_model import CRUDAIModel
from .webhook import CRUDWebhook
from .issue_compliance_result import (
    CRUDIssueComplianceResult,
    issue_compliance_result,
)
from .issue_relationship import CRUDIssueRelationship
from .issue_set import CRUDIssueSet
from .tool_configuration import CRUDToolConfiguration
from .mcp_server import CRUDMCPServer
from .mcp_tool import CRUDMCPTool
from .approval_policy import CRUDApprovalPolicy
from .approval_request import CRUDApprovalRequest, crud_approval_request
from .plan import (
    CRUDPlan,
    CRUDSubscription,
    CRUDMonthlyUsage,
    plan,
    subscription,
    monthly_usage,
)
from .user import CRUDUser, crud_user
from .permission import (
    CRUDPermission,
    CRUDRole,
    CRUDUserRole,
    CRUDTeamRole,
    crud_permission,
    crud_role,
    crud_user_role,
    crud_team_role,
)
from .team import CRUDTeam, crud_team
from .user_invitation import CRUDUserInvitation, crud_user_invitation
from .registration_token import CRUDRegistrationToken, crud_registration_token
from .issue_duplicate import CRUDIssueDuplicate, crud_issue_duplicate
from .instance import CRUDInstance, crud_instance
from . import tool_approval_condition
from . import notification_preferences

crud_account = CRUDAccount(Account)
# crud_tracker is already instantiated in tracker.py
crud_organization = CRUDOrganization(Organization)
crud_project = CRUDProject(Project)
crud_issue = CRUDIssue(Issue)
crud_embedding_model = CRUDEmbeddingModel(EmbeddingModel)
crud_issue_embedding = CRUDIssueEmbedding(IssueEmbedding)
crud_api_key = CRUDApiKey(ApiKey)
crud_api_usage = CRUDApiUsage(ApiUsage)
crud_audit_log = CRUDAuditLog(AuditLog)
crud_ai_model = CRUDAIModel(AIModel)
# crud_comment is already instantiated in its own file
crud_webhook = CRUDWebhook(Webhook)
crud_flow = CRUDFlow()  # Instantiate CRUDFlow
crud_flow_execution = CRUDFlowExecution()  # Instantiate CRUDFlowExecution
crud_tracker_scope_rule = CRUDTrackerScopeRule(TrackerScopeRule)
crud_issue_relationship = CRUDIssueRelationship(IssueRelationship)
crud_issue_set = CRUDIssueSet(IssueSet)
crud_tool_configuration = CRUDToolConfiguration()  # Instantiate CRUDToolConfiguration
crud_mcp_server = CRUDMCPServer()  # Instantiate CRUDMCPServer
crud_mcp_tool = CRUDMCPTool()  # Instantiate CRUDMCPTool
crud_approval_policy = CRUDApprovalPolicy()  # Instantiate CRUDApprovalPolicy

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
    "CRUDAuditLog",
    "CRUDComment",
    "CRUDAIModel",
    "CRUDFlow",
    "CRUDFlowExecution",
    "CRUDIssueComplianceResult",
    "CRUDIssueSet",
    "CRUDToolConfiguration",
    "CRUDMCPServer",
    "CRUDMCPTool",
    "CRUDApprovalPolicy",
    "CRUDApprovalRequest",
    "CRUDPlan",
    "CRUDSubscription",
    "CRUDMonthlyUsage",
    "CRUDUser",
    "CRUDPermission",
    "CRUDRole",
    "CRUDUserRole",
    "CRUDTeamRole",
    "CRUDTeam",
    "CRUDUserInvitation",
    "CRUDRegistrationToken",
    "CRUDIssueDuplicate",
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
    "crud_audit_log",
    "crud_comment",
    "crud_ai_model",
    "crud_webhook",
    "crud_flow",
    "crud_flow_execution",
    "crud_issue_relationship",
    "issue_compliance_result",
    "crud_issue_set",
    "crud_tool_configuration",
    "crud_mcp_server",
    "crud_mcp_tool",
    "crud_approval_policy",
    "crud_approval_request",
    "plan",
    "subscription",
    "monthly_usage",
    "crud_user",
    "crud_permission",
    "crud_role",
    "crud_user_role",
    "crud_team_role",
    "crud_team",
    "crud_user_invitation",
    "crud_registration_token",
    "crud_issue_duplicate",
    "CRUDInstance",
    "crud_instance",
    "tool_approval_condition",
    "notification_preferences",
]
