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
  getDashboardTelemetry,
  removeAccountAgent,
  type ManagedAgentListParams,
} from '../../api';
import type {
  DashboardTelemetryResponse,
  AccountManagedAgentListResponse,
  ManagedAgentSummary,
} from '../../types';
import consoleStyles from '../../styles/console-styles.css?inline';
import tailwindStyles from '../../styles/tailwind.css?inline';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';

@customElement('agents-view')
export class AgentsView extends LitElement {
  @state()
  private agents: AccountManagedAgentListResponse | null = null;

  @state()
  private telemetry: DashboardTelemetryResponse | null = null;

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
    unsafeCSS(tailwindStyles),
    css`
      :host {
        display: block;
      }
      .page {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }
      .cards {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
        gap: 1.5rem;
      }
      .filters sl-input,
      .filters sl-select {
        min-width: 180px;
      }
      .filters sl-input {
        flex: 1 1 280px;
      }
      .box-glow {
        box-shadow: 0 0 12px rgba(6, 232, 249, 0.2);
      }
      .chart-header {
        position: absolute;
        top: 24px;
        left: 24px;
        z-index: 10;
        pointer-events: none;
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
      const [agentsRes, telemetryRes] = await Promise.all([
        getAccountAgents(params),
        getDashboardTelemetry(),
      ]);
      this.agents = agentsRes;
      this.telemetry = telemetryRes;
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

    const isGlowing =
      liveActivity?.lastActivityAt &&
      Date.now() - new Date(liveActivity.lastActivityAt).getTime() < 2000;

    const cardClasses = `glass-panel flex flex-col p-5 gap-4 rounded-lg relative overflow-hidden transition-all duration-300 ${
      isGlowing
        ? 'shadow-glow-primary border-primary/50'
        : 'border-white/10 hover:border-white/20 hover:-translate-y-1 hover:shadow-2xl'
    }`;

    return html`
      <div
        class=${cardClasses}
        data-activity=${liveActivity?.lastActivityAt || ''}
      >
        <!-- Status Indicator Strip -->
        <div
          class="absolute left-0 top-0 bottom-0 w-1 ${agent.lifecycle_state ===
          'suspended'
            ? 'bg-warning'
            : agent.lifecycle_state === 'decommissioned'
              ? 'bg-danger'
              : liveTotal > 0
                ? 'bg-success shadow-glow-primary'
                : 'bg-primary/50'}"
        ></div>

        <!-- Header -->
        <div class="flex justify-between items-start pl-2">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <h3
                class="font-display font-bold text-lg text-white m-0 tracking-tight leading-none"
              >
                ${agent.display_name}
              </h3>
              ${liveTotal > 0
                ? html`
                    <div
                      class="relative flex items-center justify-center size-2.5 ml-1"
                    >
                      <div
                        class="absolute inset-0 rounded-full bg-success opacity-40 animate-ping"
                      ></div>
                      <div
                        class="relative size-1.5 rounded-full bg-success"
                      ></div>
                    </div>
                  `
                : null}
            </div>
            <div class="font-mono text-xs text-text-muted mt-1.5">
              ${this.getSourceLabel(agent.session_source_type)} ·
              ${agent.session_source_id}
            </div>
            ${agent.session_reference
              ? html`<div
                  class="font-mono text-[10px] text-text-muted opacity-80 mt-1"
                >
                  ${agent.session_reference}
                </div>`
              : null}
          </div>
          <div class="flex flex-col items-end gap-1.5">
            <sl-badge variant=${this.getLifecycleVariant(agent)}
              >${this.getLifecycleLabel(agent)}</sl-badge
            >
            <sl-badge variant=${this.getOnboardingVariant(agent)}
              >${this.getOnboardingLabel(agent)}</sl-badge
            >
          </div>
        </div>

        <!-- Metrics Grid -->
        <div class="grid grid-cols-2 gap-3 mt-2 pl-2">
          <div
            class="bg-black/40 rounded border border-white/5 p-3 flex flex-col gap-1"
          >
            <span
              class="text-text-muted text-[10px] font-medium uppercase tracking-wider"
              >Gateway Configuration</span
            >
            <span
              class="font-mono text-xs ${agent.model_gateway_configured
                ? 'text-success'
                : 'text-warning'}"
              >${agent.model_gateway_configured ? 'Verified' : 'Missing'}</span
            >
          </div>
          <div
            class="bg-black/40 rounded border border-white/5 p-3 flex flex-col gap-1"
          >
            <span
              class="text-text-muted text-[10px] font-medium uppercase tracking-wider"
              >MCP Proxy</span
            >
            <span
              class="font-mono text-xs ${agent.mcp_proxy_configured
                ? 'text-success'
                : 'text-warning'}"
              >${agent.mcp_proxy_configured ? 'Verified' : 'Missing'}</span
            >
          </div>
        </div>

        <!-- Stats List -->
        <div class="flex flex-col gap-2 mt-2 pl-2">
          <div
            class="flex justify-between items-end border-b border-white/5 pb-2"
          >
            <span class="text-text-muted text-xs font-medium tracking-wide"
              >Usage Cost</span
            >
            <span class="font-mono text-white text-sm"
              >${this.formatMoney(agent.estimated_cost)}</span
            >
          </div>
          <div
            class="flex justify-between items-end border-b border-white/5 pb-2"
          >
            <span class="text-text-muted text-xs font-medium tracking-wide"
              >Total Requests</span
            >
            <span class="font-mono text-white text-sm"
              >${agent.total_requests}</span
            >
          </div>
          <div
            class="flex justify-between items-end border-b border-white/5 pb-2"
          >
            <span class="text-text-muted text-xs font-medium tracking-wide"
              >Last Seen</span
            >
            <span class="font-mono text-white text-sm opacity-80"
              >${this.formatDateTime(
                liveActivity?.lastActivityAt || agent.last_seen_at
              )}</span
            >
          </div>
          ${agent.managed_mcp_servers.length > 0
            ? html`
                <div class="flex justify-between items-start pt-1">
                  <span
                    class="text-text-muted text-xs font-medium tracking-wide pt-1"
                    >MCP Tools</span
                  >
                  <div class="flex flex-wrap gap-1 justify-end max-w-[60%]">
                    ${agent.managed_mcp_servers
                      .slice(0, 3)
                      .map(
                        (s) =>
                          html`<span
                            class="px-1.5 py-0.5 rounded bg-primary/10 border border-primary/20 text-primary text-[10px] font-mono whitespace-nowrap"
                            >${s}</span
                          >`
                      )}
                    ${agent.managed_mcp_servers.length > 3
                      ? html`<span
                          class="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-text-muted text-[10px] font-mono whitespace-nowrap"
                          >+${agent.managed_mcp_servers.length - 3}</span
                        >`
                      : null}
                  </div>
                </div>
              `
            : null}
        </div>

        <!-- Actions -->
        <div class="mt-auto pt-4 flex gap-3 pl-2">
          <button
            @click=${() => this.removeAgent(agent)}
            class="flex-none px-3 py-1.5 rounded border border-danger/30 text-danger bg-danger/5 hover:bg-danger/20 transition-colors font-display text-xs tracking-wide"
          >
            Remove
          </button>
          <a href=${detailUrl} class="flex-1">
            <button
              class="w-full flex items-center justify-center gap-2 h-full py-1.5 rounded border border-primary/30 text-primary bg-primary/10 hover:bg-primary/20 transition-colors font-display text-xs font-bold tracking-wide"
            >
              View Agent Details
            </button>
          </a>
        </div>
      </div>
    `;
  }

  render() {
    const chartData = (this.telemetry as any)?.latency_series || [
      30, 40, 45, 50, 49, 60, 70, 91, 125, 110, 95, 105,
    ];
    const maxVal = Math.max(...chartData, 10);

    return html`
      <div class="page text-text-main font-body">
        <div
          class="glass-panel p-6 rounded-lg mb-2 relative overflow-hidden box-glow border-primary/20"
        >
          <div class="chart-header">
            <h3
              class="font-display font-medium text-text-muted text-sm uppercase tracking-widest m-0"
            >
              Global Gateway Traffic (Mocked View)
            </h3>
            <div class="mt-1 flex items-baseline gap-2">
              <span class="text-3xl font-bold font-mono text-white"
                >${chartData.reduce((a: number, b: number) => a + b, 0)}</span
              >
              <span class="text-success text-xs font-mono font-bold"
                >+12.4%</span
              >
            </div>
          </div>

          <div
            class="h-[140px] relative flex items-end gap-[4px] px-6 pb-2 pt-20"
          >
            ${chartData.map((val: number, i: number) => {
              const heightPct = Math.max((val / maxVal) * 100, 2);
              const isRecent = i >= chartData.length - 3;
              return html`
                <div
                  class="flex-1 bg-primary/20 hover:bg-primary/40 transition-all rounded-t-sm relative group"
                  style="height: ${heightPct}%; animation: pulse ${1 +
                  Math.random()}s infinite alternate;"
                >
                  <div
                    class="absolute inset-0 bg-gradient-to-t from-transparent ${isRecent
                      ? 'to-primary/60'
                      : 'to-primary/30'}"
                  ></div>
                  <div
                    class="absolute -top-8 left-1/2 -translate-x-1/2 bg-black/80 px-2 py-1 rounded text-xs font-mono opacity-0 group-hover:opacity-100 transition-opacity border border-white/10 z-20"
                  >
                    ${val} reqs
                  </div>
                </div>
              `;
            })}
          </div>
          <div
            class="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent"
          ></div>
        </div>

        <view-header
          title="Agents Registry"
          subtitle="Browse managed agent records and verify whether each one is fully routed through the Preloop gateway and MCP proxy."
        ></view-header>

        <form
          class="filters glass-panel p-4 rounded-lg mb-2 border-white/5"
          @submit=${this.handleSearchSubmit}
        >
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
          <button
            type="submit"
            class="px-6 py-[11px] rounded bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20 transition-colors font-display text-sm font-bold tracking-wide ml-2"
          >
            Filter
          </button>
        </form>

        ${this.error
          ? html`<sl-alert open variant="danger">${this.error}</sl-alert>`
          : null}
        ${this.loading
          ? html`
              <div
                class="glass-panel p-12 rounded-lg text-center flex flex-col items-center justify-center border-white/5"
              >
                <sl-spinner
                  style="font-size: 2rem; --indicator-color: var(--color-primary);"
                ></sl-spinner>
                <div class="mt-4 font-mono text-text-muted text-sm">
                  Loading enrolled agents...
                </div>
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
                <div
                  class="glass-panel p-12 rounded-lg text-center border-white/5 border-dashed"
                >
                  <div class="font-mono text-text-muted">
                    No enrolled agents matched the current filters.
                  </div>
                </div>
              `}
      </div>
    `;
  }
}
