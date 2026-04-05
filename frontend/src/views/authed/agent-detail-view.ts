import { LitElement, css, html, unsafeCSS, TemplateResult } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '../../components/governance-rule-set-editor.ts';
import '../../components/budget-policy-editor.ts';
import '../../components/tools-editor-component.ts';
import '../../components/session-history-widget.ts';
import '../../components/view-header.ts';
import '../../components/resource-actions.ts';
import type { ResourceAction } from '../../components/resource-actions.ts';
import {
  fetchWithAuth,
  getApprovalWorkflows,
  getAgentGovernance,
  getAccountAgent,
  getAccountRuntimeSessionDetail,
  getFeatures,
  getAIModels,
  getTools,
  getMCPServers,
  removeAccountAgent,
  updateAgentGovernance,
  updateAccountAgent,
} from '../../api';
import type {
  AccountRuntimeSessionDetailResponse,
  GatewayUsageByModel,
  ManagedAgentDetailResponse,
  ManagedAgentServerActivitySummary,
  ManagedAgentSummary,
  ManagedAgentToolActivitySummary,
  ManagedAgentUsageAggregate,
  RuntimeSessionActivityItem,
  RuntimeSessionSummary,
  SubjectGovernanceConfig,
} from '../../types';
import type { AccessRuleSummary } from '../../components/governance-rule-set-editor';
import consoleStyles from '../../styles/console-styles.css?inline';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import {
  normalizeScopedToolRules,
  serializeScopedToolRules,
  type ScopedToolRules,
} from '../../utils/scoped-governance';
import { renderAgentIcon } from '../../utils/agent-icons';

interface GovernanceToolDefinition {
  name: string;
  description?: string;
  schema?: Record<string, unknown>;
}

@customElement('agent-detail-view')
export class AgentDetailView extends LitElement {
  @property({ type: String })
  agentId = '';

  @state()
  private agent: ManagedAgentSummary | null = null;

  @state()
  private runtimeDetail: AccountRuntimeSessionDetailResponse | null = null;

  @state()
  private aggregate: ManagedAgentUsageAggregate | null = null;

  @state()
  private usageByModel: GatewayUsageByModel[] = [];

  @state()
  private activityByServer: ManagedAgentServerActivitySummary[] = [];

  @state()
  private activityByTool: ManagedAgentToolActivitySummary[] = [];

  @state()
  private sessions: RuntimeSessionSummary[] = [];

  @state()
  private selectedSessionId: string | null = null;

  @state()
  private loading = true;

  @state()
  private error: string | null = null;

  @state()
  private initialized = false;

  @state()
  private availableUsers: Array<{
    id: string;
    username: string;
    email: string;
  }> = [];

  @state()
  private mcpServers: any[] = [];

  @state()
  private selectedOwnerUserId = '';

  @state()
  private editableDisplayName = '';

  @state()
  private actionLoading = false;

  @state()
  private liveActivity = {
    modelCalls: 0,
    toolCalls: 0,
    lastActivityAt: null as string | null,
  };

  @state()
  private governance: SubjectGovernanceConfig = {
    allowed_models: [],
    model_budgets: {},
    tool_rules: {},
    tool_enabled_overrides: {},
  };

  @state()
  private allowedModelsText = '';

  @state()
  private modelBudgetsText = '{}';

  @state()
  private scopedToolRules: ScopedToolRules = {};

  @state()
  private toolEnabledOverrides: Record<string, boolean> = {};

  @state()
  private toolCatalog: GovernanceToolDefinition[] = [];

  @state()
  private approvalWorkflows: any[] = [];

  @state()
  private availableModels: any[] = [];

  @state()
  private featureFlags: { [key: string]: boolean | string[] } = {};

  @state()
  private governanceToolToAdd = '';

  @state()
  private showTagsDialog = false;

  @state()
  private tagsDialogInput = '';

  @state()
  private governanceCustomToolName = '';

  private unsubscribeRealtime?: () => void;
  private refreshTimer: number | null = null;

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      :host {
        display: block;
      }

      .page,
      .stack,
      .timeline {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }

