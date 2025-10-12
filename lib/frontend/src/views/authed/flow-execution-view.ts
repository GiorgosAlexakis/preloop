import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { webSocketService } from '../../services/websocket-service';
import { getFlowExecution, getFlow, sendCommandToExecution } from '../../api';
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

  static styles = css`
    :host {
      display: block;
      padding: 16px;
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
  `;

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

  async updated(changedProperties: Map<string, any>) {
    super.updated(changedProperties);

    // When executionId property changes, fetch execution data and connect WebSocket
    if (
      changedProperties.has('executionId') &&
      this.executionId &&
      !this.wsConnected
    ) {
      // First, fetch execution data (which loads persisted logs)
      await this.fetchExecution();

      console.log(`After fetchExecution, logs.length = ${this.logs.length}`);

      // Scroll to bottom after logs are loaded
      if (this.logs.length > 0 && this.isAutoScroll) {
        this.scrollToBottom();
      }

      // Then connect to WebSocket for live updates
      this.wsConnected = true;
      webSocketService.connectToExecution(
        this.executionId,
        (message: any) => this.handleWebSocketMessage(message),
        () => {
          console.log(
            `Connected to execution WebSocket, logs.length = ${this.logs.length}`
          );
          // Only add connection log if this is a live execution (no persisted logs)
          if (this.logs.length === 0) {
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
        },
        () => {
          console.log('Disconnected from execution WebSocket');
          this.wsConnected = false;
        }
      );
    }

    // Auto-scroll to bottom when new log arrives
    if (changedProperties.has('logs') && this.isAutoScroll) {
      this.scrollToBottom();
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

  scrollToBottom() {
    requestAnimationFrame(() => {
      if (this.logContainerRef) {
        this.logContainerRef.scrollTop = this.logContainerRef.scrollHeight;
      }
    });
  }

  handleScroll() {
    if (!this.logContainerRef) return;

    // Check if user scrolled away from bottom
    const { scrollTop, scrollHeight, clientHeight } = this.logContainerRef;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 10; // 10px threshold

    // If user manually scrolled away from bottom, disable auto-scroll
    if (!isAtBottom && this.isAutoScroll) {
      this.isAutoScroll = false;
    }
    // If user manually scrolled back to bottom, enable auto-scroll
    else if (isAtBottom && !this.isAutoScroll) {
      this.isAutoScroll = true;
    }
  }

  async fetchExecution() {
    if (!this.executionId) return;

    try {
      this.isLoading = true;
      this.loadingError = null;

      // Fetch execution details
      this.execution = await getFlowExecution(this.executionId);

      // Load persisted logs if available
      if (
        this.execution &&
        this.execution.execution_logs &&
        Array.isArray(this.execution.execution_logs)
      ) {
        console.log(
          `Loaded ${this.execution.execution_logs.length} persisted logs from database`
        );
        this.logs = this.execution.execution_logs;
      } else {
        console.log('No persisted logs found in execution');
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

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.executionId) {
      webSocketService.disconnectFromExecution(this.executionId);
    }
  }

  render() {
    // Waiting for router to set executionId
    if (!this.executionId) {
      return html`
        <view-header headerText="Flow Execution"></view-header>
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
        <view-header headerText="Flow Execution"></view-header>
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
        <view-header headerText="Flow Execution"></view-header>
        <div class="column-layout">
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
      ></view-header>
      <div class="column-layout">
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
              <sl-relative-time
                date=${this.execution.start_time}
              ></sl-relative-time>

              ${this.execution.end_time
                ? html`
                    <strong>Duration:</strong>
                    <span>
                      ${this.calculateDuration(
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
              <sl-relative-time
                date=${new Date(this.execution.start_time)}
              ></sl-relative-time>
            </sl-card>
            <sl-card>
              <div slot="header">
                <sl-icon name="tools"></sl-icon> Tool Calls
              </div>
              ${this.toolCalls}
            </sl-card>
            <sl-card>
              <div slot="header">
                <sl-icon name="cash"></sl-icon> Budget Used
              </div>
              $${this.budgetUsed.toFixed(2)}
            </sl-card>
          </div>

          <sl-card>
            <div
              slot="header"
              style="display: flex; justify-content: space-between; align-items: center;"
            >
              <span>
                <sl-icon name="terminal"></sl-icon>
                Output
              </span>
              <div class="controls">
                <sl-button-group>
                  <sl-button
                    size="small"
                    variant=${this.isAutoScroll ? 'primary' : 'default'}
                    @click=${() => (this.isAutoScroll = !this.isAutoScroll)}
                  >
                    <sl-icon name="arrow-down"></sl-icon>
                    Auto-scroll
                  </sl-button>
                  <sl-button size="small" @click=${this.clearLogs}>
                    <sl-icon name="trash"></sl-icon>
                    Clear
                  </sl-button>
                  ${isRunning
                    ? html`
                        <sl-button
                          size="small"
                          variant="danger"
                          @click=${this.stopExecution}
                        >
                          <sl-icon name="stop-circle"></sl-icon>
                          Stop
                        </sl-button>
                      `
                    : ''}
                </sl-button-group>
              </div>
            </div>

            <div
              class="log-container"
              ${(el: Element) => {
                this.logContainerRef = el as HTMLElement;
                if (this.logContainerRef) {
                  this.logContainerRef.addEventListener('scroll', () =>
                    this.handleScroll()
                  );
                }
              }}
            >
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
          ${this.execution.model_output_summary
            ? html`
                <sl-card>
                  <div slot="header">
                    <sl-icon name="file-text"></sl-icon>
                    Summary
                  </div>
                  <pre style="white-space: pre-wrap; word-wrap: break-word;">
${this.execution.model_output_summary}</pre
                  >
                </sl-card>
              `
            : ''}
        </div>
      </div>
    `;
  }

  renderLogEntry(log: FlowExecutionUpdate) {
    const time = new Date(log.timestamp).toLocaleTimeString();

    // For log lines, show timestamp + content
    if (log.type === 'agent_log_line') {
      const content = log.payload.line || log.payload.message || '';
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
      webSocketService.sendToExecution(this.executionId, commandData);

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

  clearLogs() {
    this.logs = [];
  }

  async stopExecution() {
    if (this.executionId) {
      await sendCommandToExecution(this.executionId, 'stop');
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

  calculateDuration(startTime: string, endTime: string): string {
    const start = new Date(startTime);
    const end = new Date(endTime);
    const durationMs = end.getTime() - start.getTime();
    const seconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  }
}
