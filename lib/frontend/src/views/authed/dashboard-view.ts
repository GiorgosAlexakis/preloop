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
import '../../components/tracker-pill.ts';
import '../../components/theme-switcher.ts';
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

interface IssueCount {
  total_issues: number;
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
  private totalIssues = 0;

  @state()
  private isLoading = true;

  async connectedCallback() {
    super.connectedCallback();
    this.fetchDashboardData();
  }

  async fetchDashboardData() {
    this.isLoading = true;
    try {
      const [trackers, apiUsage, apiUsageStats, issueCount] = await Promise.all(
        [
          api.getTrackers(),
          api.getApiUsageStats(),
          this.fetchData('/api/v1/auth/api-usage?timeseries=true') as Promise<
            ApiUsageStat[]
          >,
          api.getIssueCount(),
        ]
      );
      this.trackers = trackers;
      this.apiUsage = apiUsage;
      this.apiUsageStats = apiUsageStats;
      this.totalIssues = issueCount.total_issues;
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
      .tracker-pills {
        display: flex;
        gap: var(--sl-spacing-2x-small);
        align-items: center;
        flex-wrap: wrap;
        justify-content: flex-end;
      }
    `,
  ];

  render() {

    return html`
        <view-header headerText="Overview">
          <div slot="side-column">
            <theme-switcher></theme-switcher>
          </div>
        </view-header>
        <div class="column-layout">
          <div class="main-column">
            ${this.trackers.length > 0 || this.isLoading
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
                  <div class="tracker-pills">
                    ${this.trackers.slice(0, 2).map(
                      tracker => html`
                        <sl-tooltip content="${tracker.name}">
                          <tracker-pill .tracker=${tracker}></tracker-pill>
                        </sl-tooltip>
                      `
                    )}
                    ${this.trackers.length > 2
                      ? html`
                          <sl-tooltip
                            content="${this.trackers
                              .slice(2)
                              .map(t => t.name)
                              .join(', ')}"
                          >
                            <sl-tag size="small" pill
                              >+${this.trackers.length - 2}</sl-tag
                            >
                          </sl-tooltip>
                        `
                      : ''}
                    ${this.trackers.length === 0
                      ? html`<strong>0</strong>`
                      : ''}
                  </div>
                </li>
                <li class="summary-item">
                  <a href="/console/settings/api-keys">Total API Requests</a>
                  <strong>${this.apiUsage?.total_requests || 0}</strong>
                </li>
                <li class="summary-item">
                  <span>Total Issues Processed</span>
                  <strong>${this.totalIssues}</strong>
                </li>
              </ul>
            </sl-card>
          </div>
        </div>
    `;
  }
}
