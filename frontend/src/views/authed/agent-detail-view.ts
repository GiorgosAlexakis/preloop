import { LitElement, css, html, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '../../components/view-header.ts';
import { getAccountAgent, getAccountRuntimeSessionDetail } from '../../api';
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
    if (!this.initialized) {
      this.initialized = true;
      if (this.agentId) {
        void this.loadData();
      }
    }
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
      const detail: ManagedAgentDetailResponse = await getAccountAgent(
        this.agentId
      );
      this.agent = detail.agent;
      this.aggregate = detail.aggregate;
      this.usageByModel = detail.usage_by_model;
      this.activityByServer = detail.activity_by_server;
      this.activityByTool = detail.activity_by_tool;
      this.sessions = detail.sessions;
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
                <sl-badge
                  variant=${this.agent.ended_at ? 'neutral' : 'success'}
                >
                  ${this.agent.ended_at ? 'Ended' : 'Active'}
                </sl-badge>
                <sl-badge variant="primary"
                  >${this.agent.enrolled_via}</sl-badge
                >
              </div>
            </div>

            <div class="summary-grid">
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
