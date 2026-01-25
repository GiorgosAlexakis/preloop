import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import consoleStyles from '../../styles/console-styles.css?inline';
import {
  getFlowExecution,
  getFlow,
  sendCommandToExecution,
  getFlowExecutionMetrics,
  getFlowExecutionLogs,
} from '../../api';
import {
  parseUTCDate,
  formatLocalTime,
  formatUTCDateTime,
  calculateDuration,
} from '../../utils/date';
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

interface FlowExecutionUpdate {
  execution_id: string;
  timestamp: string;
  type: string;
  payload: any;
}

interface FlowExecution {
  id: string;
  flow_id: string;
  status: string;
  start_time: string;
  end_time?: string;
  actions_taken_summary?: any[];
  model_output_summary?: string;
  resolved_input_prompt?: string;
  trigger_event_details?: any;
  trigger_event_id?: string;
  agent_session_reference?: string;
  error_message?: string;
  execution_logs?: FlowExecutionUpdate[];
}

interface Flow {
  id: string;
  name: string;
  description?: string;
  agent_type: string;
  trigger_event_source: string;
  trigger_event_type: string;
}

@customElement('flow-execution-view')
export class FlowExecutionView extends LitElement {
  // Vaadin Router lifecycle callback
  onBeforeEnter(location: any) {
    this.executionId = location.params.executionId;
  }

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      :host {
        display: block;
      }
      .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        margin-bottom: 16px;
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
    `,
  ];

  @property()
  executionId?: string;

  @state()
  private execution: FlowExecution | null = null;

  @state()
  private flow: Flow | null = null;

  @state()
  private logs: FlowExecutionUpdate[] = [];

  @state()
  private toolCalls = 0;

  @state()
  private budgetUsed = 0;

  @state()
  private totalTokens = 0;

  @state()
  private hasPricing = false;

  @state()
  private commandInput = '';

  @state()
  private isAutoScroll = true;

  @state()
  private isSendingCommand = false;

  @state()
  private loadingError: string | null = null;

  @state()
  private isLoading = false;

  private logContainerRef?: HTMLElement;
  private wsConnected = false;
  private autoScrollInterval?: number;
  private unsubscribe?: () => void;

  disconnectedCallback() {
    super.disconnectedCallback();
    // Clean up auto-scroll interval when component is removed
    if (this.autoScrollInterval) {
      clearInterval(this.autoScrollInterval);
      this.autoScrollInterval = undefined;
    }
    // Unsubscribe from WebSocket
    this.unsubscribe?.();
  }

  async updated(changedProperties: Map<string, any>) {
    super.updated(changedProperties);

    // When executionId property changes, fetch execution data
    if (
      changedProperties.has('executionId') &&
      this.executionId &&
      !this.wsConnected
    ) {
      // First, fetch execution data (which loads persisted logs)
      await this.fetchExecution();

      console.log(`After fetchExecution, logs.length = ${this.logs.length}`);
      console.log(`Execution status: ${this.execution?.status}`);
      console.log(
        `Has model_output_summary: ${!!this.execution?.model_output_summary}`
      );
      if (this.execution?.model_output_summary) {
        console.log(
          `model_output_summary length: ${this.execution.model_output_summary.length} chars`
        );
      }

      // Check if execution is still running
      const isRunning =
        this.execution &&
        (this.execution.status === 'RUNNING' ||
          this.execution.status === 'STARTING' ||
          this.execution.status === 'INITIALIZING' ||
          this.execution.status === 'PENDING');

      console.log(`isRunning: ${isRunning}`);

      // If finished, show model_output_summary in logs
      if (!isRunning && this.execution?.model_output_summary) {
        console.log(
          'Adding model_output_summary to logs (execution finished on page load)'
        );
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
      } else {
        console.log(
          `Not adding model_output: isRunning=${isRunning}, has_summary=${!!this.execution?.model_output_summary}`
        );
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

        // Subscribe to flow execution updates for this specific execution
        this.unsubscribe = unifiedWebSocketManager.subscribe(
          'flow_executions',
          (message: any) => this.handleWebSocketMessage(message),
          // Filter to only receive messages for this execution
          (message: any) => message.execution_id === this.executionId
        );

        // Track connection state
        unifiedWebSocketManager.onStateChange((state) => {
          const wasConnected = this.wsConnected;
          this.wsConnected = state === 'connected';

          // Add connection log if this is initial connection
          if (
            state === 'connected' &&
            !wasConnected &&
            this.logs.length === 0
          ) {
            console.log('Adding connection log message');
            this.logs = [
              {
                execution_id: this.executionId!,
                timestamp: new Date().toISOString(),
                type: 'connected',
                payload: { message: 'Connected to flow execution stream' },
              },
            ];
          }

          // Stop auto-scroll when disconnected
          if (state !== 'connected') {
            this.stopAutoScrollChecker();
          }
        });
      } else {
        console.log(
          'Execution is finished, not connecting to WebSocket stream'
        );
      }
    }
  }

  private handleWebSocketMessage(message: any) {
    console.log('WebSocket message:', message);

    // Handle connection confirmation
    if (message.type === 'connected') {
      return; // Already handled in onOpen callback
    }

    // Handle NATS forwarded messages
    if (message.execution_id === this.executionId) {
      this.logs = [...this.logs, message];

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
          const wasRunning =
            previousStatus === 'RUNNING' ||
            previousStatus === 'STARTING' ||
            previousStatus === 'INITIALIZING' ||
            previousStatus === 'PENDING';
          const isNowFinished =
            this.execution.status !== 'RUNNING' &&
            this.execution.status !== 'STARTING' &&
            this.execution.status !== 'INITIALIZING' &&
            this.execution.status !== 'PENDING';

          // If execution just finished, add the model output to logs
          if (wasRunning && isNowFinished) {
            // Check if we haven't already added it
            const hasModelOutput = this.logs.some(
              (log) => log.type === 'model_output'
            );
            if (!hasModelOutput) {
              this.logs = [
                ...this.logs,
                {
                  execution_id: this.executionId!,
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

      // Handle agent log lines
      if (message.type === 'agent_log_line') {
        // Log lines are already added to this.logs above
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
      if (message.type === 'token_usage_update') {
        this.totalTokens = message.payload.total_tokens || 0;
      }

      // Track budget usage
      if (message.type === 'budget_update') {
        this.budgetUsed = message.payload.budget_used || 0;
      }

      // Auto-scroll to bottom when new log arrives
      if (this.isAutoScroll) {
        this.scrollToBottom();
      }
    }
  }

  startAutoScrollChecker() {
    // Clear any existing interval
    this.stopAutoScrollChecker();

    this.logContainerRef = this.shadowRoot?.querySelector(
      '.log-container'
    ) as HTMLElement;
    this.logContainerRef.addEventListener('scroll', () => this.handleScroll());
    // Check scroll position every 200ms and force scroll if auto-scroll is enabled
    this.autoScrollInterval = window.setInterval(() => {
      if (this.isAutoScroll && this.logContainerRef) {
        const { scrollTop, scrollHeight, clientHeight } = this.logContainerRef;
        const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;

        // If not at bottom, force scroll
        if (!isAtBottom) {
          this.logContainerRef.scrollTop = this.logContainerRef.scrollHeight;
        }
      }
    }, 200);
  }

  stopAutoScrollChecker() {
    if (this.autoScrollInterval) {
      clearInterval(this.autoScrollInterval);
      this.autoScrollInterval = undefined;
    }
  }

  scrollToBottom() {
    if (this.logContainerRef) {
      this.logContainerRef.scrollTop = this.logContainerRef.scrollHeight;
    }
  }

  handleScroll() {
    if (!this.logContainerRef) return;

    // Check if user scrolled away from bottom
    const { scrollTop, scrollHeight, clientHeight } = this.logContainerRef;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50; // 50px threshold

    // Disable auto-scroll when user manually scrolls away from bottom
    if (!isAtBottom && this.isAutoScroll) {
      console.log('User scrolled away from bottom, disabling auto-scroll');
      this.isAutoScroll = false;
    } else if (isAtBottom && !this.isAutoScroll) {
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
    if (!this.executionId) return;

    try {
      this.isLoading = true;
      this.loadingError = null;

      // Fetch execution details
      this.execution = await getFlowExecution(this.executionId);

      // Fetch logs from container (if running) or database (if finished)
      // This ensures we get all historical logs, even for running executions
      try {
        const logsResponse = await getFlowExecutionLogs(this.executionId);
        if (logsResponse.logs && Array.isArray(logsResponse.logs)) {
          console.log(
            `Loaded ${logsResponse.logs.length} logs from ${logsResponse.source}`
          );
          this.logs = logsResponse.logs;
        } else {
          console.log('No logs found in response');
        }
      } catch (error) {
        console.error('Failed to fetch logs:', error);
        // Fallback to execution_logs from database if available
        if (
          this.execution &&
          this.execution.execution_logs &&
          Array.isArray(this.execution.execution_logs)
        ) {
          console.log(
            `Using fallback: Loaded ${this.execution.execution_logs.length} persisted logs from database`
          );
          this.logs = this.execution.execution_logs;
        } else {
          console.log('No fallback logs available');
        }
      }

      // Fetch flow details
      if (this.execution && this.execution.flow_id) {
        try {
          this.flow = await getFlow(this.execution.flow_id);
        } catch (error) {
          console.error('Failed to fetch flow details:', error);
          // Don't fail the whole page if flow fetch fails
        }
      }

      // Fetch execution metrics (for completed executions)
      if (
        this.execution &&
        ['COMPLETED', 'FAILED', 'STOPPED', 'TIMEOUT'].includes(
          this.execution.status
        )
      ) {
        try {
          const metrics = await getFlowExecutionMetrics(this.executionId);
          this.toolCalls = metrics.tool_calls;
          this.budgetUsed = metrics.estimated_cost;
          this.totalTokens = metrics.token_usage.total_tokens;
          this.hasPricing = metrics.has_pricing;
          console.log('Loaded execution metrics:', metrics);
        } catch (error) {
          console.error('Failed to fetch execution metrics:', error);
          // Don't fail the whole page if metrics fetch fails
        }
      }

      this.isLoading = false;
    } catch (error) {
      console.error('Failed to fetch execution:', error);
      this.loadingError =
        error instanceof Error
          ? error.message
          : 'Failed to load execution details';
      this.isLoading = false;
    }
  }

  getTriggerSource(): string {
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

  getTriggerIcon(): string {
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

  render() {
    // Waiting for router to set executionId
    if (!this.executionId) {
      return html`
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
      return html`
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
      return html`
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

