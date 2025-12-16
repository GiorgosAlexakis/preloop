import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import {
  getUsers,
  getTeams,
  getAccountDetails,
  getToolApprovalCondition,
} from '../api';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/switch/switch.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';

// Preloop badge SVG
const preloopBadgeSvg = `<svg width="20px" height="18px" viewBox="0 0 1024 914" version="1.1" xmlns="http://www.w3.org/2000/svg">
  <g transform="translate(60.9693, 56)" fill="currentColor" fill-rule="nonzero">
    <path d="M531.030651,0 C730.405446,0 892.030651,161.625205 892.030651,361 C892.030651,560.374795 730.405446,722 531.030651,722 C465.291938,722 403.657288,704.428413 350.567272,673.725809 L405.250574,619.042004 C443.232077,637.590388 485.915717,648 531.030651,648 C689.536375,648 818.030651,519.505723 818.030651,361 C818.030651,202.494277 689.536375,74 531.030651,74 C372.524928,74 244.030651,202.494277 244.030651,361 C244.030651,406.132219 254.448241,448.831279 273.009969,486.823729 L218.329321,541.5057 C187.611578,488.406119 170.030651,426.756182 170.030651,361 C170.030651,161.625205 331.655857,0 531.030651,0 Z"></path>
    <path d="M571.730882,266.133399 L623.623354,318.88917 L237.226702,700.61499 L233.513357,704.27738 C210.166625,727.303745 172.658216,727.321636 149.289528,704.317554 L140.228363,695.397764 L140.228363,695.397764 L0,554.370673 L52.3259018,502.044771 L191.850951,641.569768 L571.730882,266.133399 Z"></path>
  </g>
</svg>`;

export interface Tool {
  name: string;
  description: string;
  source: 'builtin' | 'mcp' | 'http';
  source_id: string | null;
  source_name: string;
  schema: any;
  is_enabled: boolean;
  approval_policy_id: string | null;
  has_approval_condition: boolean;
  config_id: string | null;
}

export interface ApprovalPolicy {
  id: string;
  name: string;
  description?: string;
  approval_type: string;
  channel?: string;
  user?: string;
  approval_config?: {
    webhook_url?: string;
  };
  is_default?: boolean;
  // Proprietary fields
  approver_user_ids?: string[];
  approver_team_ids?: string[];
  approvals_required?: number;
  timeout_seconds?: number;
  escalation_user_ids?: string[];
  escalation_team_ids?: string[];
  notification_channels?: string[];
}

@customElement('tool-card')
export class ToolCard extends LitElement {
  @property({ type: Object })
  tool?: Tool;

  @property({ type: Array })
  policies: ApprovalPolicy[] = [];

  @property({ type: Object })
  features: { [key: string]: boolean } = {};

  @state()
  private showPreloopDialog = false;

  @state()
  private pendingApproval = false;

  @state()
  private selectedPolicyId: string = '';

  @state()
  private isCreatingPolicy = false;

  @state()
  private newPolicyName = '';

  @state()
  private newPolicyDescription = '';

  @state()
  private newPolicyType = 'standard';

  @state()
  private newPolicyChannel = '';

  @state()
  private newPolicyUser = '';

  @state()
  private newPolicyWebhookUrl = '';

  @state()
  private newPolicyIsDefault = false;

  @state()
  private editingPolicyId: string | null = null;

  @state()
  private newPolicyApproverUserIds: string[] = [];

  @state()
  private newPolicyApproverTeamIds: string[] = [];

  @state()
  private newPolicyApprovalsRequired = 1;

  @state()
  private newPolicyTimeoutSeconds = 300;

  @state()
  private newPolicyEscalationUserIds: string[] = [];

  @state()
  private newPolicyEscalationTeamIds: string[] = [];

  @state()
  private availableUsers: Array<{
    id: string;
    username: string;
    email: string;
  }> = [];

  @state()
  private availableTeams: Array<{ id: string; name: string }> = [];

  @state()
  private currentUserId: string = '';

  @state()
  private showConditionConfig = false;

  @state()
  private conditionField: string = '';

  @state()
  private conditionOperator: string = 'equals';

  @state()
  private conditionValue: string = '';

  connectedCallback() {
    super.connectedCallback();
    this.loadCurrentUser();
  }

  /**
   * Check if a specific feature is enabled.
   * Enterprise features like RBAC, advanced_approvals are controlled by backend plugins.
   */
  private hasFeature(featureName: string): boolean {
    return this.features[featureName] === true;
  }

  /**
   * Check if advanced approval features are available (enterprise feature).
   * This enables:
   * - User/team approver selection
   * - Quorum (multiple approvals required)
   * - Escalation policies
   * - Slack/Mattermost notification channels
   */
  private hasAdvancedApprovals(): boolean {
    return this.hasFeature('advanced_approvals');
  }

  private async loadCurrentUser() {
    try {
      const currentUser = await getAccountDetails();
      this.currentUserId = currentUser?.id || '';
    } catch (error) {
      console.error('Failed to load current user:', error);
    }
  }

  private async loadUsersAndTeams() {
    // Only load users and teams if advanced approvals feature is enabled (enterprise)
    if (!this.hasAdvancedApprovals()) {
      return;
    }
    try {
      const [usersResponse, teamsResponse] = await Promise.all([
        getUsers(),
        getTeams(),
      ]);
      this.availableUsers = usersResponse.users || [];
      this.availableTeams = teamsResponse.teams || [];
    } catch (error) {
      console.error('Failed to load users and teams:', error);
    }
  }

