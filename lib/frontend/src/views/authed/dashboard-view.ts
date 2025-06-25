import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import * as api from '../../api';
import { AuthedElement } from '../../api';
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
} from 'chart.js';

Chart.register(
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend
);

interface Tracker {
  id: string;
  name: string;
  type: string;
}

interface ApiUsage {
  total_requests: number;
  issues_created: number;
  issues_updated: number;
  issues_closed: number;
}

interface ApiUsageStat {
  date: string;
  total_requests: number;
  issues_created: number;
  issues_updated: number;
  issues_closed: number;
}

@customElement('dashboard-view')
export class DashboardView extends AuthedElement {
  @state()
  private trackers: Tracker[] = [];

  @state()
  private apiUsage?: ApiUsage;

  @state()
  private apiUsageStats: ApiUsageStat[] = [];

  @state()
  private isLoading = true;

  private chart?: Chart;

  async connectedCallback() {
    super.connectedCallback();
    this.fetchDashboardData();
  }

  async fetchDashboardData() {
    this.isLoading = true;
    try {
      const [trackers, apiUsage, apiUsageStats] = await Promise.all([
        api.getTrackers(),
        api.getApiUsageStats(),
        this.fetchData('/api/v1/auth/api-usage?timeseries=true') as Promise<
          ApiUsageStat[]
        >,
      ]);
      this.trackers = trackers;
      this.apiUsage = apiUsage;
      this.apiUsageStats = apiUsageStats;
    } catch (error) {
      console.error('Failed to fetch dashboard data', error);
    } finally {
      this.isLoading = false;
    }
  }

  static styles = css`
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
    }
    sl-card {
      text-align: center;
    }
    .chart-container {
      margin-top: 2rem;
    }
  `;

  updated(changedProperties: Map<string, any>) {
    if (
      changedProperties.has('apiUsageStats') &&
      this.apiUsageStats.length > 0
    ) {
      this.renderChart();
    }
  }

  renderChart() {
    const canvas = this.renderRoot.querySelector(
      '#apiUsageChart'
    ) as HTMLCanvasElement;
    if (!canvas) return;

    const labels = this.apiUsageStats.map((stat) =>
      new Date(stat.date).toLocaleDateString()
    );
    const data = {
      labels: labels,
      datasets: [
        {
          label: 'Total API Requests',
          data: this.apiUsageStats.map((stat) => stat.total_requests),
          borderColor: 'rgba(75, 192, 192, 1)',
          tension: 0.1,
        },
      ],
    };

    if (this.chart) {
      this.chart.destroy();
    }

    this.chart = new Chart(canvas, {
      type: 'line',
      data: data,
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: 'top',
          },
          tooltip: {
            mode: 'index',
            intersect: false,
          },
        },
        scales: {
          y: {
            beginAtZero: true,
          },
        },
      },
    });
  }

  render() {
    if (this.isLoading) {
      return html`<sl-spinner></sl-spinner>`;
    }

    const totalIssuesProcessed =
      (this.apiUsage?.issues_created || 0) +
      (this.apiUsage?.issues_updated || 0) +
      (this.apiUsage?.issues_closed || 0);

    return html`
      <div class="stats-grid">
        <sl-card>
          <h3>${this.trackers.length}</h3>
          <p>Connected Trackers</p>
        </sl-card>
        <sl-card>
          <h3>${this.apiUsage?.total_requests}</h3>
          <p>Total API Requests</p>
        </sl-card>
        <sl-card>
          <h3>${totalIssuesProcessed}</h3>
          <p>Issues Processed</p>
        </sl-card>
      </div>
      <div class="chart-container">
        <canvas id="apiUsageChart"></canvas>
      </div>
    `;
  }
}