    const isRunning =
      this.execution.status === 'RUNNING' ||
      this.execution.status === 'STARTING' ||
      this.execution.status === 'INITIALIZING';

    return html`
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
              ? html`
                  <sl-button size="small" href="/console/flows/${this.flow.id}">
                    <sl-icon name="diagram-3"></sl-icon>
                    View Flow
                  </sl-button>
                `
              : ''}
          </div>

          <!-- Execution Metadata Card -->
          <sl-card style="margin-bottom: 16px;">
            <div slot="header">
              <sl-icon name="info-circle"></sl-icon>
              Execution Details
            </div>
            <div
              style="display: grid; grid-template-columns: 150px 1fr; gap: 12px;"
            >
              <strong>Execution ID:</strong>
              <span>${this.execution.id}</span>

              ${this.flow
                ? html`
                    <strong>Flow:</strong>
                    <a href="/console/flows/${this.flow.id}"
                      >${this.flow.name}</a
                    >

                    <strong>Agent Type:</strong>
                    <sl-badge>${this.flow.agent_type}</sl-badge>
                  `
                : ''}

              <strong>Triggered By:</strong>
              <div style="display: flex; align-items: center; gap: 8px;">
                <sl-icon name="${this.getTriggerIcon()}"></sl-icon>
                ${this.getTriggerSource()}
              </div>

              <strong>Started:</strong>
              <sl-tooltip
                content=${formatUTCDateTime(this.execution.start_time)}
              >
                <sl-relative-time
                  date=${parseUTCDate(this.execution.start_time).toISOString()}
                ></sl-relative-time>
              </sl-tooltip>

              ${this.execution.end_time
                ? html`
                    <strong>Duration:</strong>
                    <span>
                      ${calculateDuration(
                        this.execution.start_time,
                        this.execution.end_time
                      )}
                    </span>
                  `
                : ''}
              ${this.execution.agent_session_reference
                ? html`
                    <strong>Session:</strong>
                    <code style="font-size: 0.85em;">
                      ${this.execution.agent_session_reference.slice(0, 12)}...
                    </code>
                  `
                : ''}
            </div>
          </sl-card>

          <!-- Status Grid -->
          <div class="summary-grid">
            <sl-card>
              <div slot="header">
                <sl-icon name="info-circle"></sl-icon> Status
              </div>
              <sl-badge variant=${this.getStatusVariant(this.execution.status)}
                >${this.execution.status}</sl-badge
              >
            </sl-card>
            <sl-card>
              <div slot="header"><sl-icon name="clock"></sl-icon> Started</div>
              <sl-tooltip
                content=${formatUTCDateTime(this.execution.start_time)}
              >
                <sl-relative-time
                  date=${parseUTCDate(this.execution.start_time).toISOString()}
                ></sl-relative-time>
              </sl-tooltip>
            </sl-card>
            <sl-card>
              <div slot="header">
                <sl-icon name="tools"></sl-icon> Tool Calls
              </div>
              ${this.toolCalls}
            </sl-card>
            <sl-card>
              <div slot="header">
                <sl-icon name="${this.hasPricing ? 'cash' : 'cpu'}"></sl-icon>
                ${this.hasPricing ? 'Budget' : 'Tokens Used'}
              </div>
              ${this.hasPricing
                ? html`
                    <div>
                      <div style="font-size: 1.2em; font-weight: bold;">
                        $${this.budgetUsed.toFixed(2)}
                      </div>
                      <div
                        style="font-size: 0.85em; color: var(--sl-color-neutral-600); margin-top: 4px;"
                      >
                        ${this.totalTokens.toLocaleString()} tokens
                      </div>
                    </div>
                  `
                : html` ${this.totalTokens.toLocaleString()} `}
            </sl-card>
          </div>

          <!-- Trigger Event Details (collapsible) -->
          ${this.execution.trigger_event_details
            ? html`
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
            ? html`
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
                ? html`
                    <div class="controls">
                      <sl-button-group>
                        <sl-button
                          size="small"
                          variant=${this.isAutoScroll ? 'primary' : 'default'}
                          @click=${() =>
                            (this.isAutoScroll = !this.isAutoScroll)}
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
                ? html`
                    <div class="empty-logs">
                      <sl-icon name="inbox" style="font-size: 3rem;"></sl-icon>
                      <p>Waiting for logs...</p>
                    </div>
                  `
                : this.logs.map((log) => this.renderLogEntry(log))}
            </div>

            ${isRunning
              ? html`
                  <div class="terminal-input">
                    <sl-input
                      placeholder="Enter command (e.g., 'pause', 'message: Hello')"
                      .value=${this.commandInput}
                      @input=${(e: any) => (this.commandInput = e.target.value)}
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

          ${this.execution.error_message
            ? html`
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

  renderLogEntry(log: FlowExecutionUpdate) {
    const time = formatLocalTime(log.timestamp);

    // For model output (summary), show as a highlighted section
    if (log.type === 'model_output') {
      return html`
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
      const content =
        log.payload.line || log.payload.message || log.payload.content || '';
      const stream = log.payload.stream || 'stdout';
      const streamClass = stream === 'stderr' ? 'log-stderr' : '';

      return html`
        <div class="log-entry ${streamClass}">
          <span class="log-timestamp">${time}</span>
          <span class="log-content">${content}</span>
        </div>
      `;
    }

    // For metadata/status updates, show with different styling
    const typeClass = this.getLogTypeClass(log.type);
    const message = this.formatMetadataMessage(log);

    return html`
      <div class="log-entry log-metadata">
        <span class="log-timestamp">${time}</span>
        <span class="log-type ${typeClass}"
          >[${this.formatLogType(log.type)}]</span
        >
        <span>${message}</span>
      </div>
    `;
  }

  formatLogType(type: string): string {
    // Convert snake_case to Title Case
    return type
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  formatMetadataMessage(log: FlowExecutionUpdate): string {
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
        return `Called tool: ${log.payload.tool_name || 'unknown'}`;
      case 'budget_update':
        return `Budget used: $${log.payload.budget_used?.toFixed(2) || '0.00'}`;
      default:
        return log.payload.message || JSON.stringify(log.payload);
    }
  }

  getLogTypeClass(type: string): string {
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
    if (!this.commandInput.trim() || !this.executionId) return;

    this.isSendingCommand = true;
    try {
      const input = this.commandInput.trim();
      let commandData: any = {};

      // Parse command: "message: hello" -> { command: "send_message", message: "hello" }
      if (input.includes(':')) {
        const [cmd, ...rest] = input.split(':');
        const command = cmd.trim();
        const message = rest.join(':').trim();

        if (command === 'message') {
          commandData = { command: 'send_message', message };
        } else {
          commandData = { command, payload: message };
        }
      } else {
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
    } catch (error) {
      console.error('Failed to send command:', error);
      // TODO: Show error notification
    } finally {
      this.isSendingCommand = false;
    }
  }

  handleInputKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.sendCommand();
    }
  }

  async stopExecution() {
    if (!this.executionId) return;

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
          console.log(
            `Loaded ${logsResponse.logs.length} logs after stop from ${logsResponse.source}`
          );
        }
      } catch (error) {
        console.error('Failed to fetch logs after stop:', error);
      }

      // Stop auto-scroll checker
      this.stopAutoScrollChecker();
      this.isAutoScroll = false;

      // Force UI update
      this.requestUpdate();
    } catch (error) {
      console.error('Failed to stop execution:', error);
      // TODO: Show error notification to user
    }
  }

  getStatusVariant(status: string) {
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
}