  updated(changedProperties: Map<string, unknown>) {
    super.updated(changedProperties);
    // Load users/teams when features change (in case enterprise features become available)
    if (changedProperties.has('features') && this.hasAdvancedApprovals()) {
      this.loadUsersAndTeams();
    }
  }

  private getToolArguments(): Array<{ name: string; type: string }> {
    // Support both JSON Schema formats:
    // 1. Direct properties: { properties: {...} }
    // 2. MCP format: { input: { properties: {...} } }
    const properties =
      this.tool?.schema?.properties || this.tool?.schema?.input?.properties;

    if (!properties) {
      return [];
    }

    return Object.keys(properties).map((key) => ({
      name: key,
      type: properties[key].type || 'string',
    }));
  }

  private getOperatorsForType(
    type: string
  ): Array<{ value: string; label: string }> {
    const baseOperators = [
      { value: 'equals', label: 'Equals' },
      { value: 'not_equals', label: 'Not Equals' },
    ];

    if (type === 'number' || type === 'integer') {
      return [
        ...baseOperators,
        { value: 'less_than', label: 'Less Than' },
        { value: 'less_than_or_equal', label: 'Less Than or Equal' },
        { value: 'greater_than', label: 'Greater Than' },
        { value: 'greater_than_or_equal', label: 'Greater Than or Equal' },
      ];
    }

    return baseOperators;
  }

  private buildConditionExpression(): string {
    if (
      !this.conditionField ||
      !this.conditionOperator ||
      !this.conditionValue
    ) {
      return '';
    }

    // Build CEL expression based on operator
    const operatorMap: Record<string, string> = {
      equals: '==',
      not_equals: '!=',
      less_than: '<',
      less_than_or_equal: '<=',
      greater_than: '>',
      greater_than_or_equal: '>=',
    };

    const celOperator = operatorMap[this.conditionOperator] || '==';

    // Check if value should be a number
    const arg = this.getToolArguments().find(
      (a) => a.name === this.conditionField
    );
    const isNumber = arg?.type === 'number' || arg?.type === 'integer';
    const value = isNumber ? this.conditionValue : `"${this.conditionValue}"`;

    return `args.${this.conditionField} ${celOperator} ${value}`;
  }

  static styles = css`
    .tool-card {
      width: 280px;
      display: flex;
      flex-direction: column;
      height: 100%;
    }

    .card-content {
      flex-grow: 1;
      display: flex;
      flex-direction: column;
    }

    .tool-header {
      margin-bottom: var(--sl-spacing-medium);
    }

    .tool-name {
      font-size: var(--sl-font-size-large);
      font-weight: var(--sl-font-weight-semibold);
      margin: 0 0 var(--sl-spacing-2x-small) 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .tool-source {
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-600);
      margin: 0;
    }

    .tool-description {
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-700);
      line-height: 1.5;
      margin: 0;
      height: 4.5em;
      overflow: hidden;
      text-overflow: ellipsis;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
    }

    sl-card {
      height: 100%;
    }

    sl-card::part(footer) {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-small);
      padding: var(--sl-spacing-medium);
      border-top: 1px solid var(--sl-color-neutral-200);
    }

    .control-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .control-label {
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-700);
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-2x-small);
    }

    .preloop-icon {
      width: 16px;
      height: 14px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      opacity: 0.7;
    }

    .approval-section {
      margin-top: var(--sl-spacing-medium);
    }

    .policy-selector {
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-x-small);
      margin-top: var(--sl-spacing-small);
      padding-left: var(--sl-spacing-small);
    }

    .policy-selector sl-select {
      flex: 1;
    }

    .dialog-content {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-medium);
    }

    .policy-list {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-small);
      max-height: 300px;
      overflow-y: auto;
    }

    .policy-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: var(--sl-spacing-small);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s;
    }

    .policy-item:hover {
      border-color: var(--sl-color-primary-600);
      background: var(--sl-color-primary-50);
    }

    .policy-item.selected {
      border-color: var(--sl-color-primary-600);
      background: var(--sl-color-primary-100);
    }

    .policy-info {
      flex: 1;
    }

    .policy-name {
      font-weight: var(--sl-font-weight-semibold);
      margin: 0 0 var(--sl-spacing-2x-small) 0;
    }

    .policy-meta {
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-600);
    }

    .form-field {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-2x-small);
    }

    .form-label {
      font-size: var(--sl-font-size-small);
      font-weight: var(--sl-font-weight-semibold);
    }

    .dialog-section {
      border-top: 1px solid var(--sl-color-neutral-200);
      padding-top: var(--sl-spacing-medium);
    }

    .empty-state {
      text-align: center;
      padding: var(--sl-spacing-large);
      color: var(--sl-color-neutral-600);
      font-size: var(--sl-font-size-small);
    }

    .default-badge {
      display: inline-flex;
      align-items: center;
      gap: var(--sl-spacing-2x-small);
      padding: 2px 8px;
      background: var(--sl-color-primary-100);
      color: var(--sl-color-primary-700);
      border-radius: 4px;
      font-size: var(--sl-font-size-x-small);
      font-weight: var(--sl-font-weight-semibold);
      margin-left: var(--sl-spacing-x-small);
    }

    .policy-actions {
      display: flex;
      gap: var(--sl-spacing-2x-small);
    }
  `;

