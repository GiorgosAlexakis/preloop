import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import {
  getTools,
  getApprovalPolicies,
  createApprovalPolicy,
  updateApprovalPolicy,
  deleteApprovalPolicy,
  createToolConfiguration,
  updateToolConfiguration,
  getUsers,
  getTeams,
  getFeatures,
  fetchWithAuth,
} from '../../api';
import type { Tool, ApprovalPolicy } from '../../components/tool-card';
import '../../components/view-header';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/switch/switch.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio/radio.js';
import '@shoelace-style/shoelace/dist/components/range/range.js';
import '@shoelace-style/shoelace/dist/components/tab-group/tab-group.js';
import '@shoelace-style/shoelace/dist/components/tab/tab.js';
import '@shoelace-style/shoelace/dist/components/tab-panel/tab-panel.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';
import '@shoelace-style/shoelace/dist/components/copy-button/copy-button.js';
import consoleStyles from '../../styles/console-styles.css?inline';

// Types for tool access rules
interface ToolAccessRule {
  toolName: string;
  source: string;
  sourceId: string | null;
  sourceName: string;
  action: 'allow' | 'deny' | 'require_approval';
  policyId: string | null;
  condition: string | null;
  isEnabled: boolean;
  configId: string | null;
}

// Types for policy file history
interface PolicyFileHistory {
  id: string;
  filename: string;
  appliedAt: string;
  summary: string;
  status: 'applied' | 'pending' | 'failed';
}

// Types for diff result
interface DiffChange {
  type: 'added' | 'removed' | 'modified';
  category: 'mcp_servers' | 'approval_policies' | 'tools';
  name: string;
  details?: string;
}

interface PolicyDiffResult {
  summary: string;
  has_changes: boolean;
  changes: {
    added: DiffChange[];
    removed: DiffChange[];
    modified: DiffChange[];
  };
}

// Types for policy versions
interface PolicyVersion {
  id: string;
  version_number: number;
  tag: string | null;
  description: string | null;
  created_at: string;
  created_by_username: string | null;
  is_active: boolean;
  snapshot_summary: {
    mcp_servers_count: number;
    tools_count: number;
    policies_count: number;
  };
}

interface CreateVersionRequest {
  description?: string;
  tag?: string;
}

interface RollbackResponse {
  success: boolean;
  message: string;
  preview_only: boolean;
  changes?: PolicyDiffResult;
  rolled_back_to_version?: number;
}

interface PruneOptions {
  keep_days?: number;
  keep_tagged?: boolean;
  min_versions_to_keep?: number;
}

interface PruneResponse {
  deleted_count: number;
  remaining_count: number;
}

@customElement('policies-view')
export class PoliciesView extends LitElement {
  @state() private _activeTab = 'access';
  @state() private _tools: Tool[] = [];
  @state() private _approvalPolicies: ApprovalPolicy[] = [];
  @state() private _loading = false;
  @state() private _error: string | null = null;
  @state() private _features: { [key: string]: boolean } = {};

  // Access policies state
  @state() private _toolAccessRules: ToolAccessRule[] = [];
  @state() private _expandedTools: Set<string> = new Set();

  // Approval policies state
  @state() private _showPolicyDialog = false;
  @state() private _editingPolicy: ApprovalPolicy | null = null;
  @state() private _policyForm = {
    name: '',
    description: '',
    approvalType: 'standard',
    approvalsRequired: 1,
    timeoutSeconds: 300,
    isDefault: false,
    webhookUrl: '',
    channel: '',
    user: '',
    approverUserIds: [] as string[],
    approverTeamIds: [] as string[],
    // AI-driven fields
    aiModel: '',
    aiGuidelines: '',
    aiConfidenceThreshold: 0.8,
    aiFallbackBehavior: 'escalate' as 'escalate' | 'approve' | 'deny',
    escalationPolicyId: '',
  };
  @state() private _availableUsers: Array<{
    id: string;
    username: string;
    email: string;
  }> = [];
  @state() private _availableTeams: Array<{ id: string; name: string }> = [];

  // Policy files state
  @state() private _policyFileHistory: PolicyFileHistory[] = [];
  @state() private _showDiffDialog = false;
  @state() private _diffResult: PolicyDiffResult | null = null;
  @state() private _pendingFile: File | null = null;
  @state() private _isUploading = false;
  @state() private _isExporting = false;

  // Version management state
  @state() private _versions: PolicyVersion[] = [];
  @state() private _loadingVersions = false;
  @state() private _selectedVersion: PolicyVersion | null = null;
  @state() private _expandedVersions: Set<string> = new Set();
  @state() private _showSaveVersionDialog = false;
  @state() private _showPruneDialog = false;
  @state() private _showTagDialog = false;
  @state() private _showRollbackDialog = false;
  @state() private _rollbackPreview: RollbackResponse | null = null;
  @state() private _savingVersion = false;
  @state() private _pruningVersions = false;
  @state() private _rollingBack = false;
  @state() private _taggingVersion = false;
  @state() private _deletingVersion = false;
  @state() private _versionForm = {
    description: '',
    tag: '',
  };
  @state() private _pruneForm = {
    keepDays: 30,
    keepTagged: true,
    minVersionsToKeep: 5,
  };
  @state() private _tagForm = {
    tag: '',
  };
  @state() private _versionToTag: PolicyVersion | null = null;
  @state() private _versionToRollback: PolicyVersion | null = null;

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      :host {
        display: block;
      }

      .tabs-container {
        margin-bottom: var(--sl-spacing-large);
      }

      sl-tab-group {
        --indicator-color: var(--sl-color-primary-600);
      }

      sl-tab::part(base) {
        font-size: var(--sl-font-size-medium);
        padding: var(--sl-spacing-medium) var(--sl-spacing-large);
      }

      sl-tab-panel {
        padding-top: var(--sl-spacing-large);
      }

