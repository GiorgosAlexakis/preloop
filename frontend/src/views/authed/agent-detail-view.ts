import { LitElement, css, html, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '../../components/view-header.ts';
import {
  fetchWithAuth,
  getAccountAgent,
  getAccountRuntimeSessionDetail,
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
} from '../../types';
import consoleStyles from '../../styles/console-styles.css?inline';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';

@customElement('agent-detail-view')
export class AgentDetailView extends LitElement {
  private static readonly UPDATEABLE_LIFECYCLE_STATES = new Set([
    'active',
    'suspended',
    'decommissioned',
  ]);

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
  private selectedOwnerUserId = '';

  @state()
  private actionLoading = false;

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
      unifiedWebSocketManager.subscribe('gateway_activity', scheduleRefresh),
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
      const [detail, users] = await Promise.all([
        getAccountAgent(this.agentId),
        this.fetchUsers(),
      ]);
      this.agent = detail.agent;
      this.aggregate = detail.aggregate;
      this.usageByModel = detail.usage_by_model;
      this.activityByServer = detail.activity_by_server;
      this.activityByTool = detail.activity_by_tool;
      this.sessions = detail.sessions;
      this.availableUsers = users;
      this.selectedOwnerUserId = detail.agent.owner_user_id ?? '';
      this.selectedSessionId =
        detail.agent.runtime_session_id ?? detail.sessions[0]?.id ?? null;
      this.runtimeDetail = this.selectedSessionId
        ? await getAccountRuntimeSessionDetail(this.selectedSessionId)
        : null;
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
    if (this.agent.ended_at) return 'neutral';
    return 'primary';
  }

  private getLifecycleLabel(): string {
    if (!this.agent) return 'Unknown';
    if (this.agent.lifecycle_state === 'decommissioned')
      return 'Decommissioned';
    if (this.agent.lifecycle_state === 'suspended') return 'Suspended';
    if (this.agent.activity_status === 'active_now') return 'Active now';
    if (this.agent.ended_at) return 'Ended';
    return 'Idle';
  }

  private async applyLifecycleAction(
    action: 'suspend' | 'resume' | 'decommission' | 'reenroll'
  ): Promise<void> {
    if (!this.agentId || !this.agent) {
      return;
    }
    if (
      action === 'decommission' &&
      !window.confirm(`Decommission ${this.agent.display_name}?`)
    ) {
      return;
    }
    this.actionLoading = true;
    try {
      await updateAccountAgent(this.agentId, { lifecycle_action: action });
      await this.loadData();
    } catch (error) {
      console.error('Failed to update managed agent:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to update managed agent';
    } finally {
      this.actionLoading = false;
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
      <div class="page">
        <view-header
          title="Agent Detail"
          subtitle="Inspect the enrolled runtime identity and its linked session activity."
        ></view-header>

        <sl-card>
          <div class="stack">
            <div class="hero">
              <div>
                <div class="hero-title">${this.agent.display_name}</div>
                <div class="meta-line">
                  ${this.getSourceLabel(this.agent.session_source_type)} ·
                  ${this.agent.session_source_id}
                </div>
                ${this.agent.session_reference
                  ? html`
                      <div class="meta-line">
                        ${this.agent.session_reference}
                      </div>
                    `
                  : null}
              </div>
              <div class="badge-row">
                <sl-badge variant=${this.getLifecycleVariant()}>
                  ${this.getLifecycleLabel()}
                </sl-badge>
                <sl-badge variant="primary"
                  >${this.agent.enrolled_via}</sl-badge
                >
              </div>
            </div>

            <div class="control-row">
              ${AgentDetailView.UPDATEABLE_LIFECYCLE_STATES.has(
                this.agent.lifecycle_state
              ) && this.agent.lifecycle_state === 'active'
                ? html`
                    <sl-button
                      variant="warning"
                      ?loading=${this.actionLoading}
                      @click=${() => this.applyLifecycleAction('suspend')}
                    >
                      Suspend
                    </sl-button>
                    <sl-button
                      variant="danger"
                      ?loading=${this.actionLoading}
                      @click=${() => this.applyLifecycleAction('decommission')}
                    >
                      Decommission
                    </sl-button>
                  `
                : null}
              ${this.agent.lifecycle_state === 'suspended'
                ? html`
                    <sl-button
                      variant="success"
                      ?loading=${this.actionLoading}
                      @click=${() => this.applyLifecycleAction('resume')}
                    >
                      Resume
                    </sl-button>
                    <sl-button
                      variant="danger"
                      ?loading=${this.actionLoading}
                      @click=${() => this.applyLifecycleAction('decommission')}
                    >
                      Decommission
                    </sl-button>
                  `
                : null}
              ${this.agent.lifecycle_state === 'decommissioned'
                ? html`
                    <sl-button
                      variant="success"
                      ?loading=${this.actionLoading}
                      @click=${() => this.applyLifecycleAction('reenroll')}
                    >
                      Re-enroll
                    </sl-button>
                  `
                : null}
            </div>

            <div class="summary-grid">
              <div class="stat-card">
                <div class="stat-label">Owner</div>
                <div class="stat-value">
                  ${this.agent.owner_username ||
                  this.agent.owner_email ||
                  'Unassigned'}
                </div>
                <div class="control-row">
                  <sl-select
                    hoist
                    value=${this.selectedOwnerUserId}
                    @sl-change=${(event: CustomEvent) => {
                      this.selectedOwnerUserId = event.detail.value || '';
                    }}
                  >
                    <sl-option value="">Unassigned</sl-option>
                    ${this.availableUsers.map(
                      (user) => html`
                        <sl-option value=${user.id}>
                          ${user.username} (${user.email})
                        </sl-option>
                      `
                    )}
                  </sl-select>
                  <sl-button
                    variant="default"
                    ?loading=${this.actionLoading}
                    @click=${this.saveOwnerAssignment}
                  >
                    Save owner
                  </sl-button>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Managed MCP Servers</div>
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
                        >No managed MCP servers recorded</span
                      >`}
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Historical Sessions</div>
                <div class="stat-value">${aggregate?.session_count ?? 0}</div>
                <div class="meta-line">
                  Last seen ${this.formatDateTime(this.agent.last_seen_at)}
                </div>
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
                <div class="stat-label">Estimated Cost</div>
                <div class="stat-value">
                  ${this.formatMoney(aggregate?.estimated_cost)}
                </div>
                <div class="meta-line">
                  Latest model ${aggregate?.latest_model_alias || 'None yet'}
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-label">Historical Tokens</div>
                <div class="stat-value">
                  ${aggregate?.token_usage.total_tokens ?? 0}
                </div>
                <div class="meta-line">
                  Last request
                  ${this.formatDateTime(aggregate?.last_request_at)}
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

        <sl-card>
          <div class="stack">
            <div class="hero-title">Historical Model Usage</div>
            ${this.renderHistoricalModelBreakdown()}
          </div>
        </sl-card>

        <sl-card>
          <div class="stack">
            <div class="hero-title">Historical MCP Server Activity</div>
            ${this.renderServerActivityBreakdown()}
          </div>
        </sl-card>

        <sl-card>
          <div class="stack">
            <div class="hero-title">Historical Tool Activity</div>
            ${this.renderToolActivityBreakdown()}
          </div>
        </sl-card>

        ${this.runtimeDetail
          ? html`
              ${this.sessions.length
                ? html`
                    <sl-card>
                      <div class="stack">
                        <div class="hero-title">Session History</div>
                        <div class="timeline">
                          ${this.sessions.map(
                            (session) => html`
                              <div class="timeline-item">
                                <div class="timeline-title">
                                  <a
                                    class="session-link"
                                    href="#"
                                    @click=${(event: Event) => {
                                      event.preventDefault();
                                      void this.selectSession(session.id);
                                    }}
                                  >
                                    ${this.getSourceLabel(
                                      session.session_source_type
                                    )}
                                    · ${session.session_source_id}
                                  </a>
                                </div>
                                <div class="timeline-meta">
                                  ${this.formatDateTime(session.started_at)} ·
                                  ${session.total_requests} request(s) ·
                                  ${this.formatMoney(session.estimated_cost)}
                                </div>
                              </div>
                            `
                          )}
                        </div>
                      </div>
                    </sl-card>
                  `
                : null}

              <sl-card>
                <div class="stack">
                  <div class="hero-title">Linked Session Overview</div>
                  <div class="summary-grid">
                    <div class="stat-card">
                      <div class="stat-label">Requests</div>
                      <div class="stat-value">
                        ${this.runtimeDetail.session.total_requests}
                      </div>
                    </div>
                    <div class="stat-card">
                      <div class="stat-label">Tokens</div>
                      <div class="stat-value">
                        ${this.runtimeDetail.session.token_usage.total_tokens}
                      </div>
                    </div>
                    <div class="stat-card">
                      <div class="stat-label">Cost</div>
                      <div class="stat-value">
                        ${this.formatMoney(
                          this.runtimeDetail.session.estimated_cost
                        )}
                      </div>
                    </div>
                    <div class="stat-card">
                      <div class="stat-label">Last Activity</div>
                      <div class="stat-value">
                        ${this.formatDateTime(
                          this.runtimeDetail.session.last_activity_at
                        )}
                      </div>
                    </div>
                  </div>

                  <div>
                    <div class="hero-title">Recent Activity</div>
                    <div class="timeline">
                      ${this.runtimeDetail.activity_timeline.length
                        ? this.runtimeDetail.activity_timeline
                            .slice(0, 8)
                            .map((item) => this.renderTimelineItem(item))
                        : html`
                            <div class="empty-state">
                              No activity recorded for the linked runtime
                              session.
                            </div>
                          `}
                    </div>
                  </div>
                </div>
              </sl-card>
            `
          : html`
              <sl-card>
                <div class="empty-state">
                  This agent has not produced a linked runtime-session detail
                  yet.
                </div>
              </sl-card>
            `}
      </div>
    `;
  }
}
