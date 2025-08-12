import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { webSocketService } from '../../services/websocket-service';

interface FlowExecutionUpdate {
  execution_id: string;
  timestamp: string;
  type: string;
  payload: any;
}

@customElement('flow-execution-view')
export class FlowExecutionView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: 16px;
    }
    .log-container {
      background-color: #f5f5f5;
      border: 1px solid #ddd;
      padding: 10px;
      max-height: 500px;
      overflow-y: auto;
    }
    .log-entry {
      font-family: monospace;
      white-space: pre-wrap;
    }
  `;

  @property()
  executionId?: string;

  @state()
  private status = 'Connecting...';

  @state()
  private logs: FlowExecutionUpdate[] = [];

  connectedCallback() {
    super.connectedCallback();
    if (this.executionId) {
      const wsUrl = `ws://${window.location.host}/api/v1/ws/flow-updates`;
      webSocketService.connect(wsUrl, (message: FlowExecutionUpdate) => {
        if (message.execution_id === this.executionId) {
          this.logs = [...this.logs, message];
          if (message.type === 'status_update') {
            this.status = message.payload.status;
          }
        }
      });
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    webSocketService.disconnect();
  }

  render() {
    return html`
      <h1>Flow Execution: ${this.executionId}</h1>
      <p><strong>Status:</strong> ${this.status}</p>

      <div class="log-container">
        ${this.logs.map(
          (log) => html`
            <div class="log-entry">
              <strong
                >[${new Date(log.timestamp).toLocaleTimeString()}]
                [${log.type}]</strong
              >
              <pre>${JSON.stringify(log.payload, null, 2)}</pre>
            </div>
          `
        )}
      </div>
    `;
  }
}
