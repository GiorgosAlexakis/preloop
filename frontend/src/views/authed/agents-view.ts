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
import { getAccountAgents, type ManagedAgentListParams } from '../../api';
import type {
  AccountManagedAgentListResponse,
  ManagedAgentSummary,
} from '../../types';
import consoleStyles from '../../styles/console-styles.css?inline';

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

  private renderAgentCard(agent: ManagedAgentSummary) {
    const detailUrl = this.getAgentDetailUrl(agent);
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
            <sl-badge variant=${agent.ended_at ? 'neutral' : 'success'}>
              ${agent.ended_at ? 'Ended' : 'Active'}
            </sl-badge>
          </div>

          ${agent.session_reference
            ? html`<div class="agent-meta">${agent.session_reference}</div>`
            : null}

          <div class="metric-row">
            <span class="label">Managed MCP Servers</span>
            <span class="value">${agent.managed_mcp_servers.length}</span>
          </div>
          <div class="badges">
            ${agent.managed_mcp_servers.length
              ? agent.managed_mcp_servers.map(
                  (serverName) =>
                    html`<sl-badge variant="primary">${serverName}</sl-badge>`
                )
              : html`<span class="label"
                  >No managed MCP servers recorded</span
                >`}
          </div>

          <div class="metric-row">
            <span class="label">Latest Model</span>
            <span class="value">${agent.latest_model_alias || 'None yet'}</span>
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
              >${this.formatDateTime(agent.last_seen_at)}</span
            >
          </div>

          <div class="action-row">
            <span class="label">
              Inspect the enrolled agent, linked session, and recent activity
            </span>
            <a href=${detailUrl}>
              <sl-button size="small" variant="default">View Agent</sl-button>
            </a>
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
          subtitle="Browse enrolled external agents and jump into their linked runtime sessions."
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
