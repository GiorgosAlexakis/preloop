import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import {
  getRuntimeSessionGatewayEvents,
  getRuntimeSessionGatewayEventDetail,
} from '../api';
import type { FlowGatewayEvent } from '../types';
import './json-tree.js';

@customElement('session-history-widget')
export class SessionHistoryWidget extends LitElement {
  @property({ type: Array }) sessions: any[] = [];

  @state() private activeSessionId: string | null = null;
  @state() private loadedEvents: Record<string, FlowGatewayEvent[]> = {};
  @state() private loadingSessions: Set<string> = new Set();
  @state() private errorSessions: Record<string, string> = {};

  @state() private loadedEventDetails: Record<string, FlowGatewayEvent> = {};
  @state() private loadingEventDetails: Set<string> = new Set();
  @state() private errorEventDetails: Record<string, string> = {};

  private unsubscribeRealtime?: () => void;

  connectedCallback() {
    super.connectedCallback();
    this.connectRealtime();
    // Auto-select first session if available
    if (this.sessions && this.sessions.length > 0 && !this.activeSessionId) {
      this._selectSession(this.sessions[0].id);
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.unsubscribeRealtime?.();
  }

  private connectRealtime() {
    this.unsubscribeRealtime = (
      window as any
    ).unifiedWebSocketManager?.subscribe('gateway_activity', (message: any) => {
      const payload = message?.payload ?? {};
      const sessionId = payload.runtime_session_id;
      if (!sessionId) return;

      // Update session order
      const sessionIndex = this.sessions.findIndex((s) => s.id === sessionId);
      if (sessionIndex >= 0) {
        const newSessions = [...this.sessions];
        const [session] = newSessions.splice(sessionIndex, 1);
        session.last_activity_at =
          payload.timestamp || session.last_activity_at;
        if (message.type === 'model_gateway_call') {
          session.total_requests = (session.total_requests || 0) + 1;
          session.estimated_cost =
            (session.estimated_cost || 0) + Number(payload.estimated_cost || 0);
        }
        this.sessions = [session, ...newSessions];
      }

      // Stream event to the active session view
      if (sessionId === this.activeSessionId && this.loadedEvents[sessionId]) {
        const newEvent: FlowGatewayEvent = {
          id: message.id || crypto.randomUUID(),
          execution_id: message.execution_id || '',
          timestamp: payload.timestamp || new Date().toISOString(),
          type: message.type,
          payload: {
            ...payload,
            outcome:
              message.type === 'model_gateway_request_started'
                ? 'pending'
                : payload.status_code >= 400
                  ? 'error'
                  : 'success',
          },
        };

        const existingEvents = this.loadedEvents[sessionId];
        let nextEvents = existingEvents;

        if (message.type === 'model_gateway_call') {
          nextEvents = existingEvents.filter(
            (e) =>
              !(
                e.type === 'model_gateway_request_started' &&
                Math.abs(
                  new Date(e.timestamp || new Date().toISOString()).getTime() -
                    new Date(
                      payload.timestamp || new Date().toISOString()
                    ).getTime()
                ) < 60000
              )
          );
        }

        // Add to the top of the events array (newest first)
        this.loadedEvents = {
          ...this.loadedEvents,
          [sessionId]: [newEvent, ...nextEvents],
        };
      }
    });
  }

  static styles = css`
    :host {
      display: block;
    }
    .widget-container {
      display: grid;
      grid-template-columns: minmax(280px, 350px) 1fr;
      gap: var(--sl-spacing-large);
      height: 600px;
    }
    @media (max-width: 900px) {
      .widget-container {
        grid-template-columns: 1fr;
        grid-template-rows: 250px 1fr;
      }
    }
    .sessions-col {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-small);
      border-right: 1px solid var(--sl-color-neutral-200);
      padding-right: var(--sl-spacing-medium);
      overflow-y: auto;
    }
    .events-col {
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      padding-left: var(--sl-spacing-small);
      position: relative;
    }
    @media (max-width: 900px) {
      .sessions-col {
        border-right: none;
        border-bottom: 1px solid var(--sl-color-neutral-200);
        padding-right: 0;
        padding-bottom: var(--sl-spacing-medium);
      }
      .events-col {
        padding-left: 0;
      }
    }
    .session-card {
      padding: var(--sl-spacing-small) var(--sl-spacing-medium);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      background: var(--sl-color-neutral-0);
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      flex-direction: column;
    }
    .session-card:hover {
      border-color: var(--sl-color-primary-400);
      background: var(--sl-color-primary-50);
    }
    .session-card.active {
      border-color: var(--sl-color-primary-600);
      background: var(--sl-color-primary-50);
      box-shadow: 0 0 0 1px var(--sl-color-primary-600);
    }
    .session-title {
      font-weight: 600;
      color: var(--sl-color-neutral-900);
    }
    .session-meta {
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-500);
      margin-top: 4px;
    }
    .event-list {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-small);
    }
    .event-item {
      padding: var(--sl-spacing-small) var(--sl-spacing-medium);
      border-radius: var(--sl-border-radius-medium);
      background: var(--sl-color-neutral-50);
      font-size: var(--sl-font-size-small);
      border-left: 3px solid var(--sl-color-neutral-300);
    }
    .event-title {
      font-weight: 600;
      margin-bottom: 4px;
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-small);
    }
    .event-meta {
      color: var(--sl-color-neutral-600);
    }
    .loading-state,
    .empty-state {
      padding: var(--sl-spacing-medium);
      text-align: center;
      color: var(--sl-color-neutral-500);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      gap: var(--sl-spacing-small);
      font-size: var(--sl-font-size-small);
    }
  `;

  public reloadActiveSession() {
    if (this.activeSessionId) {
      delete this.loadedEvents[this.activeSessionId];
      this._selectSession(this.activeSessionId);
    }
  }

  private async _selectSession(sessionId: string) {
    this.activeSessionId = sessionId;
    if (this.loadedEvents[sessionId] || this.loadingSessions.has(sessionId)) {
      return;
    }

    const nextLoading = new Set(this.loadingSessions);
    nextLoading.add(sessionId);
    this.loadingSessions = nextLoading;

    try {
      const response = await getRuntimeSessionGatewayEvents(sessionId, 100);
      // Sort newest events first for the timeline view
      const events = (response.logs || []).sort(
        (a: any, b: any) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      this.loadedEvents = {
        ...this.loadedEvents,
        [sessionId]: events,
      };
    } catch (err: any) {
      this.errorSessions = {
        ...this.errorSessions,
        [sessionId]: err.message || 'Failed to load events',
      };
    } finally {
      const doneLoading = new Set(this.loadingSessions);
      doneLoading.delete(sessionId);
      this.loadingSessions = doneLoading;
    }
  }

  private async _handleEventShow(sessionId: string, eventId: string) {
    if (
      this.loadedEventDetails[eventId] ||
      this.loadingEventDetails.has(eventId)
    ) {
      return;
    }

    const nextLoading = new Set(this.loadingEventDetails);
    nextLoading.add(eventId);
    this.loadingEventDetails = nextLoading;

    try {
      const response = await getRuntimeSessionGatewayEventDetail(
        sessionId,
        eventId
      );
      this.loadedEventDetails = {
        ...this.loadedEventDetails,
        [eventId]: response,
      };
    } catch (err: any) {
      this.errorEventDetails = {
        ...this.errorEventDetails,
        [eventId]: err.message || 'Failed to load event details',
      };
    } finally {
      const doneLoading = new Set(this.loadingEventDetails);
      doneLoading.delete(eventId);
      this.loadingEventDetails = doneLoading;
    }
  }

  private _formatDate(dateStr: string | null | undefined) {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString();
  }

  private _renderEvent(sessionId: string, event: FlowGatewayEvent) {
    const payload = event.payload || {};
    const isTool = event.type === 'tool_call';
    const isModel = event.type === 'model_gateway_call';

    let title = event.type;
    let icon = 'activity';
    let borderColor = 'var(--sl-color-neutral-300)';

    if (isTool) {
      title = `Tool Call: ${payload.tool_name || 'Unknown'}`;
      icon = 'tools';
      borderColor = 'var(--sl-color-primary-500)';
    } else if (isModel) {
      title = `Model: ${payload.model_alias || payload.requested_model || 'Unknown'}`;
      icon = 'cpu';
      borderColor = 'var(--sl-color-success-500)';
    }

    return html`
      <div class="event-item" style="border-left-color: ${borderColor}">
        <div class="event-title">
          <sl-icon name=${icon}></sl-icon>
          ${title}
          ${payload.outcome
            ? html`<sl-badge
                variant=${payload.outcome === 'error' ? 'danger' : 'neutral'}
                >${payload.outcome}</sl-badge
              >`
            : ''}
        </div>
        <div class="event-meta">
          ${this._formatDate(event.timestamp)}
          ${payload.estimated_cost
            ? `· $${payload.estimated_cost.toFixed(4)}`
            : ''}
          ${payload.total_tokens ? `· ${payload.total_tokens} tokens` : ''}
        </div>
        ${payload.error_detail
          ? html`<div
              style="color: var(--sl-color-danger-600); margin-top: 4px;"
            >
              ${payload.error_detail}
            </div>`
          : ''}

        <sl-details
          summary="View Payload"
          style="margin-top: var(--sl-spacing-small);"
          @sl-show=${() => this._handleEventShow(sessionId, String(event.id))}
        >
          ${this.loadingEventDetails.has(String(event.id))
            ? html`
                <div class="loading-state">
                  <sl-spinner></sl-spinner> Loading details...
                </div>
              `
            : this.errorEventDetails[event.id]
              ? html`
                  <div
                    class="empty-state"
                    style="color: var(--sl-color-danger-600)"
                  >
                    ${this.errorEventDetails[event.id]}
                  </div>
                `
              : this.loadedEventDetails[event.id]
                ? (() => {
                    const detailPayload =
                      this.loadedEventDetails[event.id].payload || {};
                    return html`
                      ${detailPayload.request
                        ? html`
                            <div
                              style="font-weight: bold; margin-bottom: 8px; color: var(--sl-color-neutral-700);"
                            >
                              Prompt / Request Context
                            </div>
                            <json-tree
                              .data=${detailPayload.request}
                              .initiallyExpanded=${true}
                            ></json-tree>
                          `
                        : ''}
                      ${detailPayload.response
                        ? html`
                            <div
                              style="font-weight: bold; margin-top: 16px; margin-bottom: 8px; color: var(--sl-color-neutral-700);"
                            >
                              Model Completion / Logic Execution
                            </div>
                            <json-tree
                              .data=${detailPayload.response}
                              .initiallyExpanded=${true}
                            ></json-tree>
                          `
                        : detailPayload.outcome === 'error' ||
                            event.type === 'model_gateway_request_started'
                          ? html`
                              <div
                                class="${event.type ===
                                'model_gateway_request_started'
                                  ? 'empty-state'
                                  : 'empty-state danger'}"
                                style="${event.type ===
                                'model_gateway_request_started'
                                  ? ''
                                  : 'color: var(--sl-color-danger-600); border: 1px solid var(--sl-color-danger-200); background: var(--sl-color-danger-50); border-radius: var(--sl-border-radius-medium); padding: var(--sl-spacing-small);'}"
                              >
                                ${event.type === 'model_gateway_request_started'
                                  ? 'Waiting for model response...'
                                  : 'No response received. The gateway request failed or timed out.'}
                              </div>
                            `
                          : html`
                              <div class="empty-state">
                                No response payload provided
                              </div>
                            `}
                    `;
                  })()
                : null}
        </sl-details>
      </div>
    `;
  }

  render() {
    if (!this.sessions?.length) {
      return html`
        <div class="empty-state" style="height: auto;">
          No sessions recorded for this agent yet.
        </div>
      `;
    }

    // Sort by last_activity_at or started_at
    const sortedSessions = [...this.sessions].sort((a, b) => {
      const timeA = new Date(a.last_activity_at || a.started_at).getTime();
      const timeB = new Date(b.last_activity_at || b.started_at).getTime();
      return timeB - timeA;
    });

    return html`
      <div class="widget-container">
        <!-- Sessions Left Pane -->
        <div class="sessions-col">
          ${repeat(
            sortedSessions,
            (s) => s.id,
            (session) => html`
              <div
                class="session-card ${this.activeSessionId === session.id
                  ? 'active'
                  : ''}"
                @click=${() => this._selectSession(session.id)}
              >
                <div class="session-title">
                  ${session.session_alias || 'Session'}
                </div>
                <div class="session-meta">
                  ${session.session_source_type} · ${session.session_source_id}
                </div>
                <div class="session-meta">
                  ${this._formatDate(
                    session.last_activity_at || session.started_at
                  )}
                  · ${session.total_requests} requests ·
                  $${(session.estimated_cost || 0).toFixed(4)}
                </div>
              </div>
            `
          )}
        </div>

        <!-- Events Right Pane -->
        <div class="events-col">
          ${!this.activeSessionId
            ? html`
                <div class="empty-state">
                  Select a session to view its interactions
                </div>
              `
            : this.loadingSessions.has(this.activeSessionId)
              ? html`
                  <div class="loading-state">
                    <sl-spinner></sl-spinner> Loading interaction timeline...
                  </div>
                `
              : this.errorSessions[this.activeSessionId]
                ? html`
                    <div
                      class="empty-state"
                      style="color: var(--sl-color-danger-600)"
                    >
                      <sl-icon
                        name="exclamation-triangle"
                        style="font-size: 2rem;"
                      ></sl-icon>
                      ${this.errorSessions[this.activeSessionId]}
                    </div>
                  `
                : this.loadedEvents[this.activeSessionId]
                  ? html`
                      <div
                        style="display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--sl-spacing-medium);"
                      >
                        <div style="font-weight: 600;">
                          Interactions Timeline
                          (${this.loadedEvents[this.activeSessionId].length})
                        </div>
                        <sl-button
                          size="small"
                          variant="default"
                          href="/console/runtime-sessions?sessionId=${encodeURIComponent(
                            this.activeSessionId
                          )}"
                        >
                          View full session
                        </sl-button>
                      </div>
                      <div class="event-list">
                        ${this.loadedEvents[this.activeSessionId].length > 0
                          ? this.loadedEvents[this.activeSessionId].map(
                              (event) =>
                                this._renderEvent(this.activeSessionId!, event)
                            )
                          : html`<div class="empty-state" style="height: auto;">
                              No interactions captured.
                            </div>`}
                      </div>
                    `
                  : null}
        </div>
      </div>
    `;
  }
}
