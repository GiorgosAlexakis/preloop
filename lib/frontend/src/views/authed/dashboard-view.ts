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
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
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

interface MCPServer {
  id: string;
  name: string;
  url: string;
  status: string; // 'active', 'error', 'inactive'
  transport: string;
  last_scan_at: string | null;
  last_error: string | null;
}

interface Tool {
  id: string;
  tool_name: string;
  tool_source: string; // 'builtin' or 'mcp'
  enabled: boolean;
  requires_approval: boolean;
  mcp_server_id?: string;
}

interface FlowExecution {
  id: string;
  flow_id: string;
  flow_name?: string;
  status: string; // 'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', etc.
  start_time: string;
  end_time: string | null;
  error_message: string | null;
}

interface ComplianceMetrics {
  total_issues: number;
  compliant_issues: number;
  non_compliant_issues: number;
  compliance_rate: number;
}

interface ApprovalRequest {
  id: string;
  tool_name: string;
  tool_arguments: any;
  status: string; // 'pending', 'approved', 'declined'
  requested_at: string;
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
  private mcpServers: MCPServer[] = [];

  @state()
  private tools: Tool[] = [];

  @state()
  private recentFlowExecutions: FlowExecution[] = [];

  @state()
  private failedFlowExecutions: FlowExecution[] = [];

  @state()
  private complianceMetrics?: ComplianceMetrics;

  @state()
  private pendingApprovals: ApprovalRequest[] = [];

  @state()
  private isLoading = true;

  @state()
  private hasFlows = false;

  @state()
  private hasIssues = false;

  async connectedCallback() {
    super.connectedCallback();
    this.fetchDashboardData();
  }

  async fetchDashboardData() {
    this.isLoading = true;
    try {
      // Fetch all dashboard data in parallel
      const [
        trackers,
        apiUsage,
        apiUsageStats,
        issueCount,
        mcpServers,
        tools,
        flows,
        flowExecutions,
        complianceMetrics,
        approvalRequests,
      ] = await Promise.all([
        api.getTrackers().catch(() => []),
        api.getApiUsageStats().catch(() => undefined),
        (
          this.fetchData('/api/v1/auth/api-usage?timeseries=true') as Promise<
            ApiUsageStat[]
          >
        ).catch(() => []),
        api.getIssueCount().catch(() => ({ total_issues: 0 })),
        this.fetchData('/api/v1/mcp-servers').catch(() => []),
        api.getTools().catch(() => []),
        api.getFlows().catch(() => []),
        api.getFlowExecutions().catch(() => []),
        this.fetchComplianceMetrics().catch(() => undefined),
        this.fetchData('/api/v1/approval-requests?status=pending').catch(
          () => []
        ),
      ]);

      this.trackers = trackers;
      this.apiUsage = apiUsage;
      this.apiUsageStats = apiUsageStats;
      this.totalIssues = issueCount.total_issues;
      this.mcpServers = mcpServers;
      this.tools = tools;

      // Check if flows exist
      this.hasFlows = (flows || []).length > 0;

      // Check if issues exist
      this.hasIssues = issueCount.total_issues > 0;

      // Sort flow executions by start time (most recent first)
      const sortedExecutions = (flowExecutions || []).sort(
        (a, b) =>
          new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
      );
      this.recentFlowExecutions = sortedExecutions.slice(0, 5);
      this.failedFlowExecutions = sortedExecutions.filter(
        (exec) => exec.status === 'FAILED'
      );

      this.complianceMetrics = complianceMetrics;
      this.pendingApprovals = approvalRequests || [];
    } catch (error) {
      console.error('Failed to fetch dashboard data', error);
    } finally {
      this.isLoading = false;
    }
  }

  async fetchComplianceMetrics(): Promise<ComplianceMetrics | undefined> {
    try {
      // Fetch a sample of issues to calculate compliance
      const response = await this.fetchData('/api/v1/issues?limit=100');
      if (!response || !response.results) return undefined;

      const issues = response.results;
      let compliantCount = 0;

      // Check each issue for basic compliance (has description, labels, etc.)
      for (const issue of issues) {
        const hasDescription =
          issue.description && issue.description.length > 20;
        const hasLabels = issue.labels && issue.labels.length > 0;
        if (hasDescription && hasLabels) {
          compliantCount++;
        }
      }

      return {
        total_issues: issues.length,
        compliant_issues: compliantCount,
        non_compliant_issues: issues.length - compliantCount,
        compliance_rate: issues.length > 0 ? compliantCount / issues.length : 0,
      };
    } catch (error) {
      console.error('Failed to fetch compliance metrics', error);
      return undefined;
    }
  }

