import { LitElement, html, css, unsafeCSS } from 'lit';
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

import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '../../components/view-header.ts';
import consoleStyles from '../../styles/console-styles.css?inline';

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

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      /* Component-specific styles */
      .selectors {
        display: flex;
        gap: var(--sl-spacing-medium);
        align-items: center;
        flex-wrap: wrap;
      }
      h2 {
        margin: 0;
      }
      .endpoints-list ul {
        list-style-type: none;
        padding: 0;
        margin: 0;
      }
      .endpoints-list li {
        display: flex;
        justify-content: space-between;
        padding: var(--sl-spacing-small) 0;
        border-bottom: 1px solid var(--sl-color-neutral-200);
      }
      .endpoints-list li:last-child {
        border-bottom: none;
      }
    `,
  ];

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
      <view-header headerText="API Usage" width="extra-wide"></view-header>
      <div class="column-layout dashboard extra-wide">
        <div class="main-column">
          <sl-card>
            <h2 slot="header">Filters</h2>
            <div class="selectors">
              <sl-select label="Date Range" value="last-30">
                <sl-option value="last-7">Last 7 Days</sl-option>
                <sl-option value="last-30">Last 30 Days</sl-option>
                <sl-option value="last-90">Last 90 Days</sl-option>
                <sl-option value="custom">Custom</sl-option>
              </sl-select>
              <sl-input type="date" label="Start Date"></sl-input>
              <sl-input type="date" label="End Date"></sl-input>
            </div>
          </sl-card>
          <sl-card>
            <h2 slot="header">API Usage Detail</h2>
            <canvas id="apiUsageChart"></canvas>
          </sl-card>
        </div>
        <div class="side-column">
          <sl-card>
            <h2 slot="header">Issue Actions</h2>
            <canvas id="issueActionsChart"></canvas>
          </sl-card>
          <sl-card>
            <h2 slot="header">Endpoints Usage</h2>
            <div class="endpoints-list">
              <ul>
                <li><span>/api/v1/issues</span> <span>1,234 calls</span></li>
                <li><span>/api/v1/trackers</span> <span>876 calls</span></li>
                <li><span>/api/v1/users/me</span> <span>543 calls</span></li>
                <li><span>/api/v1/projects</span> <span>210 calls</span></li>
              </ul>
            </div>
          </sl-card>
        </div>
      </div>
    `;
  }
}