      /* Access Policies Tab */
      .access-rules-list {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-medium);
      }

      .access-rule-card {
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        overflow: hidden;
      }

      .access-rule-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-50);
        cursor: pointer;
        transition: background 0.2s;
      }

      .access-rule-header:hover {
        background: var(--sl-color-neutral-100);
      }

      .access-rule-info {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-medium);
        flex: 1;
      }

      .access-rule-name {
        font-weight: var(--sl-font-weight-semibold);
        color: var(--sl-color-neutral-900);
      }

      .access-rule-source {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
      }

      .access-rule-actions {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
      }

      .access-rule-details {
        padding: var(--sl-spacing-medium);
        border-top: 1px solid var(--sl-color-neutral-200);
        background: var(--sl-color-neutral-0);
      }

      .rule-row {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-medium);
        padding: var(--sl-spacing-small) 0;
      }

      .rule-label {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-700);
        min-width: 120px;
      }

      .rule-value {
        flex: 1;
      }

      /* Approval Policies Tab */
      .policies-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
        gap: var(--sl-spacing-large);
      }

      .policy-card {
        display: flex;
        flex-direction: column;
        height: 100%;
      }

      .policy-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: var(--sl-spacing-small);
      }

      .policy-name {
        font-size: var(--sl-font-size-large);
        font-weight: var(--sl-font-weight-semibold);
        margin: 0;
      }

      .policy-description {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
        margin: 0 0 var(--sl-spacing-medium) 0;
        line-height: 1.5;
      }

      .policy-meta {
        display: flex;
        flex-wrap: wrap;
        gap: var(--sl-spacing-small);
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-600);
      }

      .policy-meta-item {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-2x-small);
      }

      sl-card::part(footer) {
        display: flex;
        justify-content: flex-end;
        gap: var(--sl-spacing-small);
        padding: var(--sl-spacing-medium);
        border-top: 1px solid var(--sl-color-neutral-200);
      }

      /* Policy Files Tab */
      .policy-files-container {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }

      .policy-files-actions {
        display: flex;
        gap: var(--sl-spacing-medium);
        flex-wrap: wrap;
      }

      .upload-area {
        border: 2px dashed var(--sl-color-neutral-300);
        border-radius: var(--sl-border-radius-large);
        padding: var(--sl-spacing-2x-large);
        text-align: center;
        background: var(--sl-color-neutral-50);
        transition: all 0.2s;
      }

      .upload-area:hover {
        border-color: var(--sl-color-primary-400);
        background: var(--sl-color-primary-50);
      }

      .upload-area.drag-over {
        border-color: var(--sl-color-primary-600);
        background: var(--sl-color-primary-100);
      }

      .upload-icon {
        font-size: 3rem;
        color: var(--sl-color-neutral-400);
        margin-bottom: var(--sl-spacing-medium);
      }

      .upload-text {
        font-size: var(--sl-font-size-medium);
        color: var(--sl-color-neutral-700);
        margin-bottom: var(--sl-spacing-small);
      }

      .upload-hint {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-500);
      }

      .history-list {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-small);
      }

      .history-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-50);
        border-radius: var(--sl-border-radius-medium);
        border-left: 3px solid var(--sl-color-primary-600);
      }

      .history-item.failed {
        border-left-color: var(--sl-color-danger-600);
      }

      .history-info {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-2x-small);
      }

      .history-filename {
        font-weight: var(--sl-font-weight-semibold);
      }

      .history-meta {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
      }

      /* Diff view */
      .diff-container {
        max-height: 400px;
        overflow-y: auto;
      }

      .diff-section {
        margin-bottom: var(--sl-spacing-large);
      }

      .diff-section-title {
        font-weight: var(--sl-font-weight-semibold);
        margin-bottom: var(--sl-spacing-small);
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
      }

      .diff-item {
        padding: var(--sl-spacing-small) var(--sl-spacing-medium);
        margin: var(--sl-spacing-2x-small) 0;
        border-radius: var(--sl-border-radius-small);
        font-size: var(--sl-font-size-small);
      }

      .diff-item.added {
        background: var(--sl-color-success-100);
        border-left: 3px solid var(--sl-color-success-600);
      }

      .diff-item.removed {
        background: var(--sl-color-danger-100);
        border-left: 3px solid var(--sl-color-danger-600);
      }

      .diff-item.modified {
        background: var(--sl-color-warning-100);
        border-left: 3px solid var(--sl-color-warning-600);
      }

      /* Loading */
      .loading-container {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 200px;
      }

      /* Form styles */
      .form-field {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-2x-small);
        margin-bottom: var(--sl-spacing-medium);
      }

      .form-label {
        font-size: var(--sl-font-size-small);
        font-weight: var(--sl-font-weight-semibold);
        color: var(--sl-color-neutral-700);
      }

      .form-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--sl-spacing-medium);
      }

      /* Dialog styles */
      sl-dialog::part(panel) {
        max-width: 600px;
      }

      .dialog-footer {
        display: flex;
        justify-content: flex-end;
        gap: var(--sl-spacing-small);
      }

      /* Version management styles */
      .versions-section {
        margin-top: var(--sl-spacing-large);
      }

      .versions-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: var(--sl-spacing-medium);
      }

      .versions-header h3 {
        margin: 0;
        font-size: var(--sl-font-size-large);
        font-weight: var(--sl-font-weight-semibold);
      }

      .versions-actions {
        display: flex;
        gap: var(--sl-spacing-small);
      }

      .version-list {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-small);
      }

      .version-item {
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        overflow: hidden;
        background: var(--sl-color-neutral-0);
      }

      .version-item.active {
        border-color: var(--sl-color-primary-400);
        border-width: 2px;
      }

      .version-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-50);
        cursor: pointer;
        transition: background 0.2s;
      }

      .version-header:hover {
        background: var(--sl-color-neutral-100);
      }

      .version-info {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-medium);
        flex: 1;
      }

      .version-number {
        font-weight: var(--sl-font-weight-bold);
        font-size: var(--sl-font-size-medium);
        color: var(--sl-color-neutral-900);
        min-width: 60px;
      }

      .version-meta {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-2x-small);
      }

      .version-description {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-700);
      }

      .version-date {
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-500);
      }

      .version-badges {
        display: flex;
        gap: var(--sl-spacing-x-small);
        align-items: center;
      }

      .version-actions {
        display: flex;
        gap: var(--sl-spacing-2x-small);
        align-items: center;
      }

      .version-details {
        padding: var(--sl-spacing-medium);
        border-top: 1px solid var(--sl-color-neutral-200);
        background: var(--sl-color-neutral-0);
      }

      .version-stats {
        display: flex;
        gap: var(--sl-spacing-large);
        flex-wrap: wrap;
      }

      .version-stat {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-x-small);
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
      }

      .version-stat sl-icon {
        color: var(--sl-color-neutral-500);
      }

      .empty-versions {
        text-align: center;
        padding: var(--sl-spacing-2x-large);
        color: var(--sl-color-neutral-500);
      }

      .rollback-preview {
        margin-top: var(--sl-spacing-medium);
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-50);
        border-radius: var(--sl-border-radius-medium);
      }

      .rollback-warning {
        display: flex;
        align-items: flex-start;
        gap: var(--sl-spacing-small);
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-warning-100);
        border-radius: var(--sl-border-radius-medium);
        margin-bottom: var(--sl-spacing-medium);
      }

      .rollback-warning sl-icon {
        color: var(--sl-color-warning-700);
        flex-shrink: 0;
      }
    `,
  ];

  connectedCallback() {
    super.connectedCallback();
    this.loadData();
  }

  private async loadData() {
    this._loading = true;
    this._error = null;

    try {
      const [tools, policies, featuresResponse] = await Promise.all([
        getTools(),
        getApprovalPolicies(),
        getFeatures(),
      ]);

      this._tools = tools;
      this._approvalPolicies = policies;
      this._features = featuresResponse.features || {};

      // Build tool access rules from tools
      this._toolAccessRules = this._tools.map((tool) => ({
        toolName: tool.name,
        source: tool.source,
        sourceId: tool.source_id,
        sourceName: tool.source_name,
        action: tool.approval_policy_id
          ? 'require_approval'
          : tool.is_enabled
            ? 'allow'
            : 'deny',
        policyId: tool.approval_policy_id,
        condition: tool.has_approval_condition ? '(condition set)' : null,
        isEnabled: tool.is_enabled,
        configId: tool.config_id,
      }));

      // Load users and teams if advanced approvals feature is enabled
      if (this._features['advanced_approvals']) {
        await this.loadUsersAndTeams();
      }
    } catch (err: any) {
      this._error = err.message || 'Failed to load data';
      console.error('Error loading policies data:', err);
    } finally {
      this._loading = false;
    }
  }

  private async loadUsersAndTeams() {
    try {
      const [usersResponse, teamsResponse] = await Promise.all([
        getUsers(),
        getTeams(),
      ]);
      this._availableUsers = usersResponse.users || [];
      this._availableTeams = teamsResponse.teams || [];
    } catch (error) {
      console.error('Failed to load users and teams:', error);
    }
  }

  private hasAdvancedApprovals(): boolean {
    return this._features['advanced_approvals'] === true;
  }

  private toggleToolExpanded(toolKey: string) {
    const newExpanded = new Set(this._expandedTools);
    if (newExpanded.has(toolKey)) {
      newExpanded.delete(toolKey);
    } else {
      newExpanded.add(toolKey);
    }
    this._expandedTools = newExpanded;
  }

  private getToolKey(rule: ToolAccessRule): string {
    return `${rule.toolName}-${rule.source}-${rule.sourceId || 'null'}`;
  }

  private async handleAccessActionChange(
    rule: ToolAccessRule,
    newAction: 'allow' | 'deny' | 'require_approval'
  ) {
    try {
      const tool = this._tools.find(
        (t) =>
          t.name === rule.toolName &&
          t.source === rule.source &&
          t.source_id === rule.sourceId
      );

      if (!tool) return;

      if (newAction === 'deny') {
        // Disable the tool
        if (tool.config_id) {
          await updateToolConfiguration(tool.config_id, {
            is_enabled: false,
            approval_policy_id: null,
          });
        } else {
          await createToolConfiguration({
            tool_name: tool.name,
            tool_source: tool.source,
            mcp_server_id: tool.source_id,
            is_enabled: false,
            account_id: '',
          });
        }
      } else if (newAction === 'allow') {
        // Enable the tool without approval
        if (tool.config_id) {
          await updateToolConfiguration(tool.config_id, {
            is_enabled: true,
            approval_policy_id: null,
          });
        } else {
          await createToolConfiguration({
            tool_name: tool.name,
            tool_source: tool.source,
            mcp_server_id: tool.source_id,
            is_enabled: true,
            account_id: '',
          });
        }
      } else if (newAction === 'require_approval') {
        // Enable with default approval policy
        const defaultPolicy =
          this._approvalPolicies.find((p) => p.is_default) ||
          this._approvalPolicies[0];
        if (tool.config_id) {
          await updateToolConfiguration(tool.config_id, {
            is_enabled: true,
            approval_policy_id: defaultPolicy?.id || null,
          });
        } else {
          await createToolConfiguration({
            tool_name: tool.name,
            tool_source: tool.source,
            mcp_server_id: tool.source_id,
            is_enabled: true,
            approval_policy_id: defaultPolicy?.id || null,
            account_id: '',
          });
        }
      }

      await this.loadData();
    } catch (err: any) {
      this._error = err.message || 'Failed to update tool access';
    }
  }

  private openPolicyDialog(policy: ApprovalPolicy | null = null) {
    this._editingPolicy = policy;
    if (policy) {
      this._policyForm = {
        name: policy.name,
        description: policy.description || '',
        approvalType: policy.approval_type,
        approvalsRequired: policy.approvals_required || 1,
        timeoutSeconds: policy.timeout_seconds || 300,
        isDefault: policy.is_default || false,
        webhookUrl: policy.approval_config?.webhook_url || '',
        channel: policy.channel || '',
        user: policy.user || '',
        approverUserIds: policy.approver_user_ids || [],
        approverTeamIds: policy.approver_team_ids || [],
        // AI-driven fields
        aiModel: policy.ai_model || '',
        aiGuidelines: policy.ai_guidelines || '',
        aiConfidenceThreshold: policy.ai_confidence_threshold ?? 0.8,
        aiFallbackBehavior: policy.ai_fallback_behavior || 'escalate',
        escalationPolicyId: policy.escalation_policy_id || '',
      };
    } else {
      this._policyForm = {
        name: '',
        description: '',
        approvalType: 'standard',
        approvalsRequired: 1,
        timeoutSeconds: 300,
        isDefault: false,
        webhookUrl: '',
        channel: '',
        user: '',
        approverUserIds: [],
        approverTeamIds: [],
        // AI-driven fields
        aiModel: '',
        aiGuidelines: '',
        aiConfidenceThreshold: 0.8,
        aiFallbackBehavior: 'escalate',
        escalationPolicyId: '',
      };
    }
    this._showPolicyDialog = true;
  }

  private closePolicyDialog() {
    this._showPolicyDialog = false;
    this._editingPolicy = null;
  }

  private async savePolicy() {
    try {
      const policyData: any = {
        name: this._policyForm.name,
        description: this._policyForm.description || null,
        approval_type: this._policyForm.approvalType,
        approvals_required: this._policyForm.approvalsRequired,
        timeout_seconds: this._policyForm.timeoutSeconds,
        is_default: this._policyForm.isDefault,
        channel: this._policyForm.channel || null,
        user: this._policyForm.user || null,
      };

      if (this._policyForm.webhookUrl) {
        policyData.approval_config = {
          webhook_url: this._policyForm.webhookUrl,
        };
      }

      if (this._policyForm.approverUserIds.length > 0) {
        policyData.approver_user_ids = this._policyForm.approverUserIds;
      }

      if (this._policyForm.approverTeamIds.length > 0) {
        policyData.approver_team_ids = this._policyForm.approverTeamIds;
      }

      // AI-driven fields
      if (this._policyForm.approvalType === 'ai_driven') {
        policyData.ai_model = this._policyForm.aiModel;
        policyData.ai_guidelines = this._policyForm.aiGuidelines || null;
        policyData.ai_confidence_threshold =
          this._policyForm.aiConfidenceThreshold;
        policyData.ai_fallback_behavior = this._policyForm.aiFallbackBehavior;
        if (
          this._policyForm.aiFallbackBehavior === 'escalate' &&
          this._policyForm.escalationPolicyId
        ) {
          policyData.escalation_policy_id = this._policyForm.escalationPolicyId;
        }
      }

      if (this._editingPolicy) {
        await updateApprovalPolicy(this._editingPolicy.id, policyData);
      } else {
        await createApprovalPolicy(policyData);
      }

      this.closePolicyDialog();
      await this.loadData();
    } catch (err: any) {
      this._error = err.message || 'Failed to save policy';
    }
  }

  private async deletePolicy(policy: ApprovalPolicy) {
    if (
      !confirm(
        `Are you sure you want to delete the policy "${policy.name}"? This cannot be undone.`
      )
    ) {
      return;
    }

    try {
      await deleteApprovalPolicy(policy.id);
      await this.loadData();
    } catch (err: any) {
      this._error = err.message || 'Failed to delete policy';
    }
  }

  private async handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    await this.previewPolicyFile(file);
    input.value = '';
  }

  private async previewPolicyFile(file: File) {
    this._pendingFile = file;
    this._isUploading = true;

    try {
      // Get diff preview
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetchWithAuth('/api/v1/policies/diff', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail?.message || 'Failed to preview policy');
      }

      this._diffResult = await response.json();
      this._showDiffDialog = true;
    } catch (err: any) {
      this._error = err.message || 'Failed to preview policy file';
    } finally {
      this._isUploading = false;
    }
  }

  private async applyPolicyFile() {
    if (!this._pendingFile) return;

    this._isUploading = true;

    try {
      const formData = new FormData();
      formData.append('file', this._pendingFile);

      const response = await fetchWithAuth('/api/v1/policies/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail?.message || 'Failed to apply policy');
      }

      this._showDiffDialog = false;
      this._pendingFile = null;
      this._diffResult = null;

      await this.loadData();
    } catch (err: any) {
      this._error = err.message || 'Failed to apply policy file';
    } finally {
      this._isUploading = false;
    }
  }

  private async exportPolicies() {
    this._isExporting = true;

    try {
      const response = await fetchWithAuth(
        '/api/v1/policies/export?format=yaml'
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to export policies');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'policies.yaml';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      this._error = err.message || 'Failed to export policies';
    } finally {
      this._isExporting = false;
    }
  }

  // ============================================================================
  // Version Management API Methods
  // ============================================================================

  private async loadVersions() {
    this._loadingVersions = true;
    try {
      const response = await fetchWithAuth(
        '/api/v1/policies/versions?limit=50'
      );
      if (!response.ok) {
        throw new Error('Failed to fetch versions');
      }
      this._versions = await response.json();
    } catch (err: any) {
      this._error = err.message || 'Failed to load versions';
    } finally {
      this._loadingVersions = false;
    }
  }

  private async createVersion() {
    this._savingVersion = true;
    try {
      const body: CreateVersionRequest = {};
      if (this._versionForm.description.trim()) {
        body.description = this._versionForm.description.trim();
      }
      if (this._versionForm.tag.trim()) {
        body.tag = this._versionForm.tag.trim();
      }

      const response = await fetchWithAuth('/api/v1/policies/versions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          error.detail?.message || error.detail || 'Failed to save version'
        );
      }

      this._showSaveVersionDialog = false;
      this._versionForm = { description: '', tag: '' };
      await this.loadVersions();
    } catch (err: any) {
      this._error = err.message || 'Failed to save version';
    } finally {
      this._savingVersion = false;
    }
  }

  private async rollbackToVersion(versionId: string, previewOnly: boolean) {
    if (previewOnly) {
      this._rollingBack = true;
    }
    try {
      const response = await fetchWithAuth(
        `/api/v1/policies/versions/${versionId}/rollback`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ preview_only: previewOnly }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          error.detail?.message || error.detail || 'Failed to rollback'
        );
      }

      const result: RollbackResponse = await response.json();

      if (previewOnly) {
        this._rollbackPreview = result;
        this._showRollbackDialog = true;
      } else {
        this._showRollbackDialog = false;
        this._rollbackPreview = null;
        this._versionToRollback = null;
        // Refresh everything after successful rollback
        await Promise.all([this.loadData(), this.loadVersions()]);
      }
    } catch (err: any) {
      this._error = err.message || 'Failed to rollback to version';
    } finally {
      this._rollingBack = false;
    }
  }

  private async tagVersion(versionId: string, tag: string) {
    this._taggingVersion = true;
    try {
      const response = await fetchWithAuth(
        `/api/v1/policies/versions/${versionId}/tag`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tag: tag.trim() || null }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          error.detail?.message || error.detail || 'Failed to update tag'
        );
      }

      this._showTagDialog = false;
      this._versionToTag = null;
      this._tagForm = { tag: '' };
      await this.loadVersions();
    } catch (err: any) {
      this._error = err.message || 'Failed to update tag';
    } finally {
      this._taggingVersion = false;
    }
  }

  private async deleteVersion(version: PolicyVersion) {
    if (
      !confirm(
        `Are you sure you want to delete version ${version.version_number}${version.tag ? ` (${version.tag})` : ''}? This cannot be undone.`
      )
    ) {
      return;
    }

    this._deletingVersion = true;
    try {
      const response = await fetchWithAuth(
        `/api/v1/policies/versions/${version.id}`,
        { method: 'DELETE' }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          error.detail?.message || error.detail || 'Failed to delete version'
        );
      }

      await this.loadVersions();
    } catch (err: any) {
      this._error = err.message || 'Failed to delete version';
    } finally {
      this._deletingVersion = false;
    }
  }

  private async pruneVersions() {
    this._pruningVersions = true;
    try {
      const body: PruneOptions = {
        keep_days: this._pruneForm.keepDays,
        keep_tagged: this._pruneForm.keepTagged,
        min_versions_to_keep: this._pruneForm.minVersionsToKeep,
      };

      const response = await fetchWithAuth('/api/v1/policies/versions/prune', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          error.detail?.message || error.detail || 'Failed to prune versions'
        );
      }

      const result: PruneResponse = await response.json();
      this._showPruneDialog = false;

      // Show success message
      const alertEl = document.createElement('sl-alert');
      alertEl.variant = 'success';
      alertEl.closable = true;
      alertEl.duration = 5000;
      alertEl.innerHTML = `
        <sl-icon slot="icon" name="check-circle"></sl-icon>
        Pruned ${result.deleted_count} old versions. ${result.remaining_count} versions remaining.
      `;
      document.body.appendChild(alertEl);
      alertEl.toast();

      await this.loadVersions();
    } catch (err: any) {
      this._error = err.message || 'Failed to prune versions';
    } finally {
      this._pruningVersions = false;
    }
  }

  private toggleVersionExpanded(versionId: string) {
    const newExpanded = new Set(this._expandedVersions);
    if (newExpanded.has(versionId)) {
      newExpanded.delete(versionId);
    } else {
      newExpanded.add(versionId);
    }
    this._expandedVersions = newExpanded;
  }

  private openTagDialog(version: PolicyVersion) {
    this._versionToTag = version;
    this._tagForm = { tag: version.tag || '' };
    this._showTagDialog = true;
  }

  private openRollbackPreview(version: PolicyVersion) {
    this._versionToRollback = version;
    this.rollbackToVersion(version.id, true);
  }

  private formatVersionDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  private renderAccessPoliciesTab() {
    const sortedRules = [...this._toolAccessRules].sort((a, b) => {
      // Sort by source first, then by name
      if (a.source !== b.source) {
        if (a.source === 'builtin') return -1;
        if (b.source === 'builtin') return 1;
      }
      return a.toolName.localeCompare(b.toolName);
    });

    return html`
      <div class="access-rules-list">
        ${sortedRules.length === 0
          ? html`
              <div class="empty-state">
                <sl-icon name="tools"></sl-icon>
                <p>No tools configured. Add an MCP server to get started.</p>
                <sl-button href="/console/tools" variant="primary">
                  Go to Tools
                </sl-button>
              </div>
            `
          : repeat(
              sortedRules,
              (rule) => this.getToolKey(rule),
              (rule) => this.renderAccessRuleCard(rule)
            )}
      </div>
    `;
  }

  private renderAccessRuleCard(rule: ToolAccessRule) {
    const toolKey = this.getToolKey(rule);
    const isExpanded = this._expandedTools.has(toolKey);
    const assignedPolicy = this._approvalPolicies.find(
      (p) => p.id === rule.policyId
    );

    return html`
      <div class="access-rule-card">
        <div
          class="access-rule-header"
          @click=${() => this.toggleToolExpanded(toolKey)}
        >
          <div class="access-rule-info">
            <sl-icon
              name=${isExpanded ? 'chevron-down' : 'chevron-right'}
            ></sl-icon>
            <div>
              <div class="access-rule-name">${rule.toolName}</div>
              <div class="access-rule-source">${rule.sourceName}</div>
            </div>
          </div>
          <div
            class="access-rule-actions"
            @click=${(e: Event) => e.stopPropagation()}
          >
            <sl-badge
              variant=${rule.action === 'allow'
                ? 'success'
                : rule.action === 'deny'
                  ? 'danger'
                  : 'warning'}
            >
              ${rule.action === 'allow'
                ? 'Allowed'
                : rule.action === 'deny'
                  ? 'Denied'
                  : 'Approval Required'}
            </sl-badge>
            <sl-select
              size="small"
              value=${rule.action}
              @sl-change=${(e: any) =>
                this.handleAccessActionChange(rule, e.target.value)}
              style="min-width: 160px;"
            >
              <sl-option value="allow">Allow</sl-option>
              <sl-option value="deny">Deny</sl-option>
              <sl-option value="require_approval">Require Approval</sl-option>
            </sl-select>
          </div>
        </div>
        ${isExpanded
          ? html`
              <div class="access-rule-details">
                <div class="rule-row">
                  <span class="rule-label">Source:</span>
                  <span class="rule-value">
                    <sl-badge variant="neutral" size="small">
                      ${rule.source}
                    </sl-badge>
                  </span>
                </div>
                <div class="rule-row">
                  <span class="rule-label">Enabled:</span>
                  <span class="rule-value">
                    ${rule.isEnabled ? 'Yes' : 'No'}
                  </span>
                </div>
                ${rule.action === 'require_approval'
                  ? html`
                      <div class="rule-row">
                        <span class="rule-label">Policy:</span>
                        <span class="rule-value">
                          ${assignedPolicy
                            ? assignedPolicy.name
                            : 'Default Policy'}
                        </span>
                      </div>
                      ${rule.condition
                        ? html`
                            <div class="rule-row">
                              <span class="rule-label">Condition:</span>
                              <span class="rule-value">
                                <code>${rule.condition}</code>
                              </span>
                            </div>
                          `
                        : ''}
                    `
                  : ''}
              </div>
            `
          : ''}
      </div>
    `;
  }

  private renderApprovalPoliciesTab() {
    return html`
      <div style="margin-bottom: var(--sl-spacing-large);">
        <sl-button variant="primary" @click=${() => this.openPolicyDialog()}>
          <sl-icon slot="prefix" name="plus-lg"></sl-icon>
          Create Policy
        </sl-button>
      </div>

      ${this._approvalPolicies.length === 0
        ? html`
            <div class="empty-state">
              <sl-icon name="shield-check"></sl-icon>
              <p>No approval policies configured yet.</p>
              <p
                style="font-size: var(--sl-font-size-small); color: var(--sl-color-neutral-500);"
              >
                Create an approval policy to require human review before tool
                executions.
              </p>
            </div>
          `
        : html`
            <div class="policies-grid">
              ${repeat(
                this._approvalPolicies,
                (policy) => policy.id,
                (policy) => this.renderPolicyCard(policy)
              )}
            </div>
          `}
      ${this.renderPolicyDialog()}
    `;
  }

  private renderPolicyCard(policy: ApprovalPolicy) {
    const isAiDriven = policy.approval_type === 'ai_driven';
    return html`
      <sl-card class="policy-card">
        <div class="card-content">
          <div class="policy-card-header">
            <h3 class="policy-name">${policy.name}</h3>
            <div style="display: flex; gap: var(--sl-spacing-x-small);">
              ${isAiDriven
                ? html`<sl-badge variant="warning">
                    <sl-icon name="robot" style="margin-right: 4px;"></sl-icon>
                    AI-Driven
                  </sl-badge>`
                : ''}
              ${policy.is_default
                ? html`<sl-badge variant="primary">Default</sl-badge>`
                : ''}
            </div>
          </div>
          <p class="policy-description">
            ${policy.description || 'No description'}
          </p>
          <div class="policy-meta">
            ${isAiDriven
              ? html`
                  <div class="policy-meta-item">
                    <sl-icon name="cpu"></sl-icon>
                    <span>${policy.ai_model || 'No model set'}</span>
                  </div>
                  <div class="policy-meta-item">
                    <sl-icon name="speedometer2"></sl-icon>
                    <span>
                      ${Math.round(
                        (policy.ai_confidence_threshold || 0.8) * 100
                      )}%
                      threshold
                    </span>
                  </div>
                  <div class="policy-meta-item">
                    <sl-badge variant="neutral" size="small">
                      ${policy.ai_fallback_behavior === 'escalate'
                        ? 'Escalates when uncertain'
                        : policy.ai_fallback_behavior === 'approve'
                          ? 'Auto-approves when uncertain'
                          : 'Auto-denies when uncertain'}
                    </sl-badge>
                  </div>
                `
              : html`
                  <div class="policy-meta-item">
                    <sl-icon name="clock"></sl-icon>
                    <span>${policy.timeout_seconds || 300}s timeout</span>
                  </div>
                  <div class="policy-meta-item">
                    <sl-icon name="people"></sl-icon>
                    <span>${policy.approvals_required || 1} approval(s)</span>
                  </div>
                  <div class="policy-meta-item">
                    <sl-badge variant="neutral" size="small">
                      ${policy.approval_type}
                    </sl-badge>
                  </div>
                `}
          </div>
        </div>
        <div slot="footer">
          <sl-button
            size="small"
            variant="danger"
            outline
            @click=${() => this.deletePolicy(policy)}
          >
            <sl-icon slot="prefix" name="trash"></sl-icon>
            Delete
          </sl-button>
          <sl-button size="small" @click=${() => this.openPolicyDialog(policy)}>
            <sl-icon slot="prefix" name="pencil"></sl-icon>
            Edit
          </sl-button>
        </div>
      </sl-card>
    `;
  }

  private renderPolicyDialog() {
    // Get standard policies for escalation dropdown
    const standardPolicies = this._approvalPolicies.filter(
      (p) => p.approval_type === 'standard'
    );

    return html`
      <sl-dialog
        label=${this._editingPolicy ? 'Edit Policy' : 'Create Policy'}
        ?open=${this._showPolicyDialog}
        @sl-request-close=${this.closePolicyDialog}
        style="--width: 650px;"
      >
        <div class="form-field">
          <label class="form-label">Policy Name *</label>
          <sl-input
            placeholder="e.g., Production Safeguards"
            .value=${this._policyForm.name}
            @sl-input=${(e: any) =>
              (this._policyForm = {
                ...this._policyForm,
                name: e.target.value,
              })}
          ></sl-input>
        </div>

        <div class="form-field">
          <label class="form-label">Description</label>
          <sl-textarea
            placeholder="Optional description"
            .value=${this._policyForm.description}
            @sl-input=${(e: any) =>
              (this._policyForm = {
                ...this._policyForm,
                description: e.target.value,
              })}
            rows="2"
          ></sl-textarea>
        </div>

        ${this.hasAdvancedApprovals()
          ? html`
              <div class="form-field">
                <label class="form-label">Approval Type</label>
                <sl-radio-group
                  .value=${this._policyForm.approvalType}
                  @sl-change=${(e: any) =>
                    (this._policyForm = {
                      ...this._policyForm,
                      approvalType: e.target.value,
                    })}
                >
                  <sl-radio value="standard">
                    Standard - Human approvers review requests
                  </sl-radio>
                  <sl-radio value="ai_driven">
                    AI-Driven - AI model automatically evaluates requests
                  </sl-radio>
                  <sl-radio value="slack">
                    Slack - Send approval requests to Slack
                  </sl-radio>
                  <sl-radio value="mattermost">
                    Mattermost - Send approval requests to Mattermost
                  </sl-radio>
                  <sl-radio value="webhook">
                    Webhook - Send approval requests to a webhook
                  </sl-radio>
                </sl-radio-group>
              </div>
            `
          : ''}

        <!-- AI Configuration Section -->
        ${this.hasAdvancedApprovals() &&
        this._policyForm.approvalType === 'ai_driven'
          ? html`
              <div
                class="ai-config-section"
                style="display: flex; flex-direction: column; gap: var(--sl-spacing-medium); padding: var(--sl-spacing-medium); background: var(--sl-color-primary-50); border: 1px solid var(--sl-color-primary-200); border-radius: var(--sl-border-radius-medium); margin-bottom: var(--sl-spacing-medium);"
              >
                <div
                  style="display: flex; align-items: center; gap: var(--sl-spacing-small); color: var(--sl-color-primary-700); font-weight: 500;"
                >
                  <sl-icon name="robot"></sl-icon>
                  AI Configuration
                </div>

                <div class="form-field">
                  <label class="form-label">AI Model *</label>
                  <sl-select
                    .value=${this._policyForm.aiModel}
                    @sl-change=${(e: any) =>
                      (this._policyForm = {
                        ...this._policyForm,
                        aiModel: e.target.value,
                      })}
                    placeholder="Select an AI model..."
                  >
                    <sl-option value="claude-sonnet-4-20250514"
                      >Claude Sonnet 4</sl-option
                    >
                    <sl-option value="gpt-4o">GPT-4o</sl-option>
                    <sl-option value="gpt-4-turbo">GPT-4 Turbo</sl-option>
                    <sl-option value="gemini-2.5-pro">Gemini 2.5 Pro</sl-option>
                  </sl-select>
                </div>

                <div class="form-field">
                  <label class="form-label">Guidelines</label>
                  <sl-textarea
                    .value=${this._policyForm.aiGuidelines}
                    @sl-input=${(e: any) =>
                      (this._policyForm = {
                        ...this._policyForm,
                        aiGuidelines: e.target.value,
                      })}
                    placeholder="APPROVE if:
- Read-only operations
- Non-production environments

DENY if:
- Production data modifications
- Credential access"
                    rows="8"
                    help-text="Instructions for the AI to determine when to approve or deny requests"
                  ></sl-textarea>
                </div>

                <div class="form-field">
                  <label class="form-label"
                    >Confidence Threshold:
                    ${Math.round(
                      this._policyForm.aiConfidenceThreshold * 100
                    )}%</label
                  >
                  <sl-range
                    .value=${this._policyForm.aiConfidenceThreshold * 100}
                    @sl-input=${(e: any) =>
                      (this._policyForm = {
                        ...this._policyForm,
                        aiConfidenceThreshold:
                          (parseFloat(e.target.value) || 80) / 100,
                      })}
                    min="0"
                    max="100"
                    step="5"
                    style="--thumb-size: 18px;"
                  ></sl-range>
                  <div
                    style="display: flex; justify-content: space-between; font-size: var(--sl-font-size-x-small); color: var(--sl-color-neutral-500); margin-top: var(--sl-spacing-2x-small);"
                  >
                    <span>0% (always escalate)</span>
                    <span>100% (very confident)</span>
                  </div>
                </div>

                <div class="form-field">
                  <label class="form-label">When Uncertain</label>
                  <sl-radio-group
                    .value=${this._policyForm.aiFallbackBehavior}
                    @sl-change=${(e: any) =>
                      (this._policyForm = {
                        ...this._policyForm,
                        aiFallbackBehavior: e.target.value,
                      })}
                  >
                    <sl-radio value="escalate"
                      >Escalate to human approvers</sl-radio
                    >
                    <sl-radio value="approve">Approve automatically</sl-radio>
                    <sl-radio value="deny">Deny automatically</sl-radio>
                  </sl-radio-group>
                </div>

                ${this._policyForm.aiFallbackBehavior === 'escalate'
                  ? html`
                      <div class="form-field">
                        <label class="form-label">Escalation Policy</label>
                        <sl-select
                          .value=${this._policyForm.escalationPolicyId}
                          @sl-change=${(e: any) =>
                            (this._policyForm = {
                              ...this._policyForm,
                              escalationPolicyId: e.target.value,
                            })}
                          placeholder="Select a policy for escalation..."
                          help-text="The approval policy to use when AI confidence is below threshold"
                        >
                          ${standardPolicies.map(
                            (p) => html`
                              <sl-option value=${p.id}>${p.name}</sl-option>
                            `
                          )}
                        </sl-select>
                        ${!this._policyForm.escalationPolicyId &&
                        standardPolicies.length > 0
                          ? html`
                              <div
                                style="display: flex; align-items: center; gap: var(--sl-spacing-x-small); margin-top: var(--sl-spacing-x-small); color: var(--sl-color-warning-700); font-size: var(--sl-font-size-small);"
                              >
                                <sl-icon name="exclamation-triangle"></sl-icon>
                                <span
                                  >No escalation policy selected. AI decisions
                                  below threshold will have no fallback.</span
                                >
                              </div>
                            `
                          : ''}
                        ${standardPolicies.length === 0
                          ? html`
                              <div
                                style="display: flex; align-items: center; gap: var(--sl-spacing-x-small); margin-top: var(--sl-spacing-x-small); color: var(--sl-color-warning-700); font-size: var(--sl-font-size-small);"
                              >
                                <sl-icon name="exclamation-triangle"></sl-icon>
                                <span
                                  >No standard policies available for
                                  escalation. Create one first.</span
                                >
                              </div>
                            `
                          : ''}
                      </div>
                    `
                  : ''}
              </div>
            `
          : ''}

        <!-- Standard approval settings (only for non-AI types) -->
        ${this._policyForm.approvalType !== 'ai_driven'
          ? html`
              <div class="form-row">
                <div class="form-field">
                  <label class="form-label">Approvals Required</label>
                  <sl-input
                    type="number"
                    min="1"
                    .value=${String(this._policyForm.approvalsRequired)}
                    @sl-input=${(e: any) =>
                      (this._policyForm = {
                        ...this._policyForm,
                        approvalsRequired: parseInt(e.target.value) || 1,
                      })}
                  ></sl-input>
                </div>
                <div class="form-field">
                  <label class="form-label">Timeout (seconds)</label>
                  <sl-input
                    type="number"
                    min="30"
                    .value=${String(this._policyForm.timeoutSeconds)}
                    @sl-input=${(e: any) =>
                      (this._policyForm = {
                        ...this._policyForm,
                        timeoutSeconds: parseInt(e.target.value) || 300,
                      })}
                  ></sl-input>
                </div>
              </div>
            `
          : ''}
        ${this.hasAdvancedApprovals() &&
        this._policyForm.approvalType !== 'standard' &&
        this._policyForm.approvalType !== 'ai_driven'
          ? html`
              <div class="form-field">
                <label class="form-label">Webhook URL</label>
                <sl-input
                  type="url"
                  placeholder="https://..."
                  .value=${this._policyForm.webhookUrl}
                  @sl-input=${(e: any) =>
                    (this._policyForm = {
                      ...this._policyForm,
                      webhookUrl: e.target.value,
                    })}
                ></sl-input>
              </div>
            `
          : ''}

        <div class="form-field">
          <div
            style="display: flex; justify-content: space-between; align-items: center;"
          >
            <label class="form-label">Set as Default</label>
            <sl-switch
              ?checked=${this._policyForm.isDefault}
              @sl-change=${(e: any) =>
                (this._policyForm = {
                  ...this._policyForm,
                  isDefault: e.target.checked,
                })}
            ></sl-switch>
          </div>
        </div>

        <div slot="footer" class="dialog-footer">
          <sl-button @click=${this.closePolicyDialog}>Cancel</sl-button>
          <sl-button
            variant="primary"
            @click=${this.savePolicy}
            ?disabled=${!this._policyForm.name.trim() ||
            (this._policyForm.approvalType === 'ai_driven' &&
              !this._policyForm.aiModel)}
          >
            ${this._editingPolicy ? 'Save Changes' : 'Create Policy'}
          </sl-button>
        </div>
      </sl-dialog>
    `;
  }

  private renderPolicyFilesTab() {
    // Load versions when tab is shown if not already loaded
    if (this._versions.length === 0 && !this._loadingVersions) {
      this.loadVersions();
    }

    return html`
      <div class="policy-files-container">
        <div class="policy-files-actions">
          <sl-button
            variant="primary"
            @click=${() =>
              this.shadowRoot
                ?.querySelector<HTMLInputElement>('#policy-file-input')
                ?.click()}
            ?loading=${this._isUploading}
          >
            <sl-icon slot="prefix" name="upload"></sl-icon>
            Import YAML
          </sl-button>
          <sl-button
            @click=${this.exportPolicies}
            ?loading=${this._isExporting}
          >
            <sl-icon slot="prefix" name="download"></sl-icon>
            Export YAML
          </sl-button>
          <input
            type="file"
            id="policy-file-input"
            accept=".yaml,.yml,.json"
            @change=${this.handleFileUpload}
            style="display: none"
          />
        </div>

        <sl-card>
          <div slot="header">Policy File Format</div>
          <p
            style="font-size: var(--sl-font-size-small); color: var(--sl-color-neutral-600); margin: 0 0 var(--sl-spacing-medium) 0;"
          >
            Preloop supports declarative policy-as-code using YAML files. Define
            MCP servers, approval policies, and tool configurations in a single
            file.
          </p>
          <sl-details summary="Example Policy File">
            <pre
              style="background: var(--sl-color-neutral-100); padding: var(--sl-spacing-medium); border-radius: var(--sl-border-radius-medium); font-size: var(--sl-font-size-small); overflow-x: auto;"
            ><code>version: "1.0"