      .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: var(--sl-spacing-medium);
      }

      .split-pane-layout {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--sl-spacing-large);
        align-items: stretch;
      }

      .split-pane-layout > sl-card {
        max-width: 100%;
        overflow: hidden;
      }

      @media (max-width: 1000px) {
        .split-pane-layout {
          grid-template-columns: 1fr;
        }
      }

      .stat-card {
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-0);
      }

      .stat-label,
      .meta-line,
      .timeline-meta,
      .empty-state,
      .loading-state {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .stat-value {
        margin-top: var(--sl-spacing-2x-small);
        font-size: 1.35rem;
        font-weight: 700;
        color: var(--sl-color-neutral-900);
      }

      .hero {
        display: flex;
        justify-content: space-between;
        align-items: start;
        gap: var(--sl-spacing-medium);
        flex-wrap: wrap;
      }

      .hero-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: var(--sl-color-neutral-900);
      }

      .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: var(--sl-spacing-small);
      }

      .server-badges {
        display: flex;
        flex-wrap: wrap;
        gap: var(--sl-spacing-2x-small);
      }

      .session-link {
        color: var(--sl-color-primary-700);
        text-decoration: none;
      }

      .session-link:hover {
        text-decoration: underline;
      }

      .timeline-item {
        border-bottom: 1px solid var(--sl-color-neutral-200);
        padding-bottom: var(--sl-spacing-medium);
      }

      .timeline-item:last-child {
        border-bottom: none;
        padding-bottom: 0;
      }

      .timeline-title {
        font-weight: 600;
        color: var(--sl-color-neutral-900);
      }

      .loading-state,
      .empty-state {
        text-align: center;
        padding: var(--sl-spacing-x-large);
      }

      .loading-state sl-spinner {
        font-size: 2rem;
        margin-bottom: var(--sl-spacing-small);
      }

      .control-row {
        display: flex;
        gap: var(--sl-spacing-small);
        flex-wrap: wrap;
        align-items: end;
      }

      .control-row sl-select {
        min-width: 220px;
      }
    `,
  ];

  @state()
  private changeOwnerDialogOpen = false;

  @state()
  private updateBudgetsDialogOpen = false;

  @state()
  private budgetsDialogJson = '{}';

  onBeforeEnter(location: { params: { agentId?: string } }) {
    const nextAgentId = location.params.agentId ?? '';
    const changed = this.agentId !== nextAgentId;
    this.agentId = nextAgentId;

    if (this.initialized && changed) {
      void this.loadData();
    }
  }

  connectedCallback(): void {
    super.connectedCallback();
    this.connectRealtime();
    if (!this.initialized) {
      this.initialized = true;
      if (this.agentId) {
        void this.loadData();
      }
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.unsubscribeRealtime?.();
    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  private connectRealtime(): void {
    const scheduleRefresh = () => this.scheduleRefresh();
    const unsubscribers = [
      unifiedWebSocketManager.subscribe('managed_agents', scheduleRefresh),
      unifiedWebSocketManager.subscribe('runtime_sessions', scheduleRefresh),
      unifiedWebSocketManager.subscribe('gateway_activity', (message) =>
        this.handleGatewayActivity(message)
      ),
      unifiedWebSocketManager.subscribe('audit', scheduleRefresh),
    ];
    this.unsubscribeRealtime = () => {
      for (const unsubscribe of unsubscribers) {
        unsubscribe();
      }
    };
    void unifiedWebSocketManager.connect();
  }

  private scheduleRefresh(): void {
    if (!this.agentId) {
      return;
    }
    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
    }
    this.refreshTimer = window.setTimeout(() => {
      this.refreshTimer = null;
      void this.loadData(true);
    }, 250);
  }

  private async loadData(isSoftRefresh = false): Promise<void> {
    if (!this.agentId) {
      if (!isSoftRefresh) this.error = 'Missing agent id.';
      this.loading = false;
      return;
    }

    if (!isSoftRefresh) {
      this.loading = true;
      this.error = null;
      this.aggregate = null;
      this.usageByModel = [];
      this.activityByServer = [];
      this.activityByTool = [];
    }

    try {
      const [
        detail,
        users,
        governance,
        tools,
        servers,
        workflows,
        features,
        models,
      ] = await Promise.all([
        getAccountAgent(this.agentId),
        this.fetchUsers(),
        getAgentGovernance(this.agentId),
        getTools(),
        getMCPServers(),
        getApprovalWorkflows(),
        getFeatures(),
        getAIModels(),
      ]);
      this.agent = detail.agent;
      this.availableModels = models || [];
      this.mcpServers = servers || [];
      this.aggregate = detail.aggregate;
      this.usageByModel = detail.usage_by_model;
      this.activityByServer = detail.activity_by_server;
      this.activityByTool = detail.activity_by_tool;
      this.sessions = detail.sessions;
      if (!isSoftRefresh) {
        this.liveActivity = {
          modelCalls: 0,
          toolCalls: 0,
          lastActivityAt: null,
        };
      }
      this.governance = governance.config;
      this.scopedToolRules = normalizeScopedToolRules(
        governance.config.tool_rules
      );
      this.toolEnabledOverrides =
        governance.config.tool_enabled_overrides || {};
      this.allowedModelsText = governance.config.allowed_models.join(', ');
      this.modelBudgetsText = JSON.stringify(
        governance.config.model_budgets || {},
        null,
        2
      );
      this.toolCatalog = tools || [];
      this.approvalWorkflows = workflows || [];
      this.featureFlags = features?.features || {};
      this.availableUsers = users;
      this.selectedOwnerUserId = detail.agent.owner_user_id ?? '';
      if (!isSoftRefresh) {
        this.editableDisplayName = detail.agent.display_name;
      }

      if (
        !this.selectedSessionId ||
        !this.sessions.some((s) => s.id === this.selectedSessionId)
      ) {
        this.selectedSessionId =
          detail.agent.runtime_session_id ?? detail.sessions[0]?.id ?? null;
      }
      this.runtimeDetail = this.selectedSessionId
        ? await getAccountRuntimeSessionDetail(this.selectedSessionId)
        : null;
    } catch (error) {
      console.error('Failed to load managed agent detail:', error);
      if (!isSoftRefresh) {
        this.error =
          error instanceof Error
            ? error.message
            : 'Failed to load managed agent';
      }
    } finally {
      if (!isSoftRefresh) {
        this.loading = false;
      }
    }
  }

  private async selectSession(sessionId: string): Promise<void> {
    this.selectedSessionId = sessionId;
    try {
      this.runtimeDetail = await getAccountRuntimeSessionDetail(sessionId);
    } catch (error) {
      console.error('Failed to load runtime session detail:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to load runtime session detail';
    }
  }

  private async fetchUsers(): Promise<
    Array<{ id: string; username: string; email: string }>
  > {
    const response = await fetchWithAuth('/api/v1/users');
    if (!response.ok) {
      return [];
    }
    const data = await response.json();
    return data.users || [];
  }

  private getSourceLabel(sourceType: string | null | undefined): string {
    switch (sourceType) {
      case 'claude_code':
        return 'Claude Code';
      case 'claude_desktop':
        return 'Claude Desktop';
      case 'codex':
        return 'Codex';
      case 'openclaw':
        return 'OpenClaw';
      case 'gemini_cli':
        return 'Gemini CLI';
      case 'opencode':
        return 'OpenCode';
      case 'desktop_agent':
        return 'Desktop Agent';
      case 'custom':
        return 'Custom Agent';
      default:
        return sourceType || 'Unknown';
    }
  }

  private formatMoney(amount: number | null | undefined): string {
    return `$${(amount || 0).toFixed(2)}`;
  }

  private getLifecycleVariant(): string {
    if (!this.agent) return 'neutral';
    if (this.agent.lifecycle_state === 'decommissioned') return 'danger';
    if (this.agent.lifecycle_state === 'suspended') return 'warning';
    if (this.agent.activity_status === 'active_now') return 'success';
    if (this.agent.activity_status === 'recently_active') return 'primary';
    if (this.agent.ended_at) return 'neutral';
    return 'primary';
  }

  private getLifecycleLabel(): string {
    if (!this.agent) return 'Unknown';
    if (this.agent.lifecycle_state === 'decommissioned')
      return 'Decommissioned';
    if (this.agent.lifecycle_state === 'suspended') return 'Suspended';
    if (this.agent.activity_status === 'active_now') return 'Active now';
    if (this.agent.activity_status === 'recently_active')
      return 'Recently active';
    if (this.agent.ended_at) return 'Ended';
    return 'Idle';
  }

  private getOnboardingVariant(): string {
    if (!this.agent) return 'neutral';
    if (this.agent.onboarding_state === 'fully_onboarded') return 'success';
    if (
      this.agent.onboarding_state === 'mcp_proxy_only' ||
      this.agent.onboarding_state === 'gateway_only'
    ) {
      return 'warning';
    }
    return 'neutral';
  }

  private getOnboardingLabel(): string {
    if (!this.agent) return 'Unknown';
    if (this.agent.onboarding_state === 'fully_onboarded')
      return 'Fully onboarded';
    if (this.agent.onboarding_state === 'mcp_proxy_only') return 'MCP only';
    if (this.agent.onboarding_state === 'gateway_only') return 'Gateway only';
    return 'Incomplete';
  }

  private getOnboardingDescription(): string {
    if (!this.agent) return 'This agent is not fully managed by Preloop yet.';
    if (this.agent.onboarding_state === 'fully_onboarded') {
      return 'Tool calls and model traffic both flow through Preloop.';
    }
    if (this.agent.onboarding_state === 'mcp_proxy_only') {
      return 'Tool calls flow through Preloop, but model traffic is still direct.';
    }
    if (this.agent.onboarding_state === 'gateway_only') {
      return 'Model traffic flows through Preloop, but MCP tool traffic is still direct.';
    }
    return 'This agent is not fully managed by Preloop yet.';
  }

  private getParsedModelBudgets(): Record<
    string,
    { monthly_usd_limit?: number }
  > {
    try {
      const parsed = JSON.parse(this.modelBudgetsText || '{}');
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
      return {};
    }
  }

  private getDisplayedAgentModels(): string[] {
    const configuredModel = this.agent?.configured_model_alias?.trim();
    const budgets = this.getParsedModelBudgets();
    const models = new Set<string>();

    if (configuredModel) models.add(configuredModel);

    for (const model of this.governance?.allowed_models || []) {
      if (model) models.add(model);
    }

    for (const model of Object.keys(budgets)) {
      if (model) models.add(model);
    }

    if (models.size === 0) {
      for (const usage of this.usageByModel) {
        if (usage.model_alias) models.add(usage.model_alias);
      }
    }

    return Array.from(models).sort((a, b) => {
      if (configuredModel && a === configuredModel) return -1;
      if (configuredModel && b === configuredModel) return 1;

      const usageA = this.usageByModel.find((u) => u.model_alias === a);
      const usageB = this.usageByModel.find((u) => u.model_alias === b);
      const timeA = usageA?.last_request_at
        ? new Date(usageA.last_request_at).getTime()
        : 0;
      const timeB = usageB?.last_request_at
        ? new Date(usageB.last_request_at).getTime()
        : 0;
      return timeB - timeA;
    });
  }

  private getUsageForDisplayedModel(model: string): GatewayUsageByModel | null {
    const isConfiguredModel = model === this.agent?.configured_model_alias;
    const configuredModelId = this.agent?.configured_model_id?.trim();
    if (isConfiguredModel && configuredModelId) {
      return (
        this.usageByModel.find(
          (usage) =>
            usage.model_alias === model &&
            usage.ai_model_id === configuredModelId
        ) || null
      );
    }
    return (
      this.usageByModel.find((usage) => usage.model_alias === model) || null
    );
  }

  private getDisplayedModelId(model: string): string | null {
    const isConfiguredModel = model === this.agent?.configured_model_alias;
    if (isConfiguredModel && this.agent?.configured_model_id?.trim()) {
      return this.agent.configured_model_id.trim();
    }
    return this.getUsageForDisplayedModel(model)?.ai_model_id?.trim() || null;
  }

  private getLiveValidationVariant(): string {
    if (!this.agent?.live_validation_supported) return 'neutral';
    if (this.agent.live_validation_status === 'passed') return 'success';
    if (this.agent.live_validation_status === 'failed') return 'danger';
    return 'warning';
  }

  private getLiveValidationLabel(): string {
    if (!this.agent?.live_validation_supported) return 'No live check';
    if (this.agent.live_validation_status === 'passed') return 'Live validated';
    if (this.agent.live_validation_status === 'failed')
      return 'Live check failed';
    return 'Live check pending';
  }

  private handleGatewayActivity(message: any): void {
    const payload = message?.payload ?? {};
    if (!this.agent || payload.managed_agent_id !== this.agent.id) {
      return;
    }
    const type = message?.type;
    const nextActivityAt =
      payload.timestamp ??
      payload.last_activity_at ??
      this.liveActivity.lastActivityAt ??
      new Date().toISOString();
    this.liveActivity = {
      modelCalls:
        this.liveActivity.modelCalls + (type === 'model_gateway_call' ? 1 : 0),
      toolCalls: this.liveActivity.toolCalls + (type === 'mcp_call' ? 1 : 0),
      lastActivityAt: nextActivityAt,
    };
    this.agent = {
      ...this.agent,
      activity_status: 'active_now',
      last_seen_at: nextActivityAt ?? this.agent.last_seen_at,
      last_activity_at: nextActivityAt ?? this.agent.last_activity_at,
      last_request_at:
        type === 'model_gateway_call'
          ? (nextActivityAt ?? this.agent.last_request_at)
          : this.agent.last_request_at,
    };
    if (type === 'model_gateway_call' && this.aggregate) {
      this.aggregate = {
        ...this.aggregate,
        total_requests: this.aggregate.total_requests + 1,
        successful_requests:
          this.aggregate.successful_requests +
          ((payload.status_code ?? 200) < 400 ? 1 : 0),
        failed_requests:
          this.aggregate.failed_requests +
          ((payload.status_code ?? 200) >= 400 ? 1 : 0),
        estimated_cost:
          this.aggregate.estimated_cost + Number(payload.estimated_cost ?? 0),
        last_request_at: nextActivityAt ?? this.aggregate.last_request_at,
        latest_model_alias:
          (payload.model_alias as string | null) ??
          this.aggregate.latest_model_alias,
        latest_provider_name:
          (payload.provider_name as string | null) ??
          this.aggregate.latest_provider_name,
        token_usage: {
          ...(this.aggregate.token_usage || {}),
          total_tokens:
            (this.aggregate.token_usage?.total_tokens ?? 0) +
            (payload.total_tokens ?? 0),
        },
      };
    }

    this.scheduleRefresh();
  }

  private async saveOwnerAssignment(): Promise<void> {
    if (!this.agentId) return;
    this.actionLoading = true;
    try {
      await updateAccountAgent(this.agentId, {
        owner_user_id: this.selectedOwnerUserId || null,
      });
      await this.loadData();
    } catch (error) {
      console.error('Failed to update owner:', error);
      this.error =
        error instanceof Error ? error.message : 'Failed to update owner';
    } finally {
      this.actionLoading = false;
    }
  }

  private promptChangeOwner(): void {
    const defaultVal =
      this.agent?.owner_username || this.agent?.owner_email || '';
    const user = this.availableUsers.find(
      (u) => u.username === defaultVal.trim() || u.email === defaultVal.trim()
    );
    this.selectedOwnerUserId = user
      ? user.id
      : this.availableUsers.length > 0
        ? this.availableUsers[0].id
        : '';
    this.changeOwnerDialogOpen = true;
  }

  private async saveDisplayName(): Promise<void> {
    if (!this.agentId || !this.editableDisplayName.trim()) return;
    this.actionLoading = true;
    try {
      await updateAccountAgent(this.agentId, {
        display_name: this.editableDisplayName.trim(),
      });
      await this.loadData();
    } catch (error) {
      console.error('Failed to update agent name:', error);
      this.error =
        error instanceof Error ? error.message : 'Failed to update agent name';
    } finally {
      this.actionLoading = false;
    }
  }

  private promptRename(): void {
    const newName = window.prompt(
      'Enter the new name for this agent:',
      this.editableDisplayName
    );
    if (newName !== null && newName.trim() !== '') {
      this.editableDisplayName = newName.trim();
      this.saveDisplayName();
    }
  }

  private promptEditTags(): void {
    if (!this.agent) return;
    const currentTags = Object.entries(this.agent.tags || {})
      .map(([k, v]) => (v && v !== 'true' ? `${k}=${v}` : k))
      .join(' ');

    this.tagsDialogInput = currentTags;
    this.showTagsDialog = true;
  }

  private submitTagsDialog(): void {
    if (this.tagsDialogInput !== null) {
      const tags: Record<string, string> = {};
      this.tagsDialogInput.split(/\s+/).forEach((t: string) => {
        if (!t) return;
        const [k, ...vParts] = t.split('=');
        tags[k] = vParts.length > 0 ? vParts.join('=') : 'true';
      });
      void this.saveTags(tags);
    }
    this.showTagsDialog = false;
  }

  private async saveTags(tags: Record<string, string>): Promise<void> {
    if (!this.agentId) return;
    this.actionLoading = true;
    try {
      await updateAccountAgent(this.agentId, { tags });
      await this.loadData();
    } catch (error) {
      console.error('Failed to update tags:', error);
      this.error =
        error instanceof Error ? error.message : 'Failed to update tags';
    } finally {
      this.actionLoading = false;
    }
  }

  private async saveGovernance(): Promise<void> {
    if (!this.agentId) {
      return;
    }
    this.actionLoading = true;
    try {
      const parsedBudgets = JSON.parse(this.modelBudgetsText || '{}');
      const config: SubjectGovernanceConfig = {
        allowed_models: Object.keys(parsedBudgets).filter(
          (key) => key.trim() !== ''
        ),
        model_budgets: parsedBudgets,
        tool_rules: serializeScopedToolRules(this.scopedToolRules),
        tool_enabled_overrides: this.toolEnabledOverrides,
      };
      const response = await updateAgentGovernance(this.agentId, config);
      this.governance = response.config;
      this.scopedToolRules = normalizeScopedToolRules(
        response.config.tool_rules
      );
      this.toolEnabledOverrides = response.config.tool_enabled_overrides || {};
      this.allowedModelsText = response.config.allowed_models.join(', ');
      this.modelBudgetsText = JSON.stringify(
        response.config.model_budgets || {},
        null,
        2
      );
    } catch (error) {
      console.error('Failed to update agent governance:', error);
      this.error =
        error instanceof Error ? error.message : 'Failed to update governance';
    } finally {
      this.actionLoading = false;
    }
  }

  private getGovernanceTool(toolName: string): GovernanceToolDefinition | null {
    return (
      this.toolCatalog.find((tool) => tool.name === toolName.trim()) ?? null
    );
  }

  private getAvailableGovernanceTools(): GovernanceToolDefinition[] {
    const configured = new Set(Object.keys(this.scopedToolRules));
    return this.toolCatalog.filter((tool) => !configured.has(tool.name));
  }

  private addGovernanceToolScope(): void {
    const toolName = (
      this.governanceCustomToolName.trim() || this.governanceToolToAdd.trim()
    ).trim();
    if (!toolName || this.scopedToolRules[toolName]) {
      return;
    }
    this.scopedToolRules = {
      ...this.scopedToolRules,
      [toolName]: [],
    };
    this.governanceToolToAdd = '';
    this.governanceCustomToolName = '';
  }

  private toggleToolEnabledOverride(e: CustomEvent): void {
    const { tool, isEnabled } = e.detail;
    this.toolEnabledOverrides = {
      ...this.toolEnabledOverrides,
      [tool.name]: isEnabled,
    };
    void this.saveGovernance();
  }

  private revertScopedTool(e: CustomEvent): void {
    const { tool } = e.detail;
    if (this.scopedToolRules[tool.name]) {
      delete this.scopedToolRules[tool.name];
    }
    if (tool.name in this.toolEnabledOverrides) {
      delete this.toolEnabledOverrides[tool.name];
    }
    this.scopedToolRules = { ...this.scopedToolRules };
    this.toolEnabledOverrides = { ...this.toolEnabledOverrides };
    this.saveGovernance();
  }

  private removeGovernanceToolScope(toolName: string): void {
    const nextRules = { ...this.scopedToolRules };
    delete nextRules[toolName];
    this.scopedToolRules = nextRules;
  }

  private saveScopedToolRule(
    toolName: string,
    existingRule: AccessRuleSummary | null,
    formData: {
      action: 'allow' | 'deny' | 'require_approval';
      condition_expression: string | null;
      condition_type: 'simple' | 'cel';
      description: string | null;
      is_enabled: boolean;
      approval_workflow_id: string | null;
    }
  ): void {
    const currentRules = [...(this.scopedToolRules[toolName] || [])].sort(
      (left, right) => left.priority - right.priority
    );
    const nextRules = existingRule
      ? currentRules.map((rule) =>
          rule.id === existingRule.id ? { ...rule, ...formData } : rule
        )
      : [
          ...currentRules,
          {
            id: `scoped:${toolName}:${Date.now()}:${currentRules.length}`,
            priority: currentRules.length,
            ...formData,
          },
        ];
    this.scopedToolRules = {
      ...this.scopedToolRules,
      [toolName]: nextRules.map((rule, index) => ({
        ...rule,
        priority: index,
      })),
    };
    void this.saveGovernance();
  }

  private deleteScopedToolRule(toolName: string, ruleId: string): void {
    const nextRules = (this.scopedToolRules[toolName] || [])
      .filter((rule) => rule.id !== ruleId)
      .map((rule, index) => ({
        ...rule,
        priority: index,
      }));
    this.scopedToolRules = {
      ...this.scopedToolRules,
      [toolName]: nextRules,
    };
    void this.saveGovernance();
  }

  private reorderScopedToolRules(
    toolName: string,
    reorderedRules: { id: string; priority: number }[]
  ): void {
    const priorities = new Map(
      reorderedRules.map((rule) => [rule.id, rule.priority] as const)
    );
    const nextRules = [...(this.scopedToolRules[toolName] || [])]
      .map((rule) => ({
        ...rule,
        priority: priorities.get(rule.id) ?? rule.priority,
      }))
      .sort((left, right) => left.priority - right.priority)
      .map((rule, index) => ({
        ...rule,
        priority: index,
      }));
    this.scopedToolRules = {
      ...this.scopedToolRules,
      [toolName]: nextRules,
    };
    void this.saveGovernance();
  }

  private async refreshGovernanceWorkflows(): Promise<void> {
    try {
      this.approvalWorkflows = await getApprovalWorkflows();
    } catch (error) {
      console.error('Failed to refresh approval workflows:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to refresh approval workflows';
    }
  }

  private async removeAgent(): Promise<void> {
    if (!this.agentId || !this.agent) {
      return;
    }
    if (
      !window.confirm(
        `Remove ${this.agent.display_name} from the managed agents list? This only removes the Preloop registry record.`
      )
    ) {
      return;
    }
    this.actionLoading = true;
    try {
      await removeAccountAgent(this.agentId);
      window.location.href = '/console/agents';
    } catch (error) {
      console.error('Failed to remove managed agent:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to remove managed agent';
    } finally {
      this.actionLoading = false;
    }
  }

  private async killAgent(): Promise<void> {
    if (!this.agentId || !this.agent) {
      return;
    }
    if (
      !window.confirm(
        `Are you sure you want to KILL ${this.agent.display_name}? This will instantly suspend all routing to this agent.`
      )
    ) {
      return;
    }
    this.actionLoading = true;
    try {
      await updateAccountAgent(this.agentId, {
        lifecycle_action: 'suspend',
        reason: 'Manually killed by admin kill switch',
      });
      await this.loadData();
    } catch (error) {
      console.error('Failed to kill managed agent:', error);
      this.error =
        error instanceof Error ? error.message : 'Failed to kill managed agent';
    } finally {
      this.actionLoading = false;
    }
  }

  private formatDateTime(value: string | null | undefined): string {
    if (!value) {
      return 'None';
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    return parsed.toLocaleString();
  }

  private renderTimelineItem(item: RuntimeSessionActivityItem) {
    return html`
      <div class="timeline-item">
        <div class="timeline-title">${item.title}</div>
        <div class="timeline-meta">
          ${this.formatDateTime(item.timestamp)}${item.status
            ? html` · ${item.status}`
            : null}${item.summary ? html` · ${item.summary}` : null}
        </div>
      </div>
    `;
  }

  private get agentActions(): ResourceAction[] {
    if (!this.agent) return [];

    const actions: ResourceAction[] = [
      {
        id: 'rename',
        label: 'Rename',
        icon: 'pencil',
        onClick: () => this.promptRename(),
      },
    ];

    if (this.featureFlags.user_management) {
      actions.push({
        id: 'change-owner',
        label: 'Change Owner',
        icon: 'person-gear',
        onClick: () => this.promptChangeOwner(),
      });
    }

    actions.push({
      id: 'remove',
      label: 'Remove',
      variant: 'danger',
      loading: this.actionLoading,
      onClick: () => this.removeAgent(),
    });

    const isSuspendedOrDecommissioned =
      this.agent.lifecycle_state === 'suspended' ||
      this.agent.lifecycle_state === 'decommissioned';

    if (isSuspendedOrDecommissioned) {
      actions.push({
        id: 'replug',
        label: 'REPLUG',
        variant: 'success',
        icon: 'plug',
        loading: this.actionLoading,
        onClick: () => this.killAgent(),
        tooltip: "This action re-enables the agent's API keys.",
      });
    } else {
      actions.push({
        id: 'unplug',
        label: 'UNPLUG',
        variant: 'danger',
        icon: 'power',
        loading: this.actionLoading,
        onClick: () => this.killAgent(),
        tooltip:
          "This action immediately disables the agent's API keys and is fully reversible.",
      });
    }

    return actions;
  }

  render() {
    if (this.loading) {
      return html`
        <div class="loading-state">
          <sl-spinner></sl-spinner>
          <div>Loading agent details...</div>
        </div>
      `;
    }

    if (this.error) {
      return html`<sl-alert open variant="danger">${this.error}</sl-alert>`;
    }

    if (!this.agent) {
      return html`<div class="empty-state">Managed agent not found.</div>`;
    }

    const runtimeSessionUrl = this.agent.runtime_session_id
      ? `/console/runtime-sessions?sessionId=${encodeURIComponent(this.agent.runtime_session_id)}`
      : null;
    const aggregate = this.aggregate;

    return html`
      <view-header headerText=${this.agent.display_name}>
        <div
          slot="title-prefix"
          style="display: flex; align-items: center; color: var(--sl-color-neutral-600);"
        >
          ${renderAgentIcon(
            this.agent.session_source_type,
            'font-size: 1.2em; display: block;'
          )}
        </div>
        <div slot="top" style="margin-bottom: var(--sl-spacing-small);">
          <sl-button
            variant="default"
            size="small"
            @click=${() => window.history.back()}
          >
            <sl-icon slot="prefix" name="arrow-left"></sl-icon> Back
          </sl-button>
        </div>
        <div
          slot="main-column"
          style="display: flex; justify-content: flex-end; flex: 1; min-width: 0;"
        >
          <resource-actions .actions=${this.agentActions}></resource-actions>
        </div>
      </view-header>
      <div class="page" style="padding-top: 0;">
        <div class="header">
          <div style="flex: 1;">
            <div
              style="color: var(--sl-color-neutral-500); font-size: 0.9rem; margin-top: 4px;"
            >
              ${this.getSourceLabel(this.agent.session_source_type)} ·
              ${this.agent.session_source_id}
              ${this.agent.session_reference
                ? ` · ${this.agent.session_reference}`
                : ''}
            </div>

            <div
              style="display: flex; flex-direction: column; align-items: flex-start; gap: var(--sl-spacing-small); margin-top: var(--sl-spacing-small);"
            >
              <div class="badge-row">
                <sl-badge variant=${this.getOnboardingVariant()}>
                  ${this.getOnboardingLabel()}
                </sl-badge>
                <sl-badge variant=${this.getLifecycleVariant()}>
                  ${this.getLifecycleLabel()}
                </sl-badge>
                <sl-badge variant=${this.getLiveValidationVariant()}>
                  ${this.getLiveValidationLabel()}
                </sl-badge>
                <sl-badge variant="primary"
                  >${this.agent.enrolled_via}</sl-badge
                >
                ${this.liveActivity.modelCalls || this.liveActivity.toolCalls
                  ? html`
                      <sl-badge variant="primary">
                        Live
                        ${this.liveActivity.modelCalls +
                        this.liveActivity.toolCalls}
                      </sl-badge>
                    `
                  : null}
              </div>
              <div class="meta-line">${this.getOnboardingDescription()}</div>

              <div
                style="display: flex; gap: var(--sl-spacing-small); align-items: center; margin-top: var(--sl-spacing-x-small);"
              >
                <div
                  style="font-size: var(--sl-font-size-small); font-weight: 500; color: var(--sl-color-neutral-700);"
                >
                  Tags:
                </div>
                ${!this.agent.tags || Object.keys(this.agent.tags).length === 0
                  ? html`<span
                      style="font-size: var(--sl-font-size-small); color: var(--sl-color-neutral-400); font-style: italic;"
                      >None</span
                    >`
                  : html`<div style="display: flex; flex-wrap: wrap; gap: 4px;">
                      ${Object.entries(this.agent.tags).map(
                        ([k, v]) => html`
                          <sl-badge
                            variant="neutral"
                            style="text-transform: none;"
                          >
                            <span style="opacity: 0.7">${k}</span>${v &&
                            v !== 'true'
                              ? html`<span style="opacity: 0.4; margin: 0 4px;"
                                    >=</span
                                  >${v}`
                              : ''}
                          </sl-badge>
                        `
                      )}
                    </div>`}
                <sl-button
                  size="small"
                  variant="text"
                  @click=${this.promptEditTags}
                >
                  <sl-icon name="pencil" slot="prefix"></sl-icon> Edit
                </sl-button>
              </div>
            </div>
          </div>
        </div>

        <sl-card>
          <div class="stack">
            <div class="summary-grid">
              <div class="stat-card">
                <div class="stat-label">Preloop MCP Proxy</div>
                <div class="stat-value">
                  ${this.agent.mcp_proxy_configured ? 'Configured' : 'Missing'}
                </div>
                <div class="meta-line">
                  ${this.agent.mcp_proxy_configured
                    ? 'The local agent config points at the Preloop MCP proxy.'
                    : 'No validated Preloop MCP proxy configuration was found.'}
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Preloop Model Gateway</div>
                <div class="stat-value">
                  ${this.agent.model_gateway_configured
                    ? 'Configured'
                    : 'Missing'}
                </div>
                <div class="meta-line">
                  ${this.agent.model_gateway_configured
                    ? 'The latest enrollment records a Preloop gateway model rewrite.'
                    : 'The latest enrollment does not prove the agent model is routed through Preloop.'}
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Imported Upstream MCP Servers</div>
                <div class="stat-value">
                  ${this.agent.managed_mcp_servers.length}
                </div>
                <div class="server-badges">
                  ${this.agent.managed_mcp_servers.length
                    ? this.agent.managed_mcp_servers.map(
                        (serverName) =>
                          html`<sl-badge variant="primary"
                            >${serverName}</sl-badge
                          >`
                      )
                    : html`<span class="meta-line"
                        >No upstream MCP servers imported</span
                      >`}
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Historical Sessions</div>
                <div class="stat-value">${aggregate?.session_count ?? 0}</div>
                <div class="meta-line">
                  Last seen
                  ${this.formatDateTime(
                    this.liveActivity.lastActivityAt || this.agent.last_seen_at
                  )}
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Live Validation</div>
                <div class="stat-value">${this.getLiveValidationLabel()}</div>
                <div class="meta-line">
                  ${this.agent.last_validated_at
                    ? `Updated ${this.formatDateTime(this.agent.last_validated_at)}`
                    : 'No validation timestamp recorded yet'}
                </div>
                ${this.liveActivity.modelCalls || this.liveActivity.toolCalls
                  ? html`
                      <div class="meta-line">
                        ${this.liveActivity.modelCalls} messages ·
                        ${this.liveActivity.toolCalls} tools during this session
                      </div>
                    `
                  : null}
              </div>
              <div class="stat-card">
                <div class="stat-label">Lifecycle</div>
                <div class="stat-value">${this.getLifecycleLabel()}</div>
                <div class="meta-line">
                  ${this.agent.lifecycle_updated_at
                    ? `Updated ${this.formatDateTime(this.agent.lifecycle_updated_at)}`
                    : 'Not updated yet'}
                </div>
                ${this.agent.lifecycle_reason
                  ? html`
                      <div class="meta-line">
                        ${this.agent.lifecycle_reason}
                      </div>
                    `
                  : null}
              </div>
              <div class="stat-card">
                <div class="stat-label">Total Requests</div>
                <div class="stat-value">${aggregate?.total_requests ?? 0}</div>
                <div class="meta-line">
                  ${aggregate
                    ? `${aggregate.successful_requests} success · ${aggregate.failed_requests} failed`
                    : 'No historical usage yet'}
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Configured Model</div>
                <div class="stat-value">
                  ${this.agent.configured_model_alias || 'None'}
                </div>
                <div class="meta-line">
                  Latest used ${aggregate?.latest_model_alias || 'None yet'}
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Estimated Cost</div>
                <div class="stat-value">
                  ${this.formatMoney(aggregate?.estimated_cost)}
                </div>
                <div class="meta-line">
                  Last request
                  ${this.formatDateTime(aggregate?.last_request_at)}
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Historical Tokens</div>
                <div class="stat-value">
                  ${aggregate?.token_usage.total_tokens ?? 0}
                </div>
                <div class="meta-line">
                  ${aggregate?.successful_requests ?? 0} success ·
                  ${aggregate?.failed_requests ?? 0} failed
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Linked Runtime Session</div>
                <div class="stat-value">
                  ${this.agent.runtime_session_id ? 'Attached' : 'Not linked'}
                </div>
                ${runtimeSessionUrl
                  ? html`
                      <a class="session-link" href=${runtimeSessionUrl}>
                        Open linked runtime session
                      </a>
                    `
                  : html`<div class="meta-line">
                      No runtime session is linked yet.
                    </div>`}
              </div>
            </div>
          </div>
        </sl-card>

        <div class="split-pane-layout" style="align-items: stretch;">
          <sl-card>
            <div class="stack">
              <div class="hero">
                <div
                  style="display: flex; justify-content: space-between; align-items: center; width: 100%;"
                >
                  <div>
                    <div class="hero-title">Models & Spend</div>
                    <div class="meta-line">
                      Assign budget limits restricting maximum spend per month.
                      If a model does not have a budget, it will be prohibited.
                    </div>
                  </div>
                  <sl-button
                    size="small"
                    @click=${() => {
                      this.budgetsDialogJson = this.modelBudgetsText;
                      this.updateBudgetsDialogOpen = true;
                    }}
                  >
                    <sl-icon slot="prefix" name="pencil"></sl-icon>
                    Edit Budgets
                  </sl-button>
                </div>
              </div>
              <div class="stack">
                ${this.getDisplayedAgentModels().map((model: string) => {
                  const currentBudgets = this.getParsedModelBudgets();
                  const budget = currentBudgets[model] || {};
                  const isConfiguredModel =
                    model === this.agent?.configured_model_alias;
                  const usage = this.getUsageForDisplayedModel(model);
                  const modelId = this.getDisplayedModelId(model);
                  const showZeroSpend = isConfiguredModel && !usage;
                  return html`
                    <div
                      class="stat-card"
                      style="display: flex; gap: var(--sl-spacing-medium); align-items: center; justify-content: space-between;"
                    >
                      <div class="stat-label">
                        <sl-icon
                          name="robot"
                          style="margin-right: 4px;"
                        ></sl-icon>
                        ${modelId
                          ? html`<a
                              href="/console/settings/ai-models/${encodeURIComponent(
                                modelId
                              )}"
                              class="session-link"
                              style="font-weight: 500;"
                              >${model}</a
                            >`
                          : html`<span style="font-weight: 500;"
                              >${model}</span
                            >`}
                      </div>
                      ${usage || budget.monthly_usd_limit || showZeroSpend
                        ? html`<div style="font-size: 0.9em;">
                            ${usage || showZeroSpend
                              ? html`<span
                                  style="color: var(--sl-color-primary-600); font-weight: 600;"
                                  >${this.formatMoney(
                                    usage?.estimated_cost ?? 0
                                  )}
                                  spent</span
                                >`
                              : ''}
                            ${(usage || showZeroSpend) &&
                            budget.monthly_usd_limit
                              ? ' / '
                              : ''}
                            ${budget.monthly_usd_limit
                              ? html`<span
                                  style="color: var(--sl-color-neutral-600);"
                                  >${this.formatMoney(budget.monthly_usd_limit)}
                                  budget</span
                                >`
                              : ''}
                          </div>`
                        : ''}
                    </div>
                  `;
                })}
              </div>
            </div>
          </sl-card>

          <!-- Tools Card -->
          <sl-card
            class="tools-card"
            style="width: 100%; overflow: auto; max-height: 800px; display: flex; flex-direction: column;"
          >
            <div
              class="stack"
              style="overflow-y: auto; overflow-x: hidden; height: 100%; padding-right: 8px;"
            >
              <div class="hero" style="flex-shrink: 0;">
                <div
                  style="display: flex; justify-content: space-between; align-items: center; width: 100%;"
                >
                  <div>
                    <div class="hero-title">Tools & Governance</div>
                    <div class="meta-line">
                      Agent-specific configurations overrides applying only to
                      this agent.
                    </div>
                  </div>
                </div>
              </div>

              <tools-editor-component
                mode="scoped"
                ?collapseByDefault=${true}
                .tools=${this.toolCatalog}
                .mcpServers=${this.mcpServers}
                .scopedToolRules=${this.scopedToolRules}
                .toolEnabledOverrides=${this.toolEnabledOverrides}
                .approvalPolicies=${this.approvalWorkflows}
                .features=${this.featureFlags}
                @save-rule=${(e: CustomEvent) =>
                  this.saveScopedToolRule(
                    e.detail.tool.name,
                    e.detail.existingRule || e.detail.rule,
                    e.detail.formData
                  )}
                @delete-rule=${(e: CustomEvent) =>
                  this.deleteScopedToolRule(
                    e.detail.tool.name,
                    e.detail.rule.id
                  )}
                @reorder-rules=${(e: CustomEvent) =>
                  this.reorderScopedToolRules(
                    e.detail.tool.name,
                    e.detail.reorderedRules
                  )}
                @toggle-enabled=${this.toggleToolEnabledOverride}
                @revert-tool=${this.revertScopedTool}
                @policy-created=${() => this.loadData()}
              ></tools-editor-component>
            </div>
          </sl-card>
        </div>

        <sl-card>
          <div class="stack">
            <div class="hero">
              <div
                style="display: flex; justify-content: space-between; align-items: center; width: 100%;"
              >
                <div>
                  <div
                    class="hero-title"
                    style="display: flex; align-items: center; gap: 8px;"
                  >
                    Sessions History
                    <sl-icon-button
                      name="arrow-clockwise"
                      style="font-size: 1.1rem; color: var(--sl-color-neutral-500);"
                      @click=${() => this.loadData(true)}
                    ></sl-icon-button>
                  </div>
                  <div class="meta-line">
                    Expand a session to view its captured interactions.
                  </div>
                </div>
              </div>
            </div>
            <session-history-widget
              .sessions=${this.sessions}
            ></session-history-widget>
          </div>
        </sl-card>
      </div>

      <!-- Change Owner Dialog -->
      <sl-dialog
        class="owner-dialog"
        label="Change Owner"
        ?open=${this.changeOwnerDialogOpen}
        @sl-after-hide=${() => {
          this.changeOwnerDialogOpen = false;
        }}
      >
        <sl-select
          label="Select New Owner"
          value=${this.selectedOwnerUserId || ''}
          @sl-change=${(e: any) => {
            this.selectedOwnerUserId = e.target.value;
          }}
          hoist
        >
          ${this.availableUsers.map(
            (u) => html`
              <sl-option value=${u.id}>${u.username} (${u.email})</sl-option>
            `
          )}
        </sl-select>
        <div slot="footer">
          <sl-button
            variant="primary"
            @click=${() => {
              this.saveOwnerAssignment();
              this.changeOwnerDialogOpen = false;
            }}
            >Confirm</sl-button
          >
          <sl-button
            @click=${() => {
              this.changeOwnerDialogOpen = false;
            }}
            >Cancel</sl-button
          >
        </div>
      </sl-dialog>

      <!-- Update Budgets Dialog -->
      <sl-dialog
        class="budgets-dialog"
        label="Update Budgets"
        ?open=${this.updateBudgetsDialogOpen}
        @sl-after-hide=${() => {
          this.updateBudgetsDialogOpen = false;
        }}
        style="--width: 600px;"
      >
        <budget-policy-editor
          subjectType="managed_agent"
          .subjectId=${this.agentId || ''}
        ></budget-policy-editor>
        <div slot="footer">
          <sl-button
            @click=${() => {
              this.updateBudgetsDialogOpen = false;
            }}
            >Close</sl-button
          >
        </div>
      </sl-dialog>

      ${this.renderTagsDialog()}
    `;
  }

  private renderTagsDialog(): TemplateResult {
    return html`
      <sl-dialog
        label="Edit Tags"
        ?open=${this.showTagsDialog}
        @sl-request-close=${(e: CustomEvent) => {
          if (e.detail.source === 'overlay') {
            e.preventDefault();
          } else {
            this.showTagsDialog = false;
          }
        }}
      >
        <div style="margin-bottom: var(--sl-spacing-medium);">
          Enter tags separated by space. Use 'key=value' for key-value pairs, or
          just 'key' for boolean tags.
        </div>
        <sl-input
          placeholder="e.g. env=prod target=aws db"
          .value=${this.tagsDialogInput}
          @input=${(e: Event) =>
            (this.tagsDialogInput = (e.target as HTMLInputElement).value)}
          @keydown=${(e: KeyboardEvent) => {
            if (e.key === 'Enter') {
              this.submitTagsDialog();
            }
          }}
        ></sl-input>
        <sl-button
          slot="footer"
          variant="default"
          @click=${() => (this.showTagsDialog = false)}
        >
          Cancel
        </sl-button>
        <sl-button
          slot="footer"
          variant="primary"
          @click=${() => this.submitTagsDialog()}
        >
          Save
        </sl-button>
      </sl-dialog>
    `;
  }
}
