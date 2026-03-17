import { LitElement, css, html, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';

import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '../../components/view-header.ts';
import {
  getAccountAgents,
  removeAccountAgent,
  type ManagedAgentListParams,
} from '../../api';
import type {
  AccountManagedAgentListResponse,
  ManagedAgentSummary,
} from '../../types';
import consoleStyles from '../../styles/console-styles.css?inline';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';

@customElement('agents-view')
export class AgentsView extends LitElement {
  @state()
  private agents: AccountManagedAgentListResponse | null = null;

  @state()
  private loading = true;

  @state()
  private error: string | null = null;

  @state()
  private searchQuery = '';

  @state()
  private sessionSourceType = 'all';

  @state()
  private status = 'all';

  @state()
  private actionAgentId: string | null = null;

  @state()
  private liveActivity: Record<
    string,
    { modelCalls: number; toolCalls: number; lastActivityAt: string | null }
  > = {};

  private unsubscribeRealtime?: () => void;
  private refreshTimer: number | null = null;

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

      .filters {
        display: flex;
        gap: var(--sl-spacing-medium);
        flex-wrap: wrap;
        align-items: end;
      }

      .filters sl-input,
      .filters sl-select {
        min-width: 180px;
      }

      .filters sl-input {
        flex: 1 1 280px;
      }

      .cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: var(--sl-spacing-medium);
      }

      .agent-card::part(base) {
        height: 100%;
      }

      .card-stack {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-medium);
      }

      .title-row,
      .metric-row,
      .action-row {
        display: flex;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
        align-items: center;
      }

      .title-row {
        align-items: start;
      }

      .agent-name {
        font-weight: 700;
        color: var(--sl-color-neutral-900);
      }

      .agent-meta {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        margin-top: var(--sl-spacing-2x-small);
        overflow-wrap: anywhere;
      }

      .label {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .value {
        color: var(--sl-color-neutral-900);
        font-weight: 600;
        text-align: right;
      }

      .badges {
        display: flex;
        flex-wrap: wrap;
        gap: var(--sl-spacing-2x-small);
      }

      .empty-state {
        border: 1px dashed var(--sl-color-neutral-300);
        border-radius: var(--sl-border-radius-medium);
        padding: var(--sl-spacing-large);
        color: var(--sl-color-neutral-600);
        background: var(--sl-color-neutral-0);
      }
    `,
  ];

  connectedCallback(): void {
    super.connectedCallback();
    void this.loadAgents();
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
      unifiedWebSocketManager.subscribe('managed_agents', scheduleRefresh),
      unifiedWebSocketManager.subscribe('runtime_sessions', scheduleRefresh),
      unifiedWebSocketManager.subscribe('gateway_activity', (message) =>
        this.handleGatewayActivity(message)
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
      void this.loadAgents();
    }, 250);
  }

  private async loadAgents(): Promise<void> {
    this.loading = true;
    this.error = null;

    const params: ManagedAgentListParams = {
      status: this.status as 'all' | 'active' | 'ended',
      limit: 50,
    };
    if (this.searchQuery.trim()) {
      params.query = this.searchQuery.trim();
    }
    if (this.sessionSourceType !== 'all') {
      params.sessionSourceType = this.sessionSourceType;
    }

    try {
      this.agents = await getAccountAgents(params);
    } catch (error) {
      console.error('Failed to load managed agents:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to load managed agents';
    } finally {
      this.loading = false;
    }
  }

  private handleSearchInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.searchQuery = target.value;
  }

  private handleSourceTypeChange(event: CustomEvent): void {
    this.sessionSourceType = event.detail.value || 'all';
    void this.loadAgents();
  }

  private handleStatusChange(event: CustomEvent): void {
    this.status = event.detail.value || 'all';
    void this.loadAgents();
  }

  private handleSearchSubmit(event: Event): void {
    event.preventDefault();
    void this.loadAgents();
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

  private getAgentDetailUrl(agent: ManagedAgentSummary): string {
    return `/console/agents/${encodeURIComponent(agent.id)}`;
  }

  private getLifecycleVariant(agent: ManagedAgentSummary): string {
    if (agent.lifecycle_state === 'decommissioned') return 'danger';
    if (agent.lifecycle_state === 'suspended') return 'warning';
    if (agent.activity_status === 'active_now') return 'success';
    if (agent.activity_status === 'recently_active') return 'primary';
    if (agent.ended_at) return 'neutral';
    return 'primary';
  }

  private getLifecycleLabel(agent: ManagedAgentSummary): string {
    if (agent.lifecycle_state === 'decommissioned') return 'Decommissioned';
    if (agent.lifecycle_state === 'suspended') return 'Suspended';
    if (agent.activity_status === 'active_now') return 'Active now';
    if (agent.activity_status === 'recently_active') return 'Recently active';
    if (agent.ended_at) return 'Ended';
    return 'Idle';
  }

  private getOnboardingVariant(agent: ManagedAgentSummary): string {
    if (agent.onboarding_state === 'fully_onboarded') return 'success';
    if (agent.onboarding_state === 'mcp_proxy_only') return 'warning';
    if (agent.onboarding_state === 'gateway_only') return 'warning';
    return 'neutral';
  }

  private getOnboardingLabel(agent: ManagedAgentSummary): string {
    if (agent.onboarding_state === 'fully_onboarded') {
      return 'Fully onboarded';
    }
    if (agent.onboarding_state === 'mcp_proxy_only') {
      return 'Proxy only';
    }
    if (agent.onboarding_state === 'gateway_only') {
      return 'Gateway only';
    }
    return 'Incomplete';
  }

  private getLiveValidationVariant(agent: ManagedAgentSummary): string {
    if (!agent.live_validation_supported) return 'neutral';
    if (agent.live_validation_status === 'passed') return 'success';
    if (agent.live_validation_status === 'failed') return 'danger';
    return 'warning';
  }

  private getLiveValidationLabel(agent: ManagedAgentSummary): string {
    if (!agent.live_validation_supported) return 'No live check';
    if (agent.live_validation_status === 'passed') return 'Live validated';
    if (agent.live_validation_status === 'failed') return 'Live check failed';
    return 'Live check pending';
  }

  private handleGatewayActivity(message: any): void {
    const payload = message?.payload ?? {};
    const agentId = payload.managed_agent_id;
    if (!agentId || !this.agents) {
      return;
    }
    const type = message?.type;
    const previous = this.liveActivity[agentId] ?? {
      modelCalls: 0,
      toolCalls: 0,
      lastActivityAt: null,
    };
    const next = {
      modelCalls: previous.modelCalls + (type === 'model_gateway_call' ? 1 : 0),
      toolCalls: previous.toolCalls + (type === 'mcp_call' ? 1 : 0),
      lastActivityAt:
        payload.timestamp ??
        payload.last_activity_at ??
        previous.lastActivityAt ??
        new Date().toISOString(),
    };
    this.liveActivity = {
      ...this.liveActivity,
      [agentId]: next,
    };
    this.agents = {
      ...this.agents,
      items: this.agents.items.map((agent) =>
        agent.id !== agentId
          ? agent
          : {
              ...agent,
              activity_status: 'active_now',
              last_seen_at: next.lastActivityAt ?? agent.last_seen_at,
              last_activity_at: next.lastActivityAt ?? agent.last_activity_at,
              last_request_at:
                type === 'model_gateway_call'
                  ? (next.lastActivityAt ?? agent.last_request_at)
                  : agent.last_request_at,
            }
      ),
    };
  }

  private async removeAgent(agent: ManagedAgentSummary): Promise<void> {
    if (
      !window.confirm(
        `Remove ${agent.display_name} from the managed agents list? This only removes the Preloop registry record.`
      )
    ) {
      return;
    }

    this.actionAgentId = agent.id;
    try {
      await removeAccountAgent(agent.id);
      await this.loadAgents();
    } catch (error) {
      console.error('Failed to remove managed agent:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to remove managed agent';
    } finally {
      this.actionAgentId = null;
    }
  }

  private renderAgentCard(agent: ManagedAgentSummary) {
    const detailUrl = this.getAgentDetailUrl(agent);
    const liveActivity = this.liveActivity[agent.id];
    const liveTotal =
      (liveActivity?.modelCalls || 0) + (liveActivity?.toolCalls || 0);
    return html`
      <sl-card class="agent-card">
        <div class="card-stack">
          <div class="title-row">
            <div>
              <div class="agent-name">${agent.display_name}</div>
              <div class="agent-meta">
                ${this.getSourceLabel(agent.session_source_type)} ·
                ${agent.session_source_id}
              </div>
            </div>
            <div class="badges">
              <sl-badge variant=${this.getOnboardingVariant(agent)}>
                ${this.getOnboardingLabel(agent)}
              </sl-badge>
              <sl-badge variant=${this.getLifecycleVariant(agent)}>
                ${this.getLifecycleLabel(agent)}
              </sl-badge>
              <sl-badge variant=${this.getLiveValidationVariant(agent)}>
                ${this.getLiveValidationLabel(agent)}
              </sl-badge>
              ${liveTotal
                ? html`<sl-badge variant="primary">Live ${liveTotal}</sl-badge>`
                : null}
            </div>
          </div>

          ${agent.session_reference
            ? html`<div class="agent-meta">${agent.session_reference}</div>`
            : null}
          ${agent.owner_username || agent.owner_email
            ? html`
                <div class="agent-meta">
                  Owner: ${agent.owner_username || agent.owner_email}
                </div>
              `
            : null}
          ${agent.lifecycle_reason
            ? html`
                <div class="agent-meta">
                  Lifecycle note: ${agent.lifecycle_reason}
                </div>
              `
            : null}

          <div class="metric-row">
            <span class="label">Preloop MCP Proxy</span>
            <span class="value"
              >${agent.mcp_proxy_configured ? 'Configured' : 'Missing'}</span
            >
          </div>
          <div class="metric-row">
            <span class="label">Preloop Model Gateway</span>
            <span class="value"
              >${agent.model_gateway_configured
                ? 'Configured'
                : 'Missing'}</span
            >
          </div>
          <div class="metric-row">
            <span class="label">Latest Model</span>
            <span class="value">${agent.latest_model_alias || 'Unknown'}</span>
          </div>
          <div class="badges">
            ${agent.managed_mcp_servers.length
              ? agent.managed_mcp_servers.map(
                  (serverName) =>
                    html`<sl-badge variant="primary">${serverName}</sl-badge>`
                )
              : html`<span class="label"
                  >No upstream MCP servers imported</span
                >`}
          </div>
          <div class="metric-row">
            <span class="label">Requests</span>
            <span class="value">${agent.total_requests}</span>
          </div>
          <div class="metric-row">
            <span class="label">Estimated Cost</span>
            <span class="value">${this.formatMoney(agent.estimated_cost)}</span>
          </div>
          <div class="metric-row">
            <span class="label">Last Seen</span>
            <span class="value"
              >${this.formatDateTime(
                liveActivity?.lastActivityAt || agent.last_seen_at
              )}</span
            >
          </div>
          ${liveTotal
            ? html`
                <div class="metric-row">
                  <span class="label">Live Activity</span>
                  <span class="value">
                    ${liveActivity?.modelCalls || 0} messages ·
                    ${liveActivity?.toolCalls || 0} tools
                  </span>
                </div>
              `
            : null}

          <div class="action-row">
            <span class="label"
              >Inspect, rename, or remove this agent record</span
            >
            <div class="badges">
              <sl-button
                size="small"
                variant="danger"
                ?loading=${this.actionAgentId === agent.id}
                @click=${() => this.removeAgent(agent)}
              >
                Remove
              </sl-button>
              <a href=${detailUrl}>
                <sl-button size="small" variant="default">View Agent</sl-button>
              </a>
            </div>
          </div>
        </div>
      </sl-card>
    `;
  }

  render() {
    return html`
      <div class="page">
        <view-header
          title="Agents"
          subtitle="Browse managed agent records and verify whether each one is fully routed through the Preloop gateway and MCP proxy."
        ></view-header>

        <form class="filters" @submit=${this.handleSearchSubmit}>
          <sl-input
            label="Search"
            placeholder="Search agent name or source id"
            .value=${this.searchQuery}
            @sl-input=${this.handleSearchInput}
          ></sl-input>
          <sl-select
            label="Source Type"
            .value=${this.sessionSourceType}
            @sl-change=${this.handleSourceTypeChange}
          >
            <sl-option value="all">All sources</sl-option>
            <sl-option value="claude_code">Claude Code</sl-option>
            <sl-option value="claude_desktop">Claude Desktop</sl-option>
            <sl-option value="codex">Codex</sl-option>
            <sl-option value="openclaw">OpenClaw</sl-option>
            <sl-option value="desktop_agent">Desktop Agent</sl-option>
            <sl-option value="custom">Custom</sl-option>
          </sl-select>
          <sl-select
            label="Status"
            .value=${this.status}
            @sl-change=${this.handleStatusChange}
          >
            <sl-option value="all">All</sl-option>
            <sl-option value="active">Active</sl-option>
            <sl-option value="ended">Ended</sl-option>
          </sl-select>
          <sl-button type="submit" variant="primary">Apply</sl-button>
        </form>

        ${this.error
          ? html`<sl-alert open variant="danger">${this.error}</sl-alert>`
          : null}
        ${this.loading
          ? html`
              <div class="empty-state">
                <sl-spinner></sl-spinner>
                Loading enrolled agents...
              </div>
            `
          : this.agents && this.agents.items.length > 0
            ? html`
                <div class="cards">
                  ${this.agents.items.map((agent) =>
                    this.renderAgentCard(agent)
                  )}
                </div>
              `
            : html`
                <div class="empty-state">
                  No enrolled agents matched the current filters.
                </div>
              `}
      </div>
    `;
  }
}
