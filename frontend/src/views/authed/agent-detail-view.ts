import { LitElement, css, html, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';
import '../../components/governance-rule-set-editor.ts';
import '../../components/view-header.ts';
import {
  fetchWithAuth,
  getApprovalWorkflows,
  getAgentGovernance,
  getAccountAgent,
  getAccountRuntimeSessionDetail,
  getRuntimeSessionGatewayEvents,
  getFeatures,
  getTools,
  removeAccountAgent,
  updateAgentGovernance,
  updateAccountAgent,
} from '../../api';
import type {
  AccountRuntimeSessionDetailResponse,
  FlowGatewayEvent,
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
import tailwindStyles from '../../styles/tailwind.css?inline';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import {
  normalizeScopedToolRules,
  serializeScopedToolRules,
  type ScopedToolRules,
} from '../../utils/scoped-governance';

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
  private rawEvents: FlowGatewayEvent[] = [];

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
  };

  @state()
  private allowedModelsText = '';

  @state()
  private modelBudgetsText = '{}';

  @state()
  private scopedToolRules: ScopedToolRules = {};

  @state()
  private toolCatalog: GovernanceToolDefinition[] = [];

  @state()
  private approvalWorkflows: any[] = [];

  @state()
  private featureFlags: { [key: string]: boolean | string[] } = {};

  @state()
  private governanceToolToAdd = '';

  @state()
  private governanceCustomToolName = '';

  private unsubscribeRealtime?: () => void;
  private refreshTimer: number | null = null;

  static styles = [
    unsafeCSS(consoleStyles),
    unsafeCSS(tailwindStyles),
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
        font-weight: 700;
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
      void this.loadData();
    }, 250);
  }

  private async loadData(): Promise<void> {
    if (!this.agentId) {
      this.error = 'Missing agent id.';
      this.loading = false;
      return;
    }

    this.loading = true;
    this.error = null;
    this.aggregate = null;
    this.usageByModel = [];
    this.activityByServer = [];
    this.activityByTool = [];

    try {
      const [detail, users, governance, tools, workflows, features] =
        await Promise.all([
          getAccountAgent(this.agentId),
          this.fetchUsers(),
          getAgentGovernance(this.agentId),
          getTools(),
          getApprovalWorkflows(),
          getFeatures(),
        ]);
      this.agent = detail.agent;
      this.aggregate = detail.aggregate;
      this.usageByModel = detail.usage_by_model;
      this.activityByServer = detail.activity_by_server;
      this.activityByTool = detail.activity_by_tool;
      this.sessions = detail.sessions;
      this.liveActivity = {
        modelCalls: 0,
        toolCalls: 0,
        lastActivityAt: null,
      };
      this.governance = governance.config;
      this.scopedToolRules = normalizeScopedToolRules(
        governance.config.tool_rules
      );
      this.allowedModelsText = governance.config.allowed_models.join(', ');
      this.modelBudgetsText = JSON.stringify(
        governance.config.model_budgets || {},
        null,
        2
      );
      this.toolCatalog = (tools || []).map((tool: any) => ({
        name: tool.name,
        description: tool.description,
        schema:
          tool.schema && typeof tool.schema === 'object'
            ? tool.schema
            : undefined,
      }));
      this.approvalWorkflows = workflows || [];
      this.featureFlags = features?.features || {};
      this.availableUsers = users;
      this.selectedOwnerUserId = detail.agent.owner_user_id ?? '';
      this.editableDisplayName = detail.agent.display_name;
      this.selectedSessionId =
        detail.agent.runtime_session_id ?? detail.sessions[0]?.id ?? null;

      if (this.selectedSessionId) {
        this.runtimeDetail = await getAccountRuntimeSessionDetail(
          this.selectedSessionId
        );
        const eventsRes = await getRuntimeSessionGatewayEvents(
          this.selectedSessionId,
          100
        );
        this.rawEvents = eventsRes.logs || [];
      } else {
        this.runtimeDetail = null;
        this.rawEvents = [];
      }
    } catch (error) {
      console.error('Failed to load managed agent detail:', error);
      this.error =
        error instanceof Error ? error.message : 'Failed to load managed agent';
    } finally {
      this.loading = false;
    }
  }

  private async selectSession(sessionId: string): Promise<void> {
    this.selectedSessionId = sessionId;
    try {
      this.runtimeDetail = await getAccountRuntimeSessionDetail(sessionId);
      const eventsRes = await getRuntimeSessionGatewayEvents(sessionId, 100);
      this.rawEvents = eventsRes.logs || [];
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
    if (this.agent.onboarding_state === 'mcp_proxy_only') return 'Proxy only';
    if (this.agent.onboarding_state === 'gateway_only') return 'Gateway only';
    return 'Incomplete';
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
      };
    }
  }

  private async saveOwnerAssignment(): Promise<void> {
    if (!this.agentId) {
      return;
    }
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

  private async saveDisplayName(): Promise<void> {
    if (!this.agentId || !this.editableDisplayName.trim()) {
      return;
    }
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

  private async saveGovernance(): Promise<void> {
    if (!this.agentId) {
      return;
    }
    this.actionLoading = true;
    try {
      const config: SubjectGovernanceConfig = {
        allowed_models: this.allowedModelsText
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
        model_budgets: JSON.parse(this.modelBudgetsText || '{}'),
        tool_rules: serializeScopedToolRules(this.scopedToolRules),
      };
      const response = await updateAgentGovernance(this.agentId, config);
      this.governance = response.config;
      this.scopedToolRules = normalizeScopedToolRules(
        response.config.tool_rules
      );
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
    const rawEvent = this.rawEvents.find(
      (e) => e.payload?.api_usage_id === item.api_usage_id
    );
    const hasPayload = !!rawEvent?.payload;
    const payloadStr = hasPayload
      ? JSON.stringify(rawEvent.payload, null, 2)
      : '';
    let statusClass = 'border-text-muted';
    let statusGlow = '';
    if (item.status === 'error' || item.status === 'failed') {
      statusClass = 'border-danger text-danger';
      statusGlow = 'shadow-glow-danger';
    } else if (item.status === 'success' || item.status === 'completed') {
      statusClass = 'border-success text-success';
    }

    return html`
      <div
        class="border-l-4 ${statusClass} pl-4 pb-6 relative group transition-all duration-300"
      >
        <div
          class="absolute -left-[5px] top-0 size-1.5 rounded-full bg-current opacity-0 group-hover:opacity-100 transition-opacity ${statusGlow}"
        ></div>
        <div class="font-bold text-text-main text-sm mb-1">${item.title}</div>
        <div class="text-xs text-text-muted ${hasPayload ? 'mb-3' : ''}">
          <span class="font-mono">${this.formatDateTime(item.timestamp)}</span
          >${item.status
            ? html` <span class="mx-1">·</span>
                <span class="uppercase tracking-wider font-display"
                  >${item.status}</span
                >`
            : null}${item.summary
            ? html` <span class="mx-1">·</span> ${item.summary}`
            : null}
        </div>
        ${hasPayload
          ? html`
              <sl-details
                summary="View payload trace"
                style="--background-color: transparent;"
                class="glass-panel"
              >
                <div
                  class="bg-surface-base border border-white/5 rounded-md p-3 overflow-x-auto terminal-feed"
                >
                  <pre
                    class="m-0 font-mono text-[10px] text-text-muted leading-relaxed"
                  ><code>${payloadStr}</code></pre>
                </div>
              </sl-details>
            `
          : ''}
      </div>
    `;
  }

  private renderHistoricalModelBreakdown() {
    if (!this.usageByModel.length) {
      return html`
        <div class="empty-state">
          No model usage has been recorded for this agent yet.
        </div>
      `;
    }

    return html`
      <div class="timeline">
        ${this.usageByModel.map(
          (item) => html`
            <div class="timeline-item">
              <div class="timeline-title">
                ${item.model_alias || 'Unknown model'}
              </div>
              <div class="timeline-meta">
                ${item.provider_name || 'Unknown provider'} ·
                ${item.request_count} request(s) ·
                ${item.token_usage.total_tokens} tokens ·
                ${this.formatMoney(item.estimated_cost)}
              </div>
            </div>
          `
        )}
      </div>
    `;
  }

  private renderServerActivityBreakdown() {
    if (!this.activityByServer.length) {
      return html`
        <div class="empty-state">
          No MCP server activity has been recorded for this agent yet.
        </div>
      `;
    }

    return html`
      <div class="timeline">
        ${this.activityByServer.map(
          (item) => html`
            <div class="timeline-item">
              <div class="timeline-title">
                ${item.server_name || 'Unknown server'}
              </div>
              <div class="timeline-meta">
                ${item.call_count} call(s) · ${item.successful_calls} success ·
                ${item.failed_calls} failed · Last activity
                ${this.formatDateTime(item.last_activity_at)}
              </div>
            </div>
          `
        )}
      </div>
    `;
  }

  private renderToolActivityBreakdown() {
    if (!this.activityByTool.length) {
      return html`
        <div class="empty-state">
          No tool activity has been recorded for this agent yet.
        </div>
      `;
    }

    return html`
      <div class="timeline">
        ${this.activityByTool.map(
          (item) => html`
            <div class="timeline-item">
              <div class="timeline-title">
                ${item.tool_name || 'Unknown tool'}
              </div>
              <div class="timeline-meta">
                ${item.server_name || 'Unknown server'} · ${item.call_count}
                call(s) · ${item.successful_calls} success ·
                ${item.failed_calls} failed · Last activity
                ${this.formatDateTime(item.last_activity_at)}
              </div>
            </div>
          `
        )}
      </div>
    `;
  }

  render() {
    if (this.loading) {
      return html`
        <div
          class="glass-panel p-12 rounded-lg text-center flex flex-col items-center justify-center border-white/5 mx-6 mt-6"
        >
          <sl-spinner
            style="font-size: 2rem; --indicator-color: var(--color-primary);"
          ></sl-spinner>
          <div class="mt-4 font-mono text-text-muted text-sm">
            Loading agent details...
          </div>
        </div>
      `;
    }

    if (this.error) {
      return html`<sl-alert open variant="danger" class="m-6"
        >${this.error}</sl-alert
      >`;
    }

    if (!this.agent) {
      return html`<div
        class="glass-panel border-dashed p-12 text-center m-6 font-mono text-text-muted"
      >
        Managed agent not found.
      </div>`;
    }

    const runtimeSessionUrl = this.agent.runtime_session_id
      ? `/console/runtime-sessions?sessionId=${encodeURIComponent(this.agent.runtime_session_id)}`
      : null;
    const aggregate = this.aggregate;
    const liveTotal =
      this.liveActivity.modelCalls + this.liveActivity.toolCalls;

    return html`
      <div
        class="h-full flex flex-col text-text-main font-body bg-background-dark relative z-10"
      >
        <!-- Header from Stitch Layout -->
        <header
          class="flex-none h-16 border-b border-white/10 glass-panel flex items-center justify-between px-6 z-10 shrink-0"
        >
          <div class="flex items-center gap-4">
            <sl-button
              variant="default"
              size="small"
              circle
              href="/console/agents"
              class="opacity-70 hover:opacity-100"
            >
              <sl-icon name="arrow-left"></sl-icon>
            </sl-button>
            <div class="h-6 w-px bg-white/10"></div>
            <div class="flex items-center gap-3">
              ${liveTotal > 0
                ? html`
                    <div
                      class="relative flex items-center justify-center size-3"
                    >
                      <div
                        class="absolute inset-0 rounded-full bg-success opacity-40 animate-ping"
                      ></div>
                      <div
                        class="relative size-2 rounded-full bg-success"
                      ></div>
                    </div>
                  `
                : html`
                    <div
                      class="relative flex items-center justify-center size-3"
                    >
                      <div
                        class="relative size-2 rounded-full ${this.agent
                          .lifecycle_state === 'suspended'
                          ? 'bg-warning'
                          : 'bg-text-muted'}"
                      ></div>
                    </div>
                  `}
              <h1 class="font-display font-bold text-lg tracking-tight m-0">
                ${this.agent.display_name}
                <span class="text-text-muted font-normal text-sm ml-2"
                  >${this.agent.latest_model_alias || 'Unknown Model'}</span
                >
              </h1>
            </div>
          </div>
          <div class="flex items-center gap-4">
            <div
              class="font-mono text-xs text-text-muted bg-black/40 px-3 py-1.5 rounded-md border border-white/5 hidden md:block"
            >
              ${this.getSourceLabel(this.agent.session_source_type)} ·
              ${this.agent.session_source_id}
            </div>
            <sl-button
              size="small"
              variant="danger"
              class="shadow-glow-danger"
              ?loading=${this.actionLoading}
              ?disabled=${this.agent.lifecycle_state === 'suspended' ||
              this.agent.lifecycle_state === 'decommissioned'}
              @click=${this.killAgent}
            >
              <sl-icon slot="prefix" name="power"></sl-icon>
              HALT / KILL
            </sl-button>
          </div>
        </header>

        <!-- Main Split Layout -->
        <div class="flex-1 flex overflow-hidden relative">
          <!-- Left Sidebar (Stats & Config) -->
          <aside
            class="w-[320px] flex-none border-r border-white/10 glass-panel overflow-y-auto overflow-x-hidden scrollbar-hide flex flex-col p-5 gap-6"
          >
            <div class="flex flex-col gap-1">
              <div
                class="text-text-muted text-[10px] font-medium uppercase tracking-wider mb-2"
              >
                Agent Identity
              </div>
              <sl-input
                size="small"
                value=${this.editableDisplayName}
                @sl-input=${(e: Event) =>
                  (this.editableDisplayName = (
                    e.target as HTMLInputElement
                  ).value)}
              >
                <sl-icon slot="prefix" name="person"></sl-icon>
              </sl-input>
              <sl-button
                size="small"
                variant="default"
                class="mt-1"
                ?loading=${this.actionLoading}
                @click=${this.saveDisplayName}
                >Save Name</sl-button
              >
            </div>

            <!-- Metrics -->
            <div class="grid grid-cols-2 gap-3">
              <div
                class="bg-black/40 rounded-md p-3 border border-white/5 flex flex-col gap-1"
              >
                <span
                  class="text-text-muted text-[10px] font-medium uppercase tracking-wider"
                  >Estimated Cost</span
                >
                <span class="font-mono text-primary text-base"
                  >${this.formatMoney(aggregate?.estimated_cost)}</span
                >
              </div>
              <div
                class="bg-black/40 rounded-md p-3 border border-white/5 flex flex-col gap-1"
              >
                <span
                  class="text-text-muted text-[10px] font-medium uppercase tracking-wider"
                  >Total Requests</span
                >
                <span class="font-mono text-white text-base"
                  >${aggregate?.total_requests ?? 0}</span
                >
              </div>
            </div>

            <!-- Success Rate Dial -->
            <div
              class="bg-black/40 rounded-md p-5 border border-white/5 flex flex-col items-center gap-4"
            >
              <span
                class="text-text-muted text-[10px] font-medium uppercase tracking-wider self-start"
                >Success Rate</span
              >
              <div class="relative size-32">
                ${(() => {
                  const s = aggregate?.successful_requests ?? 0;
                  const t = aggregate?.total_requests || 1;
                  const pct = Math.round((s / t) * 100);
                  const circleLen = 251.2;
                  const offset = circleLen - (pct / 100) * circleLen;
                  return html`
                    <svg class="w-full h-full -rotate-90" viewBox="0 0 100 100">
                      <circle
                        cx="50"
                        cy="50"
                        fill="none"
                        r="40"
                        stroke="rgba(255,255,255,0.05)"
                        stroke-width="8"
                      ></circle>
                      <circle
                        class="drop-shadow-[0_0_8px_rgba(0,255,157,0.4)]"
                        cx="50"
                        cy="50"
                        fill="none"
                        r="40"
                        stroke="#00FF9D"
                        stroke-dasharray="${circleLen}"
                        stroke-dashoffset="${offset}"
                        stroke-width="8"
                      ></circle>
                    </svg>
                    <div
                      class="absolute inset-0 flex flex-col items-center justify-center"
                    >
                      <span class="font-display font-bold text-2xl text-success"
                        >${pct}<span class="text-sm text-success/70"
                          >%</span
                        ></span
                      >
                    </div>
                  `;
                })()}
              </div>
              <div
                class="w-full flex justify-between text-[10px] font-mono text-text-muted px-2"
              >
                <span>Total Err: ${aggregate?.failed_requests ?? 0}</span>
                <span>Tokens: ${aggregate?.token_usage.total_tokens ?? 0}</span>
              </div>
            </div>

            <div class="flex flex-col gap-2">
              <span
                class="text-text-muted text-[10px] font-medium uppercase tracking-wider"
                >Gateway Preloop Validation</span
              >
              <sl-badge
                variant=${this.agent.model_gateway_configured
                  ? 'success'
                  : 'warning'}
                >${this.agent.model_gateway_configured
                  ? 'Routing Verified'
                  : 'Gateway Missing'}</sl-badge
              >
              <sl-badge
                variant=${this.agent.mcp_proxy_configured
                  ? 'success'
                  : 'warning'}
                >${this.agent.mcp_proxy_configured
                  ? 'Proxy Verified'
                  : 'Proxy Missing'}</sl-badge
              >
            </div>

            <!-- Active Tools List (From Stitch) -->
            <div class="flex flex-col gap-3 flex-1 mt-2">
              <div class="flex items-center justify-between">
                <span
                  class="text-text-muted text-[10px] font-medium uppercase tracking-wider"
                  >Detected MCP Tools
                  (${this.agent.managed_mcp_servers.length})</span
                >
              </div>
              <div class="flex flex-col gap-2 pr-1 max-h-48 overflow-y-auto">
                ${this.agent.managed_mcp_servers.length
                  ? this.agent.managed_mcp_servers.map(
                      (serverName) => html`
                        <div
                          class="flex items-center gap-2 p-2 rounded-md bg-white/5 border border-white/5 hover:bg-white/10 transition-colors"
                        >
                          <div
                            class="size-2 rounded-full bg-primary box-glow"
                          ></div>
                          <span
                            class="font-mono text-[11px] text-text-main group-hover:text-primary transition-colors"
                            >${serverName}</span
                          >
                        </div>
                      `
                    )
                  : html`<div
                      class="text-xs text-text-muted font-mono italic p-2"
                    >
                      No imported tools detected
                    </div>`}
              </div>
            </div>

            <!-- Danger Zone -->
            <div class="border-t border-white/10 pt-4 mt-auto">
              <sl-button
                size="small"
                variant="danger"
                outline
                class="w-full"
                ?loading=${this.actionLoading}
                @click=${this.removeAgent}
              >
                Delete Agent Record
              </sl-button>
            </div>
          </aside>

          <!-- Main Terminal Area -->
          <main
            class="flex-1 overflow-y-auto flex flex-col relative bg-background-dark/50"
          >
            <sl-details
              summary="Agent Settings & Governance"
              class="glass-panel m-6 mb-0 rounded-lg"
            >
              <div class="stack">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <div class="stat-label mb-1 font-bold text-white">
                      Owner Assignment
                    </div>
                    <sl-select
                      size="small"
                      hoist
                      value=${this.selectedOwnerUserId}
                      @sl-change=${(e: CustomEvent) =>
                        (this.selectedOwnerUserId = e.detail.value || '')}
                    >
                      <sl-option value="">Unassigned</sl-option>
                      ${this.availableUsers.map(
                        (user) =>
                          html`<sl-option value=${user.id}
                            >${user.username} (${user.email})</sl-option
                          >`
                      )}
                    </sl-select>
                    <sl-button
                      size="small"
                      variant="default"
                      class="mt-2"
                      ?loading=${this.actionLoading}
                      @click=${this.saveOwnerAssignment}
                      >Save Owner</sl-button
                    >
                  </div>
                  <div>
                    <div class="stat-label mb-1 font-bold text-white">
                      Allowed Models
                    </div>
                    <sl-input
                      size="small"
                      value=${this.allowedModelsText}
                      placeholder="e.g. preloop/google/gemini-pro"
                      @sl-input=${(e: Event) =>
                        (this.allowedModelsText = (
                          e.target as HTMLInputElement
                        ).value)}
                    ></sl-input>
                  </div>
                </div>

                <div class="mt-4 border-t border-white/10 pt-4">
                  <div class="text-text-main mb-4 font-bold">
                    Scoped Tool Governance
                  </div>
                  <div class="flex gap-2 mb-4">
                    <sl-select
                      size="small"
                      placeholder="Choose tool"
                      class="flex-1"
                      .value=${this.governanceToolToAdd}
                      @sl-change=${(e: Event) =>
                        (this.governanceToolToAdd =
                          (e.target as any).value || '')}
                    >
                      ${this.getAvailableGovernanceTools().map(
                        (t) =>
                          html`<sl-option value=${t.name}>${t.name}</sl-option>`
                      )}
                    </sl-select>
                    <sl-input
                      size="small"
                      placeholder="Custom name"
                      class="flex-1"
                      .value=${this.governanceCustomToolName}
                      @sl-input=${(e: Event) =>
                        (this.governanceCustomToolName = (
                          e.target as HTMLInputElement
                        ).value)}
                    ></sl-input>
                    <sl-button
                      size="small"
                      variant="primary"
                      @click=${() => this.addGovernanceToolScope()}
                      >Add Scope</sl-button
                    >
                  </div>

                  <div class="stack">
                    ${Object.keys(this.scopedToolRules).length === 0
                      ? html`<div
                          class="text-text-muted text-sm border border-dashed border-white/10 rounded p-4 text-center"
                        >
                          No scoped tool rules configured. Inheriting account
                          policies.
                        </div>`
                      : ''}
                    ${Object.keys(this.scopedToolRules)
                      .sort()
                      .map((toolName) => {
                        const tool = this.getGovernanceTool(toolName);
                        return html`
                          <div
                            class="glass-panel p-4 rounded-md border border-white/10"
                          >
                            <div class="flex justify-between items-center mb-3">
                              <div
                                class="text-primary font-bold font-mono text-sm"
                              >
                                ${toolName}
                              </div>
                              <sl-button
                                size="small"
                                variant="danger"
                                outline
                                @click=${() =>
                                  this.removeGovernanceToolScope(toolName)}
                                >Remove Scope</sl-button
                              >
                            </div>
                            <governance-rule-set-editor
                              .toolName=${toolName}
                              .toolSchema=${tool?.schema || null}
                              .rules=${this.scopedToolRules[toolName] || []}
                              .workflows=${this.approvalWorkflows}
                              .features=${this.featureFlags}
                              emptyMessage="No scoped rules for this tool yet."
                              @save-rule=${(e: CustomEvent) =>
                                this.saveScopedToolRule(
                                  toolName,
                                  e.detail.existingRule,
                                  e.detail.formData
                                )}
                              @delete-rule=${(e: CustomEvent) =>
                                this.deleteScopedToolRule(
                                  toolName,
                                  e.detail.rule.id
                                )}
                              @reorder-rules=${(e: CustomEvent) =>
                                this.reorderScopedToolRules(
                                  toolName,
                                  e.detail.reorderedRules
                                )}
                              @workflow-created=${() =>
                                void this.refreshGovernanceWorkflows()}
                            ></governance-rule-set-editor>
                          </div>
                        `;
                      })}
                  </div>
                  <sl-button
                    variant="primary"
                    size="small"
                    class="mt-4"
                    ?loading=${this.actionLoading}
                    @click=${this.saveGovernance}
                    >Save All Settings & Governance</sl-button
                  >
                </div>
              </div>
            </sl-details>

            <div class="flex-1 p-6 relative">
              <div
                class="flex items-center justify-between pb-2 border-b border-white/10 sticky top-0 bg-background-dark/95 backdrop-blur-md z-20 -mx-6 px-6 -mt-6 pt-6"
              >
                <h2
                  class="font-display text-text-muted text-sm tracking-widest uppercase m-0"
                >
                  Live Terminal Payload Feed
                  <span class="lowercase text-xs ml-2 opacity-50"
                    >(Linked to latest runtime execution)</span
                  >
                </h2>
                <div class="flex gap-2">
                  ${runtimeSessionUrl
                    ? html`<sl-button
                        href=${runtimeSessionUrl}
                        size="small"
                        variant="default"
                        outline
                        >View Full Session Log</sl-button
                      >`
                    : null}
                </div>
              </div>

              <div class="flex flex-col gap-3 mt-4">
                ${!this.runtimeDetail
                  ? html`
                      <div
                        class="glass-panel rounded-md border border-white/5 p-8 text-center bg-black/50"
                      >
                        <span class="font-mono text-text-muted italic text-sm"
                          >No runtime session activity linked to this agent yet.
                          Awaiting gateway payload.</span
                        >
                      </div>
                    `
                  : ''}
                ${this.runtimeDetail?.activity_timeline.length === 0
                  ? html`
                      <div
                        class="glass-panel rounded-md border border-white/5 p-8 text-center bg-black/50"
                      >
                        <span class="font-mono text-text-muted italic text-sm"
                          >Waiting for incoming gateway payload events...</span
                        >
                      </div>
                    `
                  : ''}
                ${this.runtimeDetail?.activity_timeline
                  .slice(0, 50)
                  .map((item) => this.renderTimelineItem(item))}
              </div>

              <div class="pt-8">
                <sl-details
                  summary="Show Historical Breakdowns (Usage & Servers)"
                  class="glass-panel"
                >
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-8 my-4">
                    <div>
                      <h4 class="text-white font-bold mb-4 font-display">
                        Model Breakdown
                      </h4>
                      ${this.renderHistoricalModelBreakdown()}
                    </div>
                    <div>
                      <h4 class="text-white font-bold mb-4 font-display">
                        MCP Server Traffic
                      </h4>
                      ${this.renderServerActivityBreakdown()}
                    </div>
                  </div>
                </sl-details>
              </div>
            </div>
          </main>
        </div>
      </div>
    `;
  }
}