  private handleEnabledToggle() {
    this.dispatchEvent(
      new CustomEvent('toggle-enabled', {
        detail: { tool: this.tool },
        bubbles: true,
        composed: true,
      })
    );
  }

  private handleApprovalToggle() {
    if (!this.tool) return;

    // If turning OFF, remove policy immediately
    if (this.tool.approval_policy_id || this.pendingApproval) {
      this.pendingApproval = false;
      this.dispatchEvent(
        new CustomEvent('toggle-approval', {
          detail: { tool: this.tool, enable: false },
          bubbles: true,
          composed: true,
        })
      );
    } else {
      // If turning ON
      // Check if there's already a policy assigned
      if (this.tool.approval_policy_id) {
        // Has policy: already enabled (shouldn't reach here)
        // Just ensure it's enabled
        this.dispatchEvent(
          new CustomEvent('toggle-approval', {
            detail: { tool: this.tool, enable: true },
            bubbles: true,
            composed: true,
          })
        );
      } else {
        // No policy: Open dialog to create/select one
        this.pendingApproval = true;
        this.showPreloopDialog = true;
      }
    }
  }

  private async handleConfigureCondition() {
    // Load existing condition if it exists
    if (this.tool.config_id) {
      try {
        const condition = await getToolApprovalCondition(this.tool.config_id);
        if (condition && condition.condition_expression) {
          // Parse the CEL expression back into form fields
          this.parseCelExpression(condition.condition_expression);
        }
      } catch (error) {
        console.error('Failed to load approval condition:', error);
      }
    }
    this.showConditionConfig = true;
  }

  private parseCelExpression(expression: string) {
    // Parse expressions like: args.field_name operator value
    // Examples: "args.n > 10", "args.status == 'active'"
    const match = expression.match(/^args\.(\w+)\s*(==|!=|>|>=|<|<=)\s*(.+)$/);
    if (!match) {
      console.warn('Unable to parse CEL expression:', expression);
      return;
    }

    const [, field, operator, rawValue] = match;
    this.conditionField = field;

    // Map CEL operators to our form operators
    const operatorMap: { [key: string]: string } = {
      '==': 'equals',
      '!=': 'not_equals',
      '>': 'greater_than',
      '>=': 'greater_than_or_equal',
      '<': 'less_than',
      '<=': 'less_than_or_equal',
    };
    this.conditionOperator = operatorMap[operator] || 'equals';

    // Remove quotes if it's a string value
    let value = rawValue.trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    this.conditionValue = value;
  }

  private handleCloseConditionDialog() {
    this.showConditionConfig = false;
    this.conditionField = '';
    this.conditionOperator = 'equals';
    this.conditionValue = '';
  }

  private handleSaveCondition() {
    const expression = this.buildConditionExpression();
    if (!expression) {
      alert('Please fill in all condition fields');
      return;
    }

    // Dispatch event to save the condition
    this.dispatchEvent(
      new CustomEvent('save-condition', {
        detail: {
          tool: this.tool,
          condition: expression,
        },
        bubbles: true,
        composed: true,
      })
    );

    this.showConditionConfig = false;
  }

  private handlePolicySelect(event: Event) {
    const select = event.target as any;
    if (!select.value) return;

    // Now actually enable approval with the selected policy
    this.dispatchEvent(
      new CustomEvent('policy-selected', {
        detail: { tool: this.tool, policyId: select.value },
        bubbles: true,
        composed: true,
      })
    );
    this.pendingApproval = false;
  }

  private handleManagePolicies() {
    this.showPreloopDialog = true;
  }

  private handleClosePreloopDialog(event?: any) {
    // Only close if explicitly called (not from sl-hide event during form interaction)
    if (event?.type === 'sl-hide' && this.isCreatingPolicy) {
      // Don't close during form interaction
      return;
    }

    // If dialog is closed without selecting a policy, revert the toggle
    if (this.pendingApproval) {
      this.pendingApproval = false;
    }
    this.showPreloopDialog = false;
    this.isCreatingPolicy = false;
    this.selectedPolicyId = '';
    this.resetPolicyForm();
  }

  private handleCancelDialog() {
    // Explicitly close the dialog
    if (this.pendingApproval) {
      this.pendingApproval = false;
    }
    this.showPreloopDialog = false;
    this.isCreatingPolicy = false;
    this.selectedPolicyId = '';
    this.resetPolicyForm();
  }

  private handlePolicyItemClick(policyId: string) {
    this.selectedPolicyId = policyId;
  }

  private handleToggleCreatePolicy() {
    this.isCreatingPolicy = !this.isCreatingPolicy;
    if (this.isCreatingPolicy) {
      this.selectedPolicyId = '';
    }
    this.resetPolicyForm();
  }

