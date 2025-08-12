import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { router } from '../../router';
import { getFlowExecutions } from '../../api'; // Assuming this function will be created

interface FlowExecution {
  id: string;
  flow_id: string;
  status: string;
  start_time: string;
  // Add other execution properties here
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
    }
    th,
    td {
      border: 1px solid #ddd;
      padding: 8px;
      text-align: left;
    }
  `;

  @state()
  private executions: FlowExecution[] = [];

  async connectedCallback() {
    super.connectedCallback();
    // this.executions = await getFlowExecutions(); // This will be uncommented once the API function is created
  }

  render() {
    return html`
      <h1>Flow Executions</h1>
      <table>
        <thead>
          <tr>
            <th>Execution ID</th>
            <th>Flow ID</th>
            <th>Status</th>
            <th>Start Time</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          ${this.executions.map(
            (exec) => html`
              <tr>
                <td>${exec.id}</td>
                <td>${exec.flow_id}</td>
                <td>${exec.status}</td>
                <td>${new Date(exec.start_time).toLocaleString()}</td>
                <td>
                  <a
                    href=${router.urlForPath(
                      `/console/flows/executions/${exec.id}`
                    )}
                  >
                    View
                  </a>
                </td>
              </tr>
            `
          )}
        </tbody>
      </table>
    `;
  }
}