metadata:
  name: "Production Safeguards"
  description: "Safety policies for production environment"

approval_policies:
  - name: "Critical Operations"
    approval_type: standard
    approvals_required: 2
    timeout_seconds: 600
    is_default: true

tools:
  - name: "shell"
    action: require_approval
    policy: "Critical Operations"
    condition: 'args.command.contains("rm") || args.command.contains("sudo")'

  - name: "file_write"
    action: require_approval
    policy: "Critical Operations"

defaults:
  require_approval: false
  enabled: true</code></pre>
          </sl-details>
        </sl-card>

        ${this._policyFileHistory.length > 0
          ? html`
              <sl-card>
                <div slot="header">Import History</div>
                <div class="history-list">
                  ${repeat(
                    this._policyFileHistory,
                    (item) => item.id,
                    (item) => html`
                      <div
                        class="history-item ${item.status === 'failed'
                          ? 'failed'
                          : ''}"
                      >
                        <div class="history-info">
                          <span class="history-filename">${item.filename}</span>
                          <span class="history-meta">
                            ${item.appliedAt} - ${item.summary}
                          </span>
                        </div>
                        <sl-badge
                          variant=${item.status === 'applied'
                            ? 'success'
                            : item.status === 'failed'
                              ? 'danger'
                              : 'neutral'}
                        >
                          ${item.status}
                        </sl-badge>
                      </div>
                    `
                  )}
                </div>
              </sl-card>
            `
          : ''}

        <!-- Version Management Section -->
        ${this.renderVersionsSection()}
      </div>

      ${this.renderDiffDialog()} ${this.renderSaveVersionDialog()}
      ${this.renderPruneVersionsDialog()} ${this.renderTagVersionDialog()}
      ${this.renderRollbackConfirmDialog()}
    `;
  }

  private renderVersionsSection() {
    return html`
      <div class="versions-section">
        <div class="versions-header">
          <h3>Version History</h3>
          <div class="versions-actions">
            <sl-button
              size="small"
              variant="primary"
              @click=${() => (this._showSaveVersionDialog = true)}
            >
              <sl-icon slot="prefix" name="save"></sl-icon>
              Save Version
            </sl-button>
            <sl-button
              size="small"
              @click=${() => (this._showPruneDialog = true)}
              ?disabled=${this._versions.length === 0}
            >
              <sl-icon slot="prefix" name="trash"></sl-icon>
              Prune Old Versions
            </sl-button>
            <sl-button
              size="small"
              @click=${() => this.loadVersions()}
              ?loading=${this._loadingVersions}
            >
              <sl-icon slot="prefix" name="arrow-clockwise"></sl-icon>
              Refresh
            </sl-button>
          </div>
        </div>

        ${this._loadingVersions
          ? html`
              <div class="loading-container">
                <sl-spinner></sl-spinner>
              </div>
            `
          : this._versions.length === 0
            ? html`
                <div class="empty-versions">
                  <sl-icon
                    name="clock-history"
                    style="font-size: 3rem; margin-bottom: var(--sl-spacing-medium);"
                  ></sl-icon>
                  <p>No versions saved yet.</p>
                  <p style="font-size: var(--sl-font-size-small);">
                    Save a version to create a snapshot of your current policy
                    configuration.
                  </p>
                </div>
              `
            : html`
                <div class="version-list">
                  ${repeat(
                    this._versions,
                    (v) => v.id,
                    (version) => this.renderVersionItem(version)
                  )}
                </div>
              `}
      </div>
    `;
  }

  private renderVersionItem(version: PolicyVersion) {
    const isExpanded = this._expandedVersions.has(version.id);

    return html`
      <div class="version-item ${version.is_active ? 'active' : ''}">
        <div
          class="version-header"
          @click=${() => this.toggleVersionExpanded(version.id)}
        >
          <div class="version-info">
            <sl-icon
              name=${isExpanded ? 'chevron-down' : 'chevron-right'}
            ></sl-icon>
            <span class="version-number">v${version.version_number}</span>
            <div class="version-meta">
              <span class="version-description">
                ${version.description || 'No description'}
              </span>
              <span class="version-date">
                ${this.formatVersionDate(version.created_at)}
                ${version.created_by_username
                  ? ` by ${version.created_by_username}`
                  : ''}
              </span>
            </div>
          </div>
          <div class="version-badges">
            ${version.is_active
              ? html`<sl-badge variant="success">Active</sl-badge>`
              : ''}
            ${version.tag
              ? html`<sl-badge variant="primary">${version.tag}</sl-badge>`
              : ''}
          </div>
          <div
            class="version-actions"
            @click=${(e: Event) => e.stopPropagation()}
          >
            <sl-tooltip content="View Diff">
              <sl-icon-button
                name="file-diff"
                @click=${() => this.openRollbackPreview(version)}
                ?disabled=${version.is_active}
              ></sl-icon-button>
            </sl-tooltip>
            <sl-tooltip content="Rollback to this version">
              <sl-icon-button
                name="arrow-counterclockwise"
                @click=${() => this.openRollbackPreview(version)}
                ?disabled=${version.is_active}
              ></sl-icon-button>
            </sl-tooltip>
            <sl-tooltip content="Edit Tag">
              <sl-icon-button
                name="tag"
                @click=${() => this.openTagDialog(version)}
              ></sl-icon-button>
            </sl-tooltip>
            <sl-tooltip content="Delete">
              <sl-icon-button
                name="trash"
                @click=${() => this.deleteVersion(version)}
                ?disabled=${version.is_active || this._deletingVersion}
              ></sl-icon-button>
            </sl-tooltip>
          </div>
        </div>
        ${isExpanded
          ? html`
              <div class="version-details">
                <div class="version-stats">
                  <div class="version-stat">
                    <sl-icon name="hdd-network"></sl-icon>
                    <span>
                      ${version.snapshot_summary.mcp_servers_count} MCP servers
                    </span>
                  </div>
                  <div class="version-stat">
                    <sl-icon name="tools"></sl-icon>
                    <span>${version.snapshot_summary.tools_count} tools</span>
                  </div>
                  <div class="version-stat">
                    <sl-icon name="shield-check"></sl-icon>
                    <span>
                      ${version.snapshot_summary.policies_count} policies
                    </span>
                  </div>
                </div>
              </div>
            `
          : ''}
      </div>
    `;
  }

  private renderSaveVersionDialog() {
    return html`
      <sl-dialog
        label="Save Version"
        ?open=${this._showSaveVersionDialog}
        @sl-request-close=${() => (this._showSaveVersionDialog = false)}
      >
        <p style="margin-top: 0;">
          Create a snapshot of your current policy configuration. You can
          rollback to this version later if needed.
        </p>

        <div class="form-field">
          <label class="form-label">Description</label>
          <sl-textarea
            placeholder="Optional description of this version"
            .value=${this._versionForm.description}
            @sl-input=${(e: any) =>
              (this._versionForm = {
                ...this._versionForm,
                description: e.target.value,
              })}
            rows="3"
          ></sl-textarea>
        </div>

        <div class="form-field">
          <label class="form-label">Tag (optional)</label>
          <sl-input
            placeholder="e.g., production-v1, stable, release-2024-01"
            .value=${this._versionForm.tag}
            @sl-input=${(e: any) =>
              (this._versionForm = {
                ...this._versionForm,
                tag: e.target.value,
              })}
          ></sl-input>
          <small style="color: var(--sl-color-neutral-500);">
            Tagged versions can be protected from pruning.
          </small>
        </div>

        <div slot="footer" class="dialog-footer">
          <sl-button @click=${() => (this._showSaveVersionDialog = false)}>
            Cancel
          </sl-button>
          <sl-button
            variant="primary"
            @click=${() => this.createVersion()}
            ?loading=${this._savingVersion}
          >
            Save Version
          </sl-button>
        </div>
      </sl-dialog>
    `;
  }

  private renderPruneVersionsDialog() {
    return html`
      <sl-dialog
        label="Prune Old Versions"
        ?open=${this._showPruneDialog}
        @sl-request-close=${() => (this._showPruneDialog = false)}
      >
        <p style="margin-top: 0;">
          Remove old versions to save space. Configure the criteria for which
          versions to keep.
        </p>

        <div class="form-field">
          <label class="form-label">Keep versions newer than (days)</label>
          <sl-input
            type="number"
            min="1"
            .value=${String(this._pruneForm.keepDays)}
            @sl-input=${(e: any) =>
              (this._pruneForm = {
                ...this._pruneForm,
                keepDays: parseInt(e.target.value) || 30,
              })}
          ></sl-input>
        </div>

        <div class="form-field">
          <label class="form-label">Minimum versions to keep</label>
          <sl-input
            type="number"
            min="1"
            .value=${String(this._pruneForm.minVersionsToKeep)}
            @sl-input=${(e: any) =>
              (this._pruneForm = {
                ...this._pruneForm,
                minVersionsToKeep: parseInt(e.target.value) || 5,
              })}
          ></sl-input>
        </div>

        <div class="form-field">
          <div
            style="display: flex; justify-content: space-between; align-items: center;"
          >
            <label class="form-label" style="margin-bottom: 0;">
              Keep tagged versions
            </label>
            <sl-switch
              ?checked=${this._pruneForm.keepTagged}
              @sl-change=${(e: any) =>
                (this._pruneForm = {
                  ...this._pruneForm,
                  keepTagged: e.target.checked,
                })}
            ></sl-switch>
          </div>
          <small style="color: var(--sl-color-neutral-500);">
            Tagged versions will not be deleted regardless of age.
          </small>
        </div>

        <div slot="footer" class="dialog-footer">
          <sl-button @click=${() => (this._showPruneDialog = false)}>
            Cancel
          </sl-button>
          <sl-button
            variant="danger"
            @click=${() => this.pruneVersions()}
            ?loading=${this._pruningVersions}
          >
            Prune Versions
          </sl-button>
        </div>
      </sl-dialog>
    `;
  }

  private renderTagVersionDialog() {
    return html`
      <sl-dialog
        label="Edit Version Tag"
        ?open=${this._showTagDialog}
        @sl-request-close=${() => {
          this._showTagDialog = false;
          this._versionToTag = null;
        }}
      >
        ${this._versionToTag
          ? html`
              <p style="margin-top: 0;">
                Update the tag for version ${this._versionToTag.version_number}.
                Leave empty to remove the tag.
              </p>

              <div class="form-field">
                <label class="form-label">Tag</label>
                <sl-input
                  placeholder="e.g., production-v1, stable"
                  .value=${this._tagForm.tag}
                  @sl-input=${(e: any) =>
                    (this._tagForm = { tag: e.target.value })}
                ></sl-input>
              </div>

              <div slot="footer" class="dialog-footer">
                <sl-button
                  @click=${() => {
                    this._showTagDialog = false;
                    this._versionToTag = null;
                  }}
                >
                  Cancel
                </sl-button>
                <sl-button
                  variant="primary"
                  @click=${() =>
                    this.tagVersion(this._versionToTag!.id, this._tagForm.tag)}
                  ?loading=${this._taggingVersion}
                >
                  Save Tag
                </sl-button>
              </div>
            `
          : ''}
      </sl-dialog>
    `;
  }

  private renderRollbackConfirmDialog() {
    return html`
      <sl-dialog
        label="Rollback to Version"
        ?open=${this._showRollbackDialog}
        @sl-request-close=${() => {
          this._showRollbackDialog = false;
          this._rollbackPreview = null;
          this._versionToRollback = null;
        }}
        style="--width: 700px;"
      >
        ${this._versionToRollback
          ? html`
              <div class="rollback-warning">
                <sl-icon name="exclamation-triangle"></sl-icon>
                <div>
                  <strong>Warning:</strong> Rolling back will replace your
                  current policy configuration with the snapshot from version
                  ${this._versionToRollback.version_number}. This action cannot
                  be automatically undone.
                </div>
              </div>

              ${this._rollbackPreview
                ? html`
                    <p style="margin-top: 0;">
                      ${this._rollbackPreview.changes?.has_changes
                        ? 'The following changes will be made:'
                        : 'No changes would be made by this rollback.'}
                    </p>

                    ${this._rollbackPreview.changes?.has_changes
                      ? html`
                          <div class="diff-container">
                            ${this._rollbackPreview.changes.changes.added
                              .length > 0
                              ? html`
                                  <div class="diff-section">
                                    <div class="diff-section-title">
                                      <sl-icon
                                        name="plus-circle-fill"
                                        style="color: var(--sl-color-success-600);"
                                      ></sl-icon>
                                      Added
                                      (${this._rollbackPreview.changes.changes
                                        .added.length})
                                    </div>
                                    ${this._rollbackPreview.changes.changes.added.map(
                                      (change) => html`
                                        <div class="diff-item added">
                                          <strong>${change.category}:</strong>
                                          ${change.name}
                                        </div>
                                      `
                                    )}
                                  </div>
                                `
                              : ''}
                            ${this._rollbackPreview.changes.changes.modified
                              .length > 0
                              ? html`
                                  <div class="diff-section">
                                    <div class="diff-section-title">
                                      <sl-icon
                                        name="pencil-fill"
                                        style="color: var(--sl-color-warning-600);"
                                      ></sl-icon>
                                      Modified
                                      (${this._rollbackPreview.changes.changes
                                        .modified.length})
                                    </div>
                                    ${this._rollbackPreview.changes.changes.modified.map(
                                      (change) => html`
                                        <div class="diff-item modified">
                                          <strong>${change.category}:</strong>
                                          ${change.name}
                                        </div>
                                      `
                                    )}
                                  </div>
                                `
                              : ''}
                            ${this._rollbackPreview.changes.changes.removed
                              .length > 0
                              ? html`
                                  <div class="diff-section">
                                    <div class="diff-section-title">
                                      <sl-icon
                                        name="dash-circle-fill"
                                        style="color: var(--sl-color-danger-600);"
                                      ></sl-icon>
                                      Removed
                                      (${this._rollbackPreview.changes.changes
                                        .removed.length})
                                    </div>
                                    ${this._rollbackPreview.changes.changes.removed.map(
                                      (change) => html`
                                        <div class="diff-item removed">
                                          <strong>${change.category}:</strong>
                                          ${change.name}
                                        </div>
                                      `
                                    )}
                                  </div>
                                `
                              : ''}
                          </div>
                        `
                      : ''}
                  `
                : html`
                    <div class="loading-container">
                      <sl-spinner></sl-spinner>
                    </div>
                  `}

              <div slot="footer" class="dialog-footer">
                <sl-button
                  @click=${() => {
                    this._showRollbackDialog = false;
                    this._rollbackPreview = null;
                    this._versionToRollback = null;
                  }}
                >
                  Cancel
                </sl-button>
                <sl-button
                  variant="danger"
                  @click=${() =>
                    this.rollbackToVersion(this._versionToRollback!.id, false)}
                  ?loading=${this._rollingBack}
                  ?disabled=${!this._rollbackPreview?.changes?.has_changes}
                >
                  Confirm Rollback
                </sl-button>
              </div>
            `
          : ''}
      </sl-dialog>
    `;
  }

  private renderDiffDialog() {
    return html`
      <sl-dialog
        label="Preview Policy Changes"
        ?open=${this._showDiffDialog}
        @sl-request-close=${() => {
          this._showDiffDialog = false;
          this._pendingFile = null;
          this._diffResult = null;
        }}
        style="--width: 700px;"
      >
        ${this._diffResult
          ? html`
              <p style="margin-top: 0;">
                ${this._diffResult.summary ||
                (this._diffResult.has_changes
                  ? 'The following changes will be applied:'
                  : 'No changes detected.')}
              </p>
              ${this._diffResult.has_changes
                ? html`
                    <div class="diff-container">
                      ${this._diffResult.changes.added.length > 0
                        ? html`
                            <div class="diff-section">
                              <div class="diff-section-title">
                                <sl-icon
                                  name="plus-circle-fill"
                                  style="color: var(--sl-color-success-600);"
                                ></sl-icon>
                                Added (${this._diffResult.changes.added.length})
                              </div>
                              ${this._diffResult.changes.added.map(
                                (change) => html`
                                  <div class="diff-item added">
                                    <strong>${change.category}:</strong>
                                    ${change.name}
                                    ${change.details
                                      ? html`<br /><small
                                            >${change.details}</small
                                          >`
                                      : ''}
                                  </div>
                                `
                              )}
                            </div>
                          `
                        : ''}
                      ${this._diffResult.changes.modified.length > 0
                        ? html`
                            <div class="diff-section">
                              <div class="diff-section-title">
                                <sl-icon
                                  name="pencil-fill"
                                  style="color: var(--sl-color-warning-600);"
                                ></sl-icon>
                                Modified
                                (${this._diffResult.changes.modified.length})
                              </div>
                              ${this._diffResult.changes.modified.map(
                                (change) => html`
                                  <div class="diff-item modified">
                                    <strong>${change.category}:</strong>
                                    ${change.name}
                                    ${change.details
                                      ? html`<br /><small
                                            >${change.details}</small
                                          >`
                                      : ''}
                                  </div>
                                `
                              )}
                            </div>
                          `
                        : ''}
                      ${this._diffResult.changes.removed.length > 0
                        ? html`
                            <div class="diff-section">
                              <div class="diff-section-title">
                                <sl-icon
                                  name="dash-circle-fill"
                                  style="color: var(--sl-color-danger-600);"
                                ></sl-icon>
                                Removed
                                (${this._diffResult.changes.removed.length})
                              </div>
                              ${this._diffResult.changes.removed.map(
                                (change) => html`
                                  <div class="diff-item removed">
                                    <strong>${change.category}:</strong>
                                    ${change.name}
                                  </div>
                                `
                              )}
                            </div>
                          `
                        : ''}
                    </div>
                  `
                : ''}
            `
          : html`
              <div class="loading-container">
                <sl-spinner></sl-spinner>
              </div>
            `}

        <div slot="footer" class="dialog-footer">
          <sl-button
            @click=${() => {
              this._showDiffDialog = false;
              this._pendingFile = null;
              this._diffResult = null;
            }}
          >
            Cancel
          </sl-button>
          <sl-button
            variant="primary"
            @click=${this.applyPolicyFile}
            ?loading=${this._isUploading}
            ?disabled=${!this._diffResult?.has_changes}
          >
            Apply Changes
          </sl-button>
        </div>
      </sl-dialog>
    `;
  }

  render() {
    return html`
      <view-header headerText="Policies" width="extra-wide"></view-header>

      <div class="column-layout extra-wide">
        <div class="main-column">
          ${this._error
            ? html`
                <sl-alert variant="danger" open closable>
                  <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                  <strong>Error:</strong> ${this._error}
                </sl-alert>
              `
            : ''}
          ${this._loading
            ? html`
                <div class="loading-container">
                  <sl-spinner style="font-size: 2rem;"></sl-spinner>
                </div>
              `
            : html`
                <sl-tab-group
                  @sl-tab-show=${(e: any) => (this._activeTab = e.detail.name)}
                >
                  <sl-tab
                    slot="nav"
                    panel="access"
                    ?active=${this._activeTab === 'access'}
                  >
                    <sl-icon
                      name="shield-lock"
                      style="margin-right: var(--sl-spacing-x-small);"
                    ></sl-icon>
                    Access Policies
                  </sl-tab>
                  <sl-tab
                    slot="nav"
                    panel="approval"
                    ?active=${this._activeTab === 'approval'}
                  >
                    <sl-icon
                      name="person-check"
                      style="margin-right: var(--sl-spacing-x-small);"
                    ></sl-icon>
                    Approval Policies
                  </sl-tab>
                  <sl-tab
                    slot="nav"
                    panel="files"
                    ?active=${this._activeTab === 'files'}
                  >
                    <sl-icon
                      name="file-earmark-code"
                      style="margin-right: var(--sl-spacing-x-small);"
                    ></sl-icon>
                    Policy Files
                  </sl-tab>

                  <sl-tab-panel name="access">
                    ${this.renderAccessPoliciesTab()}
                  </sl-tab-panel>
                  <sl-tab-panel name="approval">
                    ${this.renderApprovalPoliciesTab()}
                  </sl-tab-panel>
                  <sl-tab-panel name="files">
                    ${this.renderPolicyFilesTab()}
                  </sl-tab-panel>
                </sl-tab-group>
              `}
        </div>
        <div class="side-column"></div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'policies-view': PoliciesView;
  }
}
