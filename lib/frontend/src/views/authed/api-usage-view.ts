import { LitElement, html, css } from 'lit';
import { customElement, query } from 'lit/decorators.js';
import {
  Chart,
  LineController,
  DoughnutController,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';

import '@vaadin/combo-box/vaadin-combo-box.js';
import '@vaadin/date-picker/vaadin-date-picker.js';
import '@vaadin/horizontal-layout/vaadin-horizontal-layout.js';

Chart.register(
  LineController,
  DoughnutController,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Tooltip,
  Legend
);

@customElement('api-usage-view')
export class ApiUsageView extends LitElement {
  @query('#apiUsageChart')
  private apiUsageChartCanvas!: HTMLCanvasElement;

  @query('#issueActionsChart')
  private issueActionsChartCanvas!: HTMLCanvasElement;

  static styles = css`
    :host {
      display: block;
      padding: var(--lumo-space-l);
    }
    h1 {
      font-size: var(--lumo-font-size-xxl);
      margin-bottom: var(--lumo-space-l);
    }
    .selectors {
      display: flex;
      gap: var(--lumo-space-m);
      align-items: center;
      margin-bottom: var(--lumo-space-l);
    }
    .charts-container {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: var(--lumo-space-l);
    }
    .chart-card,
    .list-card {
      padding: var(--lumo-space-l);
      background: var(--lumo-base-color);
      border-radius: var(--lumo-border-radius-l);
      box-shadow: var(--lumo-box-shadow-s);
    }
    h2 {
      font-size: var(--lumo-font-size-l);
      margin-top: 0;
    }
    .endpoints-list ul {
      list-style-type: none;
      padding: 0;
    }
    .endpoints-list li {
      display: flex;
      justify-content: space-between;
      padding: var(--lumo-space-s) 0;
      border-bottom: 1px solid var(--lumo-contrast-10pct);
    }
  `;

  firstUpdated() {
    this.initApiUsageChart();
    this.initIssueActionsChart();
  }

  initApiUsageChart() {
    const ctx = this.apiUsageChartCanvas.getContext('2d');
    if (ctx) {
      new Chart(ctx, {
        type: 'line',
        data: {
          labels: [
            'January',
            'February',
            'March',
            'April',
            'May',
            'June',
            'July',
          ],
          datasets: [
            {
              label: 'API Calls',
              data: [65, 59, 80, 81, 56, 55, 40],
              fill: false,
              borderColor: 'rgb(75, 192, 192)',
              tension: 0.1,
            },
          ],
        },
      });
    }
  }

  initIssueActionsChart() {
    const ctx = this.issueActionsChartCanvas.getContext('2d');
    if (ctx) {
      new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: ['Created', 'Updated', 'Deleted'],
          datasets: [
            {
              label: 'Issue Actions',
              data: [300, 50, 100],
              backgroundColor: [
                'rgb(54, 162, 235)',
                'rgb(255, 205, 86)',
                'rgb(255, 99, 132)',
              ],
              hoverOffset: 4,
            },
          ],
        },
      });
    }
  }

  render() {
    return html`
      <h1>API Usage</h1>

      <div class="selectors">
        <vaadin-combo-box
          label="Date Range"
          .items="${['Last 7 Days', 'Last 30 Days', 'Last 90 Days', 'Custom']}"
          value="Last 30 Days"
        ></vaadin-combo-box>
        <vaadin-date-picker label="Start Date"></vaadin-date-picker>
        <vaadin-date-picker label="End Date"></vaadin-date-picker>
      </div>

      <div class="charts-container">
        <div class="chart-card">
          <h2>API Usage Detail</h2>
          <canvas id="apiUsageChart"></canvas>
        </div>
        <div class="right-column">
          <div class="chart-card">
            <h2>Issue Actions</h2>
            <canvas id="issueActionsChart"></canvas>
          </div>
          <div class="list-card" style="margin-top: var(--lumo-space-l);">
            <h2>Endpoints Usage</h2>
            <div class="endpoints-list">
              <ul>
                <li><span>/api/v1/issues</span> <span>1,234 calls</span></li>
                <li><span>/api/v1/trackers</span> <span>876 calls</span></li>
                <li><span>/api/v1/users/me</span> <span>543 calls</span></li>
                <li><span>/api/v1/projects</span> <span>210 calls</span></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    `;
  }
}
