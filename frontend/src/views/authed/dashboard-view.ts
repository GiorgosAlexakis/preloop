import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
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
import { isSaaS } from '../../brand-config';
import { AuthedElement } from '../../api';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import { parseUTCDate } from '../../utils/date';
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
import type { Tool } from '../../components/tool-card';

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

  @state()
  private hasAIModels = false;

  @state()
  private welcomeCardDismissed = false;

  @state()
  private dismissedExecutions: Set<string> = new Set();

  @state()
  private approvalStats = {
    total: 0,
    approved: 0,
    declined: 0,
    expired: 0,
    avgApprovalTime: 0,
  };

  private unsubscribe?: () => void;

  async connectedCallback() {
    super.connectedCallback();
    this.loadDismissedState();
    this.fetchDashboardData();
    this.connectToFlowUpdates();
  }

  private loadDismissedState() {
    // Load dismissed welcome card state
    const dismissedWelcome = localStorage.getItem(
      'dashboard_welcome_dismissed'
    );
    this.welcomeCardDismissed = dismissedWelcome === 'true';

    // Load dismissed executions
    const dismissedExecs = localStorage.getItem(
      'dashboard_dismissed_executions'
    );
    if (dismissedExecs) {
      try {
        this.dismissedExecutions = new Set(JSON.parse(dismissedExecs));
      } catch (e) {
        this.dismissedExecutions = new Set();
      }
    }
  }

  private dismissWelcomeCard() {
    this.welcomeCardDismissed = true;
    localStorage.setItem('dashboard_welcome_dismissed', 'true');
  }

  private dismissExecution(executionId: string) {
    this.dismissedExecutions.add(executionId);
    localStorage.setItem(
      'dashboard_dismissed_executions',
      JSON.stringify(Array.from(this.dismissedExecutions))
    );
    this.requestUpdate();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.unsubscribe?.();
  }

  private connectToFlowUpdates() {
    // Connect to WebSocket for real-time flow execution updates and approval updates
    const handleMessage = (message: any) => {
      // Handle incoming WebSocket messages
      console.log('Dashboard received update:', message);

      // Handle approval-related messages
      if (message.type?.startsWith('approval_')) {
        this.handleApprovalMessage(message);
        return;
      }

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
    };

    // Subscribe to both flow_executions and approvals topics
    const unsubscribeFlow = unifiedWebSocketManager.subscribe(
      'flow_executions',
      handleMessage
    );
    const unsubscribeApprovals = unifiedWebSocketManager.subscribe(
      'approvals',
      handleMessage
    );

    // Combine both unsubscribe functions
    this.unsubscribe = () => {
      unsubscribeFlow();
      unsubscribeApprovals();
    };

    // Track connection state
    unifiedWebSocketManager.onStateChange((state) => {
      console.log(`Dashboard WebSocket state: ${state}`);
    });
  }

  private handleApprovalMessage(message: any) {
    console.log('Dashboard received approval update:', message);

    // Handle new approval request
    if (message.type === 'approval_created') {
      const newApproval: ApprovalRequest = {
        id: message.approval_request_id,
        tool_name: message.tool_name,
        tool_arguments: message.tool_args || {},
        status: message.status,
        requested_at: message.requested_at,
      };

      // Add to pending approvals if not already there
      const exists = this.pendingApprovals.some(
        (approval) => approval.id === newApproval.id
      );
      if (!exists) {
        this.pendingApprovals = [newApproval, ...this.pendingApprovals];
      }
    }

    // Handle approval resolution (approved, declined, expired, cancelled)
    if (
      message.type === 'approval_approved' ||
      message.type === 'approval_declined' ||
      message.type === 'approval_expired' ||
      message.type === 'approval_cancelled'
    ) {
      // Remove from pending approvals
      this.pendingApprovals = this.pendingApprovals.filter(
        (approval) => approval.id !== message.approval_request_id
      );
    }
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
        aiModels,
        allApprovalRequests,
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
        catchWith403Handling(
          isSaaS()
            ? api.getUsers()
            : Promise.resolve({
                users: [],
                total: 0,
                skip: 0,
                limit: 0,
              }),
          {
            users: [],
            total: 0,
            skip: 0,
            limit: 0,
          }
        ),
        catchWith403Handling(api.getAIModels(), []),
        catchWith403Handling(
          this.fetchData('/api/v1/approval-requests?limit=100'),
          []
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
      this.failedFlowExecutions = this.recentFlowExecutions.filter(
        (exec) => exec.status === 'FAILED'
      );

      this.complianceMetrics = complianceMetrics;
      this.pendingApprovals = approvalRequests || [];

      // Check if AI models exist
      this.hasAIModels = (aiModels || []).length > 0;

      // Calculate enabled users count
      this.enabledUsersCount = (users.users || []).filter(
        (user) => user.is_active
      ).length;

      // Calculate approval statistics
      this.calculateApprovalStats(allApprovalRequests || []);
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

  private calculateApprovalStats(requests: ApprovalRequest[]) {
    const total = requests.length;
    const approved = requests.filter((r) => r.status === 'approved').length;
    const declined = requests.filter((r) => r.status === 'declined').length;
    const expired = requests.filter((r) => r.status === 'expired').length;

    // Calculate average time to approval/decline (in minutes)
    let totalTime = 0;
    let count = 0;
    requests.forEach((r) => {
      if (
        (r.status === 'approved' || r.status === 'declined') &&
        (r as any).resolved_at
      ) {
        const requestTime = parseUTCDate(r.requested_at).getTime();
        const resolvedTime = parseUTCDate((r as any).resolved_at).getTime();
        totalTime += (resolvedTime - requestTime) / 60000; // Convert to minutes
        count++;
      }
    });

    this.approvalStats = {
      total,
      approved,
      declined,
      expired,
      avgApprovalTime: count > 0 ? Math.round(totalTime / count) : 0,
    };
  }

  private formatDate(dateString: string): string {
    const date = parseUTCDate(dateString);
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
      :host {
        --gradient-brand: linear-gradient(225deg, #d35400, #6c3483, #1f618d);
      }
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
        flex-wrap: wrap;
        gap: var(--sl-spacing-2x-large);
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
      }
      /* Welcome card styles */
      .welcome-card::part(base) {
        border-color: var(--sl-color-primary-200);
      }
      mcp-setup-dialog {
        display: contents;
      }
      .welcome-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: var(--sl-spacing-medium);
      }
      .welcome-title {
        font-size: var(--sl-font-size-large);
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
      }
      .welcome-title sl-icon {
        font-size: 1.5rem;
      }
      .welcome-content {
        color: var(--sl-color-neutral-700);
        line-height: 1.6;
        margin-bottom: var(--sl-spacing-large);
      }
      .getting-started-steps {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-medium);
        margin-top: var(--sl-spacing-large);
      }
      .step-item {
        display: flex;
        align-items: flex-start;
        gap: var(--sl-spacing-medium);
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-0);
        border-radius: var(--sl-border-radius-medium);
      }
      .step-item.completed {
        background: var(--sl-color-success-50);
        border-color: var(--sl-color-success-200);
      }
      .step-icon {
        flex-shrink: 0;
      }
      .step-icon sl-icon {
        font-size: 1.5rem;
      }
      .step-content {
        flex: 1;
      }
      .step-title {
        font-weight: 600;
        margin-bottom: var(--sl-spacing-2x-small);
        color: var(--sl-color-neutral-900);
      }
      .step-description {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
        margin-bottom: var(--sl-spacing-small);
      }
      .step-action {
        display: inline-block;
        margin-top: var(--sl-spacing-x-small);
      }
      .progress-overview {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        margin-top: var(--sl-spacing-large);
      }
      .progress-overview sl-progress-bar {
        flex: 1;
      }
      .progress-overview sl-progress-bar::part(base) {
        border: 1px solid rgba(230, 130, 50, 0.35);
      }
      .progress-overview sl-progress-bar::part(indicator) {
        background: var(--gradient-brand);
        position: relative;
        overflow: hidden;
      }
      .progress-overview sl-progress-bar::part(indicator)::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(
          90deg,
          transparent,
          rgba(255, 200, 100, 0.15),
          transparent
        );
        animation: shimmer 2.5s infinite;
      }
      @keyframes shimmer {
        0% {
          left: -100%;
        }
        100% {
          left: 100%;
        }
      }
      .progress-text {
        font-size: var(--sl-font-size-small);
        font-weight: 500;
      }
      /* Analytics card styles */
      .analytics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: var(--sl-spacing-large);
        margin-top: var(--sl-spacing-medium);
      }
      .analytics-stat {
        text-align: center;
      }
      .analytics-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--sl-color-primary-600);
        line-height: 1;
      }
      .analytics-label {
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-neutral-600);
        margin-top: var(--sl-spacing-small);
      }
      .analytics-subtext {
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-500);
        margin-top: var(--sl-spacing-2x-small);
      }
    `,
  ];

  private renderWelcomeCard() {
    if (this.welcomeCardDismissed) {
      return '';
    }

    const hasMCPServers = this.mcpServers.length > 0;
    const hasFlows = this.hasFlows;
    const hasTrackersAndModels = this.trackers.length > 0 && this.hasAIModels;

    const completedSteps = [
      hasMCPServers,
      hasFlows,
      hasTrackersAndModels,
    ].filter(Boolean).length;
    const totalSteps = 3;
    const progress = (completedSteps / totalSteps) * 100;

    return html`
      <sl-card class="welcome-card">
        <div class="welcome-header">
          <div class="welcome-title">
            <sl-icon name="rocket-takeoff"></sl-icon>
            Welcome to Preloop AI!
          </div>
          <sl-button
            size="small"
            variant="text"
            @click=${this.dismissWelcomeCard}
          >
            <sl-icon name="x-lg"></sl-icon>
          </sl-button>
        </div>

        <div class="welcome-content">
          Preloop AI helps you automate your workflow with AI-powered agents,
          intelligent issue management, and seamless tool integration. Here's
          how to get started:
        </div>

        <div class="getting-started-steps">
          <!-- Step 1: MCP Servers & Tools -->
          <div class="step-item ${hasMCPServers ? 'completed' : ''}">
            <div class="step-icon">
              ${hasMCPServers
                ? html`<sl-icon
                    name="check-circle-fill"
                    style="color: var(--sl-color-success-600);"
                  ></sl-icon>`
                : html`<sl-icon
                    name="1-circle"
                    style="color: var(--sl-color-primary-600);"
                  ></sl-icon>`}
            </div>
            <div class="step-content">
              <div class="step-title">
                Add MCP Servers & Configure Approvals
              </div>
              <div class="step-description">
                Set up Model Context Protocol servers to extend your
                capabilities with custom tools. Configure approval policies for
                tools that need human oversight.
              </div>
              ${!hasMCPServers
                ? html`<sl-button
                    size="small"
                    href="/console/tools"
                    class="step-action"
                  >
                    <sl-icon slot="prefix" name="tools"></sl-icon>
                    Configure Tools
                  </sl-button>`
                : html`<sl-badge variant="success">Completed</sl-badge>`}
            </div>
          </div>

          <!-- Step 2: Create Flows -->
          <div class="step-item ${hasFlows ? 'completed' : ''}">
            <div class="step-icon">
              ${hasFlows
                ? html`<sl-icon
                    name="check-circle-fill"
                    style="color: var(--sl-color-success-600);"
                  ></sl-icon>`
                : html`<sl-icon
                    name="2-circle"
                    style="color: var(--sl-color-primary-600);"
                  ></sl-icon>`}
            </div>
            <div class="step-content">
              <div class="step-title">Create Event-Driven Agentic Flows</div>
              <div class="step-description">
                Automate your most time-consuming tasks with AI agents that
                respond to events. Start with a preset or build from scratch.
              </div>
              ${!hasFlows
                ? html`<sl-button
                    size="small"
                    href="/console/flows"
                    class="step-action"
                  >
                    <sl-icon slot="prefix" name="diagram-3"></sl-icon>
                    Create Flow
                  </sl-button>`
                : html`<sl-badge variant="success">Completed</sl-badge>`}
            </div>
          </div>

          <!-- Step 3: Connect Trackers & AI Models -->
          <div class="step-item ${hasTrackersAndModels ? 'completed' : ''}">
            <div class="step-icon">
              ${hasTrackersAndModels
                ? html`<sl-icon
                    name="check-circle-fill"
                    style="color: var(--sl-color-success-600);"
                  ></sl-icon>`
                : html`<sl-icon
                    name="3-circle"
                    style="color: var(--sl-color-primary-600);"
                  ></sl-icon>`}
            </div>
            <div class="step-content">
              <div class="step-title">Connect Trackers & AI Models</div>
              <div class="step-description">
                Link your issue trackers (Jira, GitHub, GitLab) and AI models to
                power your flows, detect duplicate issues, and assess
                compliance.
              </div>
              ${!hasTrackersAndModels
                ? html`
                    <div style="display: flex; gap: var(--sl-spacing-small);">
                      ${!this.trackers.length
                        ? html`<sl-button
                            size="small"
                            href="/console/trackers"
                            class="step-action"
                          >
                            <sl-icon slot="prefix" name="link-45deg"></sl-icon>
                            Add Tracker
                          </sl-button>`
                        : ''}
                      ${!this.hasAIModels
                        ? html`<sl-button
                            size="small"
                            href="/console/settings/ai-models"
                            class="step-action"
                          >
                            <sl-icon slot="prefix" name="cpu"></sl-icon>
                            Add AI Model
                          </sl-button>`
                        : ''}
                    </div>
                  `
                : html`<sl-badge variant="success">Completed</sl-badge>`}
            </div>
          </div>
        </div>

        <div class="progress-overview">
          <sl-progress-bar value="${progress}"></sl-progress-bar>
          <span class="progress-text"
            >${completedSteps} / ${totalSteps} completed</span
          >
        </div>
      </sl-card>
    `;
  }

  render() {
    if (this.isLoading) {
      return html`
        <view-header headerText="Overview" width="extra-wide"></view-header>
        <div class="loading-container">
          <sl-spinner style="font-size: 3rem;"></sl-spinner>
        </div>
      `;
    }

    return html`
      <view-header headerText="Overview" width="extra-wide"></view-header>
      <div class="column-layout dashboard extra-wide">
        <!-- Main Column -->
        <div class="main-column">
          <!-- Welcome Card -->
          ${this.renderWelcomeCard()}

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
                        ${this.recentFlowExecutions
                          .filter(
                            (exec) => !this.dismissedExecutions.has(exec.id)
                          )
                          .slice(0, 5)
                          .map(
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
                                    variant="${this.getStatusColor(
                                      exec.status
                                    )}"
                                  >
                                    ${exec.status}
                                  </sl-tag>
                                  <sl-button
                                    size="small"
                                    href="/console/flows/executions/${exec.id}"
                                  >
                                    View
                                  </sl-button>
                                  <sl-icon-button
                                    name="x-lg"
                                    label="Dismiss"
                                    @click=${(e: Event) => {
                                      e.preventDefault();
                                      this.dismissExecution(exec.id);
                                    }}
                                  ></sl-icon-button>
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
                        <a href="/console/approvals"
                          >View all ${this.pendingApprovals.length}
                          approvals...</a
                        >
                      </div>`
                    : ''}
                </sl-card>
              `
            : ''}

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
                  >Setup</a
                >
                <a href="/console/tools" class="header-action-link">Manage</a>
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
                        ${this.tools.filter(
                          (t) => t.is_enabled && t.is_supported !== false
                        ).length}
                      </div>
                      <div class="tool-count-label">enabled</div>
                    </div>
                    <div class="tool-count">
                      <sl-icon
                        name="shield-check"
                        style="color: var(--sl-color-warning-600);"
                      ></sl-icon>
                      <div class="tool-count-value">
                        ${this.tools.filter(
                          (t) =>
                            (t.approval_policy_id != null ||
                              t.has_approval_condition === true) &&
                            t.is_supported !== false
                        ).length}
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
                    </div>
                    <a href="/console/settings/api-keys" class="capsule-link">
                      Manage Keys
                    </a>
                  </div>
                `}
          </sl-card>

          <!-- Approval Analytics -->
          ${this.approvalStats.total > 0
            ? html`
                <sl-card>
                  <div slot="header" class="chart-header">
                    <sl-icon name="bar-chart"></sl-icon>
                    Approval Analytics
                  </div>

                  <div class="analytics-grid">
                    <div class="analytics-stat">
                      <div class="analytics-value">
                        ${this.approvalStats.total}
                      </div>
                      <div class="analytics-label">Total Requests</div>
                    </div>
                    <div class="analytics-stat">
                      <div
                        class="analytics-value"
                        style="color: var(--sl-color-success-600);"
                      >
                        ${this.approvalStats.approved}
                      </div>
                      <div class="analytics-label">Approved</div>
                      <div class="analytics-subtext">
                        ${this.approvalStats.total > 0
                          ? Math.round(
                              (this.approvalStats.approved /
                                this.approvalStats.total) *
                                100
                            )
                          : 0}%
                        approval rate
                      </div>
                    </div>
                    <div class="analytics-stat">
                      <div
                        class="analytics-value"
                        style="color: var(--sl-color-danger-600);"
                      >
                        ${this.approvalStats.declined}
                      </div>
                      <div class="analytics-label">Declined</div>
                    </div>
                    ${this.approvalStats.expired > 0
                      ? html`
                          <div class="analytics-stat">
                            <div
                              class="analytics-value"
                              style="color: var(--sl-color-neutral-500);"
                            >
                              ${this.approvalStats.expired}
                            </div>
                            <div class="analytics-label">Timed Out</div>
                          </div>
                        `
                      : ''}
                    ${this.approvalStats.avgApprovalTime > 0
                      ? html`
                          <div class="analytics-stat">
                            <div class="analytics-value">
                              ${this.approvalStats.avgApprovalTime}
                            </div>
                            <div class="analytics-label">
                              Avg. Response Time
                            </div>
                            <div class="analytics-subtext">minutes</div>
                          </div>
                        `
                      : ''}
                  </div>

                  <div style="margin-top: var(--sl-spacing-medium);">
                    <a
                      href="/console/approvals"
                      style="font-size: var(--sl-font-size-small);"
                    >
                      View all approval requests →
                    </a>
                  </div>
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
              ${isSaaS()
                ? html`
                    <li class="summary-item">
                      <a href="/console/settings/users">Enabled Users</a>
                      <strong>${this.enabledUsersCount}</strong>
                    </li>
                  `
                : ''}
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
