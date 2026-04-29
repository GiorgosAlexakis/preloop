import { css, html, nothing, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';

import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/progress-bar/progress-bar.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '../../components/mcp-setup-dialog.ts';
import '../../components/budget-policy-editor.ts';
import '../../components/view-header.ts';
import {
  AuthedElement,
  fetchWithAuth,
  getAIModels,
  getAccountAgents,
  getAccountGatewayUsageSearch,
  getAccountGatewayUsageSummary,
  getAccountRuntimeSessions,
  getBudgetPolicies,
  BudgetPolicy,
  getApiUsageStats,
  getFlowExecutions,
  getFlows,
  getIssueCount,
  getMCPServers,
  getTools,
  getTrackers,
  getUsers,
} from '../../api';
import { isSaaS } from '../../brand-config';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import type {
  AccountGatewayUsageSummaryResponse,
  GatewayUsageSearchResultItem,
  ManagedAgentSummary,
  RuntimeSessionSummary,
} from '../../types';
import { parseUTCDate } from '../../utils/date';
import type { Tool } from '../../components/tool-card';
import consoleStyles from '../../styles/console-styles.css?inline';

interface AuditEvent {
  id: string;
  action: string;
  status: string;
  timestamp: string;
  details: Record<string, unknown> | null;
}

interface AuditGroup {
  correlation_id: string | null;
  primary_event: AuditEvent;
  sub_events: AuditEvent[];
  outcome: string;
}

interface GroupedAuditResponse {
  groups: AuditGroup[];
  total: number;
}

interface Tracker {
  id: string;
  name: string;
  type: string;
}

interface ApiUsage {
  total_requests: number;
}

interface MCPServer {
  id: string;
  name: string;
  url: string;
  status: string;
}

interface FlowExecution {
  id: string;
  flow_id: string;
  flow_name?: string;
  status: string;
  start_time: string;
  end_time: string | null;
  error_message: string | null;
}

interface ApprovalRequest {
  id: string;
  tool_name: string;
  status: string;
  requested_at: string;
  resolved_at?: string | null;
}

@customElement('dashboard-view')
export class DashboardView extends AuthedElement {
  @state() private loading = true;
  @state() private error: string | null = null;
  @state() private gatewaySummary: AccountGatewayUsageSummaryResponse | null =
    null;
  @state() private runtimeSessions: RuntimeSessionSummary[] = [];
  @state() private managedAgents: ManagedAgentSummary[] = [];
  @state() private gatewayInteractions: GatewayUsageSearchResultItem[] = [];
  @state() private auditGroups: AuditGroup[] = [];
  @state() private trackers: Tracker[] = [];
  @state() private apiUsage: ApiUsage | null = null;
  @state() private totalIssues = 0;
  @state() private mcpServers: MCPServer[] = [];
  @state() private tools: Tool[] = [];
  @state() private recentFlowExecutions: FlowExecution[] = [];
  @state() private pendingApprovals: ApprovalRequest[] = [];
  @state() private lastUpdatedAt: string | null = null;
  @state() private hasFlows = false;
  @state() private hasAIModels = false;
  @state() private aiModelsCount = 0;
  @state() private enabledUsersCount = 0;
  @state() private toolCallsCount = 0;
  @state() private failedToolCallsCount = 0;
  @state() private usedToolsCount = 0;
  @state() private totalFlowsCount = 0;
  @state() private totalAgentsCount = 0;
  @state() private gatewayTimeRange: 'day' | 'week' | 'month' | 'year' =
    'month';
  @state() private budgetTimeRange: 'day' | 'week' | 'month' | 'year' = 'month';
  @state() private budgetSummary: AccountGatewayUsageSummaryResponse | null =
    null;
  @state() private fetchingBudget = false;
  @state() private activeAgentsTimeRange: '5m' | '1h' | '1d' | '1w' | '1mo' =
    '1d';
  @state() private fetchingActiveAgents = false;
  @state() private showSetupDialog = false;
  @state() private showBudgetDialog = false;
  @state() private welcomeCardDismissed = false;
  @state() private gatewayMetricsExpanded = false;

  @state() private budgetPolicies: BudgetPolicy[] = [];
  @state() private dismissedExecutions: string[] = [];
  @state()
  private approvalStats = {
    total: 0,
    approved: 0,
    declined: 0,
    expired: 0,
    avgApprovalTime: 0,
  };

  private unsubscribeRealtime?: () => void;
  private refreshTimer: number | null = null;
  private refreshInFlight = false;

  private dismissExecution(id: string) {
    if (!this.dismissedExecutions.includes(id)) {
      this.dismissedExecutions = [...this.dismissedExecutions, id];
      localStorage.setItem(
        'dashboard_dismissed_executions',
        JSON.stringify(this.dismissedExecutions)
      );
    }
  }

  private formatDate(dateStr: string | null | undefined): string {
    if (!dateStr) return '';
    try {
      const date = parseUTCDate(dateStr);
      return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      }).format(date);
    } catch {
      return dateStr;
    }
  }

  static styles = [
    css`
      .tool-counts {
        display: flex;
        flex-wrap: wrap;
        gap: var(--sl-spacing-2x-large);
        margin-top: var(--sl-spacing-small);
        justify-content: center;
      }
      .tool-count {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--sl-spacing-small);
        font-size: var(--sl-font-size-small);
      }
      .tool-count sl-icon {
        font-size: 2.5rem;
      }
      .tool-count-value {
        font-size: 1.5rem;
        font-weight: 700;
      }
      .tool-count-label {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
        text-align: center;
      }
      /* Compliance-specific styles */
      .compliance-progress {
        margin-top: var(--sl-spacing-medium);
      }
      .compliance-stats {
        display: flex;
        justify-content: space-between;
        margin-bottom: var(--sl-spacing-small);
        font-size: var(--sl-font-size-small);
      }
      /* MCP Server Capsule */
      .mcp-server-capsule {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-medium);
        padding: var(--sl-spacing-small) var(--sl-spacing-medium);
        background: var(--sl-color-neutral-50);
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: 100px;
        margin-top: var(--sl-spacing-2x-large);
        margin-bottom: var(--sl-spacing-large);
        margin-left: auto;
        margin-right: auto;
        max-width: 600px;
        transition: all 0.2s ease;
      }
      .mcp-server-capsule:hover {
        background: var(--sl-color-neutral-100);
        border-color: var(--sl-color-neutral-300);
      }
      .status-indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--sl-color-success-600);
        box-shadow: 0 0 0 2px var(--sl-color-success-100);
        flex-shrink: 0;
      }
      .server-details {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        flex: 1;
        min-width: 0;
      }
      .server-endpoint {
        font-family: monospace;
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-900);
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .server-auth {
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-600);
        padding: 0.125rem 0.5rem;
        background: var(--sl-color-neutral-0);
        border-radius: 12px;
        white-space: nowrap;
        flex-shrink: 0;
      }
      .capsule-link {
        color: var(--sl-color-primary-600);
        text-decoration: none;
        font-size: var(--sl-font-size-small);
        font-weight: 500;
        white-space: nowrap;
        flex-shrink: 0;
        float: right;
      }
      .capsule-link:hover {
        text-decoration: underline;
      }
      @media (min-width: 1024px) {
        .overview-layout {
          grid-template-columns: 1fr;
        }
      }
      /* Welcome card styles */
      .getting-started-steps {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-medium);
        margin-top: var(--sl-spacing-large);
      }
      .step-item {
        display: flex;
        align-items: flex-start;
        gap: var(--sl-spacing-medium);
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-0);
        border-radius: var(--sl-border-radius-medium);
      }
      .step-item.completed {
        background: var(--sl-color-success-50);
        border-color: var(--sl-color-success-200);
      }
      .step-icon {
        flex-shrink: 0;
      }
      .step-icon sl-icon {
        font-size: 1.5rem;
      }
      .step-content {
        flex: 1;
      }
      .step-title {
        font-weight: 600;
        margin-bottom: var(--sl-spacing-2x-small);
        color: var(--sl-color-neutral-900);
      }
      .step-description {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
        margin-bottom: var(--sl-spacing-small);
      }
      .step-action {
        display: inline-block;
        margin-top: var(--sl-spacing-x-small);
      }
      .progress-overview {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        margin-top: var(--sl-spacing-large);
      }
      .progress-overview sl-progress-bar {
        flex: 1;
      }
      .progress-overview sl-progress-bar::part(base) {
        border: 1px solid rgba(230, 130, 50, 0.35);
      }
      .progress-overview sl-progress-bar::part(indicator) {
        background: var(--gradient-brand);
        position: relative;
        overflow: hidden;
      }
      .progress-overview sl-progress-bar::part(indicator)::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(
          90deg,
          transparent,
          rgba(255, 200, 100, 0.15),
          transparent
        );
        animation: shimmer 2.5s infinite;
      }
      @keyframes shimmer {
        0% {
          left: -100%;
        }
        100% {
          left: 100%;
        }
      }
      .progress-text {
        font-size: var(--sl-font-size-small);
        font-weight: 500;
      }
    `,

    unsafeCSS(consoleStyles),
    css`
      :host {
        display: block;
      }

      .loading-container {
        display: flex;
        justify-content: center;
        padding: var(--sl-spacing-2x-large);
      }

      .dashboard-stack {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }

      .updated-at {
        color: var(--sl-color-neutral-500);
        font-size: var(--sl-font-size-small);
        margin-top: -37px;
      }

      .summary-grid,
      .control-plane-grid,
      .analytics-grid {
        display: grid;
        gap: var(--sl-spacing-medium);
      }

      .summary-grid {
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      }

      .control-plane-grid {
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      }

      .analytics-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .summary-card::part(base),
      .content-card::part(base) {
        height: 100%;
      }

      .welcome-card {
        grid-column: 1 / -1;
        margin-top: var(--sl-spacing-small);
        margin-bottom: var(--sl-spacing-medium);
      }
      .welcome-card::part(base) {
        height: 100%;
        border-color: var(--sl-color-primary-500);
        box-shadow: 0 0 12px var(--sl-color-primary-100);
      }

      .metric-label,
      .analytics-label,
      .analytics-subtext,
      .step-description,
      .empty-state,
      .updated-at,
      .row-meta,
      .summary-item span:last-child,
      .capsule-hint {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .metric-value,
      .analytics-value {
        color: var(--sl-color-neutral-900);
        font-weight: 700;
        line-height: 1.1;
      }

      .metric-value {
        font-size: 1.7rem;
        margin-top: var(--sl-spacing-2x-small);
      }

      .metric-subtext {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        margin-top: var(--sl-spacing-small);
      }

      .analytics-value {
        font-size: 1.35rem;
      }

      .card-header,
      .card-header-with-action,
      .row,
      .row-main,
      .row-meta,
      .welcome-header,
      .step-item,
      .budget-stat,
      .summary-item,
      .mcp-actions {
        display: flex;
      }

      .card-header,
      .card-header-with-action {
        align-items: center;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
      }

      .card-title,
      .welcome-title,
      .step-title,
      .row-primary,
      .capsule-hint strong {
        color: var(--sl-color-neutral-900);
        font-weight: 700;
      }

      .welcome-header {
        justify-content: space-between;
        align-items: center;
        gap: var(--sl-spacing-medium);
      }

      .welcome-title {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        font-size: 1.15rem;
      }

      .welcome-content {
        margin-top: var(--sl-spacing-medium);
        color: var(--sl-color-neutral-700);
      }

      .step-item {
        gap: var(--sl-spacing-medium);
        align-items: flex-start;
      }

      .step-content {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-x-small);
        flex: 1;
      }

      .step-actions {
        display: flex;
        gap: var(--sl-spacing-small);
        flex-wrap: wrap;
        margin-top: var(--sl-spacing-x-small);
      }

      .list,
      .budget-meter,
      .summary-list,
      .mcp-summary {
        display: flex;
        flex-direction: column;
      }

      .list,
      .budget-meter,
      .mcp-summary {
        gap: var(--sl-spacing-small);
      }

      .row {
        flex-direction: column;
        gap: var(--sl-spacing-2x-small);
        padding: var(--sl-spacing-small) 0;
        border-top: 1px solid var(--sl-color-neutral-200);
      }

      .row:first-child {
        border-top: none;
        padding-top: 0;
      }

      .row-main,
      .row-meta,
      .budget-stat,
      .summary-item {
        align-items: center;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
      }

      .row-primary {
        overflow-wrap: anywhere;
      }

      .row-value,
      .summary-item strong {
        color: var(--sl-color-neutral-900);
        font-weight: 600;
        text-align: right;
      }

      .row-link,
      .header-link,
      .capsule-link {
        color: var(--sl-color-primary-700);
        text-decoration: none;
      }

      .row-link:hover,
      .header-link:hover,
      .capsule-link:hover {
        text-decoration: underline;
      }

      .summary-list {
        list-style: none;
        padding: 0;
        margin: 0;
        gap: var(--sl-spacing-small);
      }

      .summary-item {
        padding: var(--sl-spacing-2x-small) 0;
        border-top: 1px solid var(--sl-color-neutral-200);
      }

      .summary-item:first-child {
        border-top: none;
        padding-top: 0;
      }

      .server-details {
        min-width: 0;
      }

      .server-endpoint {
        display: block;
        color: var(--sl-color-neutral-900);
        font-family: var(--sl-font-mono);
        font-size: var(--sl-font-size-small);
        overflow-wrap: anywhere;
      }

      .mcp-actions {
        gap: var(--sl-spacing-small);
        align-items: center;
      }

      .empty-state {
        border: 1px dashed var(--sl-color-neutral-300);
        border-radius: var(--sl-border-radius-medium);
        padding: var(--sl-spacing-large);
        text-align: center;
        background: var(--sl-color-neutral-0);
      }

      @media (max-width: 1200px) {
        .column-layout.dashboard {
          grid-template-columns: 1fr;
        }
      }
      @media (max-width: 800px) {
        .card-header,
        .card-header-with-action,
        .row-main,
        .row-meta,
        .summary-item,
        .step-item,
        .welcome-header {
          align-items: flex-start;
          flex-direction: column;
        }

        .row-value,
        .summary-item strong {
          text-align: left;
        }

        .tool-counts,
        .analytics-grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ];

  connectedCallback(): void {
    super.connectedCallback();
    this.loadDismissedState();
    void this.fetchDashboardData();
    this.connectRealtime();
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.unsubscribeRealtime?.();
    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  private loadDismissedState(): void {
    this.welcomeCardDismissed =
      localStorage.getItem('dashboard_welcome_dismissed') === 'true';
    this.gatewayMetricsExpanded =
      localStorage.getItem('preloop_dashboard_metrics_expanded') === 'true';

    try {
      const dismissedExecsRaw = localStorage.getItem(
        'dashboard_dismissed_executions'
      );
      if (dismissedExecsRaw) {
        const parsed = JSON.parse(dismissedExecsRaw);
        if (Array.isArray(parsed)) {
          this.dismissedExecutions = parsed as string[];
        }
      }
    } catch (e) {
      console.warn('Failed to parse dismissed executions from localStorage', e);
    }
  }

  private dismissWelcomeCard(): void {
    this.welcomeCardDismissed = true;
    localStorage.setItem('dashboard_welcome_dismissed', 'true');
  }

  private toggleGatewayMetrics(): void {
    this.gatewayMetricsExpanded = !this.gatewayMetricsExpanded;
    localStorage.setItem(
      'preloop_dashboard_metrics_expanded',
      String(this.gatewayMetricsExpanded)
    );
  }

  private connectRealtime(): void {
    const scheduleRefresh = () => this.scheduleRefresh();
    const unsubscribers = [
      unifiedWebSocketManager.subscribe('runtime_sessions', scheduleRefresh),
      unifiedWebSocketManager.subscribe('managed_agents', scheduleRefresh),
      unifiedWebSocketManager.subscribe('gateway_activity', scheduleRefresh),
      unifiedWebSocketManager.subscribe('budget_health', scheduleRefresh),
      unifiedWebSocketManager.subscribe('audit', scheduleRefresh),
      unifiedWebSocketManager.subscribe('approvals', scheduleRefresh),
      unifiedWebSocketManager.subscribe('flow_executions', scheduleRefresh),
      unifiedWebSocketManager.subscribe(
        'system',
        scheduleRefresh,
        (message) => message?.type === 'authenticated'
      ),
    ];
    this.unsubscribeRealtime = () => {
      for (const unsubscribe of unsubscribers) {
        unsubscribe();
      }
    };
    void unifiedWebSocketManager.connect();
  }

  private scheduleRefresh(): void {
    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
    }
    this.refreshTimer = window.setTimeout(() => {
      this.refreshTimer = null;
      void this.fetchDashboardData({ preserveLoadingState: true });
      void this.fetchBudgetSummary();
      void this.fetchActiveAgentsData();
    }, 250);
  }

  private async fetchActiveAgentsData() {
    this.fetchingActiveAgents = true;
    try {
      const now = new Date();
      let startDateStr = '';

      if (this.activeAgentsTimeRange === '5m') {
        const d = new Date(now);
        d.setMinutes(d.getMinutes() - 5);
        startDateStr = d.toISOString();
      } else if (this.activeAgentsTimeRange === '1h') {
        const d = new Date(now);
        d.setHours(d.getHours() - 1);
        startDateStr = d.toISOString();
      } else if (this.activeAgentsTimeRange === '1d') {
        const d = new Date(now);
        d.setDate(d.getDate() - 1);
        startDateStr = d.toISOString();
      } else if (this.activeAgentsTimeRange === '1w') {
        const d = new Date(now);
        d.setDate(d.getDate() - 7);
        startDateStr = d.toISOString();
      } else if (this.activeAgentsTimeRange === '1mo') {
        const d = new Date(now);
        d.setMonth(d.getMonth() - 1);
        startDateStr = d.toISOString();
      }

      const runtimeSessionsParams: any = { status: 'all', limit: 100 };
      const agentsParams: any = { status: 'all', limit: 100 };
      if (startDateStr) {
        runtimeSessionsParams.startDate = startDateStr;
        agentsParams.lastSeenAfter = startDateStr;
      }

      const [runtimeSessions, managedAgents] = await Promise.all([
        this.catchWith403Handling(
          getAccountRuntimeSessions(runtimeSessionsParams),
          { items: [] } as Awaited<ReturnType<typeof getAccountRuntimeSessions>>
        ),
        this.catchWith403Handling(getAccountAgents(agentsParams), {
          items: [],
        } as Awaited<ReturnType<typeof getAccountAgents>>),
      ]);

      this.runtimeSessions = runtimeSessions.items || [];
      this.managedAgents = managedAgents.items || [];
    } catch (error) {
      console.error('Failed to load active agents data', error);
    } finally {
      this.fetchingActiveAgents = false;
    }
  }

  private async fetchBudgetSummary() {
    this.fetchingBudget = true;
    try {
      const now = new Date();
      let startDateStr = '';

      if (this.budgetTimeRange === 'day') {
        const d = new Date(now);
        d.setDate(d.getDate() - 1);
        startDateStr = d.toISOString();
      } else if (this.budgetTimeRange === 'week') {
        const d = new Date(now);
        d.setDate(d.getDate() - 7);
        startDateStr = d.toISOString();
      } else if (this.budgetTimeRange === 'month') {
        const d = new Date(now);
        d.setMonth(d.getMonth() - 1);
        startDateStr = d.toISOString();
      } else if (this.budgetTimeRange === 'year') {
        const d = new Date(now);
        d.setFullYear(d.getFullYear() - 1);
        startDateStr = d.toISOString();
      }

      const [budgetSummary, policies] = await Promise.all([
        getAccountGatewayUsageSummary({ startDate: startDateStr }).catch(
          () => null
        ),
        getBudgetPolicies().catch(() => [] as BudgetPolicy[]),
      ]);
      this.budgetSummary = budgetSummary;
      this.budgetPolicies = Array.isArray(policies) ? policies : [];
    } finally {
      this.fetchingBudget = false;
    }
  }

  private async catchWith403Handling<T>(
    promise: Promise<T>,
    defaultValue: T
  ): Promise<T> {
    try {
      return await promise;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes('403')) {
        return defaultValue;
      }
      console.error('Dashboard data fetch error:', error);
      return defaultValue;
    }
  }

  private async fetchDashboardData(
    options: { preserveLoadingState?: boolean } = {}
  ) {
    if (this.refreshInFlight) {
      return;
    }
    this.refreshInFlight = true;
    if (!options.preserveLoadingState) {
      this.loading = true;
    }
    this.error = null;

    try {
      const now = new Date();
      let startDateStr = '';

      if (this.gatewayTimeRange === 'day') {
        const d = new Date(now);
        d.setDate(d.getDate() - 1);
        startDateStr = d.toISOString();
      } else if (this.gatewayTimeRange === 'week') {
        const d = new Date(now);
        d.setDate(d.getDate() - 7);
        startDateStr = d.toISOString();
      } else if (this.gatewayTimeRange === 'month') {
        const d = new Date(now);
        d.setMonth(d.getMonth() - 1);
        startDateStr = d.toISOString();
      } else if (this.gatewayTimeRange === 'year') {
        const d = new Date(now);
        d.setFullYear(d.getFullYear() - 1);
        startDateStr = d.toISOString();
      }

      const [
        gatewaySummary,
        gatewayInteractions,
        audit,
        trackers,
        apiUsage,
        issueCount,
        mcpServers,
        tools,
        flows,
        flowExecutions,
        pendingApprovals,
        allApprovalRequests,
        aiModels,
        users,
        toolCallsStats,
        failedToolCallsStats,
        usedToolsStats,
        totalAgentsStats,
      ] = await Promise.all([
        this.catchWith403Handling(
          getAccountGatewayUsageSummary({ startDate: startDateStr }),
          null
        ),
        this.catchWith403Handling(getAccountGatewayUsageSearch({ limit: 12 }), {
          items: [],
        } as Awaited<ReturnType<typeof getAccountGatewayUsageSearch>>),
        this.catchWith403Handling(this.fetchAuditExceptions(), {
          groups: [],
          total: 0,
        }),
        this.catchWith403Handling(getTrackers(), [] as Tracker[]),
        this.catchWith403Handling(getApiUsageStats(), null),
        this.catchWith403Handling(getIssueCount(), { total_issues: 0 }),
        this.catchWith403Handling(getMCPServers(), [] as MCPServer[]),
        this.catchWith403Handling(getTools(), [] as Tool[]),
        this.catchWith403Handling(getFlows(), [] as any[]),
        this.catchWith403Handling(
          getFlowExecutions({ limit: 5 }),
          [] as FlowExecution[]
        ),
        this.catchWith403Handling(this.fetchApprovalRequests('pending', 3), []),
        this.catchWith403Handling(
          this.fetchApprovalRequests(undefined, 100),
          []
        ),
        this.catchWith403Handling(getAIModels(), []),
        this.catchWith403Handling(
          isSaaS()
            ? getUsers()
            : Promise.resolve({
                users: [],
                total: 0,
                skip: 0,
                limit: 0,
              }),
          {
            users: [],
            total: 0,
            skip: 0,
            limit: 0,
          }
        ),
        this.catchWith403Handling(
          fetchWithAuth(
            '/api/v1/audit-logs/grouped?event_type=tool_call&limit=1'
          ).then((r) => r.json()),
          { total: 0 }
        ),
        this.catchWith403Handling(
          fetchWithAuth(
            '/api/v1/audit-logs/grouped?event_type=tool_call&outcome=failed&limit=1'
          ).then((r) => r.json()),
          { total: 0 }
        ),
        this.catchWith403Handling(
          fetchWithAuth(
            '/api/v1/audit-logs/grouped?event_type=tool_call&group_by=tool_name'
          ).then((r) => r.json()),
          { groups: [] }
        ),
        this.catchWith403Handling(
          getAccountAgents({ status: 'all', limit: 1 }),
          { total: 0 }
        ),
      ]);

      this.gatewaySummary = gatewaySummary;
      this.gatewayInteractions = gatewayInteractions.items || [];
      this.auditGroups = audit.groups || [];
      this.trackers = trackers;
      this.apiUsage = apiUsage;
      this.totalIssues = issueCount.total_issues;
      this.mcpServers = mcpServers;
      this.tools = tools;
      this.hasFlows = (flows || []).length > 0;
      this.totalFlowsCount = (flows || []).length;
      this.recentFlowExecutions = [...(flowExecutions || [])]
        .sort(
          (left, right) =>
            new Date(right.start_time).getTime() -
            new Date(left.start_time).getTime()
        )
        .slice(0, 5);
      this.pendingApprovals = pendingApprovals;
      this.hasAIModels = (aiModels || []).length > 0;
      this.aiModelsCount = Array.isArray(aiModels) ? aiModels.length : 0;
      this.enabledUsersCount = Array.isArray(users.users)
        ? users.users.filter((u: { is_active?: boolean }) => u.is_active).length
        : 0;
      this.toolCallsCount = toolCallsStats?.total || 0;
      this.failedToolCallsCount = failedToolCallsStats?.total || 0;
      const usedToolNames = new Set(
        (usedToolsStats?.groups || []).map((g: any) => g.group_value)
      );
      this.usedToolsCount = this.tools.filter(
        (t: any) => t.is_enabled && usedToolNames.has(t.name)
      ).length;
      this.totalAgentsCount = totalAgentsStats?.total || 0;
      this.calculateApprovalStats(allApprovalRequests);

      if (!this.budgetSummary) {
        this.budgetSummary = gatewaySummary; // initialize if null
      }

      this.lastUpdatedAt = new Date().toISOString();
    } catch (error) {
      console.error('Failed to load overview dashboard', error);
      this.error = 'Failed to load the overview dashboard.';
    } finally {
      this.loading = false;
      this.refreshInFlight = false;
    }
  }

  private async fetchAuditExceptions(): Promise<GroupedAuditResponse> {
    const params = new URLSearchParams();
    params.set('limit', '12');
    params.append('outcome', 'failed');
    params.append('outcome', 'budget_denied');
    const response = await fetchWithAuth(
      `/api/v1/audit-logs/grouped?${params}`
    );
    if (!response.ok) {
      throw new Error('Failed to fetch audit exceptions');
    }
    return response.json();
  }

  private async fetchApprovalRequests(
    status?: string,
    limit: number = 100
  ): Promise<ApprovalRequest[]> {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    if (status) {
      params.set('status', status);
    }
    const response = await fetchWithAuth(
      `/api/v1/approval-requests?${params.toString()}`
    );
    if (!response.ok) {
      throw new Error('Failed to fetch approval requests');
    }
    return response.json();
  }

  private calculateApprovalStats(requests: ApprovalRequest[]): void {
    const total = requests.length;
    const approved = requests.filter(
      (request) => request.status === 'approved'
    ).length;
    const declined = requests.filter(
      (request) => request.status === 'declined'
    ).length;
    const expired = requests.filter(
      (request) => request.status === 'expired'
    ).length;

    let totalTimeMinutes = 0;
    let resolvedCount = 0;
    for (const request of requests) {
      if (
        (request.status === 'approved' || request.status === 'declined') &&
        request.resolved_at
      ) {
        totalTimeMinutes +=
          (parseUTCDate(request.resolved_at).getTime() -
            parseUTCDate(request.requested_at).getTime()) /
          60000;
        resolvedCount += 1;
      }
    }

    this.approvalStats = {
      total,
      approved,
      declined,
      expired,
      avgApprovalTime:
        resolvedCount > 0 ? Math.round(totalTimeMinutes / resolvedCount) : 0,
    };
  }

  private get activeAgents(): ManagedAgentSummary[] {
    return [...this.managedAgents].sort(
      (left, right) =>
        new Date(right.last_seen_at).getTime() -
        new Date(left.last_seen_at).getTime()
    );
  }

  private get activeSessions(): RuntimeSessionSummary[] {
    return [...this.runtimeSessions].sort((left, right) => {
      const leftTs = left.last_activity_at || left.started_at;
      const rightTs = right.last_activity_at || right.started_at;
      return new Date(rightTs).getTime() - new Date(leftTs).getTime();
    });
  }

  private get gatewayFailures(): GatewayUsageSearchResultItem[] {
    return this.gatewayInteractions.filter(
      (item) => item.outcome !== 'success'
    );
  }

  private get failedFlowExecutions(): FlowExecution[] {
    return this.recentFlowExecutions.filter(
      (execution) =>
        execution.status === 'FAILED' &&
        !this.dismissedExecutions.includes(execution.id)
    );
  }

  private get hasBudgetCard(): boolean {
    const budget = this.gatewaySummary?.budget;
    return Boolean(
      this.gatewaySummary?.total_requests ||
      budget?.monthly_limit_usd ||
      budget?.soft_limit_usd
    );
  }

  private formatCurrency(value: number | null | undefined): string {
    return `$${(value || 0).toFixed(2)}`;
  }

  private formatNumber(value: number | null | undefined): string {
    return Intl.NumberFormat().format(value || 0);
  }

  private formatDateTime(value: string | null | undefined): string {
    if (!value) {
      return 'Never';
    }
    return parseUTCDate(value).toLocaleString();
  }

  private formatRelativeTime(value: string | null | undefined): string {
    if (!value) {
      return 'Never';
    }
    const timestamp = parseUTCDate(value).getTime();
    const deltaMinutes = Math.round((Date.now() - timestamp) / 60000);
    if (deltaMinutes < 1) {
      return 'just now';
    }
    if (deltaMinutes < 60) {
      return `${deltaMinutes}m ago`;
    }
    const deltaHours = Math.round(deltaMinutes / 60);
    if (deltaHours < 24) {
      return `${deltaHours}h ago`;
    }
    return `${Math.round(deltaHours / 24)}d ago`;
  }

  private getStatusColor(status: string): string {
    switch (status.toLowerCase()) {
      case 'active':
      case 'succeeded':
      case 'approved':
        return 'success';
      case 'failed':
      case 'error':
      case 'declined':
        return 'danger';
      case 'running':
      case 'pending':
        return 'warning';
      default:
        return 'neutral';
    }
  }

  private getGlobalPolicyUsage() {
    return this.calculatePolicyUsages().find(
      (u) =>
        u.policy.subject_type === 'global' ||
        u.policy.subject_type === 'account'
    );
  }

  private budgetVariant() {
    const globalUsage = this.getGlobalPolicyUsage();
    if (globalUsage && globalUsage.limit > 0) {
      if (globalUsage.percent >= 100) return 'danger';
      if (globalUsage.percent >= 80) return 'warning';
      return 'success';
    }

    const budget = this.budgetSummary?.budget;
    if (!budget) {
      return 'neutral';
    }
    if (budget.hard_limit_exceeded) {
      return 'danger';
    }
    if (budget.soft_limit_exceeded) {
      return 'warning';
    }
    return 'success';
  }

  private budgetPercent(): number {
    const globalUsage = this.getGlobalPolicyUsage();
    if (globalUsage && globalUsage.limit > 0) {
      return globalUsage.percent;
    }

    const budget = this.budgetSummary?.budget;
    const limit = budget?.monthly_limit_usd || budget?.soft_limit_usd || 0;
    if (!limit) {
      return 0;
    }
    return Math.min(
      100,
      Math.round(((budget?.current_spend_usd || 0) / limit) * 100)
    );
  }

  private calculatePolicyUsages() {
    if (!this.budgetSummary || !this.budgetPolicies) return [];

    return this.budgetPolicies
      .map((policy) => {
        let spend = 0;
        if (policy.subject_type === 'global') {
          spend = this.budgetSummary!.budget?.current_spend_usd || 0;
        } else if (policy.subject_type === 'ai_model') {
          spend = this.budgetSummary!.usage_by_model.filter(
            (m) => m.ai_model_id === policy.subject_id
          ).reduce((acc, m) => acc + m.estimated_cost, 0);
        } else if (policy.subject_type === 'managed_agent') {
          spend = this.budgetSummary!.usage_by_session.filter(
            (s) =>
              s.session_source_type === 'managed_agent' &&
              s.session_source_id === policy.subject_id
          ).reduce((acc, s) => acc + s.estimated_cost, 0);
        }

        const limit = policy.hard_limit_usd || policy.soft_limit_usd || 0;
        const percent =
          limit > 0 ? Math.min(100, Math.round((spend / limit) * 100)) : 0;

        return { policy, spend, limit, percent };
      })
      .sort((a, b) => b.percent - a.percent);
  }

  private renderEmptyState(message: string) {
    return html`<div class="empty-state">${message}</div>`;
  }

  private renderWelcomeCard() {
    if (this.welcomeCardDismissed) {
      return nothing;
    }

    const hasMCPServers = this.mcpServers.length > 0;
    const hasFlows = this.hasFlows;
    const hasTrackersAndModels = this.trackers.length > 0 && this.hasAIModels;

    const completedSteps = [
      hasMCPServers,
      hasFlows,
      hasTrackersAndModels,
    ].filter(Boolean).length;
    const totalSteps = 3;
    const progress = (completedSteps / totalSteps) * 100;

    return html`
      <sl-card class="welcome-card">
        <div class="welcome-header">
          <div class="welcome-title">
            <sl-icon name="rocket-takeoff"></sl-icon>
            Welcome to Preloop!
          </div>
          <sl-button
            size="small"
            variant="text"
            @click=${this.dismissWelcomeCard}
          >
            <sl-icon name="x-lg"></sl-icon>
          </sl-button>
        </div>

        <div class="welcome-content">
          Preloop helps you automate your workflow safely by deploying
          event-driven flows, or by onboarding existing agents. Here's how to
          get started:
        </div>

        <div
          class="getting-started-paths"
          style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--sl-spacing-medium); margin-top: var(--sl-spacing-large);"
        >
          <!-- Path 1: Govern Agents -->
          <div class="step-item">
            <div class="step-icon">
              <sl-icon
                name="shield-check"
                style="color: var(--sl-color-primary-600);"
              ></sl-icon>
            </div>
            <div class="step-content">
              <div class="step-title">Govern Existing Agents</div>
              <div class="step-description">
                Bring your own local agents (e.g., OpenClaw). Use the CLI to
                onboard them instantly, syncing their tools and models behind
                powerful approval firewalls.
              </div>
              <div class="step-actions">
                <sl-button size="small" href="/console/agents">
                  <sl-icon slot="prefix" name="robot"></sl-icon>
                  View Agents
                </sl-button>
              </div>
            </div>
          </div>
          <!-- Path 2: Build Flows -->
          <div class="step-item">
            <div class="step-icon">
              <sl-icon
                name="diagram-3"
                style="color: var(--sl-color-primary-600);"
              ></sl-icon>
            </div>
            <div class="step-content">
              <div class="step-title">Build Agentic Automations</div>
              <div class="step-description">
                Design custom event-driven flows natively in Preloop. Connect AI
                models, add MCP servers for custom tools, and trigger agents
                from incoming events.
              </div>
              <div class="step-actions">
                <sl-button size="small" href="/console/flows/new">
                  <sl-icon slot="prefix" name="plus-circle"></sl-icon>
                  Create Flow
                </sl-button>
                <sl-button size="small" variant="text" href="/console/tools">
                  Add Tools
                </sl-button>
              </div>
            </div>
          </div>
        </div>

        <div class="progress-overview">
          <sl-progress-bar value="${progress}"></sl-progress-bar>
          <span class="progress-text"
            >${completedSteps} / ${totalSteps} completed</span
          >
        </div>
      </sl-card>
    `;
  }

  private renderRecentFlowExecutionsCard() {
    return html`
      <!-- Flow Executions -->
      <sl-card>
        <div slot="header" class="chart-header">
          <sl-icon name="diagram-3"></sl-icon>
          Recent Flow Executions
          ${this.failedFlowExecutions.length > 0
            ? html`<sl-badge variant="danger" pulse
                >${this.failedFlowExecutions.length} failed</sl-badge
              >`
            : ''}
        </div>

        ${this.recentFlowExecutions.length === 0
          ? html`
              <div class="empty-state">
                <sl-icon name="inbox"></sl-icon>
                <p>
                  No flow executions yet.
                  <a href="/console/flows">Create a flow</a>
                </p>
              </div>
            `
          : html`
              <div class="item-list">
                ${this.recentFlowExecutions
                  .filter((exec) => !this.dismissedExecutions.includes(exec.id))
                  .slice(0, 5)
                  .map(
                    (exec) => html`
                      <div
                        class="item-card ${exec.status === 'FAILED'
                          ? 'danger'
                          : ''}"
                      >
                        <div class="item-info">
                          <span class="item-name"
                            >${exec.flow_name || 'Unnamed Flow'}</span
                          >
                          ${exec.error_message
                            ? html`<span class="item-error"
                                >${exec.error_message}</span
                              >`
                            : ''}
                          <span class="item-secondary"
                            >${this.formatDate(exec.start_time)}</span
                          >
                        </div>
                        <div
                          style="display: flex; align-items: center; gap: var(--sl-spacing-small);"
                        >
                          <sl-tag
                            size="small"
                            variant="${this.getStatusColor(exec.status)}"
                          >
                            ${exec.status}
                          </sl-tag>
                          <sl-button
                            size="small"
                            href="/console/flows/executions/${exec.id}"
                          >
                            View
                          </sl-button>
                          <sl-icon-button
                            name="x-lg"
                            label="Dismiss"
                            @click=${(e: Event) => {
                              e.preventDefault();
                              this.dismissExecution(exec.id);
                            }}
                          ></sl-icon-button>
                        </div>
                      </div>
                    `
                  )}
              </div>

              <div class="quick-actions">
                <sl-button size="small" href="/console/flows/executions">
                  <sl-icon slot="prefix" name="list"></sl-icon>
                  View All Executions
                </sl-button>
                <sl-button size="small" href="/console/flows">
                  <sl-icon slot="prefix" name="plus-circle"></sl-icon>
                  Create Flow
                </sl-button>
              </div>
            `}
      </sl-card>
    `;
  }
  private renderBudgetHealthCard() {
    if (!this.hasBudgetCard) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div slot="header" class="card-header-with-action">
          Budget health
          <select
            style="background: transparent; border: none; font-size: var(--sl-font-size-small); color: var(--sl-color-neutral-600); cursor: pointer; outline: none; margin-left: auto;"
            .value=${this.budgetTimeRange}
            @change=${(e: Event) => {
              this.budgetTimeRange = (e.target as HTMLSelectElement)
                .value as any;
              this.fetchBudgetSummary();
            }}
          >
            <option value="day">24h</option>
            <option value="week">7d</option>
            <option value="month">30d</option>
            <option value="year">1y</option>
          </select>
        </div>
        ${this.fetchingBudget
          ? html`<div
              class="loading-container"
              style="padding: var(--sl-spacing-small);"
            >
              <sl-spinner></sl-spinner>
            </div>`
          : this.renderBudgetHealthContent()}
      </sl-card>
    `;
  }

  private renderBudgetHealthContent() {
    const globalUsage = this.getGlobalPolicyUsage();
    const limit =
      globalUsage && globalUsage.limit > 0
        ? globalUsage.limit
        : this.budgetSummary?.budget?.monthly_limit_usd ||
          this.budgetSummary?.budget?.soft_limit_usd ||
          0;
    const usages = this.calculatePolicyUsages();
    return html`
      <div
        style="display: flex; flex-direction: column; gap: var(--sl-spacing-medium);"
      >
        <div
          style="display: flex; align-items: center; justify-content: space-between;"
        >
          ${limit > 0
            ? html`
                <sl-badge variant=${this.budgetVariant()}>
                  ${this.budgetVariant().toUpperCase()}
                </sl-badge>
              `
            : html` <sl-badge variant="neutral"> NO LIMIT </sl-badge> `}
          <div style="font-weight: 600; font-size: 1.1rem;">
            $${(this.budgetSummary?.budget?.current_spend_usd || 0).toFixed(2)}
          </div>
        </div>
        ${limit > 0
          ? html`
              <div class="progress-overview" style="margin-top: 0;">
                <sl-progress-bar
                  value=${this.budgetPercent()}
                  class="budget-${this.budgetVariant()}"
                ></sl-progress-bar>
              </div>
              <div
                style="display: flex; justify-content: space-between; font-size: var(--sl-font-size-x-small); color: var(--sl-color-neutral-500);"
              >
                <span>0</span>
                <span>$${limit.toFixed(2)} Limit</span>
              </div>
            `
          : nothing}
        <div style="margin-top: var(--sl-spacing-small);">
          <sl-button
            size="small"
            variant="default"
            @click=${() => (this.showBudgetDialog = true)}
            style="width: 100%;"
          >
            <sl-icon slot="prefix" name="gear"></sl-icon>
            Configure Limits
          </sl-button>
        </div>

        ${usages.length > 0
          ? html`
              <div
                style="border-top: 1px solid var(--sl-color-neutral-200); padding-top: var(--sl-spacing-small); margin-top: var(--sl-spacing-small);"
              >
                <div
                  style="color: var(--sl-color-neutral-700); font-size: var(--sl-font-size-small); font-weight: 500; margin-bottom: var(--sl-spacing-small);"
                >
                  Configured limits
                </div>
                <div
                  style="display: flex; flex-direction: column; gap: var(--sl-spacing-small); max-height: 300px; overflow-y: auto; padding-right: var(--sl-spacing-x-small);"
                >
                  ${usages.map(
                    (u) => html`
                      <div
                        style="display: flex; flex-direction: column; gap: 4px;"
                      >
                        <div
                          style="display: flex; justify-content: space-between; font-size: var(--sl-font-size-small); align-items: center;"
                        >
                          <span
                            style="display: flex; align-items: center; gap: 4px;"
                          >
                            ${u.policy.subject_type === 'global'
                              ? html`<sl-icon name="globe"></sl-icon> Global`
                              : u.policy.subject_type === 'ai_model'
                                ? html`<sl-icon name="cpu"></sl-icon> Model`
                                : html`<sl-icon name="robot"></sl-icon> Agent`}
                          </span>
                          <span style="font-weight: 500;">
                            $${u.spend.toFixed(2)} / $${u.limit.toFixed(2)}
                          </span>
                        </div>
                        <sl-progress-bar
                          value=${u.percent}
                          class="budget-${u.percent >= 100
                            ? 'danger'
                            : u.percent >= 80
                              ? 'warning'
                              : 'success'}"
                          style="--height: 4px;"
                        ></sl-progress-bar>
                      </div>
                    `
                  )}
                </div>
              </div>
            `
          : nothing}
      </div>
    `;
  }

  private renderGatewayFailuresCard() {
    if (this.gatewayFailures.length === 0) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Gateway failures needing attention</div>
          <a class="row-link" href="/console/api-usage"
            >Open gateway activity</a
          >
        </div>
        <div class="list">
          ${repeat(
            this.gatewayFailures.slice(0, 6),
            (item) => item.api_usage_id,
            (item) => html`
              <div class="row">
                <div class="row-main">
                  <a
                    class="row-link row-primary"
                    href=${item.runtime_session_id
                      ? `/console/runtime-sessions?sessionId=${item.runtime_session_id}`
                      : '/console/api-usage'}
                  >
                    ${item.model_alias || item.provider_name || item.endpoint}
                  </a>
                  <sl-badge variant="danger">${item.status_code}</sl-badge>
                </div>
                <div class="row-meta">
                  <span>
                    ${item.runtime_principal_name ||
                    item.session_reference ||
                    item.endpoint}
                  </span>
                  <span>${this.formatRelativeTime(item.timestamp)}</span>
                </div>
              </div>
            `
          )}
        </div>
      </sl-card>
    `;
  }

  private renderAuditExceptionsCard() {
    if (this.auditGroups.length === 0) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Audit exceptions</div>
          <a class="row-link" href="/console/audit">Open audit timeline</a>
        </div>
        <div class="list">
          ${repeat(
            this.auditGroups.slice(0, 6),
            (group) => group.primary_event.id,
            (group) => html`
              <div class="row">
                <div class="row-main">
                  <span class="row-primary">
                    ${group.primary_event.action.replace(/_/g, ' ')}
                  </span>
                  <sl-badge
                    variant=${group.outcome === 'budget_denied'
                      ? 'warning'
                      : 'danger'}
                  >
                    ${group.outcome}
                  </sl-badge>
                </div>
                <div class="row-meta">
                  <span>
                    ${(group.primary_event.details?.requested_model as
                      | string
                      | undefined) ||
                    (group.primary_event.details?.tool_name as
                      | string
                      | undefined) ||
                    group.primary_event.id}
                  </span>
                  <span>
                    ${this.formatRelativeTime(group.primary_event.timestamp)}
                  </span>
                </div>
              </div>
            `
          )}
        </div>
      </sl-card>
    `;
  }

  private renderTopModelsCard() {
    const models = this.gatewaySummary?.usage_by_model || [];
    if (models.length === 0) {
      return nothing;
    }

    const allSessions = this.gatewaySummary?.usage_by_session || [];

    return html`
      <sl-card class="content-card">
        <div slot="header" class="card-header-with-action">
          Top Models by Usage
          <div
            style="display: flex; gap: var(--sl-spacing-small); align-items: center;"
          >
            <a href="/console/ai-models" class="header-action-link"
              >Model fleet</a
            >
          </div>
        </div>
        <div class="list">
          ${repeat(
            models.slice(0, 6),
            (item) =>
              `${item.ai_model_id}-${item.model_alias}-${item.provider_name}`,
            (item) => {
              const modelSessions = allSessions.filter(
                (s) =>
                  (s.ai_model_id &&
                    item.ai_model_id &&
                    s.ai_model_id === item.ai_model_id) ||
                  (!s.ai_model_id &&
                    !item.ai_model_id &&
                    s.model_alias === item.model_alias)
              );

              const agentGroups = new Map<string, typeof modelSessions>();
              const orphanSessions: typeof modelSessions = [];

              modelSessions.forEach((s) => {
                if (
                  s.session_source_type === 'managed_agent' &&
                  s.session_source_id
                ) {
                  const key = s.session_source_id;
                  if (!agentGroups.has(key)) agentGroups.set(key, []);
                  agentGroups.get(key)!.push(s);
                } else {
                  orphanSessions.push(s);
                }
              });

              return html`
                <div
                  class="row"
                  style="flex-direction: column; align-items: stretch; gap: var(--sl-spacing-2x-small);"
                >
                  <div
                    style="display: flex; justify-content: space-between; align-items: center;"
                  >
                    <div
                      style="display: flex; align-items: center; gap: var(--sl-spacing-2x-small); overflow: hidden;"
                    >
                      ${item.ai_model_id
                        ? html`
                            <a
                              class="row-link row-primary"
                              href=${`/console/ai-models/${item.ai_model_id}`}
                              style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
                            >
                              ${item.model_alias || 'Unknown model'}
                            </a>
                          `
                        : html`
                            <span
                              class="row-primary"
                              style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
                            >
                              ${item.model_alias || 'Unknown model'}
                            </span>
                          `}
                    </div>
                    <span class="row-value">
                      ${this.formatCurrency(item.estimated_cost)}
                    </span>
                  </div>
                  <div
                    style="display: flex; justify-content: space-between; align-items: center; font-size: var(--sl-font-size-x-small); color: var(--sl-color-neutral-500);"
                  >
                    <span>${item.provider_name || 'provider unknown'}</span>
                    <span
                      >${this.formatNumber(item.request_count)} requests</span
                    >
                  </div>

                  ${agentGroups.size > 0 || orphanSessions.length > 0
                    ? html`
                        <div
                          style="display: flex; flex-direction: column; gap: 8px; padding-left: var(--sl-spacing-medium); margin-top: 4px; border-left: 2px solid var(--sl-color-neutral-200);"
                        >
                          ${Array.from(agentGroups.entries()).map(
                            ([agentId, sessions]) => {
                              const agentName =
                                sessions[0]?.runtime_principal_name || 'Agent';
                              const totalAgentCost = sessions.reduce(
                                (acc, s) => acc + s.estimated_cost,
                                0
                              );
                              const totalAgentReqs = sessions.reduce(
                                (acc, s) => acc + s.request_count,
                                0
                              );
                              return html`
                                <div
                                  style="display: flex; flex-direction: column; gap: 4px;"
                                >
                                  <div
                                    style="display: flex; justify-content: space-between; align-items: center; font-size: var(--sl-font-size-small);"
                                  >
                                    <div
                                      style="display: flex; align-items: center; gap: var(--sl-spacing-3x-small);"
                                    >
                                      <sl-badge
                                        variant="primary"
                                        style="font-size: 0.5rem; line-height: 1; padding: 2px 4px;"
                                        >agent</sl-badge
                                      >
                                      <a
                                        class="row-link"
                                        href=${`/console/agents/${agentId}`}
                                        style="color: var(--sl-color-neutral-800); font-weight: 500;"
                                      >
                                        ${agentName}
                                      </a>
                                    </div>
                                    <span
                                      style="color: var(--sl-color-neutral-600);"
                                      >${this.formatCurrency(totalAgentCost)}
                                      (${this.formatNumber(totalAgentReqs)}
                                      req)</span
                                    >
                                  </div>

                                  <div
                                    style="display: flex; flex-direction: column; gap: 2px; padding-left: var(--sl-spacing-medium);"
                                  >
                                    ${sessions.map(
                                      (s) => html`
                                        <div
                                          style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem;"
                                        >
                                          <a
                                            class="row-link"
                                            href=${`/console/runtime-sessions?sessionId=${s.runtime_session_id}`}
                                            style="color: var(--sl-color-neutral-600);"
                                          >
                                            ${agentName} /
                                            ${s.session_reference ||
                                            s.runtime_session_id?.substring(
                                              0,
                                              8
                                            )}
                                          </a>
                                          <span
                                            style="color: var(--sl-color-neutral-500);"
                                            >${this.formatNumber(
                                              s.request_count
                                            )}
                                            req</span
                                          >
                                        </div>
                                      `
                                    )}
                                  </div>
                                </div>
                              `;
                            }
                          )}
                          ${orphanSessions.length > 0
                            ? html`
                                <div
                                  style="display: flex; flex-direction: column; gap: 2px;"
                                >
                                  ${orphanSessions.map(
                                    (s) => html`
                                      <div
                                        style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem;"
                                      >
                                        <div
                                          style="display: flex; align-items: center; gap: var(--sl-spacing-3x-small);"
                                        >
                                          <sl-badge
                                            variant="neutral"
                                            style="font-size: 0.5rem; line-height: 1; padding: 2px 4px;"
                                            >session</sl-badge
                                          >
                                          <a
                                            class="row-link"
                                            href=${`/console/runtime-sessions?sessionId=${s.runtime_session_id}`}
                                            style="color: var(--sl-color-neutral-600);"
                                          >
                                            ${s.runtime_principal_name ||
                                            s.session_reference ||
                                            s.runtime_session_id?.substring(
                                              0,
                                              8
                                            )}
                                          </a>
                                        </div>
                                        <span
                                          style="color: var(--sl-color-neutral-500);"
                                          >${this.formatNumber(s.request_count)}
                                          req</span
                                        >
                                      </div>
                                    `
                                  )}
                                </div>
                              `
                            : ''}
                        </div>
                      `
                    : ''}
                </div>
              `;
            }
          )}
        </div>
      </sl-card>
    `;
  }

  private renderSessionsAttentionCard() {
    const items = this.gatewaySummary?.usage_by_session || [];
    if (items.length === 0) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div slot="header" class="card-header-with-action">
          Top sessions by usage
          <div
            style="display: flex; gap: var(--sl-spacing-small); align-items: center;"
          >
            <a href="/console/runtime-sessions" class="header-action-link"
              >Model fleet</a
            >
          </div>
        </div>
        <div class="list">
          ${repeat(
            items.slice(0, 6),
            (item) =>
              item.runtime_session_id ||
              `${item.session_source_type}-${item.session_source_id}-${item.model_alias}`,
            (item) => html`
              <div class="row">
                <div class="row-main">
                  <a
                    class="row-link row-primary"
                    href=${item.runtime_session_id
                      ? `/console/runtime-sessions?sessionId=${item.runtime_session_id}`
                      : '/console/runtime-sessions'}
                  >
                    ${item.session_reference ||
                    item.session_source_id ||
                    item.runtime_session_id ||
                    'Session'}
                  </a>
                  <span class="row-value">
                    ${this.formatCurrency(item.estimated_cost)}
                  </span>
                </div>
                <div class="row-meta">
                  <span>
                    ${item.model_alias || item.provider_name || 'model unknown'}
                  </span>
                  <span>${this.formatDateTime(item.last_request_at)}</span>
                </div>
              </div>
            `
          )}
        </div>
      </sl-card>
    `;
  }

  private renderActiveExecutionsCard() {
    if (
      !this.fetchingActiveAgents &&
      this.managedAgents.length === 0 &&
      this.runtimeSessions.length === 0
    ) {
      return nothing;
    }

    const agentsWithSessions: Array<{
      agent: (typeof this.activeAgents)[0];
      sessions: typeof this.activeSessions;
    }> = [];
    const usedSessionIds = new Set<string>();

    for (const agent of this.activeAgents) {
      const sessions = this.activeSessions.filter(
        (s) =>
          s.runtime_principal_id === agent.session_source_id &&
          s.runtime_principal_type === agent.session_source_type
      );
      agentsWithSessions.push({ agent, sessions });
      sessions.forEach((s) => usedSessionIds.add(s.id));
    }

    // Sort agents by last activity
    agentsWithSessions.sort((a, b) => {
      const aTime = a.agent.last_seen_at
        ? new Date(a.agent.last_seen_at).getTime()
        : 0;
      const bTime = b.agent.last_seen_at
        ? new Date(b.agent.last_seen_at).getTime()
        : 0;
      return bTime - aTime;
    });

    const orphanSessions = this.activeSessions.filter(
      (s) => !usedSessionIds.has(s.id)
    );
    orphanSessions.sort((a, b) => {
      const aTime =
        a.last_activity_at || a.started_at
          ? new Date(a.last_activity_at || a.started_at).getTime()
          : 0;
      const bTime =
        b.last_activity_at || b.started_at
          ? new Date(b.last_activity_at || b.started_at).getTime()
          : 0;
      return bTime - aTime;
    });

    const hasAnyExecutions =
      agentsWithSessions.length > 0 || orphanSessions.length > 0;

    return html`
      <sl-card class="content-card">
        <div slot="header" class="card-header-with-action">
          <div class="card-title">Active agents</div>
          <select
            style="background: transparent; border: none; font-size: var(--sl-font-size-small); color: var(--sl-color-neutral-600); cursor: pointer; outline: none; margin-left: auto; margin-right: var(--sl-spacing-small);"
            .value=${this.activeAgentsTimeRange}
            @change=${(e: Event) => {
              this.activeAgentsTimeRange = (e.target as HTMLSelectElement)
                .value as any;
              this.fetchActiveAgentsData();
            }}
          >
            <option value="5m">5m</option>
            <option value="1h">1h</option>
            <option value="1d">1d</option>
            <option value="1w">1w</option>
            <option value="1mo">1mo</option>
          </select>
          <div
            style="display: flex; gap: var(--sl-spacing-small); align-items: center;"
          >
            <a href="/console/runtime-sessions" class="header-action-link"
              >View all</a
            >
          </div>
        </div>
        ${this.fetchingActiveAgents
          ? html`<div
              class="loading-container"
              style="padding: var(--sl-spacing-small);"
            >
              <sl-spinner></sl-spinner>
            </div>`
          : html`
              <div class="list">
                ${!hasAnyExecutions
                  ? this.renderEmptyState('No active agents right now.')
                  : ''}
                ${repeat(
                  agentsWithSessions.slice(0, 8),
                  (item) => item.agent.id,
                  (item) => html`
                    <div
                      class="row"
                      style="flex-direction: column; align-items: stretch; gap: var(--sl-spacing-2x-small);"
                    >
                      <div
                        style="display: flex; justify-content: space-between; align-items: center;"
                      >
                        <div
                          style="display: flex; align-items: center; gap: var(--sl-spacing-2x-small); overflow: hidden;"
                        >
                          <sl-badge variant="primary" style="font-size: 0.6rem;"
                            >agent</sl-badge
                          >
                          <a
                            class="row-link row-primary"
                            href=${`/console/agents/${item.agent.id}`}
                            style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
                          >
                            ${item.agent.display_name || 'Agent'}
                          </a>
                        </div>
                        <span class="row-value">
                          ${this.formatCurrency(item.agent.estimated_cost)}
                        </span>
                      </div>
                      <div
                        style="display: flex; justify-content: flex-end; align-items: center; font-size: var(--sl-font-size-x-small); color: var(--sl-color-neutral-500);"
                      >
                        <span
                          >${this.formatRelativeTime(
                            item.agent.last_seen_at
                          )}</span
                        >
                      </div>

                      ${item.sessions.length > 0
                        ? html`
                            <div
                              style="display: flex; flex-direction: column; gap: 4px; padding-left: var(--sl-spacing-medium); margin-top: 4px; border-left: 2px solid var(--sl-color-neutral-200);"
                            >
                              ${item.sessions.map(
                                (session) => html`
                                  <div
                                    style="display: flex; justify-content: space-between; align-items: center; font-size: var(--sl-font-size-small);"
                                  >
                                    <a
                                      class="row-link"
                                      href=${`/console/runtime-sessions?sessionId=${session.id}`}
                                      style="color: var(--sl-color-neutral-700);"
                                    >
                                      ${session.session_reference ||
                                      session.id.substring(0, 8)}
                                    </a>
                                    <span
                                      style="color: var(--sl-color-neutral-500);"
                                      >${this.formatNumber(
                                        session.total_requests
                                      )}
                                      req</span
                                    >
                                  </div>
                                `
                              )}
                            </div>
                          `
                        : ''}
                    </div>
                  `
                )}
                ${repeat(
                  orphanSessions.slice(0, 8),
                  (session) => session.id,
                  (session) => html`
                    <div class="row">
                      <div class="row-main">
                        <div
                          style="display: flex; align-items: center; gap: var(--sl-spacing-2x-small); overflow: hidden;"
                        >
                          <sl-badge variant="neutral" style="font-size: 0.6rem;"
                            >session</sl-badge
                          >
                          <a
                            class="row-link row-primary"
                            href=${`/console/runtime-sessions?sessionId=${session.id}`}
                            style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
                          >
                            ${session.runtime_principal_name ||
                            session.session_reference ||
                            session.id.substring(0, 8)}
                          </a>
                        </div>
                        <span class="row-value">
                          ${this.formatNumber(session.total_requests)} req
                        </span>
                      </div>
                      <div class="row-meta">
                        <span
                          >${session.session_source_type} ·
                          ${session.session_source_id}</span
                        >
                        <span
                          >${this.formatRelativeTime(
                            session.last_activity_at || session.started_at
                          )}</span
                        >
                      </div>
                    </div>
                  `
                )}
              </div>
            `}
      </sl-card>
    `;
  }

  private renderPendingApprovalsCard() {
    if (this.pendingApprovals.length === 0) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div slot="header" class="card-header-with-action">
          Pending approvals
          <sl-badge variant="warning">${this.pendingApprovals.length}</sl-badge>
        </div>
        <div class="list">
          ${repeat(
            this.pendingApprovals,
            (approval) => approval.id,
            (approval) => html`
              <div class="row">
                <div class="row-main">
                  <span class="row-primary">${approval.tool_name}</span>
                  <sl-button
                    size="small"
                    href=${`/console/approval/${approval.id}`}
                  >
                    Review
                  </sl-button>
                </div>
                <div class="row-meta">
                  <span>${approval.status}</span>
                  <span>${this.formatRelativeTime(approval.requested_at)}</span>
                </div>
              </div>
            `
          )}
        </div>
      </sl-card>
    `;
  }

  private renderPreloopGatewayCard() {
    return html`
      <!-- Preloop Gateway Status -->
      <sl-card class="content-card">
        <div slot="header" class="card-header-with-action">
          <div class="chart-header">
            <sl-icon
              src="/assets/preloop-badge.svg"
              slot="prefix"
              class="mcp-icon"
              alt="Gateway"
            ></sl-icon>
            Preloop Gateway
            <sl-tooltip
              content="Unified proxy for AI models and MCP tools with budget and access controls"
            >
              <sl-icon name="question-circle"></sl-icon>
            </sl-tooltip>
          </div>
          <div
            style="display: flex; gap: var(--sl-spacing-small); align-items: center;"
          >
            <a href="/console/settings/api-keys" class="header-action-link"
              >Manage Keys</a
            >
          </div>
        </div>

        <div
          style="display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--sl-spacing-large); row-gap: var(--sl-spacing-2x-large); align-items: start; margin-bottom: var(--sl-spacing-2x-large);"
        >
          <!-- Row 1 (Always Visible) -->
          <div class="tool-count">
            <sl-icon name="cpu"></sl-icon>
            <div class="tool-count-value">${this.aiModelsCount}</div>
            <div class="tool-count-label">available models</div>
          </div>

          <div class="tool-count">
            <sl-icon name="tools"></sl-icon>
            <div class="tool-count-value">
              ${this.formatNumber(
                this.tools.filter((t) => t.is_enabled).length
              )}
            </div>
            <div class="tool-count-label">available tools</div>
          </div>

          <a
            class="tool-count"
            href="/console/audit?event_type=model_gateway_request"
            style="color: inherit; text-decoration: none;"
          >
            <sl-icon
              name="activity"
              style="color: var(--sl-color-primary-600);"
            ></sl-icon>
            <div class="tool-count-value">
              ${this.formatNumber(this.gatewaySummary?.total_requests || 0)}
            </div>
            <div class="tool-count-label hover-underline">model requests</div>
          </a>

          <a
            class="tool-count"
            href="/console/audit?event_type=tool_call"
            style="color: inherit; text-decoration: none;"
          >
            <sl-icon
              name="play-circle"
              style="color: var(--sl-color-primary-600);"
            ></sl-icon>
            <div class="tool-count-value">
              ${this.formatNumber(this.toolCallsCount)}
            </div>
            <div class="tool-count-label hover-underline">tool calls</div>
          </a>

          <!-- Rows 2 and 3 (Expandable) -->
          ${this.gatewayMetricsExpanded
            ? html`
                <!-- Row 2 -->
                <a
                  class="tool-count"
                  href="/console/agents"
                  style="color: inherit; text-decoration: none;"
                >
                  <sl-icon
                    name="robot"
                    style="color: var(--sl-color-neutral-400);"
                  ></sl-icon>
                  <div class="tool-count-value">${this.totalAgentsCount}</div>
                  <div class="tool-count-label hover-underline">
                    active agents
                  </div>
                </a>

                <div class="tool-count">
                  <sl-icon
                    name="wrench"
                    style="color: var(--sl-color-neutral-400);"
                  ></sl-icon>
                  <div class="tool-count-value">${this.usedToolsCount}</div>
                  <div class="tool-count-label">used tools</div>
                </div>

                <a
                  class="tool-count"
                  href="/console/audit?event_type=model_gateway_request&outcome=failed"
                  style="color: inherit; text-decoration: none;"
                >
                  <sl-icon
                    name="exclamation-triangle"
                    style="color: ${this.gatewaySummary?.failed_requests
                      ? 'var(--sl-color-danger-600)'
                      : 'var(--sl-color-neutral-400)'};"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${this.formatNumber(
                      this.gatewaySummary?.failed_requests || 0
                    )}
                  </div>
                  <div class="tool-count-label hover-underline">
                    failed requests
                  </div>
                </a>

                <a
                  class="tool-count"
                  href="/console/audit?event_type=tool_call&outcome=failed"
                  style="color: inherit; text-decoration: none;"
                >
                  <sl-icon
                    name="exclamation-octagon"
                    style="color: ${this.failedToolCallsCount > 0
                      ? 'var(--sl-color-danger-600)'
                      : 'var(--sl-color-neutral-400)'};"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${this.formatNumber(this.failedToolCallsCount)}
                  </div>
                  <div class="tool-count-label hover-underline">
                    failed tool calls
                  </div>
                </a>

                <!-- Row 3 -->
                <a
                  class="tool-count"
                  href="/console/flows"
                  style="color: inherit; text-decoration: none;"
                >
                  <sl-icon
                    name="diagram-3"
                    style="color: var(--sl-color-neutral-400);"
                  ></sl-icon>
                  <div class="tool-count-value">${this.totalFlowsCount}</div>
                  <div class="tool-count-label hover-underline">
                    total flows
                  </div>
                </a>

                <div class="tool-count">
                  <sl-icon
                    name="boxes"
                    style="color: var(--sl-color-neutral-400);"
                  ></sl-icon>
                  <div class="tool-count-value">${this.tools.length}</div>
                  <div class="tool-count-label">total tools</div>
                </div>

                <div class="tool-count">
                  <sl-icon
                    name="check-circle"
                    style="color: var(--sl-color-success-600);"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${(this.gatewaySummary?.total_requests || 0) > 0
                      ? (
                          (((this.gatewaySummary?.total_requests || 0) -
                            (this.gatewaySummary?.failed_requests || 0)) /
                            (this.gatewaySummary?.total_requests || 1)) *
                          100
                        ).toFixed(1) + '%'
                      : '0%'}
                  </div>
                  <div class="tool-count-label">success rate</div>
                </div>

                <div class="tool-count">
                  <sl-icon
                    name="check-circle"
                    style="color: var(--sl-color-success-600);"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${this.toolCallsCount > 0
                      ? (
                          ((this.toolCallsCount - this.failedToolCallsCount) /
                            this.toolCallsCount) *
                          100
                        ).toFixed(1) + '%'
                      : '0%'}
                  </div>
                  <div class="tool-count-label">success rate</div>
                </div>

                <!-- Row 4 (Approvals) -->
                <a
                  class="tool-count"
                  href="/console/approvals"
                  style="color: inherit; text-decoration: none;"
                >
                  <sl-icon
                    name="shield-check"
                    style="color: var(--sl-color-neutral-400);"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${this.formatNumber(this.approvalStats.total)}
                  </div>
                  <div class="tool-count-label hover-underline">
                    total approvals
                  </div>
                </a>

                <a
                  class="tool-count"
                  href="/console/approvals?status=approved"
                  style="color: inherit; text-decoration: none;"
                >
                  <sl-icon
                    name="check-circle"
                    style="color: var(--sl-color-success-600);"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${this.formatNumber(this.approvalStats.approved)}
                  </div>
                  <div class="tool-count-label hover-underline">approved</div>
                </a>

                <a
                  class="tool-count"
                  href="/console/approvals?status=declined"
                  style="color: inherit; text-decoration: none;"
                >
                  <sl-icon
                    name="x-circle"
                    style="color: var(--sl-color-danger-600);"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${this.formatNumber(this.approvalStats.declined)}
                  </div>
                  <div class="tool-count-label hover-underline">declined</div>
                </a>

                <a
                  class="tool-count"
                  href="/console/approvals?status=expired"
                  style="color: inherit; text-decoration: none;"
                >
                  <sl-icon
                    name="clock"
                    style="color: var(--sl-color-warning-600);"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${this.formatNumber(this.approvalStats.expired)}
                  </div>
                  <div class="tool-count-label hover-underline">timed out</div>
                </a>
              `
            : nothing}
        </div>

        <div
          style="text-align: center; margin-top: -var(--sl-spacing-large); margin-bottom: var(--sl-spacing-medium);"
        >
          <sl-button
            size="small"
            variant="text"
            @click=${this.toggleGatewayMetrics}
          >
            ${this.gatewayMetricsExpanded
              ? 'Show less metrics'
              : 'Show more metrics'}
            <sl-icon
              slot="suffix"
              name="${this.gatewayMetricsExpanded
                ? 'chevron-up'
                : 'chevron-down'}"
            ></sl-icon>
          </sl-button>
        </div>

        <style>
          .hover-underline:hover {
            text-decoration: underline;
          }
        </style>

        <!-- AI Model Gateway Endpoint -->
        <div
          class="mcp-server-capsule"
          style="margin-top: 0; margin-bottom: var(--sl-spacing-small);"
        >
          <div class="status-indicator"></div>
          <sl-badge variant="primary" size="small" style="margin-right: -4px;"
            >AI models</sl-badge
          >
          <div
            class="server-details"
            style="display: flex; gap: var(--sl-spacing-small); align-items: center;"
          >
            <select
              style="background: transparent; border: none; font-size: inherit; font-family: inherit; color: var(--sl-color-primary-600); cursor: pointer; outline: none; margin-right: var(--sl-spacing-2x-small);"
              @change=${(e: Event) => {
                const target = e.target as HTMLSelectElement;
                const endpointSpan = target.parentElement?.querySelector(
                  '.server-endpoint'
                ) as HTMLElement;
                if (endpointSpan) {
                  endpointSpan.innerText = `${window.location.origin}${target.value}`;
                }
              }}
            >
              <option value="/openai/v1">OpenAI</option>
              <option value="/anthropic/v1">Anthropic</option>
              <option value="/google/v1">Gemini</option>
            </select>
            <span class="server-endpoint"
              >${window.location.origin}/openai/v1</span
            >
            <a
              href="https://docs.preloop.ai/guide/ai-proxy"
              target="_blank"
              style="display: flex; color: var(--sl-color-neutral-500); margin-left: auto;"
            >
              <sl-icon name="info-circle"></sl-icon>
            </a>
          </div>
          <sl-tooltip content="Copy URL">
            <sl-icon-button
              name="clipboard"
              style="font-size: 1rem;"
              @click=${(e: Event) => {
                const capsule = (e.target as HTMLElement).closest(
                  '.mcp-server-capsule'
                );
                const url =
                  capsule?.querySelector('.server-endpoint')?.textContent ||
                  `${window.location.origin}/openai/v1`;
                navigator.clipboard.writeText(url);
                this.dispatchEvent(
                  new CustomEvent('show-toast', {
                    bubbles: true,
                    composed: true,
                    detail: { message: 'AI Gateway URL copied!' },
                  })
                );
              }}
            ></sl-icon-button>
          </sl-tooltip>
        </div>

        <!-- Built-in MCP Server Endpoint -->
        <div class="mcp-server-capsule" style="margin-top: 0;">
          <div class="status-indicator"></div>
          <sl-badge variant="neutral" size="small" style="margin-right: -4px;"
            >MCP tools</sl-badge
          >
          <div class="server-details">
            <span class="server-endpoint">${window.location.origin}/mcp</span>
            <a
              href="https://docs.preloop.ai/guide/mcp-server"
              target="_blank"
              style="display: flex; color: var(--sl-color-neutral-500); margin-left: auto;"
            >
              <sl-icon name="info-circle"></sl-icon>
            </a>
          </div>
          <sl-tooltip content="Copy URL">
            <sl-icon-button
              name="clipboard"
              style="font-size: 1rem;"
              @click=${() => {
                navigator.clipboard.writeText(`${window.location.origin}/mcp`);
                this.dispatchEvent(
                  new CustomEvent('show-toast', {
                    bubbles: true,
                    composed: true,
                    detail: { message: 'MCP URL copied!' },
                  })
                );
              }}
            ></sl-icon-button>
          </sl-tooltip>
        </div>
      </sl-card>
    `;
  }

  render() {
    if (this.loading) {
      return html`
        <view-header headerText="Overview" width="extra-wide"></view-header>
        <div class="column-layout extra-wide">
          <div class="main-column">
            <div class="loading-container">
              <sl-spinner style="font-size: 2.5rem;"></sl-spinner>
            </div>
          </div>
        </div>
      `;
    }

    return html`
      <view-header headerText="Overview" width="extra-wide"></view-header>
      <p></p>
      <div class="extra-wide" style="margin-bottom: var(--sl-spacing-large);">
        ${this.error
          ? html`<sl-alert variant="danger" open>${this.error}</sl-alert>`
          : nothing}
        <div class="updated-at">
          Last updated ${this.formatRelativeTime(this.lastUpdatedAt)}
        </div>
        ${this.renderWelcomeCard()}
      </div>
      <div class="column-layout dashboard extra-wide">
        <div class="main-column">
          <div class="dashboard-stack">
            ${this.renderPreloopGatewayCard()}
            ${this.renderActiveExecutionsCard()}
            ${this.renderRecentFlowExecutionsCard()}

            <div
              style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--sl-spacing-large); margin-top: var(--sl-spacing-large);"
            >
              ${this.renderGatewayFailuresCard()}
              ${this.renderAuditExceptionsCard()}
            </div>
          </div>
        </div>

        <div class="side-column">
          ${this.renderPendingApprovalsCard()} ${this.renderBudgetHealthCard()}
          ${this.renderTopModelsCard()}
        </div>
        <mcp-setup-dialog
          ?open=${this.showSetupDialog}
          @close=${() => (this.showSetupDialog = false)}
        ></mcp-setup-dialog>
        <sl-dialog
          label="Configure Budget Limits"
          ?open=${this.showBudgetDialog}
          @sl-after-hide=${(e: Event) => {
            if (e.target === e.currentTarget) {
              this.showBudgetDialog = false;
              this.fetchBudgetSummary();
            }
          }}
          style="--width: 600px;"
        >
          <budget-policy-editor></budget-policy-editor>
        </sl-dialog>
      </div>
    `;
  }
}
