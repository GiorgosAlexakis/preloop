import { css, html, nothing, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';

import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '../../components/view-header.ts';
import {
  AuthedElement,
  fetchWithAuth,
  getAccountAgents,
  getAccountGatewayUsageSearch,
  getAccountGatewayUsageSummary,
  getAccountRuntimeSessions,
} from '../../api';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import type {
  AccountGatewayUsageSummaryResponse,
  GatewayUsageSearchResultItem,
  ManagedAgentSummary,
  RuntimeSessionSummary,
} from '../../types';
import { parseUTCDate } from '../../utils/date';
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
  @state() private lastUpdatedAt: string | null = null;

  private unsubscribeRealtime?: () => void;
  private refreshTimer: number | null = null;
  private refreshInFlight = false;

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      :host {
        display: block;
      }

      .page {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }

      .summary-grid,
      .content-grid {
        display: grid;
        gap: var(--sl-spacing-medium);
      }

      .summary-grid {
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      }

      .content-grid {
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      }

      .summary-card::part(base),
      .content-card::part(base) {
        height: 100%;
      }

      .metric-label {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .metric-value {
        color: var(--sl-color-neutral-900);
        font-size: 1.7rem;
        font-weight: 700;
        line-height: 1.1;
        margin-top: var(--sl-spacing-2x-small);
      }

      .metric-subtext {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        margin-top: var(--sl-spacing-small);
      }

      .card-header,
      .row,
      .row-main,
      .row-meta {
        display: flex;
      }

      .card-header {
        align-items: center;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
        margin-bottom: var(--sl-spacing-medium);
      }

      .card-title {
        font-weight: 700;
        color: var(--sl-color-neutral-900);
      }

      .list {
        display: flex;
        flex-direction: column;
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

      .row-main {
        align-items: center;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
      }

      .row-primary {
        color: var(--sl-color-neutral-900);
        font-weight: 600;
        overflow-wrap: anywhere;
      }

      .row-value {
        color: var(--sl-color-neutral-900);
        font-weight: 600;
        text-align: right;
      }

      .row-meta {
        align-items: center;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .row-link {
        color: var(--sl-color-primary-700);
        text-decoration: none;
      }

      .row-link:hover {
        text-decoration: underline;
      }

      .budget-meter {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-small);
      }

      .budget-stat {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
        color: var(--sl-color-neutral-700);
        font-size: var(--sl-font-size-small);
      }

      .empty-state {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .footer-link {
        margin-top: var(--sl-spacing-medium);
      }

      .updated-at {
        color: var(--sl-color-neutral-500);
        font-size: var(--sl-font-size-small);
      }

      @media (max-width: 800px) {
        .row-main,
        .row-meta,
        .card-header {
          align-items: flex-start;
          flex-direction: column;
        }

        .row-value {
          text-align: left;
        }
      }
    `,
  ];

  connectedCallback(): void {
    super.connectedCallback();
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

  private connectRealtime(): void {
    const scheduleRefresh = () => this.scheduleRefresh();
    const unsubscribers = [
      unifiedWebSocketManager.subscribe('runtime_sessions', scheduleRefresh),
      unifiedWebSocketManager.subscribe('managed_agents', scheduleRefresh),
      unifiedWebSocketManager.subscribe('gateway_activity', scheduleRefresh),
      unifiedWebSocketManager.subscribe('budget_health', scheduleRefresh),
      unifiedWebSocketManager.subscribe('audit', scheduleRefresh),
      unifiedWebSocketManager.subscribe('approvals', scheduleRefresh),
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

    try {
      const [
        gatewaySummary,
        runtimeSessions,
        managedAgents,
        gatewayInteractions,
        audit,
      ] = await Promise.all([
        getAccountGatewayUsageSummary(),
        getAccountRuntimeSessions({ status: 'all', limit: 12 }),
        getAccountAgents({ status: 'all', limit: 12 }),
        getAccountGatewayUsageSearch({ limit: 12 }),
        this.fetchAuditExceptions(),
      ]);

      this.gatewaySummary = gatewaySummary;
      this.runtimeSessions = runtimeSessions.items;
      this.managedAgents = managedAgents.items;
      this.gatewayInteractions = gatewayInteractions.items;
      this.auditGroups = audit.groups;
      this.lastUpdatedAt = new Date().toISOString();
    } catch (error) {
      console.error('Failed to load control-plane dashboard', error);
      this.error = 'Failed to load the control-plane dashboard.';
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

  render() {
    if (this.loading) {
      return html`
        <div class="page">
          <view-header headerText="AI Control Plane"></view-header>
          <sl-spinner style="font-size: 2rem;"></sl-spinner>
        </div>
      `;
    }

    return html`
      <div class="page">
        <view-header headerText="AI Control Plane"></view-header>

        ${this.error
          ? html`<sl-alert variant="danger" open>${this.error}</sl-alert>`
          : nothing}

        <div class="updated-at">
          Last updated ${this.formatRelativeTime(this.lastUpdatedAt)}
        </div>

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
              ${this.formatNumber(this.runtimeSessions.length)} tracked sessions
            </div>
          </sl-card>

          <sl-card class="summary-card">
            <div class="metric-label">Gateway spend</div>
            <div class="metric-value">
              ${this.formatCurrency(this.gatewaySummary?.estimated_cost)}
            </div>
            <div class="metric-subtext">
              ${this.formatNumber(this.gatewaySummary?.total_requests)} requests
              in range
            </div>
          </sl-card>

          <sl-card class="summary-card">
            <div class="metric-label">Gateway failures</div>
            <div class="metric-value">${this.gatewayFailures.length}</div>
            <div class="metric-subtext">
              ${this.formatNumber(this.gatewaySummary?.failed_requests)} failed
              requests total
            </div>
          </sl-card>
        </div>

        <div class="content-grid">
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
              <a class="row-link" href="/console/settings/ai-models"
                >Open model controls</a
              >
            </div>
          </sl-card>

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
                          <span class="row-value"
                            >${this.formatCurrency(agent.estimated_cost)}</span
                          >
                        </div>
                        <div class="row-meta">
                          <span
                            >${agent.session_source_type} ·
                            ${agent.session_source_id}</span
                          >
                          <span
                            >${this.formatRelativeTime(
                              agent.last_seen_at
                            )}</span
                          >
                        </div>
                      </div>
                    `
                  )}
            </div>
          </sl-card>

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
                          <span class="row-value"
                            >${this.formatNumber(session.total_requests)}
                            req</span
                          >
                        </div>
                        <div class="row-meta">
                          <span
                            >${session.session_source_type} ·
                            ${session.session_source_id}</span
                          >
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

          <sl-card class="content-card">
            <div class="card-header">
              <div class="card-title">Gateway failures needing attention</div>
              <a class="row-link" href="/console/api-usage"
                >Open gateway activity</a
              >
            </div>
            <div class="list">
              ${this.gatewayFailures.length === 0
                ? this.renderEmptyState('No recent gateway failures.')
                : repeat(
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
                            ${item.model_alias ||
                            item.provider_name ||
                            item.endpoint}
                          </a>
                          <sl-badge variant="danger"
                            >${item.status_code}</sl-badge
                          >
                        </div>
                        <div class="row-meta">
                          <span>
                            ${item.runtime_principal_name ||
                            item.session_reference ||
                            item.endpoint}
                          </span>
                          <span
                            >${this.formatRelativeTime(item.timestamp)}</span
                          >
                        </div>
                      </div>
                    `
                  )}
            </div>
          </sl-card>

          <sl-card class="content-card">
            <div class="card-header">
              <div class="card-title">Audit exceptions</div>
              <a class="row-link" href="/console/audit">Open audit timeline</a>
            </div>
            <div class="list">
              ${this.auditGroups.length === 0
                ? this.renderEmptyState('No recent audit exceptions.')
                : repeat(
                    this.auditGroups.slice(0, 6),
                    (group) => group.primary_event.id,
                    (group) => html`
                      <div class="row">
                        <div class="row-main">
                          <span class="row-primary">
                            ${group.primary_event.action.replaceAll('_', ' ')}
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
                            ${this.formatRelativeTime(
                              group.primary_event.timestamp
                            )}
                          </span>
                        </div>
                      </div>
                    `
                  )}
            </div>
          </sl-card>

          <sl-card class="content-card">
            <div class="card-header">
              <div class="card-title">Top models</div>
              <a class="row-link" href="/console/settings/ai-models"
                >Model fleet</a
              >
            </div>
            <div class="list">
              ${(this.gatewaySummary?.usage_by_model.length || 0) === 0
                ? this.renderEmptyState('No model traffic captured yet.')
                : repeat(
                    this.gatewaySummary?.usage_by_model.slice(0, 6) || [],
                    (item) => `${item.provider_name}-${item.model_alias}`,
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
                          <span class="row-value"
                            >${this.formatCurrency(item.estimated_cost)}</span
                          >
                        </div>
                        <div class="row-meta">
                          <span
                            >${item.provider_name || 'provider unknown'}</span
                          >
                          <span
                            >${this.formatNumber(item.request_count)}
                            requests</span
                          >
                        </div>
                      </div>
                    `
                  )}
            </div>
          </sl-card>

          <sl-card class="content-card">
            <div class="card-header">
              <div class="card-title">Sessions needing attention</div>
              <a class="row-link" href="/console/runtime-sessions"
                >Investigate</a
              >
            </div>
            <div class="list">
              ${(this.gatewaySummary?.usage_by_session.length || 0) === 0
                ? this.renderEmptyState('No session usage recorded yet.')
                : repeat(
                    this.gatewaySummary?.usage_by_session.slice(0, 6) || [],
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
                          <span class="row-value"
                            >${this.formatCurrency(item.estimated_cost)}</span
                          >
                        </div>
                        <div class="row-meta">
                          <span>
                            ${item.model_alias ||
                            item.provider_name ||
                            'model unknown'}
                          </span>
                          <span
                            >${this.formatDateTime(item.last_request_at)}</span
                          >
                        </div>
                      </div>
                    `
                  )}
            </div>
          </sl-card>
        </div>
      </div>
    `;
  }
}
