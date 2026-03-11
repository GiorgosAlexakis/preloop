import { LitElement, html, css, unsafeCSS } from 'lit';
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
  getAccountRuntimeSessionDetail,
  getAccountRuntimeSessions,
  updateAccountRuntimeSession,
  type RuntimeSessionDetailParams,
  type RuntimeSessionListParams,
} from '../../api';
import type {
  AccountRuntimeSessionDetailResponse,
  AccountRuntimeSessionListResponse,
  GatewayUsageByModel,
  GatewayUsageSearchResultItem,
  RuntimeSessionActivityItem,
  RuntimeSessionSummary,
} from '../../types';
import consoleStyles from '../../styles/console-styles.css?inline';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';

type DateRangePreset = 'last-7' | 'last-30' | 'last-90' | 'all' | 'custom';

@customElement('runtime-sessions-view')
export class RuntimeSessionsView extends LitElement {
  @state()
  private sessions: AccountRuntimeSessionListResponse | null = null;

  @state()
  private detail: AccountRuntimeSessionDetailResponse | null = null;

  @state()
  private loading = true;

  @state()
  private detailLoading = false;

  @state()
  private error: string | null = null;

  @state()
  private selectedSessionId: string | null = null;

  @state()
  private selectedRange: DateRangePreset = 'last-30';

  @state()
  private startDate = '';

  @state()
  private endDate = '';

  @state()
  private searchQuery = '';

  @state()
  private sessionSourceType = 'all';

  @state()
  private status = 'all';

  @state()
  private interactionQuery = '';

  @state()
  private actionLoading = false;

  private initialized = false;
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

      .filters-grid {
        display: flex;
        gap: var(--sl-spacing-medium);
        flex-wrap: wrap;
        align-items: end;
      }

      .filters-grid sl-select,
      .filters-grid sl-input {
        min-width: 180px;
      }

      .filters-actions {
        display: flex;
        gap: var(--sl-spacing-small);
        margin-left: auto;
      }

      .layout {
        display: grid;
        grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
        gap: var(--sl-spacing-large);
      }