  private handleEditPolicy(policy: ApprovalPolicy) {
    // Switch to create/edit mode
    this.isCreatingPolicy = true;
    this.editingPolicyId = policy.id;

    // Populate form with existing policy data
    this.newPolicyName = policy.name;
    this.newPolicyDescription = policy.description || '';
    this.newPolicyType = policy.approval_type;
    this.newPolicyChannel = policy.channel || '';
    this.newPolicyUser = policy.user || '';
    this.newPolicyWebhookUrl = policy.approval_config?.webhook_url || '';
    this.newPolicyIsDefault = policy.is_default || false;
    this.newPolicyApproverUserIds = policy.approver_user_ids || [];
    this.newPolicyApproverTeamIds = policy.approver_team_ids || [];
    this.newPolicyApprovalsRequired = policy.approvals_required || 1;
    this.newPolicyTimeoutSeconds = policy.timeout_seconds || 300;
    this.newPolicyEscalationUserIds = policy.escalation_user_ids || [];
    this.newPolicyEscalationTeamIds = policy.escalation_team_ids || [];
  }

  private resetPolicyForm() {
    this.newPolicyName = '';
    this.newPolicyDescription = '';
    this.newPolicyType = 'standard';
    this.newPolicyChannel = '';
    this.newPolicyUser = '';
    this.newPolicyWebhookUrl = '';
    this.newPolicyIsDefault = false;
    // Default to current user for Standard type
    this.newPolicyApproverUserIds = this.currentUserId
      ? [this.currentUserId]
      : [];
    this.newPolicyApproverTeamIds = [];
    this.newPolicyApprovalsRequired = 1;
    this.newPolicyTimeoutSeconds = 300;
    this.newPolicyEscalationUserIds = [];
    this.newPolicyEscalationTeamIds = [];
    this.editingPolicyId = null;
  }

  private handleConfirmPolicy() {
    if (this.isCreatingPolicy) {
      // Validate form
      if (!this.newPolicyName.trim()) {
        alert('Policy name is required');
        return;
      }
      // Webhook URL only required for non-standard types
      if (
        this.newPolicyType !== 'standard' &&
        !this.newPolicyWebhookUrl.trim()
      ) {
        alert('Webhook URL is required');
        return;
      }

      // Enterprise only: validate approvers and quorum
      const totalApprovers =
        this.newPolicyApproverUserIds.length +
        this.newPolicyApproverTeamIds.length;

      // Validate approvals_required doesn't exceed total potential approvers (enterprise only)
      if (
        this.hasAdvancedApprovals() &&
        totalApprovers > 0 &&
        this.newPolicyApprovalsRequired > totalApprovers
      ) {
        alert(
          `Number of approvals required (${this.newPolicyApprovalsRequired}) cannot exceed the total number of potential approvers (${totalApprovers})`
        );
        return;
      }

      // Build approval config
      const approvalConfig: any = {};
      if (this.newPolicyWebhookUrl) {
        approvalConfig.webhook_url = this.newPolicyWebhookUrl;
      }

      // Check if we're editing or creating
      if (this.editingPolicyId) {
        // Dispatch event to update existing policy
        this.dispatchEvent(
          new CustomEvent('update-policy', {
            detail: {
              policyId: this.editingPolicyId,
              policy: {
                name: this.newPolicyName,
                description: this.newPolicyDescription,
                approval_type: this.newPolicyType,
                channel: this.newPolicyChannel || null,
                user: this.newPolicyUser || null,
                approval_config:
                  Object.keys(approvalConfig).length > 0
                    ? approvalConfig
                    : null,
                is_default: this.newPolicyIsDefault,
                approver_user_ids:
                  this.newPolicyApproverUserIds.length > 0
                    ? this.newPolicyApproverUserIds
                    : null,
                approver_team_ids:
                  this.newPolicyApproverTeamIds.length > 0
                    ? this.newPolicyApproverTeamIds
                    : null,
                approvals_required: this.newPolicyApprovalsRequired,
                timeout_seconds: this.newPolicyTimeoutSeconds,
                escalation_user_ids:
                  this.newPolicyEscalationUserIds.length > 0
                    ? this.newPolicyEscalationUserIds
                    : null,
                escalation_team_ids:
                  this.newPolicyEscalationTeamIds.length > 0
                    ? this.newPolicyEscalationTeamIds
                    : null,
              },
            },
            bubbles: true,
            composed: true,
          })
        );
      } else {
        // Dispatch event to create new policy
        this.dispatchEvent(
          new CustomEvent('create-policy', {
            detail: {
              tool: this.tool,
              policy: {
                name: this.newPolicyName,
                description: this.newPolicyDescription,
                approval_type: this.newPolicyType,
                channel: this.newPolicyChannel || null,
                user: this.newPolicyUser || null,
                approval_config:
                  Object.keys(approvalConfig).length > 0
                    ? approvalConfig
                    : null,
                is_default: this.newPolicyIsDefault,
                approver_user_ids:
                  this.newPolicyApproverUserIds.length > 0
                    ? this.newPolicyApproverUserIds
                    : null,
                approver_team_ids:
                  this.newPolicyApproverTeamIds.length > 0
                    ? this.newPolicyApproverTeamIds
                    : null,
                approvals_required: this.newPolicyApprovalsRequired,
                timeout_seconds: this.newPolicyTimeoutSeconds,
                escalation_user_ids:
                  this.newPolicyEscalationUserIds.length > 0
                    ? this.newPolicyEscalationUserIds
                    : null,
                escalation_team_ids:
                  this.newPolicyEscalationTeamIds.length > 0
                    ? this.newPolicyEscalationTeamIds
                    : null,
              },
            },
            bubbles: true,
            composed: true,
          })
        );
      }
    } else if (this.selectedPolicyId) {
      // Select existing policy
      this.dispatchEvent(
        new CustomEvent('policy-selected', {
          detail: { tool: this.tool, policyId: this.selectedPolicyId },
          bubbles: true,
          composed: true,
        })
      );
    } else {
      alert('Please select or create a policy');
      return;
    }

    this.pendingApproval = false;
    this.isCreatingPolicy = false;
    this.selectedPolicyId = '';
    this.resetPolicyForm();

    // Close dialog after a small delay to ensure state is updated
    setTimeout(() => {
      this.showPreloopDialog = false;
    }, 10);
  }

