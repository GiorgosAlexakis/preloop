var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import consoleStyles from '../../styles/console-styles.css?inline';
import { getFlowExecution, getFlow, sendCommandToExecution, getFlowExecutionMetrics, getFlowExecutionLogs, getFlowExecutionGatewayEvents, retryFlowExecution, } from '../../api';
import { parseUTCDate, formatLocalTime, formatUTCDateTime, calculateDuration, } from '../../utils/date';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/progress-bar/progress-bar.js';
import '@shoelace-style/shoelace/dist/components/relative-time/relative-time.js';
import '@shoelace-style/shoelace/dist/components/button-group/button-group.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/tab-group/tab-group.js';
import '@shoelace-style/shoelace/dist/components/tab/tab.js';
import '@shoelace-style/shoelace/dist/components/tab-panel/tab-panel.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';
let FlowExecutionView = class FlowExecutionView extends LitElement {
    constructor() {
        super(...arguments);
        this.execution = null;
        this.flow = null;
        this.logs = [];
        this.gatewayEvents = [];
        this.gatewayEventsSource = null;
        this.gatewayEventsError = null;
        this.gatewaySearchQuery = '';
        this.isLoadingGatewayEvents = false;
        this.toolCalls = 0;
        this.budgetUsed = 0;
        this.totalTokens = 0;
        this.hasPricing = false;
        this.commandInput = '';
        this.isAutoScroll = true;
        this.isSendingCommand = false;
        this.loadingError = null;
        this.isLoading = false;
        this.isRetrying = false;
        this.wsConnected = false;
        // Buffered log rendering - prevents scroll issues when many lines arrive at once
        this.logBuffer = [];
        this.BUFFER_FLUSH_INTERVAL_MS = 500;
        this.MAX_LINES_PER_FLUSH = 5;
    }
    // Vaadin Router lifecycle callback
    onBeforeEnter(location) {
        this.executionId = location.params.executionId;
    }
    disconnectedCallback() {
        super.disconnectedCallback();
        // Clean up auto-scroll interval when component is removed
        if (this.autoScrollInterval) {
            clearInterval(this.autoScrollInterval);
            this.autoScrollInterval = undefined;
        }
        // Clean up buffer flush interval
        if (this.bufferFlushInterval) {
            clearInterval(this.bufferFlushInterval);
            this.bufferFlushInterval = undefined;
        }
        // Unsubscribe from WebSocket
        this.unsubscribe?.();
    }
    async updated(changedProperties) {
        super.updated(changedProperties);
        // When executionId property changes, fetch execution data
        if (changedProperties.has('executionId') &&
            this.executionId &&
            !this.wsConnected) {
            // First, fetch execution data (which loads persisted logs)
            await this.fetchExecution();
            console.log(`After fetchExecution, logs.length = ${this.logs.length}`);
            console.log(`Execution status: ${this.execution?.status}`);
            console.log(`Has model_output_summary: ${!!this.execution?.model_output_summary}`);
            if (this.execution?.model_output_summary) {
                console.log(`model_output_summary length: ${this.execution.model_output_summary.length} chars`);
            }
            // Check if execution is still running
            const isRunning = this.execution &&
                (this.execution.status === 'RUNNING' ||
                    this.execution.status === 'STARTING' ||
                    this.execution.status === 'INITIALIZING' ||
                    this.execution.status === 'PENDING');
            console.log(`isRunning: ${isRunning}`);
            // If finished, show model_output_summary in logs
            if (!isRunning && this.execution?.model_output_summary) {
                console.log('Adding model_output_summary to logs (execution finished on page load)');
                this.logs = [
                    ...this.logs,
                    {
                        execution_id: this.executionId,
                        timestamp: this.execution.end_time || new Date().toISOString(),
                        type: 'model_output',
                        payload: { content: this.execution.model_output_summary },
                    },
                ];
                console.log(`Updated logs.length = ${this.logs.length}`);
            }
            else {
                console.log(`Not adding model_output: isRunning=${isRunning}, has_summary=${!!this.execution?.model_output_summary}`);
            }
            // Scroll to bottom after logs are loaded
            if (this.logs.length > 0) {
                setTimeout(() => this.scrollToBottom(), 100);
            }
            // Only connect to WebSocket if execution is still running
            if (isRunning) {
                this.wsConnected = true;
                this.isAutoScroll = true; // Enable auto-scroll for streaming
                this.startAutoScrollChecker(); // Start periodic scroll checker
                this.startBufferFlush(); // Start buffered log rendering
                // Subscribe to flow execution updates for this specific execution
                this.unsubscribe = unifiedWebSocketManager.subscribe('flow_executions', (message) => this.handleWebSocketMessage(message),
                // Filter to only receive messages for this execution
                (message) => message.execution_id === this.executionId);
                // Track connection state
                unifiedWebSocketManager.onStateChange((state) => {
                    const wasConnected = this.wsConnected;
                    this.wsConnected = state === 'connected';
                    // Add connection log if this is initial connection
                    if (state === 'connected' &&
                        !wasConnected &&
                        this.logs.length === 0) {
                        console.log('Adding connection log message');
                        this.logs = [
                            {
                                execution_id: this.executionId,
                                timestamp: new Date().toISOString(),
                                type: 'connected',
                                payload: { message: 'Connected to flow execution stream' },
                            },
                        ];
                    }
                    // Stop auto-scroll and buffer flush when disconnected
                    if (state !== 'connected') {
                        this.stopAutoScrollChecker();
                        this.stopBufferFlush();
                    }
                });
            }
            else {
                console.log('Execution is finished, not connecting to WebSocket stream');
            }
        }
    }
    handleWebSocketMessage(message) {
        console.log('WebSocket message:', message);
        // Handle connection confirmation
        if (message.type === 'connected') {
            return; // Already handled in onOpen callback
        }
        // Handle NATS forwarded messages
        if (message.execution_id === this.executionId) {
            if (message.type === 'model_gateway_call') {
                this.appendGatewayEvent(message);
                return;
            }
            // For agent log lines, add to buffer for controlled rendering
            // For other message types (status updates, etc.), add directly
            if (message.type === 'agent_log_line') {
                this.logBuffer.push(message);
            }
            else {
                this.logs = [...this.logs, message];
            }
            // Update execution status
            if (message.type === 'status_update' && this.execution) {
                const previousStatus = this.execution.status;
                if (message.payload.status) {
                    this.execution.status = message.payload.status;
                }
                // Update other fields if provided
                if (message.payload.resolved_input_prompt) {
                    this.execution.resolved_input_prompt =
                        message.payload.resolved_input_prompt;
                }
                if (message.payload.model_output_summary) {
                    this.execution.model_output_summary =
                        message.payload.model_output_summary;
                    // Check if execution just finished and model_output_summary is provided
                    const wasRunning = previousStatus === 'RUNNING' ||
                        previousStatus === 'STARTING' ||
                        previousStatus === 'INITIALIZING' ||
                        previousStatus === 'PENDING';
                    const isNowFinished = this.execution.status !== 'RUNNING' &&
                        this.execution.status !== 'STARTING' &&
                        this.execution.status !== 'INITIALIZING' &&
                        this.execution.status !== 'PENDING';
                    // If execution just finished, flush remaining buffer and add model output
                    if (wasRunning && isNowFinished) {
                        // Flush any remaining buffered logs first
                        this.stopBufferFlush();
                        // Check if we haven't already added it
                        const hasModelOutput = this.logs.some((log) => log.type === 'model_output');
                        if (!hasModelOutput) {
                            this.logs = [
                                ...this.logs,
                                {
                                    execution_id: this.executionId,
                                    timestamp: new Date().toISOString(),
                                    type: 'model_output',
                                    payload: { content: this.execution.model_output_summary },
                                },
                            ];
                        }
                    }
                }
                this.requestUpdate();
            }
            // Track tool calls
            if (message.type === 'tool_call' || message.type === 'mcp_call') {
                this.toolCalls++;
            }
            // Handle real-time tool calls update
            if (message.type === 'tool_calls_update') {
                this.toolCalls = message.payload.tool_calls || 0;
            }
            // Handle real-time token usage update
            if (message.type === 'token_usage_update' &&
                !this.hasGatewayUsageEvents()) {
                this.totalTokens = message.payload.total_tokens || 0;
                if (typeof message.payload.estimated_cost === 'number') {
                    this.budgetUsed = message.payload.estimated_cost;
                    this.hasPricing = true;
                }
            }
            // Track budget usage
            if (message.type === 'budget_update' && !this.hasGatewayUsageEvents()) {
                this.budgetUsed = message.payload.budget_used || 0;
            }
            // For non-buffered messages, scroll immediately
            if (message.type !== 'agent_log_line' && this.isAutoScroll) {
                this.updateComplete.then(() => this.scrollToBottom());
            }
        }
    }
    startAutoScrollChecker() {
        // Clear any existing interval
        this.stopAutoScrollChecker();
        this.logContainerRef = this.shadowRoot?.querySelector('.log-container');
        if (this.logContainerRef) {
            this.logContainerRef.addEventListener('scroll', () => this.handleScroll());
        }
        // Fallback: check scroll position every 500ms and force scroll if needed
        // Primary scrolling is done via updateComplete in handleWebSocketMessage
        this.autoScrollInterval = window.setInterval(() => {
            if (this.isAutoScroll && this.logContainerRef) {
                const { scrollTop, scrollHeight, clientHeight } = this.logContainerRef;
                const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
                // If not at bottom, force scroll (fallback for missed updates)
                if (!isAtBottom) {
                    this.logContainerRef.scrollTop = this.logContainerRef.scrollHeight;
                }
            }
        }, 500);
    }
    stopAutoScrollChecker() {
        if (this.autoScrollInterval) {
            clearInterval(this.autoScrollInterval);
            this.autoScrollInterval = undefined;
        }
    }
    startBufferFlush() {
        // Clear any existing interval
        this.stopBufferFlush();
        // Flush buffer periodically
        this.bufferFlushInterval = window.setInterval(() => {
            this.flushLogBuffer();
        }, this.BUFFER_FLUSH_INTERVAL_MS);
    }
    stopBufferFlush() {
        if (this.bufferFlushInterval) {
            clearInterval(this.bufferFlushInterval);
            this.bufferFlushInterval = undefined;
        }
        // Flush any remaining logs when stopping
        if (this.logBuffer.length > 0) {
            this.logs = [...this.logs, ...this.logBuffer];
            this.logBuffer = [];
            if (this.isAutoScroll) {
                this.updateComplete.then(() => this.scrollToBottom());
            }
        }
    }
    flushLogBuffer() {
        if (this.logBuffer.length === 0)
            return;
        // Take up to MAX_LINES_PER_FLUSH from buffer
        const linesToAdd = this.logBuffer.splice(0, this.MAX_LINES_PER_FLUSH);
        this.logs = [...this.logs, ...linesToAdd];
        // Scroll after adding lines
        if (this.isAutoScroll) {
            this.updateComplete.then(() => this.scrollToBottom());
        }
    }
    scrollToBottom() {
        // Get fresh reference in case DOM was updated
        const container = this.logContainerRef ||
            this.shadowRoot?.querySelector('.log-container');
        if (container) {
            this.logContainerRef = container;
            // Use requestAnimationFrame for smoother scrolling after DOM paint
            requestAnimationFrame(() => {
                container.scrollTop = container.scrollHeight;
            });
        }
    }
    handleScroll() {
        if (!this.logContainerRef)
            return;
        // Check if user scrolled away from bottom
        const { scrollTop, scrollHeight, clientHeight } = this.logContainerRef;
        const isAtBottom = scrollHeight - scrollTop - clientHeight < 50; // 50px threshold
        // Disable auto-scroll when user manually scrolls away from bottom
        if (!isAtBottom && this.isAutoScroll) {
            console.log('User scrolled away from bottom, disabling auto-scroll');
            this.isAutoScroll = false;
        }
        else if (isAtBottom && !this.isAutoScroll) {
            // Re-enable auto-scroll when user scrolls back to bottom
            console.log('User scrolled to bottom, enabling auto-scroll');
            this.isAutoScroll = true;
            // Restart the checker if execution is still running
            if (this.wsConnected) {
                this.startAutoScrollChecker();
            }
        }
    }
    async fetchExecution() {
        if (!this.executionId)
            return;
        try {
            this.isLoading = true;
            this.isLoadingGatewayEvents = true;
            this.loadingError = null;
            this.gatewayEventsError = null;
            this.gatewayEvents = [];
            this.gatewayEventsSource = null;
            // Fetch execution details
            this.execution = await getFlowExecution(this.executionId);
            this.hydrateMetricsFromExecution();
            // Fetch logs and normalized gateway events in parallel.
            const [logsResult, gatewayEventsResult] = await Promise.allSettled([
                getFlowExecutionLogs(this.executionId),
                getFlowExecutionGatewayEvents(this.executionId),
            ]);
            // Fetch logs from container (if running) or database (if finished)
            // This ensures we get all historical logs, even for running executions
            try {
                if (logsResult.status !== 'fulfilled') {
                    throw logsResult.reason;
                }
                const logsResponse = logsResult.value;
                if (logsResponse.logs && Array.isArray(logsResponse.logs)) {
                    console.log(`Loaded ${logsResponse.logs.length} logs from ${logsResponse.source}`);
                    this.logs = logsResponse.logs;
                }
                else {
                    console.log('No logs found in response');
                }
            }
            catch (error) {
                console.error('Failed to fetch logs:', error);
                // Fallback to execution_logs from database if available
                if (this.execution &&
                    this.execution.execution_logs &&
                    Array.isArray(this.execution.execution_logs)) {
                    console.log(`Using fallback: Loaded ${this.execution.execution_logs.length} persisted logs from database`);
                    this.logs = this.execution.execution_logs;
                }
                else {
                    console.log('No fallback logs available');
                }
            }
            this.hydrateToolActivityLogs();
            try {
                if (gatewayEventsResult.status !== 'fulfilled') {
                    throw gatewayEventsResult.reason;
                }
                this.gatewayEvents = gatewayEventsResult.value.logs || [];
                this.gatewayEventsSource = gatewayEventsResult.value.source;
                this.applyGatewayMetricsFromEvents();
            }
            catch (error) {
                console.error('Failed to fetch gateway events:', error);
                this.gatewayEventsError =
                    error instanceof Error
                        ? error.message
                        : 'Failed to load execution gateway events';
            }
            finally {
                this.isLoadingGatewayEvents = false;
            }
            // Fetch flow details
            if (this.execution && this.execution.flow_id) {
                try {
                    this.flow = await getFlow(this.execution.flow_id);
                }
                catch (error) {
                    console.error('Failed to fetch flow details:', error);
                    // Don't fail the whole page if flow fetch fails
                }
            }
            // Fetch execution metrics (for completed executions)
            if (this.execution &&
                ['COMPLETED', 'FAILED', 'STOPPED', 'TIMEOUT'].includes(this.execution.status)) {
                try {
                    const metrics = await getFlowExecutionMetrics(this.executionId);
                    this.toolCalls = metrics.tool_calls;
                    this.budgetUsed = metrics.estimated_cost;
                    this.totalTokens = metrics.token_usage.total_tokens;
                    this.hasPricing = metrics.has_pricing;
                    console.log('Loaded execution metrics:', metrics);
                }
                catch (error) {
                    console.error('Failed to fetch execution metrics:', error);
                    // Don't fail the whole page if metrics fetch fails
                }
            }
            this.isLoading = false;
        }
        catch (error) {
            console.error('Failed to fetch execution:', error);
            this.loadingError =
                error instanceof Error
                    ? error.message
                    : 'Failed to load execution details';
            this.isLoading = false;
            this.isLoadingGatewayEvents = false;
        }
    }
    getTriggerSource() {
        if (!this.execution?.trigger_event_details) {
            return 'Unknown';
        }
        const details = this.execution.trigger_event_details;
        if (details.test_mode) {
            return 'Manual Test Run';
        }
        if (details.source && details.type) {
            return `${details.source} ${details.type}`;
        }
        return 'Automatic';
    }
    getTriggerIcon() {
        if (!this.execution?.trigger_event_details) {
            return 'question-circle';
        }
        const details = this.execution.trigger_event_details;
        if (details.test_mode) {
            return 'play-circle';
        }
        if (details.source === 'github') {
            return 'github';
        }
        if (details.source === 'gitlab') {
            return 'git';
        }
        return 'lightning';
    }
    appendGatewayEvent(event) {
        const nextEventKey = this.getGatewayEventKey(event);
        const exists = this.gatewayEvents.some((existingEvent) => this.getGatewayEventKey(existingEvent) === nextEventKey);
        if (!exists) {
            this.gatewayEvents = [...this.gatewayEvents, event];
            this.gatewayEventsSource = 'container';
            this.applyGatewayMetricsFromEvents();
        }
    }
    hasGatewayUsageEvents() {
        return this.gatewayEvents.some((event) => this.gatewayEventHasUsageMetrics(event));
    }
    gatewayEventHasUsageMetrics(event) {
        return (typeof event.payload.total_tokens === 'number' ||
            typeof event.payload.estimated_cost === 'number');
    }
    applyGatewayMetricsFromEvents() {
        const summary = this.gatewayEvents.reduce((totals, event) => {
            totals.totalTokens += this.getGatewayMetricNumber(event.payload.total_tokens);
            totals.estimatedCost += this.getGatewayMetricNumber(event.payload.estimated_cost);
            if (typeof event.payload.estimated_cost === 'number' ||
                event.payload.budget
                    ?.pricing_available === true) {
                totals.hasPricing = true;
            }
            return totals;
        }, { totalTokens: 0, estimatedCost: 0, hasPricing: false });
        if (summary.totalTokens > 0 ||
            summary.estimatedCost > 0 ||
            summary.hasPricing) {
            this.totalTokens = summary.totalTokens;
            this.budgetUsed = summary.estimatedCost;
            this.hasPricing = summary.hasPricing;
        }
    }
    getGatewayMetricNumber(value) {
        return typeof value === 'number' && !Number.isNaN(value) ? value : 0;
    }
    hydrateMetricsFromExecution() {
        if (!this.execution) {
            return;
        }
        const executionToolCalls = typeof this.execution.tool_calls_count === 'number'
            ? this.execution.tool_calls_count
            : Array.isArray(this.execution.mcp_usage_logs)
                ? this.execution.mcp_usage_logs.length
                : 0;
        this.toolCalls = executionToolCalls;
        if (!this.hasGatewayUsageEvents()) {
            if (typeof this.execution.total_tokens === 'number') {
                this.totalTokens = this.execution.total_tokens;
            }
            if (typeof this.execution.estimated_cost === 'number') {
                this.budgetUsed = this.execution.estimated_cost;
                if (this.execution.estimated_cost > 0) {
                    this.hasPricing = true;
                }
            }
        }
    }
    hydrateToolActivityLogs() {
        if (!this.execution?.mcp_usage_logs?.length) {
            return;
        }
        if (this.execution.mcp_usage_logs.length > this.toolCalls) {
            this.toolCalls = this.execution.mcp_usage_logs.length;
        }
    }
    getGatewayEventKey(event) {
        const apiUsageId = event.payload?.api_usage_id;
        if (typeof apiUsageId === 'string' && apiUsageId) {
            return apiUsageId;
        }
        return [
            event.execution_id,
            event.timestamp ?? 'no-timestamp',
            event.payload?.upstream_request_id ?? 'no-request-id',
            event.payload?.model_alias ??
                event.payload?.requested_model ??
                'no-model',
        ].join(':');
    }
    getTotalToolCallCount() {
        const persistedCount = Array.isArray(this.execution?.mcp_usage_logs)
            ? this.execution.mcp_usage_logs.length
            : 0;
        return Math.max(this.toolCalls, persistedCount, this.getToolActivityEntries().length);
    }
    normalizeToolName(value) {
        if (typeof value !== 'string') {
            return null;
        }
        const normalized = value.trim();
        if (!normalized) {
            return null;
        }
        if (/^v\d+$/i.test(normalized) ||
            /^(mcp|tool|tools|http|https)$/i.test(normalized) ||
            normalized.startsWith('/') ||
            normalized.includes('://') ||
            normalized.split('/').length > 1) {
            return null;
        }
        return normalized;
    }
    extractToolNameFromText(value) {
        if (typeof value !== 'string') {
            return null;
        }
        for (const pattern of [
            /called tool:\s*([a-zA-Z0-9._:-]+)/i,
            /tool:\s*([a-zA-Z0-9._:-]+)/i,
        ]) {
            const match = value.match(pattern);
            const toolName = this.normalizeToolName(match?.[1]);
            if (toolName) {
                return toolName;
            }
        }
        return null;
    }
    normalizeToolActivityEntry(payload, timestamp) {
        if (!payload || typeof payload !== 'object') {
            return null;
        }
        const toolName = this.normalizeToolName(payload.tool_name) ||
            this.normalizeToolName(payload.tool) ||
            this.normalizeToolName(payload.name) ||
            this.extractToolNameFromText(payload.message) ||
            this.extractToolNameFromText(payload.result_summary) ||
            this.extractToolNameFromText(payload.error);
        if (!toolName) {
            return null;
        }
        const serverName = typeof payload.server_name === 'string' && payload.server_name.trim()
            ? payload.server_name.trim()
            : 'MCP';
        const detail = typeof payload.result_summary === 'string' && payload.result_summary.trim()
            ? payload.result_summary.trim()
            : typeof payload.error === 'string' && payload.error.trim()
                ? payload.error.trim()
                : typeof payload.message === 'string' &&
                    payload.message.trim() &&
                    !payload.message.includes(toolName)
                    ? payload.message.trim()
                    : undefined;
        return {
            key: [
                timestamp || 'no-timestamp',
                serverName,
                toolName,
                payload.status || 'unknown',
                detail || '',
            ].join(':'),
            timestamp,
            toolName,
            serverName,
            status: typeof payload.status === 'string' ? payload.status : undefined,
            detail,
        };
    }
    getToolActivityEntries() {
        const entries = [];
        const persistedLogs = Array.isArray(this.execution?.mcp_usage_logs)
            ? this.execution.mcp_usage_logs
            : [];
        for (const entry of persistedLogs) {
            const timestamp = typeof entry?.timestamp === 'string'
                ? entry.timestamp
                : this.execution?.start_time || new Date().toISOString();
            const normalized = this.normalizeToolActivityEntry(entry, timestamp);
            if (normalized) {
                entries.push(normalized);
            }
        }
        for (const log of this.logs) {
            if (log.type !== 'tool_call' && log.type !== 'mcp_call') {
                continue;
            }
            const normalized = this.normalizeToolActivityEntry(log.payload, log.timestamp);
            if (normalized) {
                entries.push(normalized);
            }
        }
        const seen = new Set();
        return entries
            .sort((left, right) => new Date(right.timestamp).getTime() -
            new Date(left.timestamp).getTime())
            .filter((entry) => {
            if (seen.has(entry.key)) {
                return false;
            }
            seen.add(entry.key);
            return true;
        });
    }
    renderToolActivityList(toolEntries) {
        return html `
      <div class="tool-activity-list">
        ${toolEntries.map((entry) => {
            return html `
            <div class="tool-activity-item">
              <div class="tool-activity-header">
                <div>
                  <div class="tool-activity-title">${entry.toolName}</div>
                  <div class="tool-activity-meta">
                    ${entry.serverName} ·
                    ${formatLocalTime(entry.timestamp)}
                  </div>
                </div>
                ${entry.status
                ? html `
                      <sl-badge
                        variant=${entry.status === 'error' || entry.status === 'failed'
                    ? 'danger'
                    : 'success'}
                      >
                        ${entry.status}
                      </sl-badge>
                    `
                : ''}
              </div>
              ${entry.detail
                ? html `<div class="tool-activity-meta">${entry.detail}</div>`
                : ''}
            </div>
          `;
        })}
      </div>
    `;
    }
    renderToolActivitySidebar() {
        const toolEntries = this.getToolActivityEntries();
        const totalToolCalls = this.getTotalToolCallCount();
        if (toolEntries.length === 0 && totalToolCalls === 0) {
            return '';
        }
        return html `
      <sl-card class="output-sidebar-card">
        <div
          slot="header"
          style="display: flex; justify-content: space-between; align-items: center; gap: 12px;"
        >
          <span>
            <sl-icon name="tools"></sl-icon>
            Tool Activity
          </span>
          <sl-badge pill>${toolEntries.length}</sl-badge>
        </div>
        ${toolEntries.length > 0
            ? this.renderToolActivityList(toolEntries)
            : html `
              <div class="tool-activity-empty">
                Tool calls are being counted, but no structured tool names have
                been captured yet.
              </div>
            `}
        ${totalToolCalls > toolEntries.length
            ? html `
              <div class="tool-activity-note">
                ${totalToolCalls.toLocaleString()} total call${totalToolCalls === 1 ? '' : 's'}
                recorded, showing ${toolEntries.length.toLocaleString()} structured
                entr${toolEntries.length === 1 ? 'y' : 'ies'}.
              </div>
            `
            : ''}
      </sl-card>
    `;
    }
    renderExecutionMetadataSidebar() {
        if (!this.execution) {
            return '';
        }
        return html `
      <sl-card class="output-sidebar-card">
        <div slot="header">
          <sl-icon name="info-circle"></sl-icon>
          Live Summary
        </div>
        <div class="execution-metadata-list">
          ${this.flow
            ? html `
                <div class="execution-metadata-label">Flow</div>
                <div class="execution-metadata-value">
                  <a href="/console/flows/${this.flow.id}">${this.flow.name}</a>
                </div>

                <div class="execution-metadata-label">Agent Type</div>
                <div class="execution-metadata-value">
                  <sl-badge>${this.flow.agent_type}</sl-badge>
                </div>
              `
            : ''}

          <div class="execution-metadata-label">Triggered By</div>
          <div class="execution-metadata-value">${this.getTriggerSource()}</div>
          ${this.execution.agent_session_reference
            ? html `
                <div class="execution-metadata-label">Session</div>
                <div class="execution-metadata-value">
                  <code>${this.execution.agent_session_reference}</code>
                </div>
              `
            : ''}

          <div class="execution-metadata-label">Recorded Calls</div>
          <div class="execution-metadata-value">${this.getTotalToolCallCount()}</div>

          <div class="execution-metadata-label">Detailed Activity</div>
          <div class="execution-metadata-value">
            ${this.getToolActivityEntries().length}
          </div>

          <div class="execution-metadata-label">
            ${this.hasPricing ? 'Budget' : 'Tokens'}
          </div>
          <div class="execution-metadata-value">
            ${this.hasPricing
            ? html `
                  <div>$${this.budgetUsed.toFixed(2)}</div>
                  <div class="tool-activity-meta">
                    ${this.totalTokens.toLocaleString()} tokens
                  </div>
                `
            : html `${this.totalTokens.toLocaleString()} tokens`}
          </div>
        </div>
      </sl-card>
    `;
    }
    renderGatewayField(label, value) {
        return html `
      <div class="gateway-event-field">
        <div class="gateway-event-label">${label}</div>
        <div class="gateway-event-value">${value ?? 'n/a'}</div>
      </div>
    `;
    }
    getGatewayModelLabel(event) {
        return (event.payload.model_alias ||
            event.payload.requested_model ||
            'Unknown model');
    }
    getGatewayProviderLabel(event) {
        return (event.payload.provider_name ||
            event.payload.gateway_provider ||
            'Unknown provider');
    }
    getGatewayOutcomeVariant(outcome) {
        switch (outcome) {
            case 'success':
                return 'success';
            case 'budget_denied':
                return 'warning';
            case 'error':
                return 'danger';
            default:
                return 'neutral';
        }
    }
    formatGatewayOutcome(outcome) {
        if (!outcome) {
            return 'Unknown';
        }
        return outcome
            .split('_')
            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }
    formatGatewayCost(cost) {
        if (typeof cost !== 'number' || Number.isNaN(cost)) {
            return 'n/a';
        }
        if (cost === 0) {
            return '$0.00';
        }
        return cost >= 0.01 ? `$${cost.toFixed(2)}` : `$${cost.toFixed(4)}`;
    }
    formatGatewayTokens(tokens) {
        if (typeof tokens !== 'number' || Number.isNaN(tokens)) {
            return 'n/a';
        }
        return tokens.toLocaleString();
    }
    formatGatewayPayload(payload) {
        return JSON.stringify(payload, null, 2);
    }
    handleGatewaySearchQueryChange(event) {
        this.gatewaySearchQuery = event.target.value;
    }
    getGatewaySearchText(event) {
        const payload = event.payload || {};
        const previewText = this.getGatewayPreviewMessages(payload)
            .map((message) => `${message.source || ''} ${message.role || ''} ${message.text || ''}`)
            .join('\n');
        return [
            event.type,
            event.timestamp || '',
            payload.endpoint || '',
            payload.endpoint_kind || '',
            payload.model_alias || '',
            payload.requested_model || '',
            payload.provider_name || '',
            payload.gateway_provider || '',
            payload.error_detail || '',
            payload.message || '',
            previewText,
            this.formatGatewayPayload(payload),
        ]
            .filter(Boolean)
            .join('\n')
            .toLowerCase();
    }
    getFilteredGatewayEvents() {
        const query = this.gatewaySearchQuery.trim().toLowerCase();
        if (!query) {
            return this.gatewayEvents;
        }
        return this.gatewayEvents.filter((event) => this.getGatewaySearchText(event).includes(query));
    }
    formatGatewayLabel(value) {
        if (!value) {
            return 'Unknown';
        }
        return value
            .split('_')
            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }
    getGatewayPreviewMessages(payload) {
        return Array.isArray(payload.conversation_preview?.messages)
            ? payload.conversation_preview?.messages
            : [];
    }
    renderGatewayCapturePolicy(payload) {
        const policy = payload.capture_policy;
        if (!policy) {
            return '';
        }
        return html `
      <div class="payload-section-title">Capture Policy</div>
      <div class="gateway-capture-policy">
        <div class="gateway-capture-grid">
          ${this.renderGatewayField('Content', policy.content_capture_enabled
            ? 'Preview captured'
            : 'Preview redacted')}
          ${this.renderGatewayField('Max Preview', typeof policy.max_preview_chars === 'number'
            ? `${policy.max_preview_chars} chars`
            : 'n/a')}
          ${this.renderGatewayField('Conversation', policy.conversation_preview_available
            ? 'Available'
            : 'Not available')}
        </div>
        <div class="gateway-badges">
          ${policy.sensitive_fields_redacted
            ? html `<sl-badge pill>Sensitive fields redacted</sl-badge>`
            : ''}
          ${policy.content_redacted
            ? html `<sl-badge pill variant="warning">Content redacted</sl-badge>`
            : ''}
          ${policy.content_truncated
            ? html `<sl-badge pill variant="warning"
                >Content truncated</sl-badge
              >`
            : ''}
        </div>
      </div>
    `;
    }
    renderGatewayPreviewMessage(message) {
        const previewText = message.text
            ? message.text
            : message.redacted
                ? 'Content redacted by capture policy.'
                : 'No text content captured.';
        return html `
      <div class="conversation-preview-message">
        <div class="conversation-preview-header">
          <div class="conversation-preview-title">
            ${this.formatGatewayLabel(message.source)}
            ${this.formatGatewayLabel(message.role)}
          </div>
          <div class="gateway-badges">
            ${message.redacted
            ? html `<sl-badge pill variant="warning">Redacted</sl-badge>`
            : ''}
            ${message.truncated
            ? html `<sl-badge pill variant="warning">Truncated</sl-badge>`
            : ''}
            ${typeof message.original_length === 'number'
            ? html `
                  <sl-badge pill variant="neutral">
                    ${message.original_length.toLocaleString()} chars
                  </sl-badge>
                `
            : ''}
          </div>
        </div>
        <pre
          class="conversation-preview-text ${message.redacted
            ? 'conversation-preview-redacted'
            : ''}"
        >
${previewText}</pre
        >
        ${message.truncated
            ? html `
              <div class="search-summary">
                This stored preview was truncated before display.
              </div>
            `
            : ''}
      </div>
    `;
    }
    renderGatewayConversationPreview(payload) {
        const messages = this.getGatewayPreviewMessages(payload);
        const metadata = payload.conversation_preview?.metadata;
        return html `
      <div class="payload-section-title">Conversation Preview</div>
      <div class="gateway-badges" style="margin-bottom: 12px;">
        <sl-badge pill>${messages.length} messages</sl-badge>
        ${metadata?.has_redacted_content
            ? html `<sl-badge pill variant="warning"
              >Contains redactions</sl-badge
            >`
            : ''}
        ${metadata?.has_truncated_content
            ? html `<sl-badge pill variant="warning"
              >Contains truncation</sl-badge
            >`
            : ''}
      </div>
      ${messages.length > 0
            ? html `
            <div class="conversation-preview-list">
              ${messages.map((message) => this.renderGatewayPreviewMessage(message))}
            </div>
          `
            : html `
            <div class="payload-block" style="margin-bottom: 16px;">
              <pre>No conversation preview captured for this event.</pre>
            </div>
          `}
    `;
    }
    renderGatewayEventsPanel() {
        const filteredEvents = this.getFilteredGatewayEvents();
        const query = this.gatewaySearchQuery.trim();
        return html `
      <sl-card>
        <div
          slot="header"
          style="display: flex; justify-content: space-between; align-items: center; gap: 12px;"
        >
          <span>
            <sl-icon name="cpu"></sl-icon>
            Gateway Events
          </span>
          <div style="display: flex; align-items: center; gap: 8px;">
            ${this.gatewayEventsSource
            ? html `
                  <span class="gateway-panel-intro">
                    ${this.gatewayEventsSource === 'database'
                ? 'Stored execution events'
                : 'Live execution events'}
                  </span>
                `
            : ''}
            <sl-badge pill>
              ${query
            ? `${filteredEvents.length}/${this.gatewayEvents.length}`
            : this.gatewayEvents.length}
            </sl-badge>
          </div>
        </div>

        <div class="gateway-events-panel">
          <div class="gateway-panel-intro">
            Inspect normalized model gateway calls for this execution, including
            sanitized request and response payload previews when available.
          </div>
          <sl-input
            label="Search gateway events"
            placeholder="Search previews, payloads, tool outputs, or errors"
            .value=${this.gatewaySearchQuery}
            @sl-input=${this.handleGatewaySearchQueryChange}
          ></sl-input>
          <div class="search-summary">
            ${query
            ? `Showing ${filteredEvents.length} matching event${filteredEvents.length === 1 ? '' : 's'} for "${query}".`
            : `Showing all ${this.gatewayEvents.length} captured event${this.gatewayEvents.length === 1 ? '' : 's'}.`}
          </div>

          ${this.gatewayEventsError
            ? html `
                <sl-alert variant="warning" open>
                  <sl-icon slot="icon" name="exclamation-triangle"></sl-icon>
                  ${this.gatewayEventsError}
                </sl-alert>
              `
            : ''}
          ${this.isLoadingGatewayEvents && this.gatewayEvents.length === 0
            ? html `
                <div class="gateway-event-empty">
                  <sl-spinner style="font-size: 2rem;"></sl-spinner>
                  <p>Loading gateway events...</p>
                </div>
              `
            : this.gatewayEvents.length === 0
                ? html `
                  <div class="gateway-event-empty">
                    <sl-icon
                      name="diagram-3"
                      style="font-size: 2rem;"
                    ></sl-icon>
                    <p>No gateway events recorded for this execution.</p>
                  </div>
                `
                : filteredEvents.length === 0
                    ? html `
                    <div class="gateway-event-empty">
                      <sl-icon name="search" style="font-size: 2rem;"></sl-icon>
                      <p>No gateway events matched "${query}".</p>
                    </div>
                  `
                    : html `
                    <div class="gateway-events-list">
                      ${filteredEvents.map((event) => this.renderGatewayEvent(event))}
                    </div>
                  `}
        </div>
      </sl-card>
    `;
    }
    renderGatewayEvent(event) {
        const payload = event.payload;
        const timestamp = event.timestamp
            ? html `
          <sl-tooltip content=${formatUTCDateTime(event.timestamp)}>
            <span>${formatLocalTime(event.timestamp)}</span>
          </sl-tooltip>
        `
            : 'Unknown';
        return html `
      <sl-details class="gateway-event">
        <div slot="summary" class="gateway-event-summary">
          ${this.renderGatewayField('Timestamp', timestamp)}
          ${this.renderGatewayField('Model', this.getGatewayModelLabel(event))}
          ${this.renderGatewayField('Provider', this.getGatewayProviderLabel(event))}
          ${this.renderGatewayField('Outcome', html `
              <sl-badge
                variant=${this.getGatewayOutcomeVariant(payload.outcome)}
              >
                ${this.formatGatewayOutcome(payload.outcome)}
              </sl-badge>
            `)}
          ${this.renderGatewayField('Cost', this.formatGatewayCost(payload.estimated_cost))}
          ${this.renderGatewayField('Tokens', this.formatGatewayTokens(payload.total_tokens))}
        </div>

        <div class="gateway-event-meta">
          ${this.renderGatewayField('HTTP', payload.status_code
            ? `${payload.method || 'POST'} ${payload.status_code}`
            : payload.method || 'n/a')}
          ${this.renderGatewayField('Endpoint', payload.endpoint_kind || payload.endpoint || 'n/a')}
          ${this.renderGatewayField('Duration', typeof payload.duration_ms === 'number'
            ? `${payload.duration_ms} ms`
            : 'n/a')}
          ${this.renderGatewayField('Prompt Tokens', this.formatGatewayTokens(payload.prompt_tokens))}
          ${this.renderGatewayField('Completion Tokens', this.formatGatewayTokens(payload.completion_tokens))}
          ${this.renderGatewayField('Finish Reason', payload.finish_reason || 'n/a')}
          ${this.renderGatewayField('Request ID', payload.upstream_request_id || 'n/a')}
        </div>

        ${payload.error_detail
            ? html `
              <sl-alert variant="danger" open style="margin-bottom: 16px;">
                <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                ${payload.error_detail}
              </sl-alert>
            `
            : ''}
        ${this.renderGatewayCapturePolicy(payload)}
        ${this.renderGatewayConversationPreview(payload)}

        <div class="payload-section-title">Event Payload</div>
        <div class="payload-block">
          <pre>${this.formatGatewayPayload(payload)}</pre>
        </div>
      </sl-details>
    `;
    }
    render() {
        // Waiting for router to set executionId
        if (!this.executionId) {
            return html `
        <view-header headerText="Flow Execution" width="wide"></view-header>
        <div
          style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px; gap: 16px;"
        >
          <sl-spinner style="font-size: 3rem;"></sl-spinner>
          <p>Loading...</p>
        </div>
      `;
        }
        // Loading execution data
        if (this.isLoading) {
            return html `
        <view-header headerText="Flow Execution" width="wide"></view-header>
        <div
          style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px; gap: 16px;"
        >
          <sl-spinner style="font-size: 3rem;"></sl-spinner>
          <p>Loading execution details...</p>
        </div>
      `;
        }
        // Error state
        if (this.loadingError || !this.execution) {
            return html `
        <view-header headerText="Flow Execution" width="wide"></view-header>
        <div class="column-layout wide">
          <div class="main-column">
            <sl-alert variant="danger" open>
              <sl-icon slot="icon" name="exclamation-triangle"></sl-icon>
              <strong>Error Loading Execution</strong><br />
              ${this.loadingError || 'Execution not found'}
            </sl-alert>
            <sl-button
              href="/console/flows/executions"
              style="margin-top: 16px;"
            >
              <sl-icon name="arrow-left"></sl-icon>
              Back to Executions
            </sl-button>
          </div>
        </div>
      `;
        }
        const isRunning = this.execution.status === 'RUNNING' ||
            this.execution.status === 'STARTING' ||
            this.execution.status === 'INITIALIZING' ||
            this.execution.status === 'PENDING';
        return html `
      <view-header
        headerText="${this.flow?.name || 'Flow Execution'}"
        width="wide"
      ></view-header>
      <div class="column-layout wide">
        <div class="main-column">
          <!-- Navigation -->
          <div style="display: flex; gap: 8px; margin-bottom: 16px;">
            <sl-button size="small" href="/console/flows/executions">
              <sl-icon name="arrow-left"></sl-icon>
              All Executions
            </sl-button>
            ${this.flow
            ? html `
                  <sl-button size="small" href="/console/flows/${this.flow.id}">
                    <sl-icon name="diagram-3"></sl-icon>
                    View Flow
                  </sl-button>
                `
            : ''}
            ${this.canRetry()
            ? html `
                  <sl-button
                    size="small"
                    variant="warning"
                    ?loading=${this.isRetrying}
                    @click=${this.retryExecution}
                  >
                    <sl-icon name="arrow-repeat"></sl-icon>
                    Retry
                  </sl-button>
                `
            : ''}
          </div>

          <div class="summary-grid">
            <sl-card>
              <div slot="header">
                <sl-icon name="info-circle"></sl-icon> Status
              </div>
              <div class="summary-value">
                <sl-badge variant=${this.getStatusVariant(this.execution.status)}
                  >${this.execution.status}</sl-badge
                >
              </div>
              <div class="summary-subtext">Execution ${this.execution.id}</div>
            </sl-card>
            <sl-card>
              <div slot="header"><sl-icon name="diagram-3"></sl-icon> Flow</div>
              <div class="summary-value">
                ${this.flow
            ? html `<a href="/console/flows/${this.flow.id}"
                      >${this.flow.name}</a
                    >`
            : 'Unknown flow'}
              </div>
              <div class="summary-subtext">
                ${this.flow?.agent_type
            ? html `Agent: <sl-badge>${this.flow.agent_type}</sl-badge>`
            : this.getTriggerSource()}
              </div>
            </sl-card>
            <sl-card>
              <div slot="header"><sl-icon name="clock"></sl-icon> Timing</div>
              <sl-tooltip
                content=${formatUTCDateTime(this.execution.start_time)}
              >
                <div class="summary-value">
                  <sl-relative-time
                    date=${parseUTCDate(this.execution.start_time).toISOString()}
                  ></sl-relative-time>
                </div>
              </sl-tooltip>
              <div class="summary-subtext">
                ${this.execution.end_time
            ? calculateDuration(this.execution.start_time, this.execution.end_time)
            : 'Running'}
              </div>
            </sl-card>
            <sl-card>
              <div slot="header">
                <sl-icon name="${this.getTriggerIcon()}"></sl-icon> Trigger
              </div>
              <div class="summary-value">${this.getTriggerSource()}</div>
              <div class="summary-subtext">
                ${this.execution.agent_session_reference
            ? html `Session: <code
                      >${this.execution.agent_session_reference.slice(0, 12)}...</code
                    >`
            : 'Flow-triggered run'}
              </div>
            </sl-card>
            <sl-card>
              <div slot="header">
                <sl-icon name="${this.hasPricing ? 'cash' : 'cpu'}"></sl-icon>
                ${this.hasPricing ? 'Cost' : 'Tokens'}
              </div>
              <div class="summary-value">
                ${this.hasPricing
            ? html `$${this.budgetUsed.toFixed(2)}`
            : this.totalTokens.toLocaleString()}
              </div>
              <div class="summary-subtext">
                ${this.hasPricing
            ? `${this.totalTokens.toLocaleString()} tokens`
            : `${this.getTotalToolCallCount().toLocaleString()} tool calls recorded`}
              </div>
            </sl-card>
          </div>

          <!-- Trigger Event Details (collapsible) -->
          ${this.execution.trigger_event_details
            ? html `
                <sl-details
                  summary="Trigger Event"
                  style="margin-bottom: 16px;"
                >
                  <sl-card>
                    <pre
                      style="white-space: pre-wrap; word-wrap: break-word; margin: 0; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 12px; line-height: 1.4; background: var(--sl-color-neutral-100); padding: 12px; border-radius: 4px; max-height: 400px; overflow-y: auto;"
                    >
${JSON.stringify(this.execution.trigger_event_details, null, 2)}</pre
                    >
                  </sl-card>
                </sl-details>
              `
            : ''}

          <!-- Resolved Input Prompt (collapsible) -->
          ${this.execution.resolved_input_prompt
            ? html `
                <sl-details
                  summary="Resolved Input Prompt"
                  style="margin-bottom: 16px;"
                >
                  <sl-card>
                    <pre
                      style="white-space: pre-wrap; word-wrap: break-word; margin: 0; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 13px; line-height: 1.5; background: var(--sl-color-neutral-100); padding: 12px; border-radius: 4px;"
                    >
${this.execution.resolved_input_prompt}</pre
                    >
                  </sl-card>
                </sl-details>
              `
            : ''}
          <sl-tab-group class="execution-tabs">
            <sl-tab slot="nav" panel="output">Output</sl-tab>
            <sl-tab slot="nav" panel="gateway-events">Gateway Events</sl-tab>

            <sl-tab-panel name="output">
              <div class="output-workspace">
                <div class="output-main">
                  <sl-card>
                    <div
                      slot="header"
                      style="display: flex; justify-content: space-between; align-items: center;"
                    >
                      <span>
                        <sl-icon name="terminal"></sl-icon>
                        Output
                      </span>
                      ${isRunning
            ? html `
                            <div class="controls">
                              <sl-button-group>
                                <sl-button
                                  size="small"
                                  variant=${this.isAutoScroll
                ? 'primary'
                : 'default'}
                                  @click=${() => (this.isAutoScroll = !this.isAutoScroll)}
                                >
                                  <sl-icon name="arrow-down"></sl-icon>
                                  Auto-scroll
                                </sl-button>
                                <sl-button
                                  size="small"
                                  variant="danger"
                                  @click=${this.stopExecution}
                                >
                                  <sl-icon name="stop-circle"></sl-icon>
                                  Stop
                                </sl-button>
                              </sl-button-group>
                            </div>
                          `
            : ''}
                    </div>

                    <div class="log-container">
                      ${this.logs.length === 0
            ? html `
                            <div class="empty-logs">
                              <sl-icon
                                name="inbox"
                                style="font-size: 3rem;"
                              ></sl-icon>
                              <p>Waiting for logs...</p>
                            </div>
                          `
            : this.logs.map((log) => this.renderLogEntry(log))}
                      ${isRunning
            ? html `
                            <div class="loading-indicator">
                              <div class="loading-dots">
                                <span></span>
                                <span></span>
                                <span></span>
                              </div>
                            </div>
                          `
            : ''}
                    </div>

                    ${isRunning
            ? html `
                          <div class="terminal-input">
                            <sl-input
                              placeholder="Enter command (e.g., 'pause', 'message: Hello')"
                              .value=${this.commandInput}
                              @input=${(e) => (this.commandInput = e.target.value)}
                              @keydown=${this.handleInputKeydown}
                              style="flex: 1;"
                            >
                              <sl-icon name="terminal" slot="prefix"></sl-icon>
                            </sl-input>
                            <sl-button
                              variant="primary"
                              ?loading=${this.isSendingCommand}
                              @click=${this.sendCommand}
                            >
                              <sl-icon name="send"></sl-icon>
                              Send
                            </sl-button>
                          </div>
                        `
            : ''}
                  </sl-card>
                </div>

                <aside class="output-sidebar">
                  ${this.renderExecutionMetadataSidebar()}
                  ${this.renderToolActivitySidebar()}
                </aside>
              </div>
            </sl-tab-panel>

            <sl-tab-panel name="gateway-events">
              ${this.renderGatewayEventsPanel()}
            </sl-tab-panel>
          </sl-tab-group>

          ${this.execution.error_message
            ? html `
                <sl-card>
                  <div slot="header" style="color: var(--sl-color-danger-600);">
                    <sl-icon name="exclamation-triangle"></sl-icon>
                    Error
                  </div>
                  <sl-alert variant="danger" open>
                    <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                    <pre
                      style="white-space: pre-wrap; word-wrap: break-word; margin: 0;"
                    >
${this.execution.error_message}</pre
                    >
                  </sl-alert>
                </sl-card>
              `
            : ''}
        </div>
      </div>
    `;
    }
    renderLogEntry(log) {
        const time = formatLocalTime(log.timestamp);
        // For model output (summary), show as a highlighted section
        if (log.type === 'model_output') {
            return html `
        <div class="log-entry log-metadata" style="border-left-color: #b5cea8;">
          <span class="log-timestamp">${time}</span>
          <span class="log-type log-type-success">[Summary]</span>
          <div class="log-content" style="margin-top: 8px;">
            <pre
              style="white-space: pre-wrap; word-wrap: break-word; margin: 0; color: #b5cea8;"
            >
${log.payload.content}</pre
            >
          </div>
        </div>
      `;
        }
        // For log lines, show timestamp + content
        if (log.type === 'agent_log_line') {
            const content = log.payload.line || log.payload.message || log.payload.content || '';
            const stream = log.payload.stream || 'stdout';
            const streamClass = stream === 'stderr' ? 'log-stderr' : '';
            // Check for Kubernetes status messages (pod initializing, etc.)
            // These are JSON objects with "kind":"Status" - display a friendly message instead
            if (content.startsWith('{"kind":"Status"')) {
                try {
                    const statusObj = JSON.parse(content);
                    // Show a friendly message for pod initialization
                    if (statusObj.reason === 'BadRequest' &&
                        statusObj.message?.includes('PodInitializing')) {
                        return html `
              <div
                class="log-entry log-metadata"
                style="border-left-color: #dcdcaa;"
              >
                <span class="log-timestamp">${time}</span>
                <span class="log-type log-type-warning">[Initializing]</span>
                <span>Container is starting up, please wait...</span>
              </div>
            `;
                    }
                    // For other status messages, show a condensed version
                    if (statusObj.message) {
                        return html `
              <div
                class="log-entry log-metadata"
                style="border-left-color: #858585;"
              >
                <span class="log-timestamp">${time}</span>
                <span class="log-type">[K8s Status]</span>
                <span>${statusObj.message}</span>
              </div>
            `;
                    }
                }
                catch {
                    // Not valid JSON, fall through to regular display
                }
            }
            return html `
        <div class="log-entry ${streamClass}">
          <span class="log-timestamp">${time}</span>
          <span class="log-content">${content}</span>
        </div>
      `;
        }
        // For metadata/status updates, show with different styling
        const typeClass = this.getLogTypeClass(log.type);
        const message = this.formatMetadataMessage(log);
        return html `
      <div class="log-entry log-metadata">
        <span class="log-timestamp">${time}</span>
        <span class="log-type ${typeClass}"
          >[${this.formatLogType(log.type)}]</span
        >
        <span>${message}</span>
      </div>
    `;
    }
    formatLogType(type) {
        // Convert snake_case to Title Case
        return type
            .split('_')
            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }
    formatMetadataMessage(log) {
        if (typeof log.payload === 'string') {
            return log.payload;
        }
        switch (log.type) {
            case 'status_update':
                return `Status: ${log.payload.status}`;
            case 'connected':
                return log.payload.message || 'Connected to execution stream';
            case 'agent_started':
                return 'Agent session started';
            case 'agent_stopped':
                return 'Agent session stopped';
            case 'tool_call':
            case 'mcp_call':
                return `Called tool: ${this.normalizeToolActivityEntry(log.payload, log.timestamp)?.toolName ||
                    'structured MCP call'}`;
            case 'budget_update':
                return `Budget used: $${log.payload.budget_used?.toFixed(2) || '0.00'}`;
            default:
                return log.payload.message || JSON.stringify(log.payload);
        }
    }
    getLogTypeClass(type) {
        if (type.includes('error') || type.includes('fail')) {
            return 'log-type-error';
        }
        if (type.includes('success') || type.includes('complete')) {
            return 'log-type-success';
        }
        if (type.includes('warning') || type.includes('warn')) {
            return 'log-type-warning';
        }
        return '';
    }
    async sendCommand() {
        if (!this.commandInput.trim() || !this.executionId)
            return;
        this.isSendingCommand = true;
        try {
            const input = this.commandInput.trim();
            let commandData = {};
            // Parse command: "message: hello" -> { command: "send_message", message: "hello" }
            if (input.includes(':')) {
                const [cmd, ...rest] = input.split(':');
                const command = cmd.trim();
                const message = rest.join(':').trim();
                if (command === 'message') {
                    commandData = { command: 'send_message', message };
                }
                else {
                    commandData = { command, payload: message };
                }
            }
            else {
                // Simple command like "stop" or "pause"
                commandData = { command: input };
            }
            // Send command via WebSocket
            unifiedWebSocketManager.send({
                type: 'command',
                execution_id: this.executionId,
                ...commandData,
            });
            // Add command to logs for user feedback
            this.logs = [
                ...this.logs,
                {
                    execution_id: this.executionId,
                    timestamp: new Date().toISOString(),
                    type: 'user_command',
                    payload: { command: commandData.command },
                },
            ];
            this.commandInput = '';
        }
        catch (error) {
            console.error('Failed to send command:', error);
            // TODO: Show error notification
        }
        finally {
            this.isSendingCommand = false;
        }
    }
    handleInputKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendCommand();
        }
    }
    async stopExecution() {
        if (!this.executionId)
            return;
        try {
            // Send stop command to backend (which stops the container directly)
            await sendCommandToExecution(this.executionId, 'stop');
            // Wait a moment for the container to stop
            await new Promise((resolve) => setTimeout(resolve, 500));
            // Refresh execution details to get updated status
            this.execution = await getFlowExecution(this.executionId);
            // Fetch final logs from the stopped container
            try {
                const logsResponse = await getFlowExecutionLogs(this.executionId);
                if (logsResponse.logs && Array.isArray(logsResponse.logs)) {
                    this.logs = logsResponse.logs;
                    console.log(`Loaded ${logsResponse.logs.length} logs after stop from ${logsResponse.source}`);
                }
            }
            catch (error) {
                console.error('Failed to fetch logs after stop:', error);
            }
            // Stop auto-scroll checker and flush remaining buffer
            this.stopAutoScrollChecker();
            this.stopBufferFlush();
            this.isAutoScroll = false;
            // Force UI update
            this.requestUpdate();
        }
        catch (error) {
            console.error('Failed to stop execution:', error);
            // TODO: Show error notification to user
        }
    }
    canRetry() {
        if (!this.execution)
            return false;
        const retryableStatuses = ['FAILED', 'STOPPED', 'TIMEOUT', 'CANCELLED'];
        return retryableStatuses.includes(this.execution.status);
    }
    async retryExecution() {
        if (!this.executionId)
            return;
        try {
            this.isRetrying = true;
            const result = await retryFlowExecution(this.executionId);
            // Navigate to the new execution
            // Backend returns { id, status, flow_id }
            if (result.id) {
                window.location.href = `/console/flows/executions/${result.id}`;
            }
        }
        catch (error) {
            console.error('Failed to retry execution:', error);
            // Show error message
            const message = error instanceof Error ? error.message : 'Failed to retry execution';
            alert(message); // TODO: Use proper notification
        }
        finally {
            this.isRetrying = false;
        }
    }
    getStatusVariant(status) {
        switch (status) {
            case 'SUCCEEDED':
                return 'success';
            case 'FAILED':
                return 'danger';
            case 'RUNNING':
                return 'primary';
            default:
                return 'neutral';
        }
    }
};
FlowExecutionView.styles = [
    unsafeCSS(consoleStyles),
    css `
      :host {
        display: block;
      }
      .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        margin-bottom: 16px;
      }
      .summary-value {
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--sl-color-neutral-900);
        overflow-wrap: anywhere;
      }
      .summary-subtext {
        margin-top: 6px;
        color: var(--sl-color-neutral-600);
        font-size: 0.875rem;
      }
      .execution-tabs {
        margin-bottom: 16px;
      }
      .output-workspace {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .output-main {
        min-width: 0;
      }
      .output-sidebar {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .output-sidebar-card {
        min-width: 0;
      }
      .execution-metadata-list {
        display: grid;
        grid-template-columns: minmax(110px, auto) minmax(0, 1fr);
        gap: 10px 12px;
        align-items: start;
        font-size: 0.95rem;
      }
      .execution-metadata-label {
        color: var(--sl-color-neutral-600);
        font-weight: 600;
      }
      .execution-metadata-value {
        min-width: 0;
        overflow-wrap: anywhere;
      }
      .execution-metadata-value code {
        font-size: 0.85em;
      }
      .output-sidebar .tool-activity-list {
        max-height: 520px;
        overflow-y: auto;
        padding-right: 4px;
      }
      .log-container {
        background-color: #1e1e1e;
        color: #d4d4d4;
        border: 1px solid var(--sl-color-neutral-300);
        border-radius: 4px;
        padding: 16px;
        height: 500px;
        overflow-y: auto;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
        font-size: 13px;
        line-height: 1.5;
      }
      .log-container::-webkit-scrollbar {
        width: 8px;
      }
      .log-container::-webkit-scrollbar-track {
        background: #2d2d2d;
      }
      .log-container::-webkit-scrollbar-thumb {
        background: #555;
        border-radius: 4px;
      }
      .log-container::-webkit-scrollbar-thumb:hover {
        background: #666;
      }
      .loading-indicator {
        display: flex;
        align-items: center;
        color: #858585;
        font-size: 13px;
        height: 20px;
      }
      .loading-dots {
        display: inline-flex;
        gap: 4px;
      }
      .loading-dots span {
        width: 6px;
        height: 6px;
        background-color: #858585;
        border-radius: 50%;
        animation: loadingDot 1.4s infinite ease-in-out both;
      }
      .loading-dots span:nth-child(1) {
        animation-delay: -0.32s;
      }
      .loading-dots span:nth-child(2) {
        animation-delay: -0.16s;
      }
      .loading-dots span:nth-child(3) {
        animation-delay: 0s;
      }
      @keyframes loadingDot {
        0%,
        80%,
        100% {
          transform: scale(0.6);
          opacity: 0.5;
        }
        40% {
          transform: scale(1);
          opacity: 1;
        }
      }
      .log-entry {
        display: flex;
        margin-bottom: 4px;
        animation: fadeIn 0.2s ease-in;
        line-height: 1.5;
      }
      @keyframes fadeIn {
        from {
          opacity: 0;
        }
        to {
          opacity: 1;
        }
      }
      .log-timestamp {
        color: #858585;
        margin-right: 12px;
        user-select: none;
        -webkit-user-select: none;
        -moz-user-select: none;
        min-width: 90px;
        flex-shrink: 0;
      }
      .log-type {
        color: #4ec9b0;
        font-weight: 600;
        margin-right: 8px;
      }
      .log-type-error {
        color: #f48771;
      }
      .log-type-success {
        color: #b5cea8;
      }
      .log-type-warning {
        color: #dcdcaa;
      }
      .log-stderr {
        color: #f48771;
      }
      .log-metadata {
        background-color: #2d2d30;
        border-left: 3px solid #4ec9b0;
        padding-left: 8px;
      }
      .log-content {
        white-space: pre-wrap;
        word-wrap: break-word;
        flex: 1;
        overflow-wrap: break-word;
      }
      .terminal-input {
        display: flex;
        gap: 8px;
        margin-top: 12px;
      }
      .controls {
        display: flex;
        gap: 8px;
        margin-bottom: 12px;
      }
      .empty-logs {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: #858585;
        gap: 12px;
      }
      .gateway-events-panel {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .gateway-panel-intro {
        color: var(--sl-color-neutral-600);
        font-size: 0.875rem;
        line-height: 1.5;
      }
      .search-summary {
        color: var(--sl-color-neutral-600);
        font-size: 0.875rem;
      }
      .gateway-events-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .gateway-event-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 240px;
        gap: 12px;
        color: var(--sl-color-neutral-600);
        border: 1px dashed var(--sl-color-neutral-300);
        border-radius: var(--sl-border-radius-medium);
        background: var(--sl-color-neutral-50);
      }
      .gateway-event {
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        background: var(--sl-color-neutral-0);
      }
      .gateway-event::part(summary) {
        padding: 16px;
      }
      .gateway-event::part(content) {
        border-top: 1px solid var(--sl-color-neutral-200);
        padding: 16px;
        background: var(--sl-color-neutral-50);
      }
      .gateway-event-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 12px;
        align-items: center;
        width: 100%;
        padding-right: 12px;
      }
      .gateway-event-field {
        min-width: 0;
      }
      .gateway-event-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--sl-color-neutral-600);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 4px;
      }
      .gateway-event-value {
        font-size: 0.95rem;
        font-weight: 500;
        color: var(--sl-color-neutral-900);
        overflow-wrap: anywhere;
      }
      .gateway-event-meta {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-bottom: 16px;
      }
      .payload-section-title {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--sl-color-neutral-700);
        margin-bottom: 8px;
      }
      .payload-block {
        background: var(--sl-color-neutral-100);
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        padding: 12px;
        max-height: 360px;
        overflow: auto;
      }
      .payload-block pre {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
        font-size: 12px;
        line-height: 1.5;
      }
      .gateway-capture-policy {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-bottom: 16px;
      }
      .gateway-capture-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 12px;
      }
      .gateway-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .conversation-preview-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-bottom: 16px;
      }
      .conversation-preview-message {
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        background: var(--sl-color-neutral-100);
        padding: 12px;
      }
      .conversation-preview-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 8px;
      }
      .conversation-preview-title {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--sl-color-neutral-800);
      }
      .conversation-preview-text {
        margin: 0;
        white-space: pre-wrap;
        word-break: break-word;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
        font-size: 12px;
        line-height: 1.5;
        color: var(--sl-color-neutral-900);
      }
      .conversation-preview-redacted {
        color: var(--sl-color-neutral-600);
      }
      .tool-activity-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .tool-activity-item {
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        background: var(--sl-color-neutral-50);
        padding: 12px;
      }
      .tool-activity-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
        flex-wrap: wrap;
        margin-bottom: 8px;
      }
      .tool-activity-title {
        font-weight: 600;
        color: var(--sl-color-neutral-900);
      }
      .tool-activity-meta {
        color: var(--sl-color-neutral-600);
        font-size: 0.875rem;
        overflow-wrap: anywhere;
      }
      .tool-activity-note {
        margin-top: 12px;
        color: var(--sl-color-neutral-600);
        font-size: 0.875rem;
      }
      .tool-activity-empty {
        color: var(--sl-color-neutral-600);
        font-size: 0.95rem;
        line-height: 1.5;
      }
      @media (min-width: 1500px) {
        .output-workspace {
          display: grid;
          grid-template-columns: minmax(0, 2fr) minmax(320px, 420px);
          align-items: start;
        }
        .output-sidebar {
          position: sticky;
          top: 16px;
        }
      }
    `,
];
__decorate([
    property()
], FlowExecutionView.prototype, "executionId", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "execution", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "flow", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "logs", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "gatewayEvents", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "gatewayEventsSource", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "gatewayEventsError", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "gatewaySearchQuery", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "isLoadingGatewayEvents", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "toolCalls", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "budgetUsed", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "totalTokens", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "hasPricing", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "commandInput", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "isAutoScroll", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "isSendingCommand", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "loadingError", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "isLoading", void 0);
__decorate([
    state()
], FlowExecutionView.prototype, "isRetrying", void 0);
FlowExecutionView = __decorate([
    customElement('flow-execution-view')
], FlowExecutionView);
export { FlowExecutionView };
