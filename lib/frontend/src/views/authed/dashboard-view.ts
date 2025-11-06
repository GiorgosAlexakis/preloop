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
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import * as api from '../../api';
import { AuthedElement } from '../../api';
import { webSocketService } from '../../services/websocket-service';
import '../../components/similar-issues-widget.ts';
import '../../components/duplicate-stats-chart.ts';
import '../../components/tracker-pill.ts';
import '../../components/theme-switcher.ts';
import '../../components/mcp-setup-dialog.ts';
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
  name: string;
  source: string; // 'builtin' or 'mcp'
  is_enabled: boolean;
  requires_approval: boolean;
  source_id?: string;
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

  @state()
  private enabledUsersCount = 0;

  @state()
  private showSetupDialog = false;

  async connectedCallback() {
    super.connectedCallback();
    this.fetchDashboardData();
    this.connectToFlowUpdates();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    webSocketService.disconnectFromFlowUpdates();
  }

  private connectToFlowUpdates() {
    // Connect to WebSocket for real-time flow execution updates
    webSocketService.connectToFlowUpdates(
      (message) => {
        // Handle incoming WebSocket messages
        console.log('Dashboard received flow update:', message);

        // If this is an execution_started event, add it to recent executions
        if (message.type === 'execution_started') {
          const newExecution = {
            id: message.execution_id,
            flow_id: message.flow_id,
            status: message.payload.status || 'PENDING',
            start_time: message.timestamp,
            end_time: null,
            flow_name: message.payload.flow_name,
            error_message: null,
          };

          // Add to the beginning of recent executions and keep only top 5
          this.recentFlowExecutions = [
            newExecution,
            ...this.recentFlowExecutions,
          ].slice(0, 5);

          // Dispatch custom event for global notification
          window.dispatchEvent(
            new CustomEvent('flow-execution-update', {
              detail: { execution: newExecution, type: 'started' },
              bubbles: true,
              composed: true,
            })
          );
        }

        // If this is a status update, update the execution
        if (message.type === 'status_update' && message.execution_id) {
          const executionIndex = this.recentFlowExecutions.findIndex(
            (exec) => exec.id === message.execution_id
          );
          if (executionIndex !== -1) {
            const updatedExecution = {
              ...this.recentFlowExecutions[executionIndex],
              status: message.payload.status,
              end_time: message.payload.end_time || null,
            };
            this.recentFlowExecutions = [
              ...this.recentFlowExecutions.slice(0, executionIndex),
              updatedExecution,
              ...this.recentFlowExecutions.slice(executionIndex + 1),
            ];

            // Dispatch custom event for global notification
            window.dispatchEvent(
              new CustomEvent('flow-execution-update', {
                detail: { execution: updatedExecution, type: 'updated' },
                bubbles: true,
                composed: true,
              })
            );
          }
        }
      },
      () => {
        console.log('Dashboard WebSocket connected');
      },
      () => {
        console.log('Dashboard WebSocket disconnected');
      }
    );
  }

  async fetchDashboardData() {
    this.isLoading = true;
    try {
      // Helper to catch errors and log 403 (Forbidden) silently
      const catchWith403Handling = <T>(
        promise: Promise<T>,
        defaultValue: T
      ): Promise<T> => {
        return promise.catch((error) => {
          // Don't log 403 errors - they're expected when user lacks permission
          if (error?.message?.includes('403') || error?.status === 403) {
            return defaultValue;
          }
          console.error('Dashboard data fetch error:', error);
          return defaultValue;
        });
      };

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
        users,
      ] = await Promise.all([
        catchWith403Handling(api.getTrackers(), []),
        catchWith403Handling(api.getApiUsageStats(), undefined),
        catchWith403Handling(
          this.fetchData('/api/v1/auth/api-usage?timeseries=true') as Promise<
            ApiUsageStat[]
          >,
          []
        ),
        catchWith403Handling(api.getIssueCount(), { total_issues: 0 }),
        catchWith403Handling(this.fetchData('/api/v1/mcp-servers'), []),
        catchWith403Handling(api.getTools(), []),
        catchWith403Handling(api.getFlows(), []),
        catchWith403Handling(api.getFlowExecutions(), []),
        catchWith403Handling(this.fetchComplianceMetrics(), undefined),
        catchWith403Handling(
          this.fetchData('/api/v1/approval-requests?status=pending'),
          []
        ),
        catchWith403Handling(api.getUsers(), {
          users: [],
          total: 0,
          skip: 0,
          limit: 0,
        }),
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

      // Calculate enabled users count
      this.enabledUsersCount = (users.users || []).filter(
        (user) => user.is_active
      ).length;
    } catch (error) {
      console.error('Failed to fetch dashboard data', error);
    } finally {
      this.isLoading = false;
    }
  }

  async fetchComplianceMetrics(): Promise<ComplianceMetrics | undefined> {
    try {
      // Fetch a sample of issues using the search endpoint (same as issues-compliance-view.ts)
      const response = await this.fetchData(
        '/api/v1/search?search_type=similarity&embedding_type=issue&query=&sort=newest&limit=100&status=opened'
      );
      if (!response || !Array.isArray(response)) return undefined;

      const issues = response;
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
      /* Dashboard-specific styles only */
      sl-icon {
        font-size: 1rem;
      }
      .tracker-pills {
        display: flex;
        gap: var(--sl-spacing-2x-small);
        align-items: center;
        flex-wrap: wrap;
        justify-content: flex-end;
      }
      .tool-counts {
        display: flex;
        gap: var(--sl-spacing-large);
        margin-top: var(--sl-spacing-small);
        justify-content: center;
      }
      .tool-count {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--sl-spacing-small);
        font-size: var(--sl-font-size-small);
      }
      .tool-count sl-icon {
        font-size: 2.5rem;
      }
      .tool-count-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--sl-color-primary-600);
      }
      .tool-count-label {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
        text-align: center;
      }
      /* Compliance-specific styles */
      .compliance-progress {
        margin-top: var(--sl-spacing-medium);
      }
      .compliance-stats {
        display: flex;
        justify-content: space-between;
        margin-bottom: var(--sl-spacing-small);
        font-size: var(--sl-font-size-small);
      }
      /* Stat display styles */
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
      /* MCP Server Capsule */
      .mcp-server-capsule {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-medium);
        padding: var(--sl-spacing-small) var(--sl-spacing-medium);
        background: var(--sl-color-neutral-50);
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: 100px;
        margin-top: var(--sl-spacing-2x-large);
        margin-bottom: var(--sl-spacing-large);
        margin-left: auto;
        margin-right: auto;
        max-width: 600px;
        transition: all 0.2s ease;
      }
      .mcp-server-capsule:hover {
        background: var(--sl-color-neutral-100);
        border-color: var(--sl-color-neutral-300);
      }
      .status-indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--sl-color-success-600);
        box-shadow: 0 0 0 2px var(--sl-color-success-100);
        flex-shrink: 0;
      }
      .server-details {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        flex: 1;
        min-width: 0;
      }
      .server-endpoint {
        font-family: monospace;
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-900);
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .server-auth {
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-600);
        padding: 0.125rem 0.5rem;
        background: var(--sl-color-neutral-0);
        border-radius: 12px;
        white-space: nowrap;
        flex-shrink: 0;
      }
      .capsule-link {
        color: var(--sl-color-primary-600);
        text-decoration: none;
        font-size: var(--sl-font-size-small);
        font-weight: 500;
        white-space: nowrap;
        flex-shrink: 0;
      }
      .capsule-link:hover {
        text-decoration: underline;
      }
      @media (min-width: 1024px) {
        .overview-layout {
          grid-template-columns: 1fr;
        }
        .tool-counts {
          gap: 5rem;
        }
      }
      @media (min-width: 1200px) {
        .tool-counts {
          gap: 9rem;
        }
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
            <div slot="header" class="card-header-with-action">
              <div class="chart-header">
                <img
                  src="/images/mcp.png"
                  alt="MCP"
                  style="width: 20px; height: 20px;"
                />
                MCP Server
                <sl-tooltip
                  content="Built-in and external MCP tools for issue management and automation"
                >
                  <sl-icon name="question-circle"></sl-icon>
                </sl-tooltip>
              </div>
              <div
                style="display: flex; gap: var(--sl-spacing-small); align-items: center;"
              >
                <a
                  href="#"
                  class="header-action-link"
                  @click=${(e: Event) => {
                    e.preventDefault();
                    this.showSetupDialog = true;
                  }}
                  >Setup Instructions</a
                >
                <a href="/console/tools" class="header-action-link"
                  >Manage Tools</a
                >
              </div>
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
                      <div class="tool-count-value">
                        ${this.tools.filter((t) => t.source === 'builtin')
                          .length}
                      </div>
                      <div class="tool-count-label">built-in tools</div>
                    </div>
                    <div class="tool-count">
                      <sl-icon
                        name="check-circle"
                        style="color: var(--sl-color-success-600);"
                      ></sl-icon>
                      <div class="tool-count-value">
                        ${this.tools.filter((t) => t.is_enabled).length}
                      </div>
                      <div class="tool-count-label">enabled</div>
                    </div>
                    <div class="tool-count">
                      <sl-icon
                        name="shield-check"
                        style="color: var(--sl-color-warning-600);"
                      ></sl-icon>
                      <div class="tool-count-value">
                        ${this.tools.filter((t) => t.requires_approval).length}
                      </div>
                      <div class="tool-count-label">require approval</div>
                    </div>
                  </div>

                  <!-- Built-in MCP Server -->
                  <div class="mcp-server-capsule">
                    <div class="status-indicator"></div>
                    <div class="server-details">
                      <span class="server-endpoint"
                        >${window.location.origin}/mcp/v1</span
                      >
                      <span class="server-auth">Bearer Token</span>
                    </div>
                    <a href="/console/settings/api-keys" class="capsule-link">
                      Manage Keys
                    </a>
                  </div>
                `}
          </sl-card>

          <!-- Setup Instructions Dialog -->
          <mcp-setup-dialog
            ?open=${this.showSetupDialog}
            @close=${() => (this.showSetupDialog = false)}
          ></mcp-setup-dialog>

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
                      <div class="item-list">
                        ${this.recentFlowExecutions.slice(0, 5).map(
                          (exec) => html`
                            <div
                              class="item-card ${exec.status === 'FAILED'
                                ? 'danger'
                                : ''}"
                            >
                              <div class="item-info">
                                <span class="item-name"
                                  >${exec.flow_name || 'Unnamed Flow'}</span
                                >
                                ${exec.error_message
                                  ? html`<span class="item-error"
                                      >${exec.error_message}</span
                                    >`
                                  : ''}
                                <span class="item-secondary"
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

                  <div class="item-list">
                    ${this.pendingApprovals.slice(0, 3).map(
                      (approval) => html`
                        <div class="item-card warning">
                          <div class="item-info">
                            <span class="item-name">${approval.tool_name}</span>
                            <span class="item-secondary"
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
                <strong
                  >${this.tools.filter((t) => t.is_enabled).length}</strong
                >
              </li>
              <li class="summary-item">
                <a href="/console/settings/users">Enabled Users</a>
                <strong>${this.enabledUsersCount}</strong>
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
              ${this.trackers.length > 0
                ? html`<li class="summary-item">
                    <span>Total Issues Processed</span>
                    <strong>${this.totalIssues}</strong>
                  </li>`
                : ''}
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
