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
import '../../components/view-header.ts';
import {
  AuthedElement,
  fetchWithAuth,
  getAIModels,
  getAccountAgents,
  getAccountGatewayUsageSearch,
  getAccountGatewayUsageSummary,
  getAccountRuntimeSessions,
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
  @state() private enabledUsersCount = 0;
  @state() private showSetupDialog = false;
  @state() private welcomeCardDismissed = false;
  @state() private dismissedExecutions = new Set<string>();
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
    const newSet = new Set(this.dismissedExecutions);
    newSet.add(id);
    this.dismissedExecutions = newSet;
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
      .content-card::part(base),
      .welcome-card::part(base) {
        height: 100%;
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
  }

  private dismissWelcomeCard(): void {
    this.welcomeCardDismissed = true;
    localStorage.setItem('dashboard_welcome_dismissed', 'true');
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
    }, 250);
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

    const catchWith403Handling = async <T>(
      promise: Promise<T>,
      defaultValue: T
    ): Promise<T> => {
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
    };

    try {
      const [
        gatewaySummary,
        runtimeSessions,
        managedAgents,
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
      ] = await Promise.all([
        catchWith403Handling(getAccountGatewayUsageSummary(), null),
        catchWith403Handling(
          getAccountRuntimeSessions({ status: 'all', limit: 12 }),
          {
            items: [],
          } as Awaited<ReturnType<typeof getAccountRuntimeSessions>>
        ),
        catchWith403Handling(getAccountAgents({ status: 'all', limit: 12 }), {
          items: [],
        } as Awaited<ReturnType<typeof getAccountAgents>>),
        catchWith403Handling(getAccountGatewayUsageSearch({ limit: 12 }), {
          items: [],
        } as Awaited<ReturnType<typeof getAccountGatewayUsageSearch>>),
        catchWith403Handling(this.fetchAuditExceptions(), {
          groups: [],
          total: 0,
        }),
        catchWith403Handling(getTrackers(), [] as Tracker[]),
        catchWith403Handling(getApiUsageStats(), null),
        catchWith403Handling(getIssueCount(), { total_issues: 0 }),
        catchWith403Handling(getMCPServers(), [] as MCPServer[]),
        catchWith403Handling(getTools(), [] as Tool[]),
        catchWith403Handling(getFlows(), [] as any[]),
        catchWith403Handling(
          getFlowExecutions({ limit: 5 }),
          [] as FlowExecution[]
        ),
        catchWith403Handling(this.fetchApprovalRequests('pending', 3), []),
        catchWith403Handling(this.fetchApprovalRequests(undefined, 100), []),
        catchWith403Handling(getAIModels(), []),
        catchWith403Handling(
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
      ]);

      this.gatewaySummary = gatewaySummary;
      this.runtimeSessions = runtimeSessions.items || [];
      this.managedAgents = managedAgents.items || [];
      this.gatewayInteractions = gatewayInteractions.items || [];
      this.auditGroups = audit.groups || [];
      this.trackers = trackers;
      this.apiUsage = apiUsage;
      this.totalIssues = issueCount.total_issues;
      this.mcpServers = mcpServers;
      this.tools = tools;
      this.hasFlows = (flows || []).length > 0;
      this.recentFlowExecutions = [...(flowExecutions || [])]
        .sort(
          (left, right) =>
            new Date(right.start_time).getTime() -
            new Date(left.start_time).getTime()
        )
        .slice(0, 5);
      this.pendingApprovals = pendingApprovals;
      this.hasAIModels = (aiModels || []).length > 0;
      this.enabledUsersCount = (users.users || []).filter(
        (user: { is_active?: boolean }) => user.is_active
      ).length;
      this.calculateApprovalStats(allApprovalRequests);
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
    return [...this.managedAgents]
      .filter((agent) => agent.activity_status === 'active_now')
      .sort(
        (left, right) =>
          new Date(right.last_seen_at).getTime() -
          new Date(left.last_seen_at).getTime()
      );
  }

  private get activeSessions(): RuntimeSessionSummary[] {
    return [...this.runtimeSessions]
      .filter((session) => session.activity_status === 'active_now')
      .sort((left, right) => {
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
      (execution) => execution.status === 'FAILED'
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

  private budgetVariant(): 'success' | 'warning' | 'danger' | 'neutral' {
    const budget = this.gatewaySummary?.budget;
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
    const budget = this.gatewaySummary?.budget;
    const limit = budget?.monthly_limit_usd || budget?.soft_limit_usd || 0;
    if (!limit) {
      return 0;
    }
    return Math.min(
      100,
      Math.round(((budget?.current_spend_usd || 0) / limit) * 100)
    );
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
          <!-- Path 1: Build Flows -->
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

          <!-- Path 2: Govern Agents -->
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
      <!-- Flow Executions - Only show if flows exist -->
      ${this.hasFlows
        ? html`<sl-card>
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
                      .filter((exec) => !this.dismissedExecutions.has(exec.id))
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
          </sl-card>`
        : ''}
    `;
  }
  private renderBudgetHealthCard() {
    if (!this.hasBudgetCard) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Budget health</div>
          <sl-badge variant=${this.budgetVariant()}>
            ${this.gatewaySummary?.budget.hard_limit_exceeded
              ? 'Hard limit exceeded'
              : this.gatewaySummary?.budget.soft_limit_exceeded
                ? 'Soft limit exceeded'
                : 'Healthy'}
          </sl-badge>
        </div>
        <div class="budget-meter">
          <div class="budget-stat">
            <span>Current spend</span>
            <strong>
              ${this.formatCurrency(
                this.gatewaySummary?.budget.current_spend_usd
              )}
            </strong>
          </div>
          <div class="budget-stat">
            <span>Monthly limit</span>
            <strong>
              ${this.gatewaySummary?.budget.monthly_limit_usd
                ? this.formatCurrency(
                    this.gatewaySummary?.budget.monthly_limit_usd
                  )
                : 'Not set'}
            </strong>
          </div>
          <div class="budget-stat">
            <span>Soft limit</span>
            <strong>
              ${this.gatewaySummary?.budget.soft_limit_usd
                ? this.formatCurrency(
                    this.gatewaySummary?.budget.soft_limit_usd
                  )
                : 'Not set'}
            </strong>
          </div>
          <div class="budget-stat">
            <span>Pressure</span>
            <strong>${this.budgetPercent()}%</strong>
          </div>
        </div>
        <div class="footer-link">
          <a class="row-link" href="/console/settings/ai-models">
            Open model controls
          </a>
        </div>
      </sl-card>
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
    const items = this.gatewaySummary?.usage_by_model || [];
    if (items.length === 0) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Top models</div>
          <a class="row-link" href="/console/settings/ai-models">Model fleet</a>
        </div>
        <div class="list">
          ${repeat(
            items.slice(0, 6),
            (item) =>
              `${item.ai_model_id}-${item.model_alias}-${item.provider_name}`,
            (item) => html`
              <div class="row">
                <div class="row-main">
                  ${item.ai_model_id
                    ? html`
                        <a
                          class="row-link row-primary"
                          href=${`/console/settings/ai-models/${item.ai_model_id}`}
                        >
                          ${item.model_alias || 'Unknown model'}
                        </a>
                      `
                    : html`
                        <span class="row-primary">
                          ${item.model_alias || 'Unknown model'}
                        </span>
                      `}
                  <span class="row-value">
                    ${this.formatCurrency(item.estimated_cost)}
                  </span>
                </div>
                <div class="row-meta">
                  <span>${item.provider_name || 'provider unknown'}</span>
                  <span>${this.formatNumber(item.request_count)} requests</span>
                </div>
              </div>
            `
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
        <div class="card-header">
          <div class="card-title">Top sessions by usage</div>
          <a class="row-link" href="/console/runtime-sessions">Investigate</a>
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

  private renderActiveAgentsCard() {
    if (this.managedAgents.length === 0) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Active agents</div>
          <a class="row-link" href="/console/agents">View all</a>
        </div>
        <div class="list">
          ${this.activeAgents.length === 0
            ? this.renderEmptyState('No active agents right now.')
            : repeat(
                this.activeAgents.slice(0, 6),
                (agent) => agent.id,
                (agent) => html`
                  <div class="row">
                    <div class="row-main">
                      <a
                        class="row-link row-primary"
                        href=${`/console/agents/${agent.id}`}
                      >
                        ${agent.display_name}
                      </a>
                      <span class="row-value">
                        ${this.formatCurrency(agent.estimated_cost)}
                      </span>
                    </div>
                    <div class="row-meta">
                      <span>
                        ${agent.session_source_type} ·
                        ${agent.session_source_id}
                      </span>
                      <span
                        >${this.formatRelativeTime(agent.last_seen_at)}</span
                      >
                    </div>
                  </div>
                `
              )}
        </div>
      </sl-card>
    `;
  }

  private renderActiveSessionsCard() {
    if (this.runtimeSessions.length === 0) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Active runtime sessions</div>
          <a class="row-link" href="/console/runtime-sessions">View all</a>
        </div>
        <div class="list">
          ${this.activeSessions.length === 0
            ? this.renderEmptyState('No active runtime sessions right now.')
            : repeat(
                this.activeSessions.slice(0, 6),
                (session) => session.id,
                (session) => html`
                  <div class="row">
                    <div class="row-main">
                      <a
                        class="row-link row-primary"
                        href=${`/console/runtime-sessions?sessionId=${session.id}`}
                      >
                        ${session.runtime_principal_name ||
                        session.session_reference ||
                        session.id}
                      </a>
                      <span class="row-value">
                        ${this.formatNumber(session.total_requests)} req
                      </span>
                    </div>
                    <div class="row-meta">
                      <span>
                        ${session.session_source_type} ·
                        ${session.session_source_id}
                      </span>
                      <span>
                        ${this.formatRelativeTime(
                          session.last_activity_at || session.started_at
                        )}
                      </span>
                    </div>
                  </div>
                `
              )}
        </div>
      </sl-card>
    `;
  }

  private renderPendingApprovalsCard() {
    if (this.pendingApprovals.length === 0) {
      return nothing;
    }

    return html`
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Pending approvals</div>
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

  private renderMcpServerCard() {
    return html`
      <!-- MCP Server & Tools Status -->
      <sl-card>
        <div slot="header" class="card-header-with-action">
          <div class="chart-header">
            <sl-icon
              src="/images/mcp.svg"
              slot="prefix"
              class="mcp-icon"
              alt="MCP"
            ></sl-icon>
            MCP Server
            <sl-tooltip
              content="Built-in and external MCP tools for issue management and automation"
            >
              <sl-icon name="question-circle"></sl-icon>
            </sl-tooltip>
          </div>
          <div
            style="display: flex; gap: var(--sl-spacing-small); align-items: center;"
          >
            <a
              href="#"
              class="header-action-link"
              @click=${(e: Event) => {
                e.preventDefault();
                this.showSetupDialog = true;
              }}
              >Setup</a
            >
            <a href="/console/tools" class="header-action-link">Manage</a>
          </div>
        </div>

        ${this.mcpServers.length === 0 && this.tools.length === 0
          ? html`
              <div class="empty-state">
                <sl-icon name="inbox"></sl-icon>
                <p>
                  No MCP servers or tools configured yet.
                  <a href="/console/tools">Configure tools</a>
                </p>
              </div>
            `
          : html`
              <!-- Built-in Tools Summary -->
              <div class="tool-counts">
                <div class="tool-count">
                  <sl-icon name="tools"></sl-icon>
                  <div class="tool-count-value">
                    ${this.tools.filter((t) => t.source === 'builtin').length}
                  </div>
                  <div class="tool-count-label">built-in tools</div>
                </div>
                <div class="tool-count">
                  <sl-icon
                    name="check-circle"
                    style="color: var(--sl-color-success-600);"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${this.tools.filter(
                      (t) => t.is_enabled && t.is_supported !== false
                    ).length}
                  </div>
                  <div class="tool-count-label">enabled</div>
                </div>
                <div class="tool-count">
                  <sl-icon
                    name="shield-check"
                    style="color: var(--sl-color-warning-600);"
                  ></sl-icon>
                  <div class="tool-count-value">
                    ${this.tools.filter(
                      (t) =>
                        (t.approval_workflow_id != null ||
                          t.has_approval_condition === true) &&
                        t.is_supported !== false
                    ).length}
                  </div>
                  <div class="tool-count-label">require approval</div>
                </div>
              </div>

              <!-- Built-in MCP Server -->
              <div class="mcp-server-capsule">
                <div class="status-indicator"></div>
                <div class="server-details">
                  <span class="server-endpoint"
                    >${window.location.origin}/mcp</span
                  >
                </div>
                <sl-tooltip content="Copy URL">
                  <sl-icon-button
                    name="clipboard"
                    style="font-size: 1rem;"
                    @click=${() => {
                      navigator.clipboard.writeText(
                        `${window.location.origin}/mcp`
                      );
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
              <a href="/console/settings/api-keys" class="capsule-link">
                Manage Keys
              </a>
            `}
      </sl-card>
    `;
  }
  private renderApprovalAnalyticsCard() {
    return html`
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Approval analytics</div>
          <a class="row-link" href="/console/approvals">View all</a>
        </div>
        ${this.approvalStats.total === 0
          ? this.renderEmptyState('No approval requests recorded yet.')
          : html`
              <div class="analytics-grid">
                <div class="tool-count">
                  <div class="analytics-value">${this.approvalStats.total}</div>
                  <div class="analytics-label">Total requests</div>
                </div>
                <div class="tool-count">
                  <div class="analytics-value">
                    ${this.approvalStats.approved}
                  </div>
                  <div class="analytics-label">Approved</div>
                  <div class="analytics-subtext">
                    ${Math.round(
                      (this.approvalStats.approved / this.approvalStats.total) *
                        100
                    )}%
                    approval rate
                  </div>
                </div>
                <div class="tool-count">
                  <div class="analytics-value">
                    ${this.approvalStats.declined}
                  </div>
                  <div class="analytics-label">Declined</div>
                </div>
                ${this.approvalStats.expired > 0
                  ? html`
                      <div class="tool-count">
                        <div class="analytics-value">
                          ${this.approvalStats.expired}
                        </div>
                        <div class="analytics-label">Timed out</div>
                      </div>
                    `
                  : nothing}
                ${this.approvalStats.avgApprovalTime > 0
                  ? html`
                      <div class="tool-count">
                        <div class="analytics-value">
                          ${this.approvalStats.avgApprovalTime}
                        </div>
                        <div class="analytics-label">Avg response time</div>
                        <div class="analytics-subtext">minutes</div>
                      </div>
                    `
                  : nothing}
              </div>
            `}
      </sl-card>
    `;
  }

  private renderKeyMetricsCard() {
    return html`
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Key metrics</div>
        </div>
        <ul class="summary-list">
          <li class="summary-item">
            <span>Connected trackers</span>
            <strong>${this.formatNumber(this.trackers.length)}</strong>
          </li>
          <li class="summary-item">
            <span>Enabled tools</span>
            <strong>
              ${this.formatNumber(
                this.tools.filter((tool) => tool.is_enabled).length
              )}
            </strong>
          </li>
          ${isSaaS()
            ? html`
                <li class="summary-item">
                  <span>Enabled users</span>
                  <strong>${this.formatNumber(this.enabledUsersCount)}</strong>
                </li>
              `
            : nothing}
          <li class="summary-item">
            <span>Configured flows</span>
            <strong>${this.hasFlows ? 'Yes' : 'No'}</strong>
          </li>
          <li class="summary-item">
            <span>Total API requests</span>
            <strong>${this.formatNumber(this.apiUsage?.total_requests)}</strong>
          </li>
          <li class="summary-item">
            <span>Total issues processed</span>
            <strong>${this.formatNumber(this.totalIssues)}</strong>
          </li>
        </ul>
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
      <div class="column-layout dashboard extra-wide">
        <div class="main-column">
          <div class="dashboard-stack">
            ${this.error
              ? html`<sl-alert variant="danger" open>${this.error}</sl-alert>`
              : nothing}
            <div class="updated-at">
              Last updated ${this.formatRelativeTime(this.lastUpdatedAt)}
            </div>
            ${this.renderWelcomeCard()}

            <div class="summary-grid">
              <sl-card class="summary-card">
                <div class="metric-label">Active agents</div>
                <div class="metric-value">${this.activeAgents.length}</div>
                <div class="metric-subtext">
                  ${this.formatNumber(this.managedAgents.length)} enrolled total
                </div>
              </sl-card>
              <sl-card class="summary-card">
                <div class="metric-label">Active runtime sessions</div>
                <div class="metric-value">${this.activeSessions.length}</div>
                <div class="metric-subtext">
                  ${this.formatNumber(this.runtimeSessions.length)} tracked
                  sessions
                </div>
              </sl-card>
              <sl-card class="summary-card">
                <div class="metric-label">Gateway spend</div>
                <div class="metric-value">
                  ${this.formatCurrency(this.gatewaySummary?.estimated_cost)}
                </div>
                <div class="metric-subtext">
                  ${this.formatNumber(this.gatewaySummary?.total_requests)}
                  requests in range
                </div>
              </sl-card>
              <sl-card class="summary-card">
                <div class="metric-label">Gateway failures</div>
                <div class="metric-value">${this.gatewayFailures.length}</div>
                <div class="metric-subtext">
                  ${this.formatNumber(this.gatewaySummary?.failed_requests)}
                  failed requests total
                </div>
              </sl-card>
            </div>

            ${this.renderRecentFlowExecutionsCard()}
          </div>
        </div>

        <div class="side-column">
          ${this.renderPendingApprovalsCard()} ${this.renderMcpServerCard()}
          ${this.renderApprovalAnalyticsCard()} ${this.renderActiveAgentsCard()}
          ${this.renderActiveSessionsCard()} ${this.renderKeyMetricsCard()}
        </div>
        <mcp-setup-dialog
          ?open=${this.showSetupDialog}
          @close=${() => (this.showSetupDialog = false)}
        ></mcp-setup-dialog>
      </div>
      <div class="control-plane-grid">
        ${this.renderBudgetHealthCard()} ${this.renderGatewayFailuresCard()}
        ${this.renderAuditExceptionsCard()} ${this.renderTopModelsCard()}
        ${this.renderSessionsAttentionCard()}
      </div>
    `;
  }
}