  render() {
    if (!this.tool) {
      return html``;
    }

    return html`
      <sl-card class="tool-card">
        <div class="card-content">
          <div class="tool-header">
            <h3 class="tool-name" title=${this.tool.name}>${this.tool.name}</h3>
            <p class="tool-source">
              <sl-badge
                variant=${this.tool.source === 'builtin'
                  ? 'primary'
                  : 'neutral'}
                size="small"
              >
                ${this.tool.source_name}
              </sl-badge>
            </p>
          </div>
          <p class="tool-description" title=${this.tool.description}>
            ${this.tool.description}
          </p>
        </div>
        <div slot="footer">
          <div class="control-row">
            <span class="control-label">Enabled</span>
            <sl-switch
              ?checked=${this.tool.is_enabled}
              @sl-change=${this.handleEnabledToggle}
            ></sl-switch>
          </div>

          ${
            // Hide approval section for the request_approval tool since it doesn't
            // make sense to require approval for a tool that requests approval
            this.tool.name === 'request_approval'
              ? ''
              : html`
                  <div class="approval-section">
                    <div class="control-row">
                      <span class="control-label">
                        Require Approval
                        <span class="preloop-icon">
                          ${unsafeHTML(preloopBadgeSvg)}
                        </span>
                      </span>
                      <sl-switch
                        ?checked=${this.tool.approval_policy_id ||
                        this.pendingApproval}
                        ?disabled=${!this.tool.is_enabled}
                        @sl-change=${this.handleApprovalToggle}
                      ></sl-switch>
                    </div>
                    ${this.tool.approval_policy_id && this.tool.is_enabled
                      ? html`
                          <div class="policy-selector">
                            <sl-select
                              size="small"
                              placeholder="Select a policy..."
                              value=${this.tool.approval_policy_id || ''}
                              @sl-change=${this.handlePolicySelect}
                            >
                              ${this.policies.map(
                                (policy) => html`
                                  <sl-option value=${policy.id}
                                    >${policy.name}</sl-option
                                  >
                                `
                              )}
                            </sl-select>
                            <sl-icon-button
                              name="gear"
                              label="Manage policies"
                              @click=${this.handleManagePolicies}
                            ></sl-icon-button>
                          </div>
                          <div class="policy-selector">
                            <sl-button
                              size="small"
                              @click=${this.handleConfigureCondition}
                              style="width: 100%;"
                            >
                              <sl-icon
                                slot="prefix"
                                name="code-square"
                              ></sl-icon>
                              ${this.tool.has_approval_condition
                                ? 'Edit Condition'
                                : 'Add Condition'}
                            </sl-button>
                          </div>
                        `
                      : ''}
                    ${this.pendingApproval && this.tool.is_enabled
                      ? html`
                          <div class="policy-selector">
                            <sl-select
                              size="small"
                              placeholder="Select a policy..."
                              value=""
                              @sl-change=${this.handlePolicySelect}
                            >
                              ${this.policies.map(
                                (policy) => html`
                                  <sl-option value=${policy.id}
                                    >${policy.name}</sl-option
                                  >
                                `
                              )}
                            </sl-select>
                            <sl-icon-button
                              name="gear"
                              label="Manage policies"
                              @click=${this.handleManagePolicies}
                            ></sl-icon-button>
                          </div>
                        `
                      : ''}
                  </div>
                `
          }
        </div>
      </sl-card>

      <sl-dialog
        label="Configure Approval Policy"
        ?open=${this.showPreloopDialog}
        no-header=${false}
        @sl-request-close=${(e: any) => {
          // Only allow closing via cancel/confirm buttons
          if (e.detail.source === 'overlay' || e.detail.source === 'keyboard') {
            e.preventDefault();
          }
        }}
        @sl-hide=${this.handleClosePreloopDialog}
        style="--width: 600px;"
      >
        <div class="dialog-content">
          <p>
            Configure approval policy for <strong>${this.tool.name}</strong>
          </p>
          <p
            style="color: var(--sl-color-neutral-600); font-size: var(--sl-font-size-small); margin-top: 0;"
          >
            Preloop allows you to review and approve tool executions before they
            run.
            ${this.pendingApproval
              ? 'Select an existing policy or create a new one to enable approval for this tool.'
              : 'Manage approval policies for this tool.'}
          </p>

          ${!this.isCreatingPolicy
            ? html`
                <!-- Existing Policies List -->
                <div>
                  <div
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--sl-spacing-small);"
                  >
                    <h4
                      style="margin: 0; font-size: var(--sl-font-size-medium);"
                    >
                      Select Existing Policy
                    </h4>
                    <sl-button
                      size="small"
                      @click=${this.handleToggleCreatePolicy}
                    >
                      <sl-icon slot="prefix" name="plus-lg"></sl-icon>
                      Create New
                    </sl-button>
                  </div>
                  ${this.policies.length > 0
                    ? html`
                        <div class="policy-list">
                          ${this.policies.map(
                            (policy) => html`
                              <div
                                class="policy-item ${this.selectedPolicyId ===
                                policy.id
                                  ? 'selected'
                                  : ''}"
                                @click=${() =>
                                  this.handlePolicyItemClick(policy.id)}
                              >
                                <div class="policy-info">
                                  <h5 class="policy-name">
                                    ${policy.name}
                                    ${policy.is_default
                                      ? html`<span class="default-badge">
                                          <sl-icon name="star-fill"></sl-icon>
                                          Default
                                        </span>`
                                      : ''}
                                  </h5>
                                  <div class="policy-meta">
                                    ${policy.description || 'No description'}
                                    <br />
                                    Type: ${policy.approval_type}
                                    ${policy.approval_config?.webhook_url
                                      ? ` • Webhook configured`
                                      : ' • No webhook'}
                                    ${policy.channel
                                      ? ` • Channel: ${policy.channel}`
                                      : ''}
                                    ${policy.user
                                      ? ` • User: ${policy.user}`
                                      : ''}
                                  </div>
                                </div>
                                <div class="policy-actions">
                                  <sl-icon-button
                                    name="pencil"
                                    label="Edit policy"
                                    @click=${(e: Event) => {
                                      e.stopPropagation();
                                      this.handleEditPolicy(policy);
                                    }}
                                  ></sl-icon-button>
                                  ${this.selectedPolicyId === policy.id
                                    ? html`<sl-icon
                                        name="check-circle-fill"
                                        style="color: var(--sl-color-primary-600);"
                                      ></sl-icon>`
                                    : ''}
                                </div>
                              </div>
                            `
                          )}
                        </div>
                      `
                    : html`
                        <div class="empty-state">
                          <sl-icon
                            name="inbox"
                            style="font-size: 2rem; margin-bottom: var(--sl-spacing-small);"
                          ></sl-icon>
                          <p>
                            No policies found. Create your first policy to get
                            started.
                          </p>
                        </div>
                      `}
                </div>
              `
            : html`
                <!-- Create New Policy Form -->
                <div class="dialog-section">
                  <div
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--sl-spacing-medium);"
                  >
                    <h4
                      style="margin: 0; font-size: var(--sl-font-size-medium);"
                    >
                      ${this.editingPolicyId
                        ? 'Edit Policy'
                        : 'Create New Policy'}
                    </h4>
                    <sl-button
                      size="small"
                      @click=${this.handleToggleCreatePolicy}
                    >
                      <sl-icon slot="prefix" name="arrow-left"></sl-icon>
                      Back to List
                    </sl-button>
                  </div>

                  <div class="form-field">
                    <label class="form-label">Policy Name *</label>
                    <sl-input
                      placeholder="e.g., Default Approval Policy"
                      value=${this.newPolicyName}
                      @sl-input=${(e: any) => {
                        e.stopPropagation();
                        this.newPolicyName = e.target.value;
                      }}
                    ></sl-input>
                  </div>

                  <div class="form-field">
                    <label class="form-label">Description</label>
                    <sl-textarea
                      placeholder="Optional description"
                      value=${this.newPolicyDescription}
                      @sl-input=${(e: any) => {
                        e.stopPropagation();
                        this.newPolicyDescription = e.target.value;
                      }}
                      rows="2"
                    ></sl-textarea>
                  </div>

                  <div class="form-field">
                    <label class="form-label">Approval Type</label>
                    <sl-select
                      value=${this.newPolicyType}
                      @sl-change=${(e: any) => {
                        e.preventDefault();
                        e.stopPropagation();
                        e.stopImmediatePropagation();
                        this.newPolicyType = e.target.value;
                        this.requestUpdate();
                      }}
                    >
                      <sl-option value="standard">Standard</sl-option>
                      ${this.hasAdvancedApprovals()
                        ? html`
                            <sl-option value="slack">Slack</sl-option>
                            <sl-option value="mattermost">Mattermost</sl-option>
                          `
                        : ''}
                      <sl-option value="webhook">Webhook</sl-option>
                    </sl-select>
                  </div>

                  ${this.newPolicyType !== 'standard'
                    ? html`
                        <div class="form-field">
                          <label class="form-label">Webhook URL *</label>
                          <sl-input
                            type="url"
                            placeholder="${this.newPolicyType === 'slack'
                              ? 'https://hooks.slack.com/services/...'
                              : this.newPolicyType === 'mattermost'
                                ? 'https://your-mattermost.com/hooks/...'
                                : 'https://your-webhook-endpoint.com/approval-request'}"
                            value=${this.newPolicyWebhookUrl}
                            @sl-input=${(e: any) => {
                              e.stopPropagation();
                              this.newPolicyWebhookUrl = e.target.value;
                            }}
                            help-text="The webhook URL where approval requests will be sent"
                          ></sl-input>
                        </div>
                      `
                    : ''}

                  <!-- Enterprise Features: Advanced Approval Configuration -->
                  ${this.hasAdvancedApprovals() &&
                  (this.availableUsers.length > 0 ||
                    this.availableTeams.length > 0)
                    ? html`
                        <div class="form-field">
                          <label class="form-label">
                            Approvers (Optional)
                          </label>
                          <sl-select
                            multiple
                            clearable
                            placeholder="Select users and teams who can approve..."
                            .value=${[
                              ...this.newPolicyApproverUserIds.map(
                                (id) => `user:${id}`
                              ),
                              ...this.newPolicyApproverTeamIds.map(
                                (id) => `team:${id}`
                              ),
                            ]}
                            @sl-change=${(e: any) => {
                              e.stopPropagation();
                              const selected = e.target.value || [];
                              this.newPolicyApproverUserIds = selected
                                .filter((v: string) => v.startsWith('user:'))
                                .map((v: string) => v.substring(5));
                              this.newPolicyApproverTeamIds = selected
                                .filter((v: string) => v.startsWith('team:'))
                                .map((v: string) => v.substring(5));
                            }}
                            help-text="Select users and teams who can provide approval"
                          >
                            ${this.availableUsers.length > 0
                              ? html`
                                  <sl-option-group label="Users">
                                    ${this.availableUsers.map(
                                      (user) => html`
                                        <sl-option value=${'user:' + user.id}
                                          >${user.username}
                                          (${user.email})</sl-option
                                        >
                                      `
                                    )}
                                  </sl-option-group>
                                `
                              : ''}
                            ${this.availableTeams.length > 0
                              ? html`
                                  <sl-option-group label="Teams">
                                    ${this.availableTeams.map(
                                      (team) => html`
                                        <sl-option value=${'team:' + team.id}
                                          >${team.name}</sl-option
                                        >
                                      `
                                    )}
                                  </sl-option-group>
                                `
                              : ''}
                          </sl-select>
                        </div>

                        <div class="form-field">
                          <label class="form-label"
                            >Number of Approvals Required</label
                          >
                          <sl-input
                            type="number"
                            min="1"
                            value=${this.newPolicyApprovalsRequired}
                            @sl-input=${(e: any) => {
                              e.stopPropagation();
                              this.newPolicyApprovalsRequired =
                                parseInt(e.target.value) || 1;
                            }}
                            help-text="How many approvals are needed before execution (quorum)"
                          ></sl-input>
                        </div>

                        <div class="form-field">
                          <label class="form-label"
                            >Approval Timeout (seconds)</label
                          >
                          <sl-input
                            type="number"
                            min="30"
                            value=${this.newPolicyTimeoutSeconds}
                            @sl-input=${(e: any) => {
                              e.stopPropagation();
                              this.newPolicyTimeoutSeconds =
                                parseInt(e.target.value) || 300;
                            }}
                            help-text="Time to wait for approvals before timing out"
                          ></sl-input>
                        </div>

                        ${
                          // Only show escalation if there are additional users/teams not selected as approvers
                          this.availableUsers.length +
                            this.availableTeams.length >
                          this.newPolicyApproverUserIds.length +
                            this.newPolicyApproverTeamIds.length
                            ? html`
                                <div class="form-field">
                                  <label class="form-label"
                                    >Escalation (Optional)</label
                                  >
                                  <sl-select
                                    multiple
                                    clearable
                                    placeholder="Select users and teams for escalation..."
                                    .value=${[
                                      ...this.newPolicyEscalationUserIds.map(
                                        (id) => `user:${id}`
                                      ),
                                      ...this.newPolicyEscalationTeamIds.map(
                                        (id) => `team:${id}`
                                      ),
                                    ]}
                                    @sl-change=${(e: any) => {
                                      e.stopPropagation();
                                      const selected = e.target.value || [];
                                      this.newPolicyEscalationUserIds = selected
                                        .filter((v: string) =>
                                          v.startsWith('user:')
                                        )
                                        .map((v: string) => v.substring(5));
                                      this.newPolicyEscalationTeamIds = selected
                                        .filter((v: string) =>
                                          v.startsWith('team:')
                                        )
                                        .map((v: string) => v.substring(5));
                                    }}
                                    help-text="Contact these users/teams if timeout is exceeded without required approvals"
                                  >
                                    ${this.availableUsers.length > 0
                                      ? html`
                                          <sl-option-group label="Users">
                                            ${this.availableUsers.map(
                                              (user) => html`
                                                <sl-option
                                                  value=${'user:' + user.id}
                                                  >${user.username}
                                                  (${user.email})</sl-option
                                                >
                                              `
                                            )}
                                          </sl-option-group>
                                        `
                                      : ''}
                                    ${this.availableTeams.length > 0
                                      ? html`
                                          <sl-option-group label="Teams">
                                            ${this.availableTeams.map(
                                              (team) => html`
                                                <sl-option
                                                  value=${'team:' + team.id}
                                                  >${team.name}</sl-option
                                                >
                                              `
                                            )}
                                          </sl-option-group>
                                        `
                                      : ''}
                                  </sl-select>
                                </div>
                              `
                            : ''
                        }
                      `
                    : ''}

                  <div class="form-field">
                    <div class="control-row">
                      <div>
                        <label class="form-label">Set as Default Policy</label>
                        <div
                          style="font-size: var(--sl-font-size-x-small); color: var(--sl-color-neutral-600); margin-top: var(--sl-spacing-2x-small);"
                        >
                          The default policy will be used when no specific
                          policy is selected
                        </div>
                      </div>
                      <sl-switch
                        ?checked=${this.newPolicyIsDefault}
                        @sl-change=${(e: any) => {
                          e.stopPropagation();
                          this.newPolicyIsDefault = e.target.checked;
                        }}
                      ></sl-switch>
                    </div>
                  </div>

                  ${this.newPolicyType === 'slack' ||
                  this.newPolicyType === 'mattermost'
                    ? html`
                        <div class="form-field">
                          <label class="form-label">Channel (Optional)</label>
                          <sl-input
                            placeholder="#approvals"
                            value=${this.newPolicyChannel}
                            @sl-input=${(e: any) => {
                              e.stopPropagation();
                              this.newPolicyChannel = e.target.value;
                            }}
                            help-text="Default channel for approval notifications"
                          ></sl-input>
                        </div>

                        <div class="form-field">
                          <label class="form-label">User (Optional)</label>
                          <sl-input
                            placeholder="@username"
                            value=${this.newPolicyUser}
                            @sl-input=${(e: any) => {
                              e.stopPropagation();
                              this.newPolicyUser = e.target.value;
                            }}
                            help-text="Specific user to notify for approvals"
                          ></sl-input>
                        </div>
                      `
                    : ''}
                </div>
              `}
        </div>

        <sl-button slot="footer" @click=${this.handleCancelDialog}>
          Cancel
        </sl-button>
        <sl-button
          slot="footer"
          variant="primary"
          @click=${this.handleConfirmPolicy}
          ?disabled=${this.isCreatingPolicy
            ? !this.newPolicyName.trim() ||
              (this.newPolicyType !== 'standard' &&
                !this.newPolicyWebhookUrl.trim())
            : !this.selectedPolicyId}
        >
          ${this.isCreatingPolicy
            ? this.editingPolicyId
              ? 'Update Policy'
              : 'Create & Apply'
            : 'Apply Policy'}
        </sl-button>
      </sl-dialog>

      <sl-dialog
        label="Configure Approval Condition"
        ?open=${this.showConditionConfig}
        @sl-request-close=${this.handleCloseConditionDialog}
        style="--width: 600px;"
      >
        <div class="dialog-content">
          <p>
            Define a condition that must be met for approval to be required. If
            the condition is not met, the tool will execute without approval.
          </p>

          ${this.getToolArguments().length > 0
            ? html`
                <div class="form-field">
                  <label class="form-label">Tool Argument</label>
                  <sl-select
                    placeholder="Select argument..."
                    value=${this.conditionField}
                    @sl-change=${(e: any) => {
                      this.conditionField = e.target.value;
                      // Reset operator when field changes
                      const arg = this.getToolArguments().find(
                        (a) => a.name === e.target.value
                      );
                      const operators = this.getOperatorsForType(
                        arg?.type || 'string'
                      );
                      if (
                        !operators.find(
                          (op) => op.value === this.conditionOperator
                        )
                      ) {
                        this.conditionOperator =
                          operators[0]?.value || 'equals';
                      }
                    }}
                  >
                    ${this.getToolArguments().map(
                      (arg) => html`
                        <sl-option value=${arg.name}>
                          ${arg.name} (${arg.type})
                        </sl-option>
                      `
                    )}
                  </sl-select>
                </div>

                ${this.conditionField
                  ? html`
                      <div class="form-field">
                        <label class="form-label">Operator</label>
                        <sl-select
                          value=${this.conditionOperator}
                          @sl-change=${(e: any) => {
                            this.conditionOperator = e.target.value;
                          }}
                        >
                          ${this.getOperatorsForType(
                            this.getToolArguments().find(
                              (a) => a.name === this.conditionField
                            )?.type || 'string'
                          ).map(
                            (op) => html`
                              <sl-option value=${op.value}
                                >${op.label}</sl-option
                              >
                            `
                          )}
                        </sl-select>
                      </div>

                      <div class="form-field">
                        <label class="form-label">Value</label>
                        <sl-input
                          placeholder="Enter value..."
                          value=${this.conditionValue}
                          @sl-input=${(e: any) => {
                            this.conditionValue = e.target.value;
                          }}
                        ></sl-input>
                      </div>

                      ${this.hasAdvancedApprovals()
                        ? html`
                            <div
                              style="margin-top: var(--sl-spacing-medium); padding: var(--sl-spacing-small); background: var(--sl-color-neutral-100); border-radius: 4px; font-family: monospace; font-size: var(--sl-font-size-small);"
                            >
                              <strong>CEL Expression:</strong><br />
                              ${this.buildConditionExpression() ||
                              '(incomplete)'}
                            </div>
                            <p
                              style="font-size: var(--sl-font-size-x-small); color: var(--sl-color-neutral-600); margin-top: var(--sl-spacing-small);"
                            >
                              Enterprise: You can create more complex conditions
                              using CEL (Common Expression Language) syntax
                              directly in the backend configuration.
                            </p>
                          `
                        : ''}
                    `
                  : ''}
              `
            : html`
                <div class="empty-state">
                  <p>This tool has no arguments to create conditions with.</p>
                </div>
              `}
        </div>

        <sl-button slot="footer" @click=${this.handleCloseConditionDialog}>
          Cancel
        </sl-button>
        <sl-button
          slot="footer"
          variant="primary"
          @click=${this.handleSaveCondition}
          ?disabled=${!this.buildConditionExpression()}
        >
          Save Condition
        </sl-button>
      </sl-dialog>
    `;
  }
}
