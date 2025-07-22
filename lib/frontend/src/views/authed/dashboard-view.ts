import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/progress-bar/progress-bar.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/tag/tag.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import * as api from '../../api';
import { AuthedElement } from '../../api';
import '../../components/similar-issues-widget.ts';
import '../../components/duplicate-stats-chart.ts';
import {
  DEFAULT_SIMILARITY_THRESHOLD,
  DEFAULT_SIMILARITY_THRESHOLD_CHARTS,
} from '../../config';
import consoleStyles from '../../styles/console-styles.css?inline';

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

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      .container {
        padding: var(--sl-spacing-large);
      }
      h1 {
        margin-bottom: var(--sl-spacing-large);
      }
      .overview-layout {
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: var(--sl-spacing-large);
        align-items: start;
      }
      .main-column,
      .side-column {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }
      .side-column {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }
      .summary-list {
        list-style: none;
        padding: 0;
        margin: 0;
      }
      .summary-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--sl-spacing-small) 0;
        border-bottom: 1px solid var(--sl-color-neutral-200);
      }
      .summary-item:last-child {
        border-bottom: none;
      }
      .dor-item {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-x-small);
      }
      .dor-label {
        display: flex;
        justify-content: space-between;
      }
      .dor-suggestion-list {
        list-style: none;
        padding: 0;
        margin: 0;
      }
      .dor-suggestion-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--sl-spacing-x-small) 0;
        border-bottom: 1px solid var(--sl-color-neutral-200);
      }
      .dor-suggestion-item:last-child {
        border-bottom: none;
      }
      .dor-suggestion-item .issue-title {
        font-size: var(--sl-font-size-small);
      }
      .dor-suggestion-item .fail-reason {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-danger-600);
      }
      .flows-table {
        width: 100%;
        border-collapse: collapse;
        font-size: var(--sl-font-size-small);
      }
      .flows-table th,
      .flows-table td {
        padding: var(--sl-spacing-small);
        text-align: left;
        border-bottom: 1px solid var(--sl-color-neutral-200);
        vertical-align: top;
      }
      .flows-table th {
        font-weight: 600;
      }
      .flows-table .prompt-cell {
        max-width: 350px;
        white-space: normal;
        word-break: break-word;
      }
      .flows-table .tools-cell sl-tag {
        margin-right: var(--sl-spacing-2x-small);
        margin-bottom: var(--sl-spacing-2x-small);
      }
      .flows-table .actions-cell {
        display: flex;
        gap: var(--sl-spacing-x-small);
        white-space: nowrap;
      }
      .chart-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
      }

      sl-icon {
        font-size: 1rem;
      }
      @media (max-width: 992px) {
        .overview-layout {
          grid-template-columns: 1fr;
        }
      }
    `,
  ];

  render() {
    if (this.isLoading) {
      return html`<sl-spinner></sl-spinner>`;
    }

    const totalIssuesProcessed =
      (this.apiUsage?.issues_created || 0) +
      (this.apiUsage?.issues_updated || 0) +
      (this.apiUsage?.issues_closed || 0);

    return html`
      <div class="container">
        <div class="header">
          <h1>Overview</h1>
        </div>
        <div class="overview-layout">
          <div class="main-column">
            ${this.trackers.length > 0
              ? html`
                  <similar-issues-widget></similar-issues-widget>
                  <sl-card>
                    <div slot="header" class="chart-header">
                      Similar Issues per Project
                      <sl-tooltip
                        content="Showing issues with a similarity score of ${DEFAULT_SIMILARITY_THRESHOLD_CHARTS *
                        100}% or higher."
                      >
                        <sl-icon name="question-circle"></sl-icon>
                      </sl-tooltip>
                    </div>
                    <duplicate-stats-chart
                      .similarityThreshold=${DEFAULT_SIMILARITY_THRESHOLD_CHARTS}
                    ></duplicate-stats-chart>
                  </sl-card>
                `
              : html`
                  <sl-alert variant="primary" open>
                    <sl-icon slot="icon" name="info-circle"></sl-icon>
                    ${unsafeHTML(
                      'No projects found. <a href="/console/trackers">Add a tracker</a> to see project-specific widgets.'
                    )}
                  </sl-alert>
                `}

            <!-- Future widgets can be added here -->
          </div>
          <div class="side-column">
            <sl-card>
              <div slot="header">Key Metrics</div>
              <ul class="summary-list">
                <li class="summary-item">
                  <a href="/console/trackers">Connected Trackers</a>
                  <strong>${this.trackers.length}</strong>
                </li>
                <li class="summary-item">
                  <a href="/console/settings/api-keys">Total API Requests</a>
                  <strong>${this.apiUsage?.total_requests || 0}</strong>
                </li>
              </ul>
            </sl-card>
          </div>
        </div>
      </div>
    `;
  }
}
