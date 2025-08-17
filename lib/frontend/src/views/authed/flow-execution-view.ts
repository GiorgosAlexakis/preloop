import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { webSocketService } from '../../services/websocket-service';
import { getFlowExecutions } from '../../api';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/progress-bar/progress-bar.js';
import '@shoelace-style/shoelace/dist/components/relative-time/relative-time.js';

interface FlowExecutionUpdate {
  execution_id: string;
  timestamp: string;
  type: string;
  payload: any;
}

interface FlowExecution {
  id: string;
  flow_id: string;
  status: string;
  start_time: string;
  end_time?: string;
  actions_taken_summary?: any[];
  model_output_summary?: string;
  resolved_input_prompt?: string;
}

@customElement('flow-execution-view')
export class FlowExecutionView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: 16px;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 16px;
    }
    .log-container {
      background-color: var(--sl-color-neutral-50);
      border: 1px solid var(--sl-color-neutral-200);
      padding: 10px;
      max-height: 600px;
      overflow-y: auto;
      font-family: var(--sl-font-mono);
    }
    .log-entry {
      white-space: pre-wrap;
      margin-bottom: 8px;
    }
  `;

  @property()
  executionId?: string;

  @state()
  private execution: FlowExecution | null = null;

  @state()
  private logs: FlowExecutionUpdate[] = [];

  @state()
  private toolCalls = 0;

  @state()
  private budgetUsed = 0;

  connectedCallback() {
    super.connectedCallback();
    if (this.executionId) {
      this.fetchExecution();
      const wsUrl = `ws${window.location.protocol === 'https:' ? 's' : ''}://${window.location.host}/api/v1/ws/flow-updates`;
      webSocketService.connect(wsUrl, (message: FlowExecutionUpdate) => {
        if (message.execution_id === this.executionId) {
          this.logs = [...this.logs, message];
          if (message.type === 'status_update' && this.execution) {
            this.execution.status = message.payload.status;
            this.requestUpdate();
          }
          if (message.type === 'tool_call') {
            this.toolCalls++;
          }
          if (message.type === 'budget_update') {
            this.budgetUsed = message.payload.budget_used;
          }
        }
      });
    }
  }

  async fetchExecution() {
    if (this.executionId) {
      const executions = await getFlowExecutions();
      this.execution =
        executions.find((exec) => exec.id === this.executionId) || null;
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    webSocketService.disconnect();
  }

  render() {
    if (!this.execution) {
      return html`<sl-progress-bar indeterminate></sl-progress-bar>`;
    }
    return html`
      <view-header
        headerText="Flow Execution: ${this.execution.id}"
      ></view-header>
      <div class="column-layout">
        <div class="main-column">
          <div class="summary-grid">
            <sl-card>
              <div slot="header">Status</div>
              <sl-badge variant=${this.getStatusVariant(this.execution.status)}
                >${this.execution.status}</sl-badge
              >
            </sl-card>
            <sl-card>
              <div slot="header">Started</div>
              <sl-relative-time
                date=${new Date(this.execution.start_time)}
              ></sl-relative-time>
            </sl-card>
            <sl-card>
              <div slot="header">Tool Calls</div>
              ${this.toolCalls}
            </sl-card>
            <sl-card>
              <div slot="header">Budget Used</div>
              $${this.budgetUsed.toFixed(2)}
            </sl-card>
          </div>

          <sl-card header="Logs">
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
          </sl-card>
        </div>
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
