import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { router } from '../../router';
import { getFlowExecutions } from '../../api';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';

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
  `;

  @state()
  private executions: FlowExecution[] = [];

  async connectedCallback() {
    super.connectedCallback();
    this.executions = await getFlowExecutions();
  }

  render() {
    return html`
      <view-header headerText="Flow Executions"></view-header>
      <div class="column-layout">
        <div class="main-column">
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
                    <td>${exec.id}</td>
                    <td>${exec.flow_id}</td>
                    <td>
                      <sl-badge variant=${this.getStatusVariant(exec.status)}
                        >${exec.status}</sl-badge
                      >
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
