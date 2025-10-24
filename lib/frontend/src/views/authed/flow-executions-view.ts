import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { router } from '../../router';
import { getFlowExecutions } from '../../api';
import { webSocketService } from '../../services/websocket-service';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';

interface FlowExecution {
  id: string;
  flow_id: string;
  status: string;
  start_time: string;
  end_time?: string;
  actions_taken_summary?: any[];
}

@customElement('flow-executions-view')
export class FlowExecutionsView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: 16px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 1rem;
    }
    th,
    td {
      border: 1px solid var(--sl-color-neutral-200);
      padding: 8px;
      text-align: left;
    }
    th {
      background-color: var(--sl-color-neutral-100);
    }
    .status-cell {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      animation: pulse 2s infinite;
    }
    .status-indicator.running {
      background-color: var(--sl-color-primary-600);
    }
    .status-indicator.pending {
      background-color: var(--sl-color-warning-600);
    }
    @keyframes pulse {
      0%,
      100% {
        opacity: 1;
      }
      50% {
        opacity: 0.5;
      }
    }
    .header-controls {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .connection-status {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.9rem;
      color: var(--sl-color-neutral-600);
    }
    .connection-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: var(--sl-color-success-600);
    }
    .connection-dot.disconnected {
      background-color: var(--sl-color-danger-600);
    }
  `;

  @state()
  private executions: FlowExecution[] = [];

  @state()
  private wsConnected = false;

  async connectedCallback() {
    super.connectedCallback();
    await this.loadExecutions();
    this.connectWebSocket();
  }

  async loadExecutions() {
    this.executions = await getFlowExecutions();
  }

  connectWebSocket() {
    // Connect to general flow updates WebSocket
    webSocketService.connectToFlowUpdates(
      (message: any) => this.handleWebSocketMessage(message),
      () => {
        console.log('Connected to flow updates WebSocket');
        this.wsConnected = true;
      },
      () => {
        console.log('Disconnected from flow updates WebSocket');
        this.wsConnected = false;
      }
    );
  }

  handleWebSocketMessage(message: any) {
    console.log('Flow updates message:', message);

    // Handle status updates
    if (message.type === 'status_update' && message.execution_id) {
      const executionIndex = this.executions.findIndex(
        (exec) => exec.id === message.execution_id
      );

      if (executionIndex >= 0) {
        // Update existing execution
        const updated = [...this.executions];
        updated[executionIndex] = {
          ...updated[executionIndex],
          status: message.payload.status,
          ...(message.payload.end_time && {
            end_time: message.payload.end_time,
          }),
        };
        this.executions = updated;
      } else {
        // New execution started, reload the list
        this.loadExecutions();
      }
    }

    // Handle new executions
    if (message.type === 'execution_started' && message.payload) {
      this.loadExecutions();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    webSocketService.disconnectFromFlowUpdates();
  }

  render() {
    return html`
      <view-header headerText="Flow Executions"></view-header>
      <div class="column-layout">
        <div class="main-column">
          <div class="header-controls">
            <sl-button size="small" @click=${this.loadExecutions}>
              <sl-icon name="arrow-clockwise"></sl-icon>
              Refresh
            </sl-button>
            <div class="connection-status">
              <div
                class="connection-dot ${this.wsConnected ? '' : 'disconnected'}"
              ></div>
              <span>${this.wsConnected ? 'Live Updates' : 'Disconnected'}</span>
            </div>
          </div>
          <table>
            <thead>
              <tr>
                <th>Execution ID</th>
                <th>Flow ID</th>
                <th>Status</th>
                <th>Start Time</th>
                <th>End Time</th>
                <th>Actions</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              ${this.executions.map(
                (exec) => html`
                  <tr>
                    <td>${exec.id.slice(0, 8)}...</td>
                    <td>${exec.flow_id.slice(0, 8)}...</td>
                    <td>
                      <div class="status-cell">
                        ${exec.status === 'RUNNING' || exec.status === 'PENDING'
                          ? html`
                              <div
                                class="status-indicator ${exec.status.toLowerCase()}"
                              ></div>
                            `
                          : ''}
                        <sl-badge variant=${this.getStatusVariant(exec.status)}
                          >${exec.status}</sl-badge
                        >
                      </div>
                    </td>
                    <td>${new Date(exec.start_time).toLocaleString()}</td>
                    <td>
                      ${exec.end_time
                        ? new Date(exec.end_time).toLocaleString()
                        : '-'}
                    </td>
                    <td>${exec.actions_taken_summary?.length || 0}</td>
                    <td>
                      <sl-button
                        size="small"
                        href=${router.urlForPath(
                          `/console/flows/executions/${exec.id}`
                        )}
                      >
                        <sl-icon name="eye"></sl-icon>
                        View
                      </sl-button>
                    </td>
                  </tr>
                `
              )}
            </tbody>
          </table>
        </div>
        <div class="side-column"></div>
      </div>
    `;
  }

  getStatusVariant(status: string) {
    switch (status) {
      case 'SUCCEEDED':
        return 'success';
      case 'FAILED':
        return 'danger';
      case 'RUNNING':
        return 'primary';
      default:
        return 'neutral';
    }
  }
}