      .session-list {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-small);
      }

      .session-item {
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-0);
        cursor: pointer;
      }

      .session-item.selected {
        border-color: var(--sl-color-primary-500);
        box-shadow: 0 0 0 1px var(--sl-color-primary-300);
      }

      .session-item-title {
        font-weight: 600;
        color: var(--sl-color-neutral-900);
        overflow-wrap: anywhere;
      }

      .session-item-meta {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        margin-top: var(--sl-spacing-2x-small);
        overflow-wrap: anywhere;
      }

      .detail-stack {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }

      .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: var(--sl-spacing-medium);
      }

      .summary-card {
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-0);
      }

      .summary-label {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .summary-value {
        font-size: 1.3rem;
        font-weight: 700;
        color: var(--sl-color-neutral-900);
        margin-top: var(--sl-spacing-2x-small);
      }

      .summary-detail {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        margin-top: var(--sl-spacing-2x-small);
      }

      .breakdown-list,
      .interaction-list {
        display: flex;
        flex-direction: column;
      }

      .breakdown-header,
      .breakdown-row {
        display: grid;
        grid-template-columns: minmax(0, 2fr) 110px 110px 110px;
        gap: var(--sl-spacing-small);
        align-items: center;
        padding: var(--sl-spacing-small) 0;
        border-bottom: 1px solid var(--sl-color-neutral-200);
      }

      .breakdown-header {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-x-small);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        font-weight: 600;
      }

      .breakdown-row:last-child,
      .interaction-row:last-child {
        border-bottom: none;
      }

      .cell-numeric {
        text-align: right;
        font-variant-numeric: tabular-nums;
      }

      .interaction-toolbar {
        display: flex;
        gap: var(--sl-spacing-medium);
        align-items: end;
        flex-wrap: wrap;
      }

      .interaction-toolbar sl-input {
        min-width: 260px;
      }

      .interaction-row {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-x-small);
        padding: var(--sl-spacing-medium) 0;
        border-bottom: 1px solid var(--sl-color-neutral-200);
      }

      .interaction-header {
        display: flex;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
        align-items: flex-start;
      }

      .interaction-title {
        font-weight: 600;
        color: var(--sl-color-neutral-900);
      }

      .interaction-meta,
      .interaction-excerpt,
      .detail-meta {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        overflow-wrap: anywhere;
      }

      .interaction-excerpt {
        color: var(--sl-color-neutral-800);
      }

      .empty-state,
      .loading-state {
        text-align: center;
        padding: var(--sl-spacing-x-large);
        color: var(--sl-color-neutral-600);
      }

      .empty-state sl-icon,
      .loading-state sl-spinner {
        font-size: 2rem;
        margin-bottom: var(--sl-spacing-small);
      }

      @media (max-width: 1100px) {
        .layout {
          grid-template-columns: 1fr;
        }
      }

      @media (max-width: 720px) {
        .filters-actions {
          margin-left: 0;
          width: 100%;
        }

        .breakdown-header {
          display: none;
        }

        .breakdown-row {
          grid-template-columns: 1fr;
        }

        .cell-numeric {
          text-align: left;
        }
      }
    `,
  ];

  connectedCallback() {
    super.connectedCallback();

    if (!this.initialized) {
      const params = new URLSearchParams(window.location.search);
      this.selectedSessionId = params.get('sessionId');
      if (this.selectedRange !== 'custom') {
        this.applyPresetDates(this.selectedRange);
      }
      this.initialized = true;
      void this.loadSessions();
      this.connectRealtime();
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
      unifiedWebSocketManager.subscribe('runtime_sessions', scheduleRefresh),
      unifiedWebSocketManager.subscribe('managed_agents', scheduleRefresh),
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
    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
    }
    this.refreshTimer = window.setTimeout(() => {
      this.refreshTimer = null;
      void this.loadSessions();
    }, 250);
  }

  private getLocalDateString(date: Date): string {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  private applyPresetDates(range: Exclude<DateRangePreset, 'custom'>) {
    if (range === 'all') {
      this.startDate = '';
      this.endDate = '';
      return;
    }

    const today = new Date();
    const startDate = new Date(today);
    const days = range === 'last-7' ? 7 : range === 'last-30' ? 30 : 90;
    startDate.setDate(startDate.getDate() - (days - 1));
    this.startDate = this.getLocalDateString(startDate);
    this.endDate = this.getLocalDateString(today);
  }

  private buildListParams(): RuntimeSessionListParams {
    const params: RuntimeSessionListParams = {
      limit: 50,
      status: this.status as 'all' | 'active' | 'ended',
    };

    if (this.startDate) {
      params.startDate = new Date(`${this.startDate}T00:00:00`).toISOString();
    }
    if (this.endDate) {
      params.endDate = new Date(`${this.endDate}T23:59:59.999`).toISOString();
    }
    if (this.searchQuery.trim()) {
      params.query = this.searchQuery.trim();
    }
    if (this.sessionSourceType !== 'all') {
      params.sessionSourceType = this.sessionSourceType;
    }

    return params;
  }

  private buildDetailParams(): RuntimeSessionDetailParams {
    const params: RuntimeSessionDetailParams = {
      interactionLimit: 50,
    };

    if (this.startDate) {
      params.startDate = new Date(`${this.startDate}T00:00:00`).toISOString();
    }
    if (this.endDate) {
      params.endDate = new Date(`${this.endDate}T23:59:59.999`).toISOString();
    }
    if (this.interactionQuery.trim()) {
      params.interactionQuery = this.interactionQuery.trim();
    }

    return params;
  }

  private async loadSessions() {
    this.loading = true;
    this.error = null;

    try {
      this.sessions = await getAccountRuntimeSessions(this.buildListParams());
      if (
        !this.selectedSessionId ||
        !this.sessions.items.some((item) => item.id === this.selectedSessionId)
      ) {
        this.selectedSessionId = this.sessions.items[0]?.id ?? null;
        this.syncUrl();
      }
      await this.loadDetail();
    } catch (error) {
      console.error('Failed to load runtime sessions:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to load runtime sessions';
      this.sessions = null;
      this.detail = null;
    } finally {
      this.loading = false;
    }
  }

  private async loadDetail() {
    if (!this.selectedSessionId) {
      this.detail = null;
      return;
    }

    this.detailLoading = true;
    try {
      this.detail = await getAccountRuntimeSessionDetail(
        this.selectedSessionId,
        this.buildDetailParams()
      );
    } catch (error) {
      console.error('Failed to load runtime session detail:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to load runtime session detail';
      this.detail = null;
    } finally {
      this.detailLoading = false;
    }
  }

  private syncUrl() {
    const url = new URL(window.location.href);
    if (this.selectedSessionId) {
      url.searchParams.set('sessionId', this.selectedSessionId);
    } else {
      url.searchParams.delete('sessionId');
    }
    window.history.replaceState({}, '', `${url.pathname}${url.search}`);
  }

  private handleRangeChange(event: Event) {
    const value = (event.target as HTMLInputElement & { value: string })
      .value as DateRangePreset;
    this.selectedRange = value;
    if (value !== 'custom') {
      this.applyPresetDates(value);
      void this.loadSessions();
    }
  }

  private handleStartDateChange(event: Event) {
    this.startDate = (
      event.target as HTMLInputElement & { value: string }
    ).value;
    this.selectedRange = 'custom';
  }

  private handleEndDateChange(event: Event) {
    this.endDate = (event.target as HTMLInputElement & { value: string }).value;
    this.selectedRange = 'custom';
  }

  private handleSearchQueryChange(event: Event) {
    this.searchQuery = (
      event.target as HTMLInputElement & { value: string }
    ).value;
  }

  private handleSessionSourceTypeChange(event: Event) {
    this.sessionSourceType = (
      event.target as HTMLInputElement & { value: string }
    ).value;
  }

  private handleStatusChange(event: Event) {
    this.status = (event.target as HTMLInputElement & { value: string }).value;
  }

  private handleInteractionQueryChange(event: Event) {
    this.interactionQuery = (
      event.target as HTMLInputElement & { value: string }
    ).value;
  }

  private async applyFilters() {
    await this.loadSessions();
  }

  private async clearFilters() {
    this.selectedRange = 'last-30';
    this.applyPresetDates('last-30');
    this.searchQuery = '';
    this.sessionSourceType = 'all';
    this.status = 'all';
    this.interactionQuery = '';
    await this.loadSessions();
  }

  private async applyInteractionSearch() {
    await this.loadDetail();
  }

  private selectSession(sessionId: string) {
    this.selectedSessionId = sessionId;
    this.syncUrl();
    void this.loadDetail();
  }

  private formatNumber(value: number | null | undefined): string {
    return typeof value === 'number' ? value.toLocaleString() : '0';
  }

  private formatCost(value: number | null | undefined): string {
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return '$0.00';
    }
    return value >= 0.01 ? `$${value.toFixed(2)}` : `$${value.toFixed(4)}`;
  }

  private formatDateTime(value: string | null | undefined): string {
    if (!value) {
      return 'Unknown';
    }
    return new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date(value));
  }

  private getActivityBadgeVariant(status: string | null | undefined) {
    if (!status) {
      return 'neutral';
    }
    if (status === 'failed' || status === 'error') {
      return 'danger';
    }
    if (status === 'info' || status === 'completed') {
      return 'neutral';
    }
    return 'success';
  }

  private formatAuthAttribution(
    item:
      | GatewayUsageSearchResultItem
      | RuntimeSessionActivityItem
      | null
      | undefined
  ): string | null {
    if (!item) {
      return null;
    }
    if (item.api_key_name) {
      return `API token ${item.api_key_name}`;
    }
    if (item.api_key_id) {
      return `API token ${item.api_key_id}`;
    }
    if (item.auth_subject_type === 'api_key') {
      return 'API token';
    }
    return null;
  }

  private getSessionDisplayName(session: RuntimeSessionSummary): string {
    return (
      session.runtime_principal_name ??
      session.flow_name ??
      session.session_reference ??
      `${this.getSourceLabel(session.session_source_type)} ${session.session_source_id}`
    );
  }

  private getSessionVariant(
    session: RuntimeSessionSummary
  ): 'success' | 'primary' | 'neutral' {
    if (session.activity_status === 'active_now') {
      return 'success';
    }
    if (session.activity_status === 'ended') {
      return 'neutral';
    }
    return 'primary';
  }

  private getSessionLabel(session: RuntimeSessionSummary): string {
    if (session.activity_status === 'active_now') {
      return 'Active now';
    }
    if (session.activity_status === 'ended') {
      return 'Ended';
    }
    return 'Idle';
  }

  private getSourceLabel(sourceType: string | null | undefined): string {
    if (!sourceType) {
      return 'Runtime session';
    }
    if (sourceType === 'flow_execution') {
      return 'Flow execution';
    }
    return sourceType
      .split(/[_-]+/g)
      .filter(Boolean)
      .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
      .join(' ');
  }

  private async endSelectedSession(): Promise<void> {
    if (!this.detail?.session || this.detail.session.ended_at) {
      return;
    }
    const session = this.detail.session;
    const confirmed = window.confirm(
      `End runtime session "${this.getSessionDisplayName(session)}"?`
    );
    if (!confirmed) {
      return;
    }
    this.actionLoading = true;
    try {
      await updateAccountRuntimeSession(session.id, { action: 'end' });
      await this.loadSessions();
    } catch (error) {
      console.error('Failed to end runtime session:', error);
      this.error =
        error instanceof Error
          ? error.message
          : 'Failed to update runtime session';
    } finally {
      this.actionLoading = false;
    }
  }

  private renderSessionList() {
    if (!this.sessions || this.sessions.items.length === 0) {
      return html`
        <div class="empty-state">
          <sl-icon name="collection"></sl-icon>
          <div>No runtime sessions matched the current filters.</div>
        </div>
      `;
    }

    return html`
      <div class="session-list">
        ${this.sessions.items.map(
          (session) => html`
            <button
              class="session-item ${session.id === this.selectedSessionId
                ? 'selected'
                : ''}"
              @click=${() => this.selectSession(session.id)}
            >
              <div
                style="display: flex; justify-content: space-between; gap: var(--sl-spacing-small); align-items: start;"
              >
                <div class="session-item-title">
                  ${this.getSessionDisplayName(session)}
                </div>
                <sl-badge variant=${this.getSessionVariant(session)}>
                  ${this.getSessionLabel(session)}
                </sl-badge>
              </div>
              <div class="session-item-meta">
                ${this.getSourceLabel(session.session_source_type)} ·
                ${session.latest_model_alias || 'No model recorded'}
              </div>
              <div class="session-item-meta">
                ${this.formatNumber(session.total_requests)} requests ·
                ${this.formatNumber(session.token_usage.total_tokens)} tokens ·
                ${this.formatCost(session.estimated_cost)}
              </div>
              <div class="session-item-meta">
                Last activity
                ${this.formatDateTime(
                  session.last_request_at ||
                    session.last_activity_at ||
                    session.started_at
                )}
              </div>
            </button>
          `
        )}
      </div>
    `;
  }

  private renderModelBreakdown(models: GatewayUsageByModel[]) {
    if (models.length === 0) {
      return html`
        <div class="empty-state">
          <sl-icon name="cpu"></sl-icon>
          <div>No model usage was recorded for this session.</div>
        </div>
      `;
    }

    return html`
      <div class="breakdown-list">
        <div class="breakdown-header">
          <div>Model</div>
          <div class="cell-numeric">Requests</div>
          <div class="cell-numeric">Tokens</div>
          <div class="cell-numeric">Cost</div>
        </div>
        ${models.map(
          (model) => html`
            <div class="breakdown-row">
              <div>
                <div class="session-item-title">
                  ${model.model_alias || 'Unnamed model'}
                </div>
                <div class="session-item-meta">
                  ${model.provider_name || 'Unknown provider'}
                </div>
              </div>
              <div class="cell-numeric">
                ${this.formatNumber(model.request_count)}
              </div>
              <div class="cell-numeric">
                ${this.formatNumber(model.token_usage.total_tokens)}
              </div>
              <div class="cell-numeric">
                ${this.formatCost(model.estimated_cost)}
              </div>
            </div>
          `
        )}
      </div>
    `;
  }

  private renderInteractions(items: GatewayUsageSearchResultItem[]) {
    if (items.length === 0) {
      return html`
        <div class="empty-state">
          <sl-icon name="search"></sl-icon>
          <div>No captured interactions matched this session filter.</div>
        </div>
      `;
    }

    return html`
      <div class="interaction-list">
        ${items.map(
          (item) => html`
            <div class="interaction-row">
              <div class="interaction-header">
                <div>
                  <div class="interaction-title">
                    ${item.model_alias || 'Unknown model'}
                    ${item.provider_name ? html`· ${item.provider_name}` : ''}
                  </div>
                  <div class="interaction-meta">
                    ${item.method} ${item.endpoint} ·
                    ${this.formatDateTime(item.timestamp)}
                  </div>
                </div>
                <sl-badge
                  variant=${item.outcome === 'error' ? 'danger' : 'success'}
                >
                  ${item.outcome}
                </sl-badge>
              </div>
              <div class="interaction-excerpt">${item.excerpt}</div>
              <div class="interaction-meta">
                ${this.formatNumber(item.token_usage.total_tokens)} tokens ·
                ${this.formatCost(item.estimated_cost)}
                ${this.formatAuthAttribution(item)
                  ? html` · ${this.formatAuthAttribution(item)}`
                  : ''}
              </div>
            </div>
          `
        )}
      </div>
    `;
  }

  private renderActivityTimeline(items: RuntimeSessionActivityItem[]) {
    if (items.length === 0) {
      return html`
        <div class="empty-state">
          <sl-icon name="clock-history"></sl-icon>
          <div>No activity has been captured for this session yet.</div>
        </div>
      `;
    }

    return html`
      <div class="interaction-list">
        ${items.map(
          (item) => html`
            <div class="interaction-row">
              <div class="interaction-header">
                <div>
                  <div class="interaction-title">${item.title}</div>
                  <div class="interaction-meta">
                    ${item.activity_type === 'tool_call'
                      ? html`
                          Tool call
                          ${item.server_name ? html`· ${item.server_name}` : ''}
                        `
                      : item.activity_type === 'session_started'
                        ? html`Session lifecycle`
                        : item.activity_type === 'session_ended'
                          ? html`Session lifecycle`
                          : html`Model interaction`}
                    · ${this.formatDateTime(item.timestamp)}
                  </div>
                </div>
                ${item.status
                  ? html`
                      <sl-badge
                        variant=${this.getActivityBadgeVariant(item.status)}
                      >
                        ${item.status}
                      </sl-badge>
                    `
                  : ''}
              </div>
              ${item.summary
                ? html`<div class="interaction-excerpt">${item.summary}</div>`
                : ''}
              <div class="interaction-meta">
                ${item.total_tokens !== null && item.total_tokens !== undefined
                  ? html`${this.formatNumber(item.total_tokens)} tokens`
                  : ''}
                ${item.total_tokens !== null &&
                item.total_tokens !== undefined &&
                item.estimated_cost !== null &&
                item.estimated_cost !== undefined
                  ? html` · `
                  : ''}
                ${item.estimated_cost !== null &&
                item.estimated_cost !== undefined
                  ? html`${this.formatCost(item.estimated_cost)}`
                  : ''}
                ${this.formatAuthAttribution(item)
                  ? html`
                      ${(item.total_tokens !== null &&
                        item.total_tokens !== undefined) ||
                      (item.estimated_cost !== null &&
                        item.estimated_cost !== undefined)
                        ? html` · `
                        : ''}
                      ${this.formatAuthAttribution(item)}
                    `
                  : ''}
              </div>
            </div>
          `
        )}
      </div>
    `;
  }

  private renderDetail() {
    if (this.detailLoading) {
      return html`
        <sl-card>
          <div class="loading-state">
            <sl-spinner></sl-spinner>
            <div>Loading runtime session details...</div>
          </div>
        </sl-card>
      `;
    }

    if (!this.detail) {
      return html`
        <sl-card>
          <div class="empty-state">
            <sl-icon name="inbox"></sl-icon>
            <div>Select a runtime session to inspect its activity.</div>
          </div>
        </sl-card>
      `;
    }

    const session = this.detail.session;

    return html`
      <div class="detail-stack">
        <sl-card>
          <div slot="header" class="session-item-title">
            <div
              style="display: flex; justify-content: space-between; gap: var(--sl-spacing-small); align-items: center; flex-wrap: wrap;"
            >
              <span>${this.getSessionDisplayName(session)}</span>
              <sl-badge variant=${this.getSessionVariant(session)}>
                ${this.getSessionLabel(session)}
              </sl-badge>
            </div>
          </div>
          <div class="detail-meta">
            ${this.getSourceLabel(session.session_source_type)} · Source ID
            <code>${session.session_source_id}</code>
          </div>
          ${session.session_reference
            ? html`
                <div class="detail-meta">
                  Session reference <code>${session.session_reference}</code>
                </div>
              `
            : ''}
          ${session.flow_execution_id
            ? html`
                <div class="detail-meta">
                  Flow execution
                  <a
                    href=${`/console/flows/executions/${session.flow_execution_id}`}
                    >${session.flow_execution_id}</a
                  >
                </div>
              `
            : ''}
          <div
            style="display: flex; justify-content: flex-end; margin-top: var(--sl-spacing-medium);"
          >
            <sl-button
              variant="warning"
              ?disabled=${Boolean(session.ended_at)}
              ?loading=${this.actionLoading}
              @click=${() => this.endSelectedSession()}
            >
              ${session.ended_at ? 'Session ended' : 'End session'}
            </sl-button>
          </div>
          <div
            class="summary-grid"
            style="margin-top: var(--sl-spacing-medium);"
          >
            <div class="summary-card">
              <div class="summary-label">Requests</div>
              <div class="summary-value">
                ${this.formatNumber(session.total_requests)}
              </div>
              <div class="summary-detail">
                ${this.formatNumber(session.successful_requests)} succeeded,
                ${this.formatNumber(session.failed_requests)} failed
              </div>
            </div>
            <div class="summary-card">
              <div class="summary-label">Tokens</div>
              <div class="summary-value">
                ${this.formatNumber(session.token_usage.total_tokens)}
              </div>
              <div class="summary-detail">
                ${this.formatNumber(session.token_usage.prompt_tokens)} prompt,
                ${this.formatNumber(session.token_usage.completion_tokens)}
                completion
              </div>
            </div>
            <div class="summary-card">
              <div class="summary-label">Estimated Cost</div>
              <div class="summary-value">
                ${this.formatCost(session.estimated_cost)}
              </div>
              <div class="summary-detail">
                Last request ${this.formatDateTime(session.last_request_at)}
              </div>
            </div>
          </div>
        </sl-card>

        <sl-card>
          <div slot="header" class="session-item-title">Usage By Model</div>
          ${this.renderModelBreakdown(this.detail.usage_by_model)}
        </sl-card>

        <sl-card>
          <div slot="header" class="session-item-title">Activity Timeline</div>
          ${this.renderActivityTimeline(this.detail.activity_timeline)}
        </sl-card>

        <sl-card>
          <div slot="header" class="session-item-title">
            Captured Interactions
          </div>
          <div class="interaction-toolbar">
            <sl-input
              label="Search within this session"
              placeholder="Search captured prompts, outputs, or metadata"
              .value=${this.interactionQuery}
              @sl-input=${this.handleInteractionQueryChange}
            ></sl-input>
            <sl-button variant="primary" @click=${this.applyInteractionSearch}>
              Search
            </sl-button>
          </div>
          ${this.renderInteractions(this.detail.interactions.items)}
        </sl-card>
      </div>
    `;
  }

  render() {
    return html`
      <view-header
        headerText="Runtime Sessions"
        width="extra-wide"
      ></view-header>
      <div class="column-layout dashboard extra-wide">
        <div class="main-column">
          <div class="page">
            <sl-card>
              <div slot="header" class="session-item-title">
                Session Explorer Filters
              </div>
              <div class="filters-grid">
                <sl-select
                  label="Date range"
                  value=${this.selectedRange}
                  @sl-change=${this.handleRangeChange}
                >
                  <sl-option value="last-7">Last 7 days</sl-option>
                  <sl-option value="last-30">Last 30 days</sl-option>
                  <sl-option value="last-90">Last 90 days</sl-option>
                  <sl-option value="all">All time</sl-option>
                  <sl-option value="custom">Custom</sl-option>
                </sl-select>
                <sl-input
                  type="date"
                  label="Start date"
                  .value=${this.startDate}
                  @sl-change=${this.handleStartDateChange}
                ></sl-input>
                <sl-input
                  type="date"
                  label="End date"
                  .value=${this.endDate}
                  @sl-change=${this.handleEndDateChange}
                ></sl-input>
                <sl-input
                  label="Search sessions"
                  placeholder="Principal, session reference, or source id"
                  .value=${this.searchQuery}
                  @sl-input=${this.handleSearchQueryChange}
                ></sl-input>
                <sl-select
                  label="Source type"
                  value=${this.sessionSourceType}
                  @sl-change=${this.handleSessionSourceTypeChange}
                >
                  <sl-option value="all">All sources</sl-option>
                  <sl-option value="flow_execution">Flow execution</sl-option>
                  <sl-option value="claude_code">Claude Code</sl-option>
                  <sl-option value="claude_desktop">Claude Desktop</sl-option>
                  <sl-option value="codex">Codex</sl-option>
                  <sl-option value="openclaw">OpenClaw</sl-option>
                  <sl-option value="desktop_agent">Desktop agent</sl-option>
                  <sl-option value="custom">Custom</sl-option>
                </sl-select>
                <sl-select
                  label="Status"
                  value=${this.status}
                  @sl-change=${this.handleStatusChange}
                >
                  <sl-option value="all">All</sl-option>
                  <sl-option value="active">Active</sl-option>
                  <sl-option value="ended">Ended</sl-option>
                </sl-select>
                <div class="filters-actions">
                  <sl-button variant="primary" @click=${this.applyFilters}>
                    Apply
                  </sl-button>
                  <sl-button variant="default" @click=${this.clearFilters}>
                    Reset
                  </sl-button>
                </div>
              </div>
            </sl-card>

            ${this.error
              ? html`
                  <sl-alert variant="danger" open>
                    <sl-icon slot="icon" name="exclamation-triangle"></sl-icon>
                    ${this.error}
                  </sl-alert>
                `
              : ''}
            ${this.loading
              ? html`
                  <sl-card>
                    <div class="loading-state">
                      <sl-spinner></sl-spinner>
                      <div>Loading runtime sessions...</div>
                    </div>
                  </sl-card>
                `
              : html`
                  <div class="layout">
                    <sl-card>
                      <div slot="header" class="session-item-title">
                        Sessions
                      </div>
                      ${this.renderSessionList()}
                    </sl-card>
                    ${this.renderDetail()}
                  </div>
                `}
          </div>
        </div>
      </div>
    `;
  }
}