  private getStatusColor(status: string): string {
    switch (status.toLowerCase()) {
      case 'active':
      case 'succeeded':
      case 'approved':
        return 'success';
      case 'failed':
      case 'error':
      case 'declined':
        return 'danger';
      case 'running':
      case 'pending':
        return 'warning';
      case 'inactive':
      case 'cancelled':
        return 'neutral';
      default:
        return 'neutral';
    }
  }

  private formatDate(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
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
      .server-list {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-small);
      }
      .server-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--sl-spacing-small);
        background: var(--sl-color-neutral-50);
        border-radius: var(--sl-border-radius-medium);
      }
      .server-info {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-2x-small);
      }
      .server-name {
        font-weight: 600;
      }
      .server-url {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
      }
      .tool-counts {
        display: flex;
        gap: var(--sl-spacing-small);
        margin-top: var(--sl-spacing-small);
      }
      .tool-count {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-2x-small);
        font-size: var(--sl-font-size-small);
      }
      .execution-list {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-small);
      }
      .execution-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--sl-spacing-small);
        background: var(--sl-color-neutral-50);
        border-radius: var(--sl-border-radius-medium);
        border-left: 3px solid var(--sl-color-neutral-300);
      }
      .execution-item.failed {
        border-left-color: var(--sl-color-danger-600);
        background: var(--sl-color-danger-50);
      }
      .execution-info {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-2x-small);
        flex: 1;
      }
      .execution-name {
        font-weight: 600;
      }
      .execution-error {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-danger-700);
        font-style: italic;
      }
      .execution-time {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
      }
      .compliance-progress {
        margin-top: var(--sl-spacing-medium);
      }
      .compliance-stats {
        display: flex;
        justify-content: space-between;
        margin-bottom: var(--sl-spacing-small);
        font-size: var(--sl-font-size-small);
      }
      .approval-list {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-small);
      }
      .approval-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--sl-spacing-small);
        background: var(--sl-color-warning-50);
        border-radius: var(--sl-border-radius-medium);
        border-left: 3px solid var(--sl-color-warning-600);
      }
      .approval-info {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-2x-small);
      }
      .approval-tool {
        font-weight: 600;
      }
      .empty-state {
        text-align: center;
        padding: var(--sl-spacing-large);
        color: var(--sl-color-neutral-600);
      }
      .empty-state sl-icon {
        font-size: 3rem;
        color: var(--sl-color-neutral-400);
        margin-bottom: var(--sl-spacing-small);
      }
      .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--sl-color-primary-600);
      }
      .stat-label {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
        text-transform: uppercase;
      }
      .quick-actions {
        display: flex;
        gap: var(--sl-spacing-small);
        margin-top: var(--sl-spacing-medium);
      }
    `,
  ];

  render() {
    if (this.isLoading) {
      return html`
        <view-header headerText="Overview"></view-header>
        <div
          style="display: flex; justify-content: center; align-items: center; height: 400px;"
        >
          <sl-spinner style="font-size: 3rem;"></sl-spinner>
        </div>
      `;
    }

    return html`
      <view-header headerText="Overview"></view-header>
      <div class="column-layout">
        <!-- Main Column -->
        <div class="main-column">
          <!-- MCP Server & Tools Status -->
          <sl-card>
            <div slot="header" class="chart-header">
              <sl-icon name="server"></sl-icon>
              MCP Server & Tools
              <sl-tooltip
                content="Built-in and external MCP tools for issue management and automation"
              >
                <sl-icon name="question-circle"></sl-icon>
              </sl-tooltip>
            </div>

            ${this.mcpServers.length === 0 && this.tools.length === 0
              ? html`
                  <div class="empty-state">
                    <sl-icon name="inbox"></sl-icon>
                    <p>
                      No MCP servers or tools configured yet.
                      <a href="/console/tools">Configure tools</a>
                    </p>
                  </div>
                `
              : html`
                  <!-- Built-in Tools Summary -->
                  <div class="tool-counts">
                    <div class="tool-count">
                      <sl-icon name="tools"></sl-icon>
                      <span
                        ><strong
                          >${this.tools.filter(
                            (t) => t.tool_source === 'builtin'
                          ).length}</strong
                        >
                        built-in tools</span
                      >
                    </div>
                    <div class="tool-count">
                      <sl-icon
                        name="check-circle"
                        style="color: var(--sl-color-success-600);"
                      ></sl-icon>
                      <span
                        ><strong
                          >${this.tools.filter((t) => t.enabled).length}</strong
                        >
                        enabled</span
                      >
                    </div>
                    <div class="tool-count">
                      <sl-icon
                        name="shield-check"
                        style="color: var(--sl-color-warning-600);"
                      ></sl-icon>
                      <span
                        ><strong
                          >${this.tools.filter((t) => t.requires_approval)
                            .length}</strong
                        >
                        require approval</span
                      >
                    </div>
                  </div>

                  <!-- External MCP Servers -->
                  ${this.mcpServers.length > 0
                    ? html`
                        <div style="margin-top: var(--sl-spacing-medium);">
                          <h4
                            style="margin: 0 0 var(--sl-spacing-small) 0; font-size: var(--sl-font-size-medium);"
                          >
                            External MCP Servers
                          </h4>
                          <div class="server-list">
                            ${this.mcpServers.map(
                              (server) => html`
                                <div class="server-item">
                                  <div class="server-info">
                                    <span class="server-name"
                                      >${server.name}</span
                                    >
                                    <span class="server-url"
                                      >${server.url}</span
                                    >
                                  </div>
                                  <sl-tag
                                    size="small"
                                    variant="${this.getStatusColor(
                                      server.status
                                    )}"
                                  >
                                    ${server.status}
                                  </sl-tag>
                                </div>
                              `
                            )}
                          </div>
                        </div>
                      `
                    : ''}

                  <div class="quick-actions">
                    <sl-button size="small" href="/console/tools">
                      <sl-icon slot="prefix" name="gear"></sl-icon>
                      Manage Tools
                    </sl-button>
                  </div>
                `}
          </sl-card>

          <!-- Flow Executions - Only show if flows exist -->
          ${this.hasFlows
            ? html`<sl-card>
                <div slot="header" class="chart-header">
                  <sl-icon name="diagram-3"></sl-icon>
                  Recent Flow Executions
                  ${this.failedFlowExecutions.length > 0
                    ? html`<sl-badge variant="danger" pulse
                        >${this.failedFlowExecutions.length} failed</sl-badge
                      >`
                    : ''}
                </div>

                ${this.recentFlowExecutions.length === 0
                  ? html`
                      <div class="empty-state">
                        <sl-icon name="inbox"></sl-icon>
                        <p>
                          No flow executions yet.
                          <a href="/console/flows">Create a flow</a>
                        </p>
                      </div>
                    `
                  : html`
                      <div class="execution-list">
                        ${this.recentFlowExecutions.slice(0, 5).map(
                          (exec) => html`
                            <div
                              class="execution-item ${exec.status === 'FAILED'
                                ? 'failed'
                                : ''}"
                            >
                              <div class="execution-info">
                                <span class="execution-name"
                                  >${exec.flow_name || 'Unnamed Flow'}</span
                                >
                                ${exec.error_message
                                  ? html`<span class="execution-error"
                                      >${exec.error_message}</span
                                    >`
                                  : ''}
                                <span class="execution-time"
                                  >${this.formatDate(exec.start_time)}</span
                                >
                              </div>
                              <div
                                style="display: flex; align-items: center; gap: var(--sl-spacing-small);"
                              >
                                <sl-tag
                                  size="small"
                                  variant="${this.getStatusColor(exec.status)}"
                                >
                                  ${exec.status}
                                </sl-tag>
                                <sl-button
                                  size="small"
                                  href="/console/flows/executions/${exec.id}"
                                >
                                  View
                                </sl-button>
                              </div>
                            </div>
                          `
                        )}
                      </div>

                      <div class="quick-actions">
                        <sl-button
                          size="small"
                          href="/console/flows/executions"
                        >
                          <sl-icon slot="prefix" name="list"></sl-icon>
                          View All Executions
                        </sl-button>
                        <sl-button size="small" href="/console/flows">
                          <sl-icon slot="prefix" name="plus-circle"></sl-icon>
                          Create Flow
                        </sl-button>
                      </div>
                    `}
              </sl-card>`
            : ''}

          <!-- Compliance Metrics - Only show if issues exist -->
          ${this.hasIssues && this.complianceMetrics
            ? html`
                <sl-card>
                  <div slot="header" class="chart-header">
                    <sl-icon name="clipboard-check"></sl-icon>
                    Compliance Overview
                    <sl-tooltip
                      content="Percentage of issues that meet compliance standards"
                    >
                      <sl-icon name="question-circle"></sl-icon>
                    </sl-tooltip>
                  </div>

                  <div class="compliance-progress">
                    <div class="compliance-stats">
                      <span
                        >${this.complianceMetrics.compliant_issues} /
                        ${this.complianceMetrics.total_issues} compliant</span
                      >
                      <span
                        >${Math.round(
                          this.complianceMetrics.compliance_rate * 100
                        )}%</span
                      >
                    </div>
                    <sl-progress-bar
                      value="${this.complianceMetrics.compliance_rate * 100}"
                      style="--height: 1rem;"
                    ></sl-progress-bar>

                    ${this.complianceMetrics.non_compliant_issues > 0
                      ? html`
                          <sl-alert
                            variant="warning"
                            open
                            style="margin-top: var(--sl-spacing-medium);"
                          >
                            <sl-icon
                              slot="icon"
                              name="exclamation-triangle"
                            ></sl-icon>
                            ${this.complianceMetrics.non_compliant_issues}
                            issue${this.complianceMetrics.non_compliant_issues >
                            1
                              ? 's'
                              : ''}
                            need attention
                          </sl-alert>
                        `
                      : ''}
                  </div>

                  <div class="quick-actions">
                    <sl-button size="small" href="/console/issues/compliance">
                      <sl-icon slot="prefix" name="search"></sl-icon>
                      View Compliance Details
                    </sl-button>
                  </div>
                </sl-card>
              `
            : ''}

          <!-- Similar Issues (existing widget) -->
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
        </div>

        <!-- Side Column -->
        <div class="side-column">
          <!-- Pending Approvals -->
          ${this.pendingApprovals.length > 0
            ? html`
                <sl-card>
                  <div slot="header" class="chart-header">
                    <sl-icon name="hand-thumbs-up"></sl-icon>
                    Pending Approvals
                    <sl-badge variant="warning" pill
                      >${this.pendingApprovals.length}</sl-badge
                    >
                  </div>

                  <div class="approval-list">
                    ${this.pendingApprovals.slice(0, 3).map(
                      (approval) => html`
                        <div class="approval-item">
                          <div class="approval-info">
                            <span class="approval-tool"
                              >${approval.tool_name}</span
                            >
                            <span class="execution-time"
                              >${this.formatDate(approval.requested_at)}</span
                            >
                          </div>
                          <sl-button
                            size="small"
                            href="/console/approval/${approval.id}"
                          >
                            Review
                          </sl-button>
                        </div>
                      `
                    )}
                  </div>

                  ${this.pendingApprovals.length > 3
                    ? html`<div style="margin-top: var(--sl-spacing-small);">
                        <a href="/console/tools"
                          >View all ${this.pendingApprovals.length}
                          approvals...</a
                        >
                      </div>`
                    : ''}
                </sl-card>
              `
            : ''}

          <!-- Key Metrics -->
          <sl-card>
            <div slot="header">Key Metrics</div>
            <ul class="summary-list">
              <li class="summary-item">
                <a href="/console/trackers">Connected Trackers</a>
                <div class="tracker-pills">
                  ${this.trackers.slice(0, 2).map(
                    (tracker) => html`
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
                            .map((t) => t.name)
                            .join(', ')}"
                        >
                          <sl-tag size="small" pill
                            >+${this.trackers.length - 2}</sl-tag
                          >
                        </sl-tooltip>
                      `
                    : ''}
                  ${this.trackers.length === 0 ? html`<strong>0</strong>` : ''}
                </div>
              </li>
              <li class="summary-item">
                <a href="/console/tools">Enabled Tools</a>
                <strong>${this.tools.filter((t) => t.enabled).length}</strong>
              </li>
              <li class="summary-item">
                <a href="/console/flows">Active Flows</a>
                <strong
                  >${this.recentFlowExecutions.filter((e) =>
                    ['RUNNING', 'PENDING'].includes(e.status)
                  ).length}</strong
                >
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

          <!-- Dependencies Overview - Only show if issues exist -->
          ${this.hasIssues
            ? html`
                <sl-card>
                  <div slot="header" class="chart-header">
                    <sl-icon name="diagram-2"></sl-icon>
                    Dependencies
                  </div>
                  <div
                    class="empty-state"
                    style="padding: var(--sl-spacing-medium);"
                  >
                    <p style="margin: 0;">
                      Track issue dependencies and blockers.
                      <a href="/console/issues/dependencies">View details</a>
                    </p>
                  </div>
                </sl-card>
              `
            : ''}
        </div>
      </div>
    `;
  }
}
