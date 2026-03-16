var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { css, html, nothing, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/progress-bar/progress-bar.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '../../components/mcp-setup-dialog.ts';
import '../../components/view-header.ts';
import { AuthedElement, fetchWithAuth, getAIModels, getAccountAgents, getAccountGatewayUsageSearch, getAccountGatewayUsageSummary, getAccountRuntimeSessions, getApiUsageStats, getFlowExecutions, getFlows, getIssueCount, getMCPServers, getTools, getTrackers, getUsers, } from '../../api';
import { isSaaS } from '../../brand-config';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import { parseUTCDate } from '../../utils/date';
import consoleStyles from '../../styles/console-styles.css?inline';
let DashboardView = class DashboardView extends AuthedElement {
    constructor() {
        super(...arguments);
        this.loading = true;
        this.error = null;
        this.gatewaySummary = null;
        this.runtimeSessions = [];
        this.managedAgents = [];
        this.gatewayInteractions = [];
        this.auditGroups = [];
        this.trackers = [];
        this.apiUsage = null;
        this.totalIssues = 0;
        this.mcpServers = [];
        this.tools = [];
        this.recentFlowExecutions = [];
        this.pendingApprovals = [];
        this.lastUpdatedAt = null;
        this.hasFlows = false;
        this.hasAIModels = false;
        this.enabledUsersCount = 0;
        this.showSetupDialog = false;
        this.welcomeCardDismissed = false;
        this.approvalStats = {
            total: 0,
            approved: 0,
            declined: 0,
            expired: 0,
            avgApprovalTime: 0,
        };
        this.refreshTimer = null;
        this.refreshInFlight = false;
    }
    connectedCallback() {
        super.connectedCallback();
        this.loadDismissedState();
        void this.fetchDashboardData();
        this.connectRealtime();
    }
    disconnectedCallback() {
        super.disconnectedCallback();
        this.unsubscribeRealtime?.();
        if (this.refreshTimer !== null) {
            window.clearTimeout(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
    loadDismissedState() {
        this.welcomeCardDismissed =
            localStorage.getItem('dashboard_welcome_dismissed') === 'true';
    }
    dismissWelcomeCard() {
        this.welcomeCardDismissed = true;
        localStorage.setItem('dashboard_welcome_dismissed', 'true');
    }
    connectRealtime() {
        const scheduleRefresh = () => this.scheduleRefresh();
        const unsubscribers = [
            unifiedWebSocketManager.subscribe('runtime_sessions', scheduleRefresh),
            unifiedWebSocketManager.subscribe('managed_agents', scheduleRefresh),
            unifiedWebSocketManager.subscribe('gateway_activity', scheduleRefresh),
            unifiedWebSocketManager.subscribe('budget_health', scheduleRefresh),
            unifiedWebSocketManager.subscribe('audit', scheduleRefresh),
            unifiedWebSocketManager.subscribe('approvals', scheduleRefresh),
            unifiedWebSocketManager.subscribe('flow_executions', scheduleRefresh),
            unifiedWebSocketManager.subscribe('system', scheduleRefresh, (message) => message?.type === 'authenticated'),
        ];
        this.unsubscribeRealtime = () => {
            for (const unsubscribe of unsubscribers) {
                unsubscribe();
            }
        };
        void unifiedWebSocketManager.connect();
    }
    scheduleRefresh() {
        if (this.refreshTimer !== null) {
            window.clearTimeout(this.refreshTimer);
        }
        this.refreshTimer = window.setTimeout(() => {
            this.refreshTimer = null;
            void this.fetchDashboardData({ preserveLoadingState: true });
        }, 250);
    }
    async fetchDashboardData(options = {}) {
        if (this.refreshInFlight) {
            return;
        }
        this.refreshInFlight = true;
        if (!options.preserveLoadingState) {
            this.loading = true;
        }
        this.error = null;
        const catchWith403Handling = async (promise, defaultValue) => {
            try {
                return await promise;
            }
            catch (error) {
                const message = error instanceof Error ? error.message : String(error);
                if (message.includes('403')) {
                    return defaultValue;
                }
                console.error('Dashboard data fetch error:', error);
                return defaultValue;
            }
        };
        try {
            const [gatewaySummary, runtimeSessions, managedAgents, gatewayInteractions, audit, trackers, apiUsage, issueCount, mcpServers, tools, flows, flowExecutions, pendingApprovals, allApprovalRequests, aiModels, users,] = await Promise.all([
                catchWith403Handling(getAccountGatewayUsageSummary(), null),
                catchWith403Handling(getAccountRuntimeSessions({ status: 'all', limit: 12 }), {
                    items: [],
                }),
                catchWith403Handling(getAccountAgents({ status: 'all', limit: 12 }), {
                    items: [],
                }),
                catchWith403Handling(getAccountGatewayUsageSearch({ limit: 12 }), {
                    items: [],
                }),
                catchWith403Handling(this.fetchAuditExceptions(), {
                    groups: [],
                    total: 0,
                }),
                catchWith403Handling(getTrackers(), []),
                catchWith403Handling(getApiUsageStats(), null),
                catchWith403Handling(getIssueCount(), { total_issues: 0 }),
                catchWith403Handling(getMCPServers(), []),
                catchWith403Handling(getTools(), []),
                catchWith403Handling(getFlows(), []),
                catchWith403Handling(getFlowExecutions({ limit: 5 }), []),
                catchWith403Handling(this.fetchApprovalRequests('pending', 3), []),
                catchWith403Handling(this.fetchApprovalRequests(undefined, 100), []),
                catchWith403Handling(getAIModels(), []),
                catchWith403Handling(isSaaS()
                    ? getUsers()
                    : Promise.resolve({
                        users: [],
                        total: 0,
                        skip: 0,
                        limit: 0,
                    }), {
                    users: [],
                    total: 0,
                    skip: 0,
                    limit: 0,
                }),
            ]);
            this.gatewaySummary = gatewaySummary;
            this.runtimeSessions = runtimeSessions.items || [];
            this.managedAgents = managedAgents.items || [];
            this.gatewayInteractions = gatewayInteractions.items || [];
            this.auditGroups = audit.groups || [];
            this.trackers = trackers;
            this.apiUsage = apiUsage;
            this.totalIssues = issueCount.total_issues;
            this.mcpServers = mcpServers;
            this.tools = tools;
            this.hasFlows = (flows || []).length > 0;
            this.recentFlowExecutions = [...(flowExecutions || [])]
                .sort((left, right) => new Date(right.start_time).getTime() -
                new Date(left.start_time).getTime())
                .slice(0, 5);
            this.pendingApprovals = pendingApprovals;
            this.hasAIModels = (aiModels || []).length > 0;
            this.enabledUsersCount = (users.users || []).filter((user) => user.is_active).length;
            this.calculateApprovalStats(allApprovalRequests);
            this.lastUpdatedAt = new Date().toISOString();
        }
        catch (error) {
            console.error('Failed to load overview dashboard', error);
            this.error = 'Failed to load the overview dashboard.';
        }
        finally {
            this.loading = false;
            this.refreshInFlight = false;
        }
    }
    async fetchAuditExceptions() {
        const params = new URLSearchParams();
        params.set('limit', '12');
        params.append('outcome', 'failed');
        params.append('outcome', 'budget_denied');
        const response = await fetchWithAuth(`/api/v1/audit-logs/grouped?${params}`);
        if (!response.ok) {
            throw new Error('Failed to fetch audit exceptions');
        }
        return response.json();
    }
    async fetchApprovalRequests(status, limit = 100) {
        const params = new URLSearchParams();
        params.set('limit', String(limit));
        if (status) {
            params.set('status', status);
        }
        const response = await fetchWithAuth(`/api/v1/approval-requests?${params.toString()}`);
        if (!response.ok) {
            throw new Error('Failed to fetch approval requests');
        }
        return response.json();
    }
    calculateApprovalStats(requests) {
        const total = requests.length;
        const approved = requests.filter((request) => request.status === 'approved').length;
        const declined = requests.filter((request) => request.status === 'declined').length;
        const expired = requests.filter((request) => request.status === 'expired').length;
        let totalTimeMinutes = 0;
        let resolvedCount = 0;
        for (const request of requests) {
            if ((request.status === 'approved' || request.status === 'declined') &&
                request.resolved_at) {
                totalTimeMinutes +=
                    (parseUTCDate(request.resolved_at).getTime() -
                        parseUTCDate(request.requested_at).getTime()) /
                        60000;
                resolvedCount += 1;
            }
        }
        this.approvalStats = {
            total,
            approved,
            declined,
            expired,
            avgApprovalTime: resolvedCount > 0 ? Math.round(totalTimeMinutes / resolvedCount) : 0,
        };
    }
    get activeAgents() {
        return [...this.managedAgents]
            .filter((agent) => agent.activity_status === 'active_now')
            .sort((left, right) => new Date(right.last_seen_at).getTime() -
            new Date(left.last_seen_at).getTime());
    }
    get activeSessions() {
        return [...this.runtimeSessions]
            .filter((session) => session.activity_status === 'active_now')
            .sort((left, right) => {
            const leftTs = left.last_activity_at || left.started_at;
            const rightTs = right.last_activity_at || right.started_at;
            return new Date(rightTs).getTime() - new Date(leftTs).getTime();
        });
    }
    get gatewayFailures() {
        return this.gatewayInteractions.filter((item) => item.outcome !== 'success');
    }
    get failedFlowExecutions() {
        return this.recentFlowExecutions.filter((execution) => execution.status === 'FAILED');
    }
    get hasBudgetCard() {
        const budget = this.gatewaySummary?.budget;
        return Boolean(this.gatewaySummary?.total_requests ||
            budget?.monthly_limit_usd ||
            budget?.soft_limit_usd);
    }
    formatCurrency(value) {
        return `$${(value || 0).toFixed(2)}`;
    }
    formatNumber(value) {
        return Intl.NumberFormat().format(value || 0);
    }
    formatDateTime(value) {
        if (!value) {
            return 'Never';
        }
        return parseUTCDate(value).toLocaleString();
    }
    formatRelativeTime(value) {
        if (!value) {
            return 'Never';
        }
        const timestamp = parseUTCDate(value).getTime();
        const deltaMinutes = Math.round((Date.now() - timestamp) / 60000);
        if (deltaMinutes < 1) {
            return 'just now';
        }
        if (deltaMinutes < 60) {
            return `${deltaMinutes}m ago`;
        }
        const deltaHours = Math.round(deltaMinutes / 60);
        if (deltaHours < 24) {
            return `${deltaHours}h ago`;
        }
        return `${Math.round(deltaHours / 24)}d ago`;
    }
    getStatusColor(status) {
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
            default:
                return 'neutral';
        }
    }
    budgetVariant() {
        const budget = this.gatewaySummary?.budget;
        if (!budget) {
            return 'neutral';
        }
        if (budget.hard_limit_exceeded) {
            return 'danger';
        }
        if (budget.soft_limit_exceeded) {
            return 'warning';
        }
        return 'success';
    }
    budgetPercent() {
        const budget = this.gatewaySummary?.budget;
        const limit = budget?.monthly_limit_usd || budget?.soft_limit_usd || 0;
        if (!limit) {
            return 0;
        }
        return Math.min(100, Math.round(((budget?.current_spend_usd || 0) / limit) * 100));
    }
    renderEmptyState(message) {
        return html `<div class="empty-state">${message}</div>`;
    }
    renderWelcomeCard() {
        if (this.welcomeCardDismissed) {
            return nothing;
        }
        const hasMcp = this.mcpServers.length > 0 || this.tools.length > 0;
        const hasTrackersAndModels = this.trackers.length > 0 && this.hasAIModels;
        const completedSteps = [hasMcp, this.hasFlows, hasTrackersAndModels].filter(Boolean).length;
        const totalSteps = 3;
        return html `
      <sl-card class="welcome-card">
        <div class="welcome-header">
          <div class="welcome-title">
            <sl-icon name="rocket-takeoff"></sl-icon>
            Welcome to Preloop
          </div>
          <sl-button
            size="small"
            variant="text"
            @click=${this.dismissWelcomeCard}
          >
            <sl-icon slot="prefix" name="x-lg"></sl-icon>
            Dismiss
          </sl-button>
        </div>
        <div class="welcome-content">
          Build out your automation workspace first, then use the AI
          control-plane cards below to monitor active agents, runtime sessions,
          model spend, and failures.
        </div>
        <div class="getting-started-steps">
          <div class="step-item">
            <div class="step-icon">
              <sl-icon
                name=${hasMcp ? 'check-circle-fill' : '1-circle'}
              ></sl-icon>
            </div>
            <div class="step-content">
              <div class="step-title">
                Add MCP servers and approval controls
              </div>
              <div class="step-description">
                Configure tools, approval workflows, and the built-in MCP
                endpoint.
              </div>
              <div class="step-actions">
                <sl-button size="small" href="/console/tools">
                  ${hasMcp ? 'Tools configured' : 'Configure tools'}
                </sl-button>
                <sl-button
                  size="small"
                  variant="default"
                  @click=${() => (this.showSetupDialog = true)}
                >
                  Setup MCP
                </sl-button>
              </div>
            </div>
          </div>
          <div class="step-item">
            <div class="step-icon">
              <sl-icon
                name=${this.hasFlows ? 'check-circle-fill' : '2-circle'}
              ></sl-icon>
            </div>
            <div class="step-content">
              <div class="step-title">Create and trigger flows</div>
              <div class="step-description">
                Launch event-driven or manual agentic flows to generate runtime
                and gateway activity.
              </div>
              <div class="step-actions">
                <sl-button size="small" href="/console/flows/new">
                  ${this.hasFlows ? 'Create another flow' : 'Create flow'}
                </sl-button>
                <sl-button size="small" variant="default" href="/console/flows">
                  View flows
                </sl-button>
              </div>
            </div>
          </div>
          <div class="step-item">
            <div class="step-icon">
              <sl-icon
                name=${hasTrackersAndModels ? 'check-circle-fill' : '3-circle'}
              ></sl-icon>
            </div>
            <div class="step-content">
              <div class="step-title">Connect trackers and AI models</div>
              <div class="step-description">
                Add tracker integrations and AI model credentials so flows and
                agents can operate end-to-end.
              </div>
              <div class="step-actions">
                <sl-button size="small" href="/console/trackers?action=add">
                  ${this.trackers.length > 0
            ? 'Manage trackers'
            : 'Add tracker'}
                </sl-button>
                <sl-button
                  size="small"
                  variant="default"
                  href="/console/settings/ai-models"
                >
                  ${this.hasAIModels ? 'Manage AI models' : 'Add AI model'}
                </sl-button>
              </div>
            </div>
          </div>
        </div>
        <div class="progress-overview">
          <sl-progress-bar value=${(completedSteps / totalSteps) * 100}>
          </sl-progress-bar>
          <div class="metric-subtext">
            ${completedSteps} / ${totalSteps} onboarding steps completed
          </div>
        </div>
      </sl-card>
    `;
    }
    renderRecentFlowExecutionsCard() {
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Recent flow executions</div>
          <div class="mcp-actions">
            ${this.failedFlowExecutions.length > 0
            ? html `
                  <sl-badge variant="danger">
                    ${this.failedFlowExecutions.length} failed
                  </sl-badge>
                `
            : nothing}
            <a class="header-link" href="/console/flows/executions">View all</a>
          </div>
        </div>
        <div class="list">
          ${this.recentFlowExecutions.length === 0
            ? this.renderEmptyState(this.hasFlows
                ? 'No executions have run yet.'
                : 'No flows yet. Create your first flow to start seeing executions.')
            : repeat(this.recentFlowExecutions, (execution) => execution.id, (execution) => html `
                  <div class="row">
                    <div class="row-main">
                      <a
                        class="row-link row-primary"
                        href=${`/console/flows/executions/${execution.id}`}
                      >
                        ${execution.flow_name || 'Unnamed flow'}
                      </a>
                      <sl-badge
                        variant=${this.getStatusColor(execution.status)}
                      >
                        ${execution.status}
                      </sl-badge>
                    </div>
                    <div class="row-meta">
                      <span>
                        ${execution.error_message || execution.flow_id}
                      </span>
                      <span
                        >${this.formatRelativeTime(execution.start_time)}</span
                      >
                    </div>
                  </div>
                `)}
        </div>
      </sl-card>
    `;
    }
    renderBudgetHealthCard() {
        if (!this.hasBudgetCard) {
            return nothing;
        }
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Budget health</div>
          <sl-badge variant=${this.budgetVariant()}>
            ${this.gatewaySummary?.budget.hard_limit_exceeded
            ? 'Hard limit exceeded'
            : this.gatewaySummary?.budget.soft_limit_exceeded
                ? 'Soft limit exceeded'
                : 'Healthy'}
          </sl-badge>
        </div>
        <div class="budget-meter">
          <div class="budget-stat">
            <span>Current spend</span>
            <strong>
              ${this.formatCurrency(this.gatewaySummary?.budget.current_spend_usd)}
            </strong>
          </div>
          <div class="budget-stat">
            <span>Monthly limit</span>
            <strong>
              ${this.gatewaySummary?.budget.monthly_limit_usd
            ? this.formatCurrency(this.gatewaySummary?.budget.monthly_limit_usd)
            : 'Not set'}
            </strong>
          </div>
          <div class="budget-stat">
            <span>Soft limit</span>
            <strong>
              ${this.gatewaySummary?.budget.soft_limit_usd
            ? this.formatCurrency(this.gatewaySummary?.budget.soft_limit_usd)
            : 'Not set'}
            </strong>
          </div>
          <div class="budget-stat">
            <span>Pressure</span>
            <strong>${this.budgetPercent()}%</strong>
          </div>
        </div>
        <div class="footer-link">
          <a class="row-link" href="/console/settings/ai-models">
            Open model controls
          </a>
        </div>
      </sl-card>
    `;
    }
    renderGatewayFailuresCard() {
        if (this.gatewayFailures.length === 0) {
            return nothing;
        }
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Gateway failures needing attention</div>
          <a class="row-link" href="/console/api-usage"
            >Open gateway activity</a
          >
        </div>
        <div class="list">
          ${repeat(this.gatewayFailures.slice(0, 6), (item) => item.api_usage_id, (item) => html `
              <div class="row">
                <div class="row-main">
                  <a
                    class="row-link row-primary"
                    href=${item.runtime_session_id
            ? `/console/runtime-sessions?sessionId=${item.runtime_session_id}`
            : '/console/api-usage'}
                  >
                    ${item.model_alias || item.provider_name || item.endpoint}
                  </a>
                  <sl-badge variant="danger">${item.status_code}</sl-badge>
                </div>
                <div class="row-meta">
                  <span>
                    ${item.runtime_principal_name ||
            item.session_reference ||
            item.endpoint}
                  </span>
                  <span>${this.formatRelativeTime(item.timestamp)}</span>
                </div>
              </div>
            `)}
        </div>
      </sl-card>
    `;
    }
    renderAuditExceptionsCard() {
        if (this.auditGroups.length === 0) {
            return nothing;
        }
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Audit exceptions</div>
          <a class="row-link" href="/console/audit">Open audit timeline</a>
        </div>
        <div class="list">
          ${repeat(this.auditGroups.slice(0, 6), (group) => group.primary_event.id, (group) => html `
              <div class="row">
                <div class="row-main">
                  <span class="row-primary">
                    ${group.primary_event.action.replaceAll('_', ' ')}
                  </span>
                  <sl-badge
                    variant=${group.outcome === 'budget_denied'
            ? 'warning'
            : 'danger'}
                  >
                    ${group.outcome}
                  </sl-badge>
                </div>
                <div class="row-meta">
                  <span>
                    ${group.primary_event.details?.requested_model ||
            group.primary_event.details?.tool_name ||
            group.primary_event.id}
                  </span>
                  <span>
                    ${this.formatRelativeTime(group.primary_event.timestamp)}
                  </span>
                </div>
              </div>
            `)}
        </div>
      </sl-card>
    `;
    }
    renderTopModelsCard() {
        const items = this.gatewaySummary?.usage_by_model || [];
        if (items.length === 0) {
            return nothing;
        }
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Top models</div>
          <a class="row-link" href="/console/settings/ai-models">Model fleet</a>
        </div>
        <div class="list">
          ${repeat(items.slice(0, 6), (item) => `${item.ai_model_id}-${item.model_alias}-${item.provider_name}`, (item) => html `
              <div class="row">
                <div class="row-main">
                  ${item.ai_model_id
            ? html `
                        <a
                          class="row-link row-primary"
                          href=${`/console/settings/ai-models/${item.ai_model_id}`}
                        >
                          ${item.model_alias || 'Unknown model'}
                        </a>
                      `
            : html `
                        <span class="row-primary">
                          ${item.model_alias || 'Unknown model'}
                        </span>
                      `}
                  <span class="row-value">
                    ${this.formatCurrency(item.estimated_cost)}
                  </span>
                </div>
                <div class="row-meta">
                  <span>${item.provider_name || 'provider unknown'}</span>
                  <span>${this.formatNumber(item.request_count)} requests</span>
                </div>
              </div>
            `)}
        </div>
      </sl-card>
    `;
    }
    renderSessionsAttentionCard() {
        const items = this.gatewaySummary?.usage_by_session || [];
        if (items.length === 0) {
            return nothing;
        }
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Sessions needing attention</div>
          <a class="row-link" href="/console/runtime-sessions">Investigate</a>
        </div>
        <div class="list">
          ${repeat(items.slice(0, 6), (item) => item.runtime_session_id ||
            `${item.session_source_type}-${item.session_source_id}-${item.model_alias}`, (item) => html `
              <div class="row">
                <div class="row-main">
                  <a
                    class="row-link row-primary"
                    href=${item.runtime_session_id
            ? `/console/runtime-sessions?sessionId=${item.runtime_session_id}`
            : '/console/runtime-sessions'}
                  >
                    ${item.session_reference ||
            item.session_source_id ||
            item.runtime_session_id ||
            'Session'}
                  </a>
                  <span class="row-value">
                    ${this.formatCurrency(item.estimated_cost)}
                  </span>
                </div>
                <div class="row-meta">
                  <span>
                    ${item.model_alias || item.provider_name || 'model unknown'}
                  </span>
                  <span>${this.formatDateTime(item.last_request_at)}</span>
                </div>
              </div>
            `)}
        </div>
      </sl-card>
    `;
    }
    renderActiveAgentsCard() {
        if (this.managedAgents.length === 0) {
            return nothing;
        }
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Active agents</div>
          <a class="row-link" href="/console/agents">View all</a>
        </div>
        <div class="list">
          ${this.activeAgents.length === 0
            ? this.renderEmptyState('No active agents right now.')
            : repeat(this.activeAgents.slice(0, 6), (agent) => agent.id, (agent) => html `
                  <div class="row">
                    <div class="row-main">
                      <a
                        class="row-link row-primary"
                        href=${`/console/agents/${agent.id}`}
                      >
                        ${agent.display_name}
                      </a>
                      <span class="row-value">
                        ${this.formatCurrency(agent.estimated_cost)}
                      </span>
                    </div>
                    <div class="row-meta">
                      <span>
                        ${agent.session_source_type} ·
                        ${agent.session_source_id}
                      </span>
                      <span
                        >${this.formatRelativeTime(agent.last_seen_at)}</span
                      >
                    </div>
                  </div>
                `)}
        </div>
      </sl-card>
    `;
    }
    renderActiveSessionsCard() {
        if (this.runtimeSessions.length === 0) {
            return nothing;
        }
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Active runtime sessions</div>
          <a class="row-link" href="/console/runtime-sessions">View all</a>
        </div>
        <div class="list">
          ${this.activeSessions.length === 0
            ? this.renderEmptyState('No active runtime sessions right now.')
            : repeat(this.activeSessions.slice(0, 6), (session) => session.id, (session) => html `
                  <div class="row">
                    <div class="row-main">
                      <a
                        class="row-link row-primary"
                        href=${`/console/runtime-sessions?sessionId=${session.id}`}
                      >
                        ${session.runtime_principal_name ||
                session.session_reference ||
                session.id}
                      </a>
                      <span class="row-value">
                        ${this.formatNumber(session.total_requests)} req
                      </span>
                    </div>
                    <div class="row-meta">
                      <span>
                        ${session.session_source_type} ·
                        ${session.session_source_id}
                      </span>
                      <span>
                        ${this.formatRelativeTime(session.last_activity_at || session.started_at)}
                      </span>
                    </div>
                  </div>
                `)}
        </div>
      </sl-card>
    `;
    }
    renderPendingApprovalsCard() {
        if (this.pendingApprovals.length === 0) {
            return nothing;
        }
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Pending approvals</div>
          <sl-badge variant="warning">${this.pendingApprovals.length}</sl-badge>
        </div>
        <div class="list">
          ${repeat(this.pendingApprovals, (approval) => approval.id, (approval) => html `
              <div class="row">
                <div class="row-main">
                  <span class="row-primary">${approval.tool_name}</span>
                  <sl-button
                    size="small"
                    href=${`/console/approval/${approval.id}`}
                  >
                    Review
                  </sl-button>
                </div>
                <div class="row-meta">
                  <span>${approval.status}</span>
                  <span>${this.formatRelativeTime(approval.requested_at)}</span>
                </div>
              </div>
            `)}
        </div>
      </sl-card>
    `;
    }
    renderMcpServerCard() {
        return html `
      <sl-card class="content-card">
        <div class="card-header-with-action">
          <div class="card-title">MCP server</div>
          <div class="mcp-actions">
            <a
              class="header-link"
              href="#"
              @click=${(event) => {
            event.preventDefault();
            this.showSetupDialog = true;
        }}
            >
              Setup
            </a>
            <a class="header-link" href="/console/tools">Manage</a>
          </div>
        </div>
        <div class="mcp-summary">
          <div class="tool-counts">
            <div class="tool-count">
              <div class="tool-count-value">
                ${this.formatNumber(this.mcpServers.length)}
              </div>
              <div class="tool-count-label">external MCP servers</div>
            </div>
            <div class="tool-count">
              <div class="tool-count-value">
                ${this.formatNumber(this.tools.filter((tool) => tool.is_enabled).length)}
              </div>
              <div class="tool-count-label">enabled tools</div>
            </div>
            <div class="tool-count">
              <div class="tool-count-value">
                ${this.formatNumber(this.tools.filter((tool) => tool.approval_workflow_id != null ||
            tool.has_approval_condition === true).length)}
              </div>
              <div class="tool-count-label">tools requiring approval</div>
            </div>
            <div class="tool-count">
              <div class="tool-count-value">
                ${this.formatNumber(this.tools.filter((tool) => tool.source === 'builtin').length)}
              </div>
              <div class="tool-count-label">built-in tools</div>
            </div>
          </div>
          <div class="mcp-server-capsule">
            <div class="status-indicator"></div>
            <div class="server-details">
              <span class="server-endpoint">${window.location.origin}/mcp</span>
              <div class="capsule-hint">
                Built-in endpoint for managed agent and MCP client traffic
              </div>
            </div>
          </div>
          <a class="capsule-link" href="/console/settings/api-keys">
            Manage API keys
          </a>
        </div>
      </sl-card>
    `;
    }
    renderApprovalAnalyticsCard() {
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Approval analytics</div>
          <a class="row-link" href="/console/approvals">View all</a>
        </div>
        ${this.approvalStats.total === 0
            ? this.renderEmptyState('No approval requests recorded yet.')
            : html `
              <div class="analytics-grid">
                <div class="tool-count">
                  <div class="analytics-value">${this.approvalStats.total}</div>
                  <div class="analytics-label">Total requests</div>
                </div>
                <div class="tool-count">
                  <div class="analytics-value">
                    ${this.approvalStats.approved}
                  </div>
                  <div class="analytics-label">Approved</div>
                  <div class="analytics-subtext">
                    ${Math.round((this.approvalStats.approved / this.approvalStats.total) *
                100)}%
                    approval rate
                  </div>
                </div>
                <div class="tool-count">
                  <div class="analytics-value">
                    ${this.approvalStats.declined}
                  </div>
                  <div class="analytics-label">Declined</div>
                </div>
                ${this.approvalStats.expired > 0
                ? html `
                      <div class="tool-count">
                        <div class="analytics-value">
                          ${this.approvalStats.expired}
                        </div>
                        <div class="analytics-label">Timed out</div>
                      </div>
                    `
                : nothing}
                ${this.approvalStats.avgApprovalTime > 0
                ? html `
                      <div class="tool-count">
                        <div class="analytics-value">
                          ${this.approvalStats.avgApprovalTime}
                        </div>
                        <div class="analytics-label">Avg response time</div>
                        <div class="analytics-subtext">minutes</div>
                      </div>
                    `
                : nothing}
              </div>
            `}
      </sl-card>
    `;
    }
    renderKeyMetricsCard() {
        return html `
      <sl-card class="content-card">
        <div class="card-header">
          <div class="card-title">Key metrics</div>
        </div>
        <ul class="summary-list">
          <li class="summary-item">
            <span>Connected trackers</span>
            <strong>${this.formatNumber(this.trackers.length)}</strong>
          </li>
          <li class="summary-item">
            <span>Enabled tools</span>
            <strong>
              ${this.formatNumber(this.tools.filter((tool) => tool.is_enabled).length)}
            </strong>
          </li>
          ${isSaaS()
            ? html `
                <li class="summary-item">
                  <span>Enabled users</span>
                  <strong>${this.formatNumber(this.enabledUsersCount)}</strong>
                </li>
              `
            : nothing}
          <li class="summary-item">
            <span>Configured flows</span>
            <strong>${this.hasFlows ? 'Yes' : 'No'}</strong>
          </li>
          <li class="summary-item">
            <span>Total API requests</span>
            <strong>${this.formatNumber(this.apiUsage?.total_requests)}</strong>
          </li>
          <li class="summary-item">
            <span>Total issues processed</span>
            <strong>${this.formatNumber(this.totalIssues)}</strong>
          </li>
        </ul>
      </sl-card>
    `;
    }
    render() {
        if (this.loading) {
            return html `
        <view-header headerText="Overview" width="extra-wide"></view-header>
        <div class="column-layout extra-wide">
          <div class="main-column">
            <div class="loading-container">
              <sl-spinner style="font-size: 2.5rem;"></sl-spinner>
            </div>
          </div>
        </div>
      `;
        }
        return html `
      <view-header headerText="Overview" width="extra-wide"></view-header>
      <div class="column-layout dashboard extra-wide">
        <div class="main-column">
          <div class="dashboard-stack">
            ${this.error
            ? html `<sl-alert variant="danger" open>${this.error}</sl-alert>`
            : nothing}
            <div class="updated-at">
              Last updated ${this.formatRelativeTime(this.lastUpdatedAt)}
            </div>
            ${this.renderWelcomeCard()}
            <mcp-setup-dialog
              ?open=${this.showSetupDialog}
              @close=${() => (this.showSetupDialog = false)}
            ></mcp-setup-dialog>

            <div class="summary-grid">
              <sl-card class="summary-card">
                <div class="metric-label">Active agents</div>
                <div class="metric-value">${this.activeAgents.length}</div>
                <div class="metric-subtext">
                  ${this.formatNumber(this.managedAgents.length)} enrolled total
                </div>
              </sl-card>
              <sl-card class="summary-card">
                <div class="metric-label">Active runtime sessions</div>
                <div class="metric-value">${this.activeSessions.length}</div>
                <div class="metric-subtext">
                  ${this.formatNumber(this.runtimeSessions.length)} tracked
                  sessions
                </div>
              </sl-card>
              <sl-card class="summary-card">
                <div class="metric-label">Gateway spend</div>
                <div class="metric-value">
                  ${this.formatCurrency(this.gatewaySummary?.estimated_cost)}
                </div>
                <div class="metric-subtext">
                  ${this.formatNumber(this.gatewaySummary?.total_requests)}
                  requests in range
                </div>
              </sl-card>
              <sl-card class="summary-card">
                <div class="metric-label">Gateway failures</div>
                <div class="metric-value">${this.gatewayFailures.length}</div>
                <div class="metric-subtext">
                  ${this.formatNumber(this.gatewaySummary?.failed_requests)}
                  failed requests total
                </div>
              </sl-card>
            </div>

            ${this.renderRecentFlowExecutionsCard()}

            <div class="control-plane-grid">
              ${this.renderBudgetHealthCard()}
              ${this.renderGatewayFailuresCard()}
              ${this.renderAuditExceptionsCard()} ${this.renderTopModelsCard()}
              ${this.renderSessionsAttentionCard()}
            </div>
          </div>
        </div>

        <div class="side-column">
          ${this.renderPendingApprovalsCard()} ${this.renderMcpServerCard()}
          ${this.renderApprovalAnalyticsCard()} ${this.renderActiveAgentsCard()}
          ${this.renderActiveSessionsCard()} ${this.renderKeyMetricsCard()}
        </div>
      </div>
    `;
    }
};
DashboardView.styles = [
    unsafeCSS(consoleStyles),
    css `
      :host {
        display: block;
      }

      .loading-container {
        display: flex;
        justify-content: center;
        padding: var(--sl-spacing-2x-large);
      }

      .dashboard-stack {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }

      .updated-at {
        color: var(--sl-color-neutral-500);
        font-size: var(--sl-font-size-small);
      }

      .summary-grid,
      .control-plane-grid,
      .analytics-grid {
        display: grid;
        gap: var(--sl-spacing-medium);
      }

      .summary-grid {
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      }

      .control-plane-grid {
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      }

      .analytics-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .summary-card::part(base),
      .content-card::part(base),
      .welcome-card::part(base) {
        height: 100%;
      }

      .metric-label,
      .analytics-label,
      .analytics-subtext,
      .step-description,
      .empty-state,
      .updated-at,
      .row-meta,
      .summary-item span:last-child,
      .capsule-hint {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .metric-value,
      .analytics-value {
        color: var(--sl-color-neutral-900);
        font-weight: 700;
        line-height: 1.1;
      }

      .metric-value {
        font-size: 1.7rem;
        margin-top: var(--sl-spacing-2x-small);
      }

      .metric-subtext {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        margin-top: var(--sl-spacing-small);
      }

      .analytics-value {
        font-size: 1.35rem;
      }

      .card-header,
      .card-header-with-action,
      .row,
      .row-main,
      .row-meta,
      .welcome-header,
      .step-item,
      .budget-stat,
      .summary-item,
      .mcp-actions {
        display: flex;
      }

      .card-header,
      .card-header-with-action {
        align-items: center;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
        margin-bottom: var(--sl-spacing-medium);
      }

      .card-title,
      .welcome-title,
      .step-title,
      .row-primary,
      .capsule-hint strong {
        color: var(--sl-color-neutral-900);
        font-weight: 700;
      }

      .welcome-header {
        justify-content: space-between;
        align-items: center;
        gap: var(--sl-spacing-medium);
      }

      .welcome-title {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        font-size: 1.15rem;
      }

      .welcome-content {
        margin-top: var(--sl-spacing-medium);
        color: var(--sl-color-neutral-700);
      }

      .getting-started-steps {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-medium);
        margin-top: var(--sl-spacing-large);
      }

      .step-item {
        gap: var(--sl-spacing-medium);
        align-items: flex-start;
      }

      .step-content {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-x-small);
        flex: 1;
      }

      .step-actions {
        display: flex;
        gap: var(--sl-spacing-small);
        flex-wrap: wrap;
        margin-top: var(--sl-spacing-x-small);
      }

      .progress-overview {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-small);
        margin-top: var(--sl-spacing-large);
      }

      .list,
      .budget-meter,
      .summary-list,
      .mcp-summary {
        display: flex;
        flex-direction: column;
      }

      .list,
      .budget-meter,
      .mcp-summary {
        gap: var(--sl-spacing-small);
      }

      .row {
        flex-direction: column;
        gap: var(--sl-spacing-2x-small);
        padding: var(--sl-spacing-small) 0;
        border-top: 1px solid var(--sl-color-neutral-200);
      }

      .row:first-child {
        border-top: none;
        padding-top: 0;
      }

      .row-main,
      .row-meta,
      .budget-stat,
      .summary-item {
        align-items: center;
        justify-content: space-between;
        gap: var(--sl-spacing-small);
      }

      .row-primary {
        overflow-wrap: anywhere;
      }

      .row-value,
      .summary-item strong {
        color: var(--sl-color-neutral-900);
        font-weight: 600;
        text-align: right;
      }

      .row-link,
      .header-link,
      .capsule-link {
        color: var(--sl-color-primary-700);
        text-decoration: none;
      }

      .row-link:hover,
      .header-link:hover,
      .capsule-link:hover {
        text-decoration: underline;
      }

      .summary-list {
        list-style: none;
        padding: 0;
        margin: 0;
        gap: var(--sl-spacing-small);
      }

      .summary-item {
        padding: var(--sl-spacing-2x-small) 0;
        border-top: 1px solid var(--sl-color-neutral-200);
      }

      .summary-item:first-child {
        border-top: none;
        padding-top: 0;
      }

      .tool-counts {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--sl-spacing-medium);
      }

      .tool-count {
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        padding: var(--sl-spacing-medium);
        background: var(--sl-color-neutral-50);
      }

      .tool-count-value {
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--sl-color-neutral-900);
      }

      .tool-count-label {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .mcp-server-capsule {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        padding: var(--sl-spacing-medium);
        border-radius: var(--sl-border-radius-medium);
        background: var(--sl-color-neutral-50);
        border: 1px solid var(--sl-color-neutral-200);
      }

      .status-indicator {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: var(--sl-color-success-600);
        flex-shrink: 0;
      }

      .server-details {
        min-width: 0;
      }

      .server-endpoint {
        display: block;
        color: var(--sl-color-neutral-900);
        font-family: var(--sl-font-mono);
        font-size: var(--sl-font-size-small);
        overflow-wrap: anywhere;
      }

      .mcp-actions {
        gap: var(--sl-spacing-small);
        align-items: center;
      }

      .empty-state {
        border: 1px dashed var(--sl-color-neutral-300);
        border-radius: var(--sl-border-radius-medium);
        padding: var(--sl-spacing-large);
        text-align: center;
        background: var(--sl-color-neutral-0);
      }

      @media (max-width: 1200px) {
        .column-layout.dashboard {
          grid-template-columns: 1fr;
        }
      }

      @media (max-width: 800px) {
        .card-header,
        .card-header-with-action,
        .row-main,
        .row-meta,
        .summary-item,
        .step-item,
        .welcome-header {
          align-items: flex-start;
          flex-direction: column;
        }

        .row-value,
        .summary-item strong {
          text-align: left;
        }

        .tool-counts,
        .analytics-grid {
          grid-template-columns: 1fr;
        }
      }
    `,
];
__decorate([
    state()
], DashboardView.prototype, "loading", void 0);
__decorate([
    state()
], DashboardView.prototype, "error", void 0);
__decorate([
    state()
], DashboardView.prototype, "gatewaySummary", void 0);
__decorate([
    state()
], DashboardView.prototype, "runtimeSessions", void 0);
__decorate([
    state()
], DashboardView.prototype, "managedAgents", void 0);
__decorate([
    state()
], DashboardView.prototype, "gatewayInteractions", void 0);
__decorate([
    state()
], DashboardView.prototype, "auditGroups", void 0);
__decorate([
    state()
], DashboardView.prototype, "trackers", void 0);
__decorate([
    state()
], DashboardView.prototype, "apiUsage", void 0);
__decorate([
    state()
], DashboardView.prototype, "totalIssues", void 0);
__decorate([
    state()
], DashboardView.prototype, "mcpServers", void 0);
__decorate([
    state()
], DashboardView.prototype, "tools", void 0);
__decorate([
    state()
], DashboardView.prototype, "recentFlowExecutions", void 0);
__decorate([
    state()
], DashboardView.prototype, "pendingApprovals", void 0);
__decorate([
    state()
], DashboardView.prototype, "lastUpdatedAt", void 0);
__decorate([
    state()
], DashboardView.prototype, "hasFlows", void 0);
__decorate([
    state()
], DashboardView.prototype, "hasAIModels", void 0);
__decorate([
    state()
], DashboardView.prototype, "enabledUsersCount", void 0);
__decorate([
    state()
], DashboardView.prototype, "showSetupDialog", void 0);
__decorate([
    state()
], DashboardView.prototype, "welcomeCardDismissed", void 0);
__decorate([
    state()
], DashboardView.prototype, "approvalStats", void 0);
DashboardView = __decorate([
    customElement('dashboard-view')
], DashboardView);
export { DashboardView };
