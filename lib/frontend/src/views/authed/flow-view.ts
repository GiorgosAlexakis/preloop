import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import {
  getFlow,
  createFlow,
  updateFlow,
  getTrackers,
  getAIModels,
  createAIModel,
  getAvailableModelsForProvider,
  getFlowPresets,
  listOrganizations,
  listProjects,
  getAllTools,
  getMCPServers,
} from '../../api';
import { webSocketService } from '../../services/websocket-service';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/checkbox/checkbox.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio/radio.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '../../components/icon-selector.ts';
import '../../components/add-tracker-modal.ts';
import '../../components/add-ai-model-modal.ts';
import consoleStyles from '../../styles/console-styles.css?inline';

interface GitCloneRepository {
  tracker_id: string;
  repository_url?: string;
  clone_path: string;
  branch?: string;
}

interface GitCloneConfig {
  enabled: boolean;
  repositories?: GitCloneRepository[];
  git_user_name?: string;
  git_user_email?: string;
  source_branch?: string;
  target_branch?: string;
  create_pull_request?: boolean;
  pull_request_title?: string;
  pull_request_description?: string;
}

interface CustomCommands {
  enabled: boolean;
  commands?: string[];
}

interface WebhookConfig {
  webhook_secret: string;
}

interface Flow {
  id?: string;
  name: string;
  description?: string;
  icon?: string;
  trigger_event_source?: string;
  trigger_event_type?: string;
  trigger_organization_id?: string;
  trigger_project_id?: string;
  trigger_config?: any;
  webhook_config?: WebhookConfig;
  ai_model_id?: string;
  prompt_template?: string;
  allowed_mcp_servers?: string[];
  allowed_mcp_tools?: { server_name: string; tool_name: string }[];
  git_clone_config?: GitCloneConfig;
  custom_commands?: CustomCommands;
  max_iterations?: number;
  max_budget?: number;
  is_preset?: boolean;
  is_enabled?: boolean;
  agent_type?: string;
  agent_config?: any;
}

@customElement('flow-view')
export class FlowView extends LitElement {
  // Vaadin Router lifecycle callback
  onBeforeEnter(location: any) {
    this.flowId = location.params.flowId;
  }

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      :host {
        display: block;
        padding: var(--sl-spacing-large);
      }
      /* Flow-specific styles */
      .form-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--sl-spacing-large);
      }
      sl-card {
        width: 100%;
      }
      sl-card::part(base) {
        gap: var(--sl-spacing-large);
      }
      form {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }
      sl-input,
      sl-textarea,
      sl-select {
        margin-bottom: var(--sl-spacing-medium);
      }
      sl-input:last-child,
      sl-textarea:last-child,
      sl-select:last-child {
        margin-bottom: 0;
      }
      .preset-card {
        cursor: pointer;
        transition:
          transform 0.2s ease,
          box-shadow 0.2s ease;
      }
      .preset-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--sl-shadow-large);
      }
    `,
  ];

  @property()
  flowId?: string;

  @state()
  private flow: Flow = {
    name: '',
    agent_type: 'codex',
    allowed_mcp_servers: [],
    allowed_mcp_tools: [],
  };

  @state()
  private isNew = true;

  @state()
  private isEditing = false;

  @state()
  private trackers: any[] = [];

  @state()
  private models: any[] = [];

  @state()
  private mcpServers: any[] = [];

  @state()
  private availableTools: any[] = [];

  @state()
  private presets: any[] = [];

  @state()
  private showPresets = true;

  @state()
  private organizations: any[] = [];

  @state()
  private projects: any[] = [];

  @state()
  private recentExecutions: any[] = [];

  @state()
  private isAdmin = false;

  @state()
  private triggerType: 'webhook' | 'tracker' = 'webhook';

  @state()
  private isAddingTracker = false;

  @state()
  private isPollingOrganizations = false;

  @state()
  private isPollingProjects = false;

  @state()
  private isAddingAIModel = false;

  @state()
  private showTestRunModal = false;

  @state()
  private testRunPlaceholders: Record<string, string> = {};

  private organizationPollingInterval?: number;
  private projectPollingInterval?: number;

  disconnectedCallback() {
    super.disconnectedCallback();
    // Clean up polling intervals
    if (this.organizationPollingInterval) {
      clearInterval(this.organizationPollingInterval);
    }
    if (this.projectPollingInterval) {
      clearInterval(this.projectPollingInterval);
    }
    // Disconnect from WebSocket
    webSocketService.disconnectFromFlowUpdates();
  }

  async connectedCallback() {
    super.connectedCallback();

    // Check if current user is admin
    try {
      const { getAccountDetails } = await import('../../api');
      const currentUser = await getAccountDetails();
      this.isAdmin = currentUser.is_superuser || false;
    } catch (error) {
      console.error('Failed to get current user:', error);
      this.isAdmin = false;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const presetId = urlParams.get('preset_id');
    this.isEditing = urlParams.get('edit') === 'true';

    if (this.flowId) {
      // Viewing or editing an existing flow
      this.isNew = false;
      this.showPresets = false;
      this.flow = await getFlow(this.flowId);

      console.log(
        'DEBUG: Loaded flow git_clone_config:',
        this.flow.git_clone_config
      );

      // Set trigger type based on flow
      this.triggerType =
        this.flow.trigger_event_source === 'webhook' ? 'webhook' : 'tracker';

      // Load recent executions for this flow
      const allExecutions = await import('../../api').then((m) =>
        m.getFlowExecutions()
      );
      this.recentExecutions = allExecutions
        .filter((exec: any) => exec.flow_id === this.flowId)
        .sort(
          (a: any, b: any) =>
            new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
        )
        .slice(0, 10);

      // Load all necessary data for editing
      this.trackers = await getTrackers();
      this.models = await getAIModels();
      this.availableTools = await getAllTools();
      this.mcpServers = await getMCPServers();

      // Load all organizations and projects for git clone project selection
      // This needs to happen regardless of trigger type
      const allOrganizations = await listOrganizations();
      this.organizations = allOrganizations;

      const allProjects = await listProjects();
      this.projects = allProjects;

      // Additional trigger-specific setup if this is a tracker-based flow
      if (this.triggerType === 'tracker' && this.flow.trigger_event_source) {
        // Start polling if no organizations for this tracker yet
        const trackerOrgs = allOrganizations.filter(
          (org: any) => org.tracker_id === this.flow.trigger_event_source
        );
        if (trackerOrgs.length === 0 && this.flow.trigger_organization_id) {
          this.startPollingOrganizations(this.flow.trigger_event_source);
        }

        // Start polling projects if we have a trigger organization but no projects
        if (this.flow.trigger_organization_id) {
          const orgProjects = allProjects.filter(
            (proj: any) =>
              proj.organization_id === this.flow.trigger_organization_id
          );
          if (orgProjects.length === 0 && this.flow.trigger_project_id) {
            this.startPollingProjects(this.flow.trigger_organization_id);
          }
        }
      }

      // Ensure spacebridge-mcp is always in allowed_mcp_servers
      if (!this.flow.allowed_mcp_servers?.includes('spacebridge-mcp')) {
        this.flow.allowed_mcp_servers = ['spacebridge-mcp'];
      }

      // Connect to WebSocket for real-time flow execution updates
      this.connectToFlowUpdates();
    } else if (presetId) {
      // Creating from preset
      this.trackers = await getTrackers();
      this.models = await getAIModels();
      this.presets = await getFlowPresets();
      this.availableTools = await getAllTools();
      this.mcpServers = await getMCPServers();
      const preset = this.presets.find((p) => p.id === presetId);
      if (preset) {
        this.selectPreset(preset);
        // Ensure spacebridge-mcp is in allowed_mcp_servers
        if (!this.flow.allowed_mcp_servers?.includes('spacebridge-mcp')) {
          this.flow.allowed_mcp_servers = ['spacebridge-mcp'];
        }
      }
    } else {
      // Creating new flow - initialize with spacebridge-mcp by default
      this.trackers = await getTrackers();
      this.models = await getAIModels();
      this.presets = await getFlowPresets();
      this.availableTools = await getAllTools();
      this.mcpServers = await getMCPServers();

      // Initialize with spacebridge-mcp server and all enabled tools selected
      this.flow.allowed_mcp_servers = ['spacebridge-mcp'];
      this.flow.allowed_mcp_tools = this.getDefaultSelectedTools();
    }
  }

  private connectToFlowUpdates() {
    // Connect to WebSocket for real-time flow execution updates
    webSocketService.connectToFlowUpdates(
      (message) => {
        // Handle incoming WebSocket messages
        console.log('Received flow update:', message);

        // If this is an execution_started event for our flow, add it to recent executions
        if (
          message.type === 'execution_started' &&
          message.flow_id === this.flowId
        ) {
          // Create a new execution object from the update
          const newExecution = {
            id: message.execution_id,
            flow_id: message.flow_id,
            status: message.payload.status || 'PENDING',
            start_time: message.timestamp,
            flow_name: message.payload.flow_name,
          };

          // Add to the beginning of recent executions
          this.recentExecutions = [
            newExecution,
            ...this.recentExecutions,
          ].slice(0, 10);
        }

        // If this is a status update for an execution we're showing, update it
        if (message.type === 'status_update' && message.execution_id) {
          const executionIndex = this.recentExecutions.findIndex(
            (exec: any) => exec.id === message.execution_id
          );
          if (executionIndex !== -1) {
            // Update the execution status
            const updatedExecution = {
              ...this.recentExecutions[executionIndex],
              status: message.payload.status,
              end_time: message.payload.end_time,
            };
            this.recentExecutions = [
              ...this.recentExecutions.slice(0, executionIndex),
              updatedExecution,
              ...this.recentExecutions.slice(executionIndex + 1),
            ];
          }
        }
      },
      () => {
        console.log('WebSocket connected for flow updates');
      },
      () => {
        console.log('WebSocket disconnected for flow updates');
      }
    );
  }

  render() {
    if (!this.isNew && !this.isEditing) {
      // View mode - show flow details
      return this.renderFlowDetails();
    }

    // Edit/Create mode - show form
    return html`
      ${this.isAddingTracker
        ? html`<add-tracker-modal
            @tracker-added=${this.handleTrackerAdded}
            @close-modal=${this.closeAddTrackerDialog}
          ></add-tracker-modal>`
        : ''}
      <add-ai-model-modal
        .open=${this.isAddingAIModel}
        @model-created=${this.handleAIModelCreated}
        @close-modal=${this.closeAIModelDialog}
      ></add-ai-model-modal>
      <view-header
        headerText="${this.isNew ? 'Create Flow' : 'Edit Flow'}"
      ></view-header>
      <div class="column-layout">
        <div class="main-column">
          ${this.isNew && this.showPresets
            ? this.renderPresets()
            : this.renderForm()}
        </div>
      </div>
    `;
  }

  renderFlowDetails() {
    return html`
      <!-- Test Run Modal for Trigger Event Placeholders -->
      <sl-dialog
        label="Provide Test Values for Trigger Event"
        .open=${this.showTestRunModal}
        @sl-request-close=${this.cancelTestRun}
      >
        <p style="margin-bottom: 1rem; color: var(--sl-color-neutral-600);">
          Your flow prompt includes template variables that reference trigger
          event data. Please provide test values for these placeholders:
        </p>

        ${Object.keys(this.testRunPlaceholders).map(
          (placeholder) => html`
            <sl-input
              label="${placeholder}"
              placeholder="Enter test value"
              .value=${this.testRunPlaceholders[placeholder]}
              @sl-input=${(e: any) =>
                this.updatePlaceholderValue(placeholder, e.target.value)}
              style="margin-bottom: 1rem;"
            ></sl-input>
          `
        )}

        <div slot="footer" style="display: flex; gap: 8px;">
          <sl-button variant="default" @click=${this.cancelTestRun}>
            Cancel
          </sl-button>
          <sl-button variant="primary" @click=${this.submitTestRun}>
            Run Test
          </sl-button>
        </div>
      </sl-dialog>

      <view-header headerText="${this.flow.name}"></view-header>
      <div class="column-layout">
        <div class="main-column">
          <!-- Actions -->
          <div
            style="display: flex; gap: var(--sl-spacing-small); margin-bottom: var(--sl-spacing-large);"
          >
            <sl-button href="/console/flows">
              <sl-icon name="arrow-left"></sl-icon>
              Back to Flows
            </sl-button>
            <sl-button href="/console/flows/${this.flowId}?edit=true">
              <sl-icon name="pencil"></sl-icon>
              Edit Flow
            </sl-button>
            <sl-button
              variant="${this.flow.is_enabled ? 'default' : 'success'}"
              @click=${this.toggleFlowEnabled}
            >
              <sl-icon
                name="${this.flow.is_enabled ? 'pause-circle' : 'play-circle'}"
              ></sl-icon>
              ${this.flow.is_enabled ? 'Disable' : 'Enable'}
            </sl-button>
            <sl-button
              variant="primary"
              @click=${this.testRun}
              ?disabled=${!this.flow.is_enabled}
            >
              <sl-icon name="play-circle"></sl-icon>
              Test Run
            </sl-button>
          </div>

          <!-- Flow Info Card -->
          <sl-card>
            <div slot="header">
              <sl-icon name="info-circle"></sl-icon>
              Flow Details
            </div>
            <div
              style="display: grid; grid-template-columns: 150px 1fr; gap: var(--sl-spacing-medium);"
            >
              <strong>Name:</strong>
              <span>${this.flow.name}</span>

              ${this.flow.description
                ? html`
                    <strong>Description:</strong>
                    <span>${this.flow.description}</span>
                  `
                : ''}

              <strong>Agent Type:</strong>
              <sl-badge>${this.flow.agent_type}</sl-badge>

              <strong>Trigger:</strong>
              <span>
                ${this.flow.trigger_event_source === 'webhook'
                  ? 'Webhook'
                  : `${this.flow.trigger_event_source} - ${this.flow.trigger_event_type}`}
              </span>

              <strong>Status:</strong>
              <sl-badge
                variant="${this.flow.is_enabled ? 'success' : 'neutral'}"
              >
                ${this.flow.is_enabled ? 'Enabled' : 'Disabled'}
              </sl-badge>

              ${this.flow.git_clone_config?.enabled
                ? html`
                    <strong>Git Clone:</strong>
                    <sl-badge variant="primary">Enabled</sl-badge>
                  `
                : ''}
              ${this.flow.custom_commands?.enabled && this.isAdmin
                ? html`
                    <strong>Custom Commands:</strong>
                    <sl-badge variant="warning">Enabled</sl-badge>
                  `
                : ''}
            </div>
          </sl-card>

          ${this.flow.trigger_event_source === 'webhook' &&
          this.flow.webhook_config
            ? html`
                <sl-card>
                  <div slot="header">
                    <sl-icon name="link-45deg"></sl-icon>
                    Webhook URL
                  </div>
                  <div>
                    <p
                      style="margin-bottom: var(--sl-spacing-medium); color: var(--sl-color-neutral-600);"
                    >
                      Use this URL to trigger the flow from external services.
                      Keep it secret!
                    </p>
                    <div
                      style="display: flex; gap: var(--sl-spacing-small); align-items: center;"
                    >
                      <sl-input
                        readonly
                        style="flex: 1;"
                        value="${window.location
                          .origin}/api/webhooks/flows/${this.flowId}/${this.flow
                          .webhook_config.webhook_secret}"
                      ></sl-input>
                      <sl-button @click=${() => this.copyWebhookUrl()}>
                        <sl-icon name="clipboard"></sl-icon>
                        Copy
                      </sl-button>
                    </div>
                  </div>
                </sl-card>
              `
            : ''}
          ${this.flow.git_clone_config?.enabled &&
          (this.flow.git_clone_config.repositories?.length || 0) > 0
            ? html`
                <sl-card>
                  <div slot="header">
                    <sl-icon name="git"></sl-icon>
                    Git Clone Configuration
                  </div>
                  ${(this.flow.git_clone_config.repositories || []).map(
                    (repo, index) => html`
                      <div
                        style="border-bottom: ${index <
                        (this.flow.git_clone_config?.repositories?.length ||
                          0) -
                          1
                          ? '1px solid var(--sl-color-neutral-200)'
                          : 'none'}; padding-bottom: ${index <
                        (this.flow.git_clone_config?.repositories?.length ||
                          0) -
                          1
                          ? '12px'
                          : '0'}; margin-bottom: ${index <
                        (this.flow.git_clone_config?.repositories?.length ||
                          0) -
                          1
                          ? '12px'
                          : '0'};"
                      >
                        <strong style="display: block; margin-bottom: 8px;">
                          Repository ${index + 1}
                        </strong>
                        <div
                          style="display: grid; grid-template-columns: 150px 1fr; gap: var(--sl-spacing-small); padding-left: var(--sl-spacing-medium);"
                        >
                          <strong>Tracker:</strong>
                          <span
                            >${this.trackers.find(
                              (t) => t.id === repo.tracker_id
                            )?.name || repo.tracker_id}</span
                          >

                          ${repo.repository_url
                            ? html`
                                <strong>Repository:</strong>
                                <span>${repo.repository_url}</span>
                              `
                            : html`
                                <strong>Repository:</strong>
                                <span
                                  style="color: var(--sl-color-neutral-600);"
                                  >Auto-detect from trigger</span
                                >
                              `}

                          <strong>Clone Path:</strong>
                          <span>${repo.clone_path}</span>

                          ${repo.branch
                            ? html`
                                <strong>Branch:</strong>
                                <span>${repo.branch}</span>
                              `
                            : ''}
                        </div>
                      </div>
                    `
                  )}
                </sl-card>
              `
            : ''}
          ${this.flow.custom_commands?.enabled && this.isAdmin
            ? html`
                <sl-card>
                  <div slot="header">
                    <sl-icon name="terminal"></sl-icon>
                    Custom Commands
                    <sl-badge
                      variant="warning"
                      size="small"
                      style="margin-left: 8px;"
                      >Admin Only</sl-badge
                    >
                  </div>
                  <div>
                    <strong style="display: block; margin-bottom: 8px;"
                      >Commands:</strong
                    >
                    <pre
                      style="background: var(--sl-color-neutral-50); padding: 12px; border-radius: 4px; overflow-x: auto;"
                    >
${(this.flow.custom_commands.commands || []).join('\n')}</pre
                    >
                  </div>
                </sl-card>
              `
            : ''}

          <!-- Recent Executions -->
          <sl-card>
            <div slot="header">
              <sl-icon name="clock-history"></sl-icon>
              Recent Executions
            </div>
            ${this.recentExecutions.length === 0
              ? html`<p>No executions yet. Click "Test Run" to start one.</p>`
              : html`
                  <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                      <tr>
                        <th style="text-align: left; padding: 8px;">Status</th>
                        <th style="text-align: left; padding: 8px;">Started</th>
                        <th style="text-align: left; padding: 8px;">
                          Duration
                        </th>
                        <th style="text-align: left; padding: 8px;">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${this.recentExecutions.map(
                        (exec) => html`
                          <tr>
                            <td style="padding: 8px;">
                              <sl-badge
                                variant=${this.getStatusVariant(exec.status)}
                              >
                                ${exec.status}
                              </sl-badge>
                            </td>
                            <td style="padding: 8px;">
                              ${new Date(exec.start_time).toLocaleString()}
                            </td>
                            <td style="padding: 8px;">
                              ${exec.end_time
                                ? this.calculateDuration(
                                    exec.start_time,
                                    exec.end_time
                                  )
                                : 'Running...'}
                            </td>
                            <td style="padding: 8px;">
                              <sl-button
                                size="small"
                                href="/console/flows/executions/${exec.id}"
                              >
                                <sl-icon name="eye"></sl-icon>
                                View
                              </sl-button>
                            </td>
                          </tr>
                        `
                      )}
                    </tbody>
                  </table>
                `}
          </sl-card>
        </div>
      </div>
    `;
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

  private extractTriggerEventPlaceholders(): string[] {
    if (!this.flow.prompt_template) return [];

    // Extract all {{trigger_event.*}} placeholders
    const regex = /\{\{(trigger_event\.[^}]+)\}\}/g;
    const matches = [];
    let match;

    while ((match = regex.exec(this.flow.prompt_template)) !== null) {
      matches.push(match[1]); // Get the placeholder without the {{ }}
    }

    // Return unique placeholders
    return [...new Set(matches)];
  }

  async testRun() {
    if (!this.flowId) return;

    // Check if prompt template has trigger_event placeholders
    const placeholders = this.extractTriggerEventPlaceholders();

    if (placeholders.length > 0) {
      // Initialize placeholder values with empty strings
      this.testRunPlaceholders = {};
      placeholders.forEach((placeholder) => {
        this.testRunPlaceholders[placeholder] = '';
      });
      // Show modal to collect placeholder values
      this.showTestRunModal = true;
    } else {
      // No placeholders, trigger immediately
      await this.executeTestRun();
    }
  }

  async toggleFlowEnabled() {
    if (!this.flowId) return;

    try {
      // Toggle the enabled state
      const newEnabledState = !this.flow.is_enabled;

      // Update the flow on the backend
      await updateFlow(this.flowId, {
        is_enabled: newEnabledState,
      });

      // Update local state
      this.flow = {
        ...this.flow,
        is_enabled: newEnabledState,
      };

      // Show feedback
      const message = newEnabledState
        ? 'Flow enabled successfully'
        : 'Flow disabled successfully';
      console.log(message);
    } catch (error) {
      console.error('Failed to toggle flow enabled state:', error);
      alert('Failed to update flow. Please try again.');
    }
  }

  private async executeTestRun(triggerEventData?: Record<string, any>) {
    if (!this.flowId) return;
    try {
      const execution = await import('../../api').then((m) =>
        m.triggerFlowExecution(this.flowId!, triggerEventData)
      );
      // Navigate to execution view
      window.location.href = `/console/flows/executions/${execution.id}`;
    } catch (error) {
      console.error('Failed to trigger flow execution:', error);
      alert('Failed to trigger flow execution');
    }
  }

  private async submitTestRun() {
    // Build nested object from placeholder keys
    const triggerEventData: Record<string, any> = {};

    Object.entries(this.testRunPlaceholders).forEach(([key, value]) => {
      // key is like "trigger_event.payload.object_attributes.url"
      // Remove "trigger_event." prefix
      const path = key.replace('trigger_event.', '').split('.');

      // Build nested object
      let current = triggerEventData;
      for (let i = 0; i < path.length; i++) {
        const segment = path[i];
        if (i === path.length - 1) {
          // Last segment, set the value
          current[segment] = value;
        } else {
          // Create nested object if it doesn't exist
          if (!current[segment]) {
            current[segment] = {};
          }
          current = current[segment];
        }
      }
    });

    // Close modal
    this.showTestRunModal = false;

    // Execute test run with custom data
    await this.executeTestRun(triggerEventData);
  }

  private cancelTestRun() {
    this.showTestRunModal = false;
    this.testRunPlaceholders = {};
  }

  private updatePlaceholderValue(placeholder: string, value: string) {
    this.testRunPlaceholders = {
      ...this.testRunPlaceholders,
      [placeholder]: value,
    };
  }

  copyWebhookUrl() {
    if (!this.flow.webhook_config) return;
    const webhookUrl = `${window.location.origin}/api/webhooks/flows/${this.flowId}/${this.flow.webhook_config.webhook_secret}`;
    navigator.clipboard.writeText(webhookUrl).then(() => {
      alert('Webhook URL copied to clipboard!');
    });
  }

  renderPresets() {
    return html`
      <h2>Select a Preset</h2>
      <div class="form-grid">
        ${this.presets.map(
          (preset) => html`
            <sl-card
              class="preset-card"
              @click=${() => this.selectPreset(preset)}
            >
              <div slot="header">${preset.name}</div>
              ${preset.description}
            </sl-card>
          `
        )}
      </div>
      <sl-button @click=${() => (this.showPresets = false)}
        >Create from Scratch</sl-button
      >
    `;
  }

  selectPreset(preset: any) {
    this.flow = { ...preset };
    this.showPresets = false;
  }

  renderForm() {
    return html`
      <form @submit=${this.handleSubmit}>
        <sl-card>
          <sl-input
            label="Name"
            .value=${this.flow.name}
            @sl-input=${(e: Event) => this.handleInputChange('name', e)}
            required
          ></sl-input>
          <sl-textarea
            label="Description"
            .value=${this.flow.description || ''}
            @sl-input=${(e: Event) => this.handleInputChange('description', e)}
          ></sl-textarea>
        </sl-card>

        <sl-card>
          <div slot="header">
            <sl-icon name="calendar-event"></sl-icon>
            Trigger
          </div>

          <!-- Trigger Type Selection -->
          <div style="margin-bottom: 1.5rem;">
            <label
              style="display: block; margin-bottom: 0.5rem; font-weight: 500;"
            >
              Trigger Type
            </label>
            <sl-radio-group
              value=${this.triggerType}
              @sl-change=${(e: any) =>
                this.handleTriggerTypeChange(e.target.value)}
              style="display: flex; gap: 1rem;"
            >
              <sl-radio value="webhook">Webhook</sl-radio>
              <sl-radio value="tracker">Tracker Event</sl-radio>
            </sl-radio-group>
          </div>

          ${this.triggerType === 'webhook'
            ? this.renderWebhookTriggerFields()
            : this.renderTrackerTriggerFields()}
        </sl-card>

        <sl-card>
          <div slot="header">
            <sl-icon name="robot"></sl-icon>
            AI Agent
          </div>

          <sl-select
            label="Agent Type"
            .value=${this.flow.agent_type || 'codex'}
            @sl-change=${(e: any) => {
              this.flow.agent_type = e.target.value;
              this.requestUpdate();
            }}
            help-text="Choose which AI agent to use for executing this flow"
          >
            <sl-option value="codex">Codex (Recommended)</sl-option>
            <sl-option value="claude-code">Claude Code</sl-option>
            <sl-option value="aider">Aider</sl-option>
            <sl-option value="openhands">OpenHands</sl-option>
          </sl-select>

          ${this.models.length === 0
            ? html`
                <div
                  style="text-align: center; padding: var(--sl-spacing-2x-large); background: var(--sl-color-neutral-50); border-radius: var(--sl-border-radius-medium); margin-bottom: var(--sl-spacing-medium);"
                >
                  <p
                    style="margin-bottom: var(--sl-spacing-medium); color: var(--sl-color-neutral-600);"
                  >
                    No AI models configured yet.
                  </p>
                  <sl-button
                    variant="primary"
                    @click=${this.openAddAIModelDialog}
                  >
                    <sl-icon slot="prefix" name="plus-lg"></sl-icon>
                    Add AI Model
                  </sl-button>
                </div>
              `
            : html`
                <div>
                  <sl-select
                    label="AI Model"
                    .value=${this.flow.ai_model_id || ''}
                    @sl-change=${(e: any) =>
                      (this.flow.ai_model_id = e.target.value)}
                  >
                    ${this.models.map(
                      (model) =>
                        html`<sl-option value=${model.id}
                          >${model.name}</sl-option
                        >`
                    )}
                  </sl-select>
                  <sl-button
                    size="small"
                    variant="text"
                    @click=${this.openAddAIModelDialog}
                    style="margin-top: 0.5rem;"
                  >
                    <sl-icon slot="prefix" name="plus-lg"></sl-icon>
                    Add New AI Model
                  </sl-button>
                </div>
              `}
          <sl-textarea
            label="Prompt"
            .value=${this.flow.prompt_template || ''}
            @sl-input=${(e: Event) =>
              this.handleInputChange('prompt_template', e)}
            help-text="The prompt that will be sent to the AI agent. You can use template variables like {{trigger_event.*}}"
          ></sl-textarea>
        </sl-card>

        <sl-card>
          <div slot="header">
            <sl-icon name="tools"></sl-icon>
            Tools
          </div>

          <p style="margin-bottom: 1rem; color: var(--sl-color-neutral-600);">
            Select which tools the agent can use during flow execution. All
            enabled tools are selected by default.
          </p>

          ${this.renderToolSelection()}
        </sl-card>

        ${this.getGitTrackers().length > 0
          ? html`
              <sl-card>
                <div slot="header">
                  <sl-icon name="git"></sl-icon>
                  Git Clone Configuration
                </div>
                <p
                  style="margin-bottom: 1rem; color: var(--sl-color-neutral-600);"
                >
                  Automatically clone repositories before the agent starts.
                  ${this.getGitTrackers().length === 1
                    ? 'Your GitHub/GitLab tracker will be used automatically.'
                    : 'Select which repositories to clone.'}
                </p>
                <sl-checkbox
                  .checked=${this.flow.git_clone_config?.enabled || false}
                  @sl-change=${(e: any) =>
                    this.handleGitCloneToggle(e.target.checked)}
                  >Enable Git Clone</sl-checkbox
                >

                ${this.flow.git_clone_config?.enabled
                  ? html`
                      <div style="margin-top: 1rem;">
                        <div class="form-grid">
                          <sl-input
                            label="Git User Name"
                            .value=${this.flow.git_clone_config
                              ?.git_user_name || 'Preloop AI'}
                            @sl-input=${(e: any) => {
                              if (!this.flow.git_clone_config) return;
                              this.flow = {
                                ...this.flow,
                                git_clone_config: {
                                  ...this.flow.git_clone_config,
                                  git_user_name: e.target.value,
                                },
                              };
                            }}
                            help-text="Name to use for git commits"
                          ></sl-input>
                          <sl-input
                            label="Git User Email"
                            .value=${this.flow.git_clone_config
                              ?.git_user_email || 'git@preloop.ai'}
                            @sl-input=${(e: any) => {
                              if (!this.flow.git_clone_config) return;
                              this.flow = {
                                ...this.flow,
                                git_clone_config: {
                                  ...this.flow.git_clone_config,
                                  git_user_email: e.target.value,
                                },
                              };
                            }}
                            help-text="Email to use for git commits"
                          ></sl-input>
                          <sl-input
                            label="Source Branch"
                            .value=${this.flow.git_clone_config
                              ?.source_branch || 'main'}
                            @sl-input=${(e: any) => {
                              if (!this.flow.git_clone_config) return;
                              this.flow = {
                                ...this.flow,
                                git_clone_config: {
                                  ...this.flow.git_clone_config,
                                  source_branch: e.target.value,
                                },
                              };
                            }}
                            help-text="Branch to checkout for base code"
                          ></sl-input>
                          <sl-input
                            label="Target Branch (optional)"
                            .value=${this.flow.git_clone_config
                              ?.target_branch || ''}
                            @sl-input=${(e: any) => {
                              if (!this.flow.git_clone_config) return;
                              this.flow = {
                                ...this.flow,
                                git_clone_config: {
                                  ...this.flow.git_clone_config,
                                  target_branch: e.target.value,
                                },
                              };
                            }}
                            help-text="Branch to create for commits (auto-generated if empty)"
                          ></sl-input>
                        </div>
                        <sl-checkbox
                          .checked=${this.flow.git_clone_config
                            ?.create_pull_request || false}
                          @sl-change=${(e: any) => {
                            if (!this.flow.git_clone_config) return;
                            // Create new object reference for proper reactivity
                            this.flow = {
                              ...this.flow,
                              git_clone_config: {
                                ...this.flow.git_clone_config,
                                create_pull_request: e.target.checked,
                              },
                            };
                            this.requestUpdate();
                          }}
                          style="margin-top: 1rem;"
                          >${this.getGitTrackers().some(
                            (t) => t.tracker_type === 'gitlab'
                          )
                            ? 'Create Merge Request'
                            : 'Create Pull Request'}</sl-checkbox
                        >
                        ${this.flow.git_clone_config?.create_pull_request
                          ? html`
                              <div style="margin-top: 0.5rem;">
                                <sl-input
                                  label="${this.getGitTrackers().some(
                                    (t) => t.tracker_type === 'gitlab'
                                  )
                                    ? 'MR Title (optional)'
                                    : 'PR Title (optional)'}"
                                  .value=${this.flow.git_clone_config
                                    ?.pull_request_title || ''}
                                  @sl-input=${(e: any) => {
                                    if (!this.flow.git_clone_config) return;
                                    this.flow = {
                                      ...this.flow,
                                      git_clone_config: {
                                        ...this.flow.git_clone_config,
                                        pull_request_title: e.target.value,
                                      },
                                    };
                                  }}
                                  help-text="Title for the Pull/Merge Request (defaults to flow name)"
                                ></sl-input>
                                <sl-textarea
                                  label="${this.getGitTrackers().some(
                                    (t) => t.tracker_type === 'gitlab'
                                  )
                                    ? 'MR Description (optional)'
                                    : 'PR Description (optional)'}"
                                  .value=${this.flow.git_clone_config
                                    ?.pull_request_description || ''}
                                  @sl-input=${(e: any) => {
                                    if (!this.flow.git_clone_config) return;
                                    this.flow = {
                                      ...this.flow,
                                      git_clone_config: {
                                        ...this.flow.git_clone_config,
                                        pull_request_description:
                                          e.target.value,
                                      },
                                    };
                                  }}
                                  rows="3"
                                  help-text="Description for the Pull/Merge Request"
                                ></sl-textarea>
                              </div>
                            `
                          : ''}
                        <div style="margin-top: 1rem;">
                          <h4
                            style="margin-bottom: 0.5rem; font-size: 0.875rem;"
                          >
                            Repositories
                          </h4>
                          ${this.renderGitRepositories()}
                          <sl-button
                            size="small"
                            @click=${this.addGitRepository}
                            style="margin-top: 0.5rem;"
                          >
                            <sl-icon name="plus"></sl-icon>
                            Add Repository
                          </sl-button>
                        </div>
                      </div>
                    `
                  : ''}
              </sl-card>
            `
          : ''}
        ${this.isAdmin
          ? html`
              <sl-card>
                <div slot="header">
                  <sl-icon name="terminal"></sl-icon>
                  Custom Commands
                  <sl-badge
                    variant="warning"
                    size="small"
                    style="margin-left: 8px;"
                    >Admin Only</sl-badge
                  >
                </div>
                <p
                  style="margin-bottom: 1rem; color: var(--sl-color-warning-600);"
                >
                  <strong>Security Warning:</strong> Custom commands execute
                  with full container privileges. Only use trusted commands.
                  This feature is restricted to administrators.
                </p>
                <sl-checkbox
                  .checked=${this.flow.custom_commands?.enabled || false}
                  @sl-change=${(e: any) => {
                    if (!this.flow.custom_commands) {
                      this.flow.custom_commands = {
                        enabled: false,
                        commands: [],
                      };
                    }
                    this.flow.custom_commands.enabled = e.target.checked;
                    this.requestUpdate();
                  }}
                  >Enable Custom Commands</sl-checkbox
                >

                ${this.flow.custom_commands?.enabled
                  ? html`
                      <div style="margin-top: 1rem;">
                        <label
                          style="display: block; margin-bottom: 0.5rem; font-weight: 500;"
                        >
                          Commands (one per line)
                        </label>
                        <sl-textarea
                          placeholder="pip install -r requirements.txt&#10;npm install&#10;./setup.sh"
                          rows="5"
                          .value=${(
                            this.flow.custom_commands.commands || []
                          ).join('\n')}
                          @sl-input=${(e: any) => {
                            if (this.flow.custom_commands) {
                              const commands = e.target.value
                                .split('\n')
                                .map((cmd: string) => cmd.trim())
                                .filter((cmd: string) => cmd.length > 0);
                              this.flow.custom_commands.commands = commands;
                            }
                          }}
                          help-text="Commands will execute sequentially before the agent starts. Any command failure will stop execution."
                        ></sl-textarea>
                      </div>
                    `
                  : ''}
              </sl-card>
            `
          : ''}

        <sl-card>
          <div slot="header">
            <sl-icon name="speedometer"></sl-icon>
            Limits
          </div>
          <div class="form-grid">
            <sl-input
              label="Max Iterations"
              type="number"
              .value=${String(this.flow.max_iterations || '')}
              @sl-input=${(e: Event) =>
                this.handleInputChange('max_iterations', e)}
            ></sl-input>
            <sl-input
              label="Max Budget"
              type="number"
              .value=${String(this.flow.max_budget || '')}
              @sl-input=${(e: Event) => this.handleInputChange('max_budget', e)}
            ></sl-input>
          </div>
        </sl-card>

        <div>
          <sl-checkbox
            ?checked=${this.flow.is_preset}
            @sl-change=${(e: any) => (this.flow.is_preset = e.target.checked)}
            >Save as Preset</sl-checkbox
          >
        </div>
        <div style="display: flex; gap: var(--sl-spacing-small);">
          <sl-button type="submit" variant="primary"
            >${this.isNew ? 'Create' : 'Update'}</sl-button
          >
          <sl-button @click=${() => Router.go('/console/flows')}
            >Cancel</sl-button
          >
        </div>
      </form>
    `;
  }

  handleInputChange(field: keyof Flow, e: Event) {
    const target = e.target as HTMLInputElement | HTMLTextAreaElement;
    let value: string | number | null = target.value;
    if (target.type === 'number') {
      value = value === '' ? null : Number(value);
    }
    this.flow = { ...this.flow, [field]: value };
  }

  async handleSubmit(e: Event) {
    e.preventDefault();

    // Build payload with required fields
    const payload: any = {
      name: this.flow.name,
      prompt_template: this.flow.prompt_template || '',
      agent_type: this.flow.agent_type || 'codex',
      agent_config: this.flow.agent_config || {},
      allowed_mcp_servers: this.flow.allowed_mcp_servers || [],
      allowed_mcp_tools: this.flow.allowed_mcp_tools || [],
    };

    // Add optional fields if they have values
    const optionalFields: (keyof Flow)[] = [
      'description',
      'icon',
      'trigger_event_source',
      'trigger_event_type',
      'trigger_organization_id',
      'trigger_project_id',
      'trigger_config',
      'webhook_config',
      'ai_model_id',
      'agent_type',
      'git_clone_config',
      'custom_commands',
      'max_iterations',
      'max_budget',
      'is_preset',
      'is_enabled',
    ];

    for (const field of optionalFields) {
      const value = this.flow[field];
      if (value !== null && value !== undefined && value !== '') {
        payload[field] = value;
      }
    }

    if (this.isNew) {
      const newFlow = await createFlow(payload);
      Router.go(`/console/flows/${newFlow.id}`);
    } else {
      await updateFlow(this.flowId!, payload);
      // Redirect to flow view after successful update
      Router.go(`/console/flows/${this.flowId}`);
    }
  }
  startPollingOrganizations(trackerId: string) {
    // Stop any existing polling
    if (this.organizationPollingInterval) {
      clearInterval(this.organizationPollingInterval);
    }

    this.isPollingOrganizations = true;
    this.organizationPollingInterval = window.setInterval(async () => {
      const allOrganizations = await listOrganizations();
      const orgs = allOrganizations.filter(
        (org: any) => org.tracker_id === trackerId
      );

      if (orgs.length > 0) {
        this.organizations = orgs;
        this.isPollingOrganizations = false;
        if (this.organizationPollingInterval) {
          clearInterval(this.organizationPollingInterval);
          this.organizationPollingInterval = undefined;
        }
        this.requestUpdate();
      }
    }, 2000);
  }

  startPollingProjects(orgId: string) {
    // Stop any existing polling
    if (this.projectPollingInterval) {
      clearInterval(this.projectPollingInterval);
    }

    this.isPollingProjects = true;
    this.projectPollingInterval = window.setInterval(async () => {
      const allProjects = await listProjects();
      const orgProjects = allProjects.filter(
        (proj: any) => proj.organization_id === orgId
      );

      if (orgProjects.length > 0) {
        // Store all projects for git clone project selection
        this.projects = allProjects;
        this.isPollingProjects = false;
        if (this.projectPollingInterval) {
          clearInterval(this.projectPollingInterval);
          this.projectPollingInterval = undefined;
        }
        this.requestUpdate();
      }
    }, 2000);
  }

  async handleTrackerChange(e: any) {
    const trackerId = e.target.value;

    // Handle special options
    if (trackerId === 'add_new') {
      // Navigate to trackers page - user can then click "Add New Tracker"
      window.location.href = '/console/trackers';
      return;
    }

    // Normal tracker selected
    this.flow.trigger_event_source = trackerId;
    this.flow.trigger_event_type = undefined; // Reset event type when tracker changes
    this.flow.trigger_organization_id = undefined;
    this.flow.trigger_project_id = undefined;

    const allOrganizations = await listOrganizations();
    this.organizations = allOrganizations.filter(
      (org: any) => org.tracker_id === trackerId
    );

    // Start polling if no organizations yet
    if (this.organizations.length === 0) {
      this.startPollingOrganizations(trackerId);
    }

    this.requestUpdate();
  }

  async handleOrganizationChange(e: any) {
    const orgId = e.target.value;
    this.flow.trigger_organization_id = orgId;
    this.flow.trigger_project_id = undefined;

    // Load all projects (needed for git clone project selection)
    const allProjects = await listProjects();
    this.projects = allProjects;

    // Start polling if no projects for this org yet
    const orgProjects = allProjects.filter(
      (proj: any) => proj.organization_id === orgId
    );
    if (orgProjects.length === 0) {
      this.startPollingProjects(orgId);
    }
  }

  @state()
  private customEventType = '';

  @state()
  private filtersExpanded = false;

  getEventOptions() {
    const tracker = this.trackers.find(
      (t) => t.id === this.flow.trigger_event_source
    );
    if (tracker) {
      switch (tracker.tracker_type) {
        case 'github':
          return [
            { name: 'Issue Opened', value: 'issue_opened' },
            { name: 'Issue Updated', value: 'issue_updated' },
            { name: 'Issue Closed', value: 'issue_closed' },
            { name: 'Issue Reopened', value: 'issue_reopened' },
            { name: 'Pull Request Opened', value: 'pull_request_opened' },
            { name: 'Pull Request Updated', value: 'pull_request_updated' },
            { name: 'Pull Request Closed', value: 'pull_request_closed' },
            { name: 'Pull Request Merged', value: 'pull_request_merged' },
            { name: 'Pull Request Reopened', value: 'pull_request_reopened' },
            { name: 'Comment Created', value: 'comment_created' },
            { name: 'Comment Updated', value: 'comment_updated' },
            { name: 'Push to Repository', value: 'push' },
            { name: 'Release Published', value: 'release' },
          ];
        case 'gitlab':
          return [
            { name: 'Issue Opened', value: 'issue_opened' },
            { name: 'Issue Updated', value: 'issue_updated' },
            { name: 'Issue Closed', value: 'issue_closed' },
            { name: 'Issue Reopened', value: 'issue_reopened' },
            { name: 'Merge Request Opened', value: 'merge_request_opened' },
            { name: 'Merge Request Updated', value: 'merge_request_updated' },
            { name: 'Merge Request Closed', value: 'merge_request_closed' },
            { name: 'Merge Request Merged', value: 'merge_request_merged' },
            { name: 'Merge Request Approved', value: 'merge_request_approved' },
            { name: 'Merge Request Reopened', value: 'merge_request_reopened' },
            { name: 'Comment Created', value: 'comment_created' },
            { name: 'Comment Updated', value: 'comment_updated' },
            { name: 'Push to Repository', value: 'push' },
            { name: 'Tag Push', value: 'tag_push' },
            { name: 'Pipeline Event', value: 'pipeline' },
            { name: 'Release Published', value: 'release' },
          ];
        case 'jira':
          return [
            { name: 'Issue Opened', value: 'issue_opened' },
            { name: 'Issue Updated', value: 'issue_updated' },
            { name: 'Issue Deleted', value: 'issue_deleted' },
            { name: 'Comment Created', value: 'comment_created' },
            { name: 'Comment Updated', value: 'comment_updated' },
            { name: 'Comment Deleted', value: 'comment_deleted' },
          ];
        default:
          return [];
      }
    }
    return [];
  }

  handleEventChange(e: any) {
    const value = e.target.value;
    if (value === 'other') {
      this.flow.trigger_event_type = 'other';
    } else {
      this.flow.trigger_event_type = value;
      this.customEventType = '';
    }
    this.requestUpdate();
  }

  openFilterModal() {
    // TODO: Implement the filter modal
    alert('Filter modal not yet implemented');
  }

  getDefaultSelectedTools(): { server_name: string; tool_name: string }[] {
    // Select all enabled built-in tools by default
    return this.availableTools
      .filter((tool) => tool.source === 'builtin' && tool.is_enabled)
      .map((tool) => ({
        server_name: 'spacebridge-mcp',
        tool_name: tool.name,
      }));
  }

  renderToolSelection() {
    if (this.availableTools.length === 0) {
      return html`
        <div
          style="padding: 1rem; background: var(--sl-color-neutral-50); border-radius: 4px;"
        >
          Loading tools...
        </div>
      `;
    }

    // Group tools by source
    const builtinTools = this.availableTools.filter(
      (tool) => tool.source === 'builtin'
    );
    const mcpTools = this.availableTools.filter(
      (tool) => tool.source === 'mcp'
    );

    return html`
      <div>
        ${builtinTools.length > 0
          ? html`
              <div style="margin-bottom: 1.5rem;">
                <h4
                  style="margin-bottom: 0.75rem; font-size: 0.875rem; color: var(--sl-color-neutral-600); text-transform: uppercase; font-weight: 600;"
                >
                  Built-in Tools
                </h4>
                <div
                  style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem;"
                >
                  ${builtinTools.map(
                    (tool) => html`
                      <sl-checkbox
                        .checked=${this.isToolSelected(
                          'spacebridge-mcp',
                          tool.name
                        )}
                        @sl-change=${(e: any) =>
                          this.handleToolToggle(
                            'spacebridge-mcp',
                            tool.name,
                            e.target.checked
                          )}
                        ?disabled=${!tool.is_enabled}
                      >
                        ${tool.name}
                        ${!tool.is_enabled
                          ? html`<sl-badge variant="neutral" size="small"
                              >Disabled</sl-badge
                            >`
                          : ''}
                      </sl-checkbox>
                    `
                  )}
                </div>
              </div>
            `
          : ''}
        ${mcpTools.length > 0
          ? html`
              <div>
                <h4
                  style="margin-bottom: 0.75rem; font-size: 0.875rem; color: var(--sl-color-neutral-600); text-transform: uppercase; font-weight: 600;"
                >
                  MCP Server Tools
                </h4>
                <div
                  style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem;"
                >
                  ${mcpTools.map(
                    (tool) => html`
                      <sl-checkbox
                        .checked=${this.isToolSelected(
                          'spacebridge-mcp',
                          tool.name
                        )}
                        @sl-change=${(e: any) =>
                          this.handleToolToggle(
                            'spacebridge-mcp',
                            tool.name,
                            e.target.checked
                          )}
                        ?disabled=${!tool.is_enabled}
                      >
                        ${tool.name}
                        <sl-badge variant="primary" size="small"
                          >${tool.source_name}</sl-badge
                        >
                        ${!tool.is_enabled
                          ? html`<sl-badge variant="neutral" size="small"
                              >Disabled</sl-badge
                            >`
                          : ''}
                      </sl-checkbox>
                    `
                  )}
                </div>
              </div>
            `
          : ''}
      </div>
    `;
  }

  isToolSelected(serverName: string, toolName: string): boolean {
    if (!this.flow.allowed_mcp_tools) return false;
    return this.flow.allowed_mcp_tools.some(
      (tool) => tool.server_name === serverName && tool.tool_name === toolName
    );
  }

  handleToolToggle(serverName: string, toolName: string, checked: boolean) {
    if (!this.flow.allowed_mcp_tools) {
      this.flow.allowed_mcp_tools = [];
    }

    if (checked) {
      // Add tool
      this.flow.allowed_mcp_tools.push({
        server_name: serverName,
        tool_name: toolName,
      });
    } else {
      // Remove tool
      this.flow.allowed_mcp_tools = this.flow.allowed_mcp_tools.filter(
        (tool) =>
          !(tool.server_name === serverName && tool.tool_name === toolName)
      );
    }

    this.requestUpdate();
  }

  getGitTrackers() {
    // Return only GitHub and GitLab trackers
    return this.trackers.filter(
      (t) => t.tracker_type === 'github' || t.tracker_type === 'gitlab'
    );
  }

  handleGitCloneToggle(enabled: boolean) {
    if (enabled) {
      const gitTrackers = this.getGitTrackers();

      // Initialize git clone config with defaults
      this.flow.git_clone_config = {
        enabled: true,
        repositories: [],
        git_user_name: 'Preloop AI',
        git_user_email: 'git@preloop.ai',
        source_branch: 'main',
        target_branch: '',
        create_pull_request: false,
        pull_request_title: '',
        pull_request_description: '',
      };

      // Auto-add repository based on available trackers
      if (gitTrackers.length === 1) {
        // Single tracker - auto-select it
        this.addGitRepositoryWithTracker(gitTrackers[0].id);
      } else if (this.flow.trigger_event_source) {
        // Multiple trackers but trigger is set - use trigger tracker
        const triggerTracker = gitTrackers.find(
          (t) => t.id === this.flow.trigger_event_source
        );
        if (triggerTracker) {
          this.addGitRepositoryWithTracker(triggerTracker.id);
        }
      }
    } else {
      this.flow.git_clone_config = { enabled: false, repositories: [] };
    }
    this.requestUpdate();
  }

  addGitRepository() {
    if (!this.flow.git_clone_config) {
      this.flow.git_clone_config = { enabled: true, repositories: [] };
    }

    const gitTrackers = this.getGitTrackers();
    const defaultTracker = gitTrackers[0]?.id || '';

    this.flow.git_clone_config.repositories =
      this.flow.git_clone_config.repositories || [];
    const repoCount = this.flow.git_clone_config.repositories.length;

    this.flow.git_clone_config.repositories.push({
      tracker_id: defaultTracker,
      clone_path:
        repoCount === 0 ? '/workspace' : `/workspace-${repoCount + 1}`,
    });
    this.requestUpdate();
  }

  addGitRepositoryWithTracker(trackerId: string) {
    if (!this.flow.git_clone_config) {
      this.flow.git_clone_config = { enabled: true, repositories: [] };
    }

    this.flow.git_clone_config.repositories =
      this.flow.git_clone_config.repositories || [];
    const repoCount = this.flow.git_clone_config.repositories.length;

    this.flow.git_clone_config.repositories.push({
      tracker_id: trackerId,
      clone_path:
        repoCount === 0 ? '/workspace' : `/workspace-${repoCount + 1}`,
    });
    this.requestUpdate();
  }

  removeGitRepository(index: number) {
    if (this.flow.git_clone_config?.repositories) {
      this.flow.git_clone_config.repositories.splice(index, 1);
      this.requestUpdate();
    }
  }

  renderGitRepositories() {
    const repositories = this.flow.git_clone_config?.repositories || [];
    const gitTrackers = this.getGitTrackers();

    if (repositories.length === 0) {
      return html`
        <p style="margin-top: 0.5rem; color: var(--sl-color-neutral-600);">
          No repositories configured. Click "Add Repository" to get started.
        </p>
      `;
    }

    return html`
      ${repositories.map(
        (repo, index) => html`
          <div
            style="border: 1px solid var(--sl-color-neutral-200); border-radius: 4px; padding: 1rem; margin-top: 0.5rem;"
          >
            <div
              style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;"
            >
              <strong>Repository ${index + 1}</strong>
              <sl-button
                size="small"
                variant="danger"
                @click=${() => this.removeGitRepository(index)}
              >
                <sl-icon name="trash"></sl-icon>
              </sl-button>
            </div>

            ${gitTrackers.length > 1
              ? html`
                  <sl-select
                    label="Tracker"
                    .value=${repo.tracker_id}
                    @sl-change=${(e: any) => {
                      repo.tracker_id = e.target.value;
                      this.requestUpdate();
                    }}
                  >
                    ${gitTrackers.map(
                      (tracker) =>
                        html`<sl-option value=${tracker.id}
                          >${tracker.name} (${tracker.tracker_type})</sl-option
                        >`
                    )}
                  </sl-select>
                `
              : html`
                  <p style="margin-bottom: 0.5rem;">
                    <strong>Tracker:</strong> ${gitTrackers[0]?.name}
                  </p>
                `}

            <sl-input
              label="Repository URL (optional)"
              placeholder="Leave empty to use trigger project"
              .value=${repo.repository_url || ''}
              @sl-input=${(e: any) => {
                repo.repository_url = e.target.value;
              }}
              help-text="Manually specify repository URL or leave empty to use the project selected in trigger"
            ></sl-input>

            <sl-input
              label="Clone Path"
              .value=${repo.clone_path}
              @sl-input=${(e: any) => {
                repo.clone_path = e.target.value;
              }}
              help-text="Absolute path (starts with /) or relative to /workspace/"
            ></sl-input>

            <sl-input
              label="Branch (optional)"
              placeholder="Leave empty for default branch"
              .value=${repo.branch || ''}
              @sl-input=${(e: any) => {
                repo.branch = e.target.value;
              }}
            ></sl-input>
          </div>
        `
      )}
    `;
  }

  handleTriggerTypeChange(newType: 'webhook' | 'tracker') {
    this.triggerType = newType;

    if (newType === 'webhook') {
      // Set webhook trigger
      this.flow.trigger_event_source = 'webhook';
      this.flow.trigger_event_type = 'webhook';
      // Clear tracker-specific fields
      this.flow.trigger_organization_id = undefined;
      this.flow.trigger_project_id = undefined;
    } else {
      // Clear webhook fields
      this.flow.trigger_event_source = undefined;
      this.flow.trigger_event_type = undefined;
    }

    this.requestUpdate();
  }

  renderWebhookTriggerFields() {
    // If editing and webhook config exists, show the URL
    if (!this.isNew && this.flow.webhook_config) {
      return html`
        <div>
          <p
            style="margin-bottom: var(--sl-spacing-medium); color: var(--sl-color-neutral-600);"
          >
            This flow will be triggered when a POST request is sent to the
            webhook URL below.
          </p>
          <div>
            <label
              style="display: block; margin-bottom: var(--sl-spacing-2x-small); font-weight: 600;"
            >
              Webhook URL
            </label>
            <div
              style="display: flex; gap: var(--sl-spacing-small); align-items: center;"
            >
              <sl-input
                readonly
                style="flex: 1;"
                value="${window.location.origin}/api/webhooks/flows/${this
                  .flowId}/${this.flow.webhook_config.webhook_secret}"
              ></sl-input>
              <sl-button @click=${() => this.copyWebhookUrl()}>
                <sl-icon name="clipboard"></sl-icon>
                Copy
              </sl-button>
            </div>
          </div>
          <div>
            <label
              style="display: block; margin-bottom: 0.5rem; font-weight: 500;"
            >
              Example Payload
            </label>
            <sl-textarea
              readonly
              rows="6"
              value='{
  "data": "your custom data",
  "event": "custom_event",
  "any_key": "any_value"
}'
              style="font-family: monospace;"
            ></sl-textarea>
            <p
              style="margin-top: 0.5rem; color: var(--sl-color-neutral-600); font-size: 0.875rem;"
            >
              The payload will be available in your prompt template via
              <code>{{trigger_event.payload.*}}</code>
            </p>
          </div>
        </div>
      `;
    }

    // For new flows, show info message
    return html`
      <div>
        <p style="color: var(--sl-color-neutral-600); margin: 0;">
          <sl-icon name="info-circle"></sl-icon>
          The webhook URL will be generated after you create the flow. You can
          then use it to trigger this flow from external services.
        </p>
      </div>
    `;
  }

  openAddTrackerDialog() {
    this.isAddingTracker = true;
  }

  private closeAddTrackerDialog() {
    this.isAddingTracker = false;
  }

  private async handleTrackerAdded(event: CustomEvent) {
    this.isAddingTracker = false;
    // Reload trackers list
    this.trackers = await getTrackers();

    // Auto-select the newly added tracker if we're in tracker mode
    if (this.triggerType === 'tracker' && this.trackers.length > 0) {
      // The newest tracker should be the last one
      const newestTracker = this.trackers[this.trackers.length - 1];
      this.flow.trigger_event_source = newestTracker.id;

      // Load organizations for the new tracker
      const allOrganizations = await listOrganizations();
      this.organizations = allOrganizations.filter(
        (org: any) => org.tracker_id === newestTracker.id
      );

      // Start polling for orgs if none exist yet
      if (this.organizations.length === 0) {
        this.startPollingOrganizations(newestTracker.id);
      }
    }

    this.requestUpdate();
  }

  openAddAIModelDialog() {
    this.isAddingAIModel = true;
  }

  closeAIModelDialog() {
    this.isAddingAIModel = false;
  }

  async handleAIModelCreated(event: CustomEvent) {
    const newModel = event.detail.model;

    // Reload models list
    this.models = await getAIModels();

    // Auto-select the newly created model
    if (newModel && newModel.id) {
      this.flow.ai_model_id = newModel.id;
    }

    this.requestUpdate();
  }

  renderTrackerTriggerFields() {
    // If no trackers, show add tracker button
    if (this.trackers.length === 0) {
      return html`
        <div style="text-align: center; padding: var(--sl-spacing-2x-large);">
          <p
            style="margin-bottom: var(--sl-spacing-medium); color: var(--sl-color-neutral-600);"
          >
            You don't have any trackers configured yet.
          </p>
          <sl-button variant="primary" @click=${this.openAddTrackerDialog}>
            <sl-icon slot="prefix" name="plus-lg"></sl-icon>
            Add New Tracker
          </sl-button>
        </div>
      `;
    }

    return html`
      <div class="form-grid">
        <sl-select
          label="Tracker"
          .value=${this.flow.trigger_event_source || ''}
          @sl-change=${this.handleTrackerChange}
        >
          ${this.trackers.map(
            (tracker) =>
              html`<sl-option value=${tracker.id}>${tracker.name}</sl-option>`
          )}
        </sl-select>
        <sl-select
          label="Organization"
          .value=${this.flow.trigger_organization_id || ''}
          @sl-change=${this.handleOrganizationChange}
          ?disabled=${this.isPollingOrganizations ||
          !this.flow.trigger_event_source}
        >
          ${this.isPollingOrganizations
            ? html`<sl-option value="">
                <sl-spinner style="font-size: 1rem;"></sl-spinner>
                Loading organizations...
              </sl-option>`
            : this.organizations.length === 0 &&
                this.flow.trigger_organization_id
              ? html`<sl-option value=${this.flow.trigger_organization_id}>
                  ${this.flow.trigger_organization_id} (syncing...)
                </sl-option>`
              : this.organizations.map(
                  (org) =>
                    html`<sl-option value=${org.id}>${org.name}</sl-option>`
                )}
        </sl-select>
        <sl-select
          label="Project"
          .value=${this.flow.trigger_project_id || ''}
          @sl-change=${(e: any) =>
            (this.flow.trigger_project_id = e.target.value)}
          ?disabled=${this.isPollingProjects ||
          !this.flow.trigger_organization_id}
        >
          ${this.isPollingProjects
            ? html`<sl-option value="">
                <sl-spinner style="font-size: 1rem;"></sl-spinner>
                Loading projects...
              </sl-option>`
            : (() => {
                // Filter projects by selected organization for trigger
                const orgProjects = this.projects.filter(
                  (proj: any) =>
                    proj.organization_id === this.flow.trigger_organization_id
                );
                return orgProjects.length === 0 && this.flow.trigger_project_id
                  ? html`<sl-option value=${this.flow.trigger_project_id}>
                      ${this.flow.trigger_project_id} (syncing...)
                    </sl-option>`
                  : orgProjects.map(
                      (proj: any) =>
                        html`<sl-option value=${proj.id}
                          >${proj.name}</sl-option
                        >`
                    );
              })()}
        </sl-select>
        <sl-select
          label="Event"
          .value=${this.flow.trigger_event_type || ''}
          @sl-change=${this.handleEventChange}
        >
          ${this.getEventOptions().map(
            (event) =>
              html`<sl-option value=${event.value}>${event.name}</sl-option>`
          )}
          <sl-option value="other">Other</sl-option>
        </sl-select>
        ${this.flow.trigger_event_type === 'other'
          ? html`
              <sl-input
                label="Custom Event"
                .value=${this.customEventType}
                @sl-input=${(e: any) => (this.customEventType = e.target.value)}
              ></sl-input>
            `
          : ''}
      </div>

      ${this.flow.trigger_event_source ? this.renderEventFilters() : ''}
    `;
  }

  renderEventFilters() {
    if (!this.flow.trigger_config) {
      this.flow.trigger_config = {};
    }

    const tracker = this.trackers.find(
      (t) => t.id === this.flow.trigger_event_source
    );
    if (!tracker) return '';

    // Check if any filters are defined
    const hasFilters =
      this.flow.trigger_config &&
      Object.keys(this.flow.trigger_config).length > 0;

    // Show filters if expanded or if any filter is already defined
    const showFilters = this.filtersExpanded || hasFilters;

    // Determine if this is a PR/MR event
    const isMREvent =
      this.flow.trigger_event_type?.includes('merge_request') ||
      this.flow.trigger_event_type?.includes('pull_request');

    return html`
      <div style="margin-top: 1.5rem;">
        <div
          style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;"
        >
          <label style="font-weight: 500;">
            Event Filters (Optional)
            <span style="font-weight: 400; color: var(--sl-color-neutral-600);">
              - Only trigger when conditions match
            </span>
          </label>
          ${!showFilters
            ? html`
                <sl-button
                  size="small"
                  @click=${() => (this.filtersExpanded = true)}
                >
                  <sl-icon slot="prefix" name="plus-circle"></sl-icon>
                  Add Filters
                </sl-button>
              `
            : html`
                <sl-button
                  size="small"
                  variant="text"
                  @click=${() => (this.filtersExpanded = false)}
                >
                  <sl-icon slot="prefix" name="dash-circle"></sl-icon>
                  Hide Filters
                </sl-button>
              `}
        </div>

        ${showFilters
          ? html`
              <div class="form-grid">
                <!-- Author/Creator filter -->
                <sl-input
                  label="Created By (username)"
                  placeholder="e.g., octocat, admin@example.com"
                  .value=${this.flow.trigger_config?.author || ''}
                  @sl-input=${(e: any) => {
                    if (!this.flow.trigger_config)
                      this.flow.trigger_config = {};
                    const value = e.target.value.trim();
                    if (value) {
                      this.flow.trigger_config.author = value;
                    } else {
                      delete this.flow.trigger_config.author;
                    }
                    this.requestUpdate();
                  }}
                  help-text="Filter by who created the issue/PR"
                ></sl-input>

                <!-- Assignee filter -->
                <sl-input
                  label="Assigned To (username)"
                  placeholder="e.g., john_doe"
                  .value=${this.flow.trigger_config?.assignee || ''}
                  @sl-input=${(e: any) => {
                    if (!this.flow.trigger_config)
                      this.flow.trigger_config = {};
                    const value = e.target.value.trim();
                    if (value) {
                      this.flow.trigger_config.assignee = value;
                    } else {
                      delete this.flow.trigger_config.assignee;
                    }
                    this.requestUpdate();
                  }}
                  help-text="Filter by assignee (matches if any assignee matches)"
                ></sl-input>

                <!-- Labels filter -->
                <sl-input
                  label="Labels (comma-separated)"
                  placeholder="e.g., bug, critical, backend"
                  .value=${this.flow.trigger_config?.labels?.join(', ') || ''}
                  @sl-input=${(e: any) => {
                    if (!this.flow.trigger_config)
                      this.flow.trigger_config = {};
                    const value = e.target.value.trim();
                    if (value) {
                      this.flow.trigger_config.labels = value
                        .split(',')
                        .map((l: string) => l.trim())
                        .filter((l: string) => l.length > 0);
                    } else {
                      delete this.flow.trigger_config.labels;
                    }
                    this.requestUpdate();
                  }}
                  help-text="Filter by labels (triggers if ANY label matches)"
                ></sl-input>

                <!-- Milestone filter (GitHub/GitLab only) -->
                ${tracker.tracker_type !== 'jira'
                  ? html`
                      <sl-input
                        label="Milestone"
                        placeholder="e.g., v1.0, Sprint 10"
                        .value=${this.flow.trigger_config?.milestone || ''}
                        @sl-input=${(e: any) => {
                          if (!this.flow.trigger_config)
                            this.flow.trigger_config = {};
                          const value = e.target.value.trim();
                          if (value) {
                            this.flow.trigger_config.milestone = value;
                          } else {
                            delete this.flow.trigger_config.milestone;
                          }
                          this.requestUpdate();
                        }}
                        help-text="Filter by milestone name"
                      ></sl-input>
                    `
                  : ''}

                <!-- Priority filter (Jira only) -->
                ${tracker.tracker_type === 'jira'
                  ? html`
                      <sl-select
                        label="Priority"
                        .value=${this.flow.trigger_config?.priority || ''}
                        @sl-change=${(e: any) => {
                          if (!this.flow.trigger_config)
                            this.flow.trigger_config = {};
                          const value = e.target.value;
                          if (value) {
                            this.flow.trigger_config.priority = value;
                          } else {
                            delete this.flow.trigger_config.priority;
                          }
                          this.requestUpdate();
                        }}
                        clearable
                      >
                        <sl-option value="">Any Priority</sl-option>
                        <sl-option value="Highest">Highest</sl-option>
                        <sl-option value="High">High</sl-option>
                        <sl-option value="Medium">Medium</sl-option>
                        <sl-option value="Low">Low</sl-option>
                        <sl-option value="Lowest">Lowest</sl-option>
                      </sl-select>

                      <sl-input
                        label="Issue Type"
                        placeholder="e.g., Task, Bug, Story"
                        .value=${this.flow.trigger_config?.issue_type || ''}
                        @sl-input=${(e: any) => {
                          if (!this.flow.trigger_config)
                            this.flow.trigger_config = {};
                          const value = e.target.value.trim();
                          if (value) {
                            this.flow.trigger_config.issue_type = value;
                          } else {
                            delete this.flow.trigger_config.issue_type;
                          }
                          this.requestUpdate();
                        }}
                        help-text="Filter by Jira issue type"
                      ></sl-input>
                    `
                  : ''}

                <!-- Merge Request / Pull Request State Filters -->
                ${isMREvent && tracker.tracker_type !== 'jira'
                  ? html`
                      <sl-checkbox
                        ?checked=${this.flow.trigger_config?.merged === true}
                        @sl-change=${(e: any) => {
                          if (!this.flow.trigger_config)
                            this.flow.trigger_config = {};
                          if (e.target.checked) {
                            this.flow.trigger_config.merged = true;
                          } else {
                            delete this.flow.trigger_config.merged;
                          }
                          this.requestUpdate();
                        }}
                      >
                        Only when
                        ${tracker.tracker_type === 'gitlab'
                          ? 'Merge Request'
                          : 'Pull Request'}
                        is merged
                      </sl-checkbox>

                      <sl-checkbox
                        ?checked=${this.flow.trigger_config?.draft === false}
                        @sl-change=${(e: any) => {
                          if (!this.flow.trigger_config)
                            this.flow.trigger_config = {};
                          if (e.target.checked) {
                            this.flow.trigger_config.draft = false;
                          } else {
                            delete this.flow.trigger_config.draft;
                          }
                          this.requestUpdate();
                        }}
                      >
                        Only when marked as ready (not draft)
                      </sl-checkbox>

                      ${tracker.tracker_type === 'gitlab'
                        ? html`
                            <sl-checkbox
                              ?checked=${this.flow.trigger_config
                                ?.detailed_merge_status === 'approved'}
                              @sl-change=${(e: any) => {
                                if (!this.flow.trigger_config)
                                  this.flow.trigger_config = {};
                                if (e.target.checked) {
                                  this.flow.trigger_config.detailed_merge_status =
                                    'approved';
                                } else {
                                  delete this.flow.trigger_config
                                    .detailed_merge_status;
                                }
                                this.requestUpdate();
                              }}
                            >
                              Only when approved
                            </sl-checkbox>

                            <sl-select
                              label="Merge Status"
                              .value=${this.flow.trigger_config?.state || ''}
                              @sl-change=${(e: any) => {
                                if (!this.flow.trigger_config)
                                  this.flow.trigger_config = {};
                                const value = e.target.value;
                                if (value) {
                                  this.flow.trigger_config.state = value;
                                } else {
                                  delete this.flow.trigger_config.state;
                                }
                                this.requestUpdate();
                              }}
                              clearable
                              help-text="Filter by merge request state"
                            >
                              <sl-option value="">Any State</sl-option>
                              <sl-option value="opened">Opened</sl-option>
                              <sl-option value="closed">Closed</sl-option>
                              <sl-option value="merged">Merged</sl-option>
                            </sl-select>
                          `
                        : tracker.tracker_type === 'github'
                          ? html`
                              <sl-select
                                label="Pull Request State"
                                .value=${this.flow.trigger_config?.state || ''}
                                @sl-change=${(e: any) => {
                                  if (!this.flow.trigger_config)
                                    this.flow.trigger_config = {};
                                  const value = e.target.value;
                                  if (value) {
                                    this.flow.trigger_config.state = value;
                                  } else {
                                    delete this.flow.trigger_config.state;
                                  }
                                  this.requestUpdate();
                                }}
                                clearable
                                help-text="Filter by pull request state"
                              >
                                <sl-option value="">Any State</sl-option>
                                <sl-option value="open">Open</sl-option>
                                <sl-option value="closed">Closed</sl-option>
                              </sl-select>

                              <sl-select
                                label="Mergeable State"
                                .value=${this.flow.trigger_config
                                  ?.mergeable_state || ''}
                                @sl-change=${(e: any) => {
                                  if (!this.flow.trigger_config)
                                    this.flow.trigger_config = {};
                                  const value = e.target.value;
                                  if (value) {
                                    this.flow.trigger_config.mergeable_state =
                                      value;
                                  } else {
                                    delete this.flow.trigger_config
                                      .mergeable_state;
                                  }
                                  this.requestUpdate();
                                }}
                                clearable
                                help-text="Filter by whether PR can be merged"
                              >
                                <sl-option value="">Any</sl-option>
                                <sl-option value="clean"
                                  >Clean (can merge)</sl-option
                                >
                                <sl-option value="unstable"
                                  >Unstable (tests failing)</sl-option
                                >
                                <sl-option value="dirty"
                                  >Dirty (merge conflict)</sl-option
                                >
                                <sl-option value="blocked">Blocked</sl-option>
                              </sl-select>
                            `
                          : ''}
                    `
                  : ''}
              </div>

              <sl-alert variant="primary" open style="margin-top: 1rem;">
                <sl-icon slot="icon" name="info-circle"></sl-icon>
                <strong>How filters work:</strong> Leave empty to match all
                events. When multiple filters are set, ALL conditions must match
                for the flow to trigger.
              </sl-alert>
            `
          : ''}
      </div>
    `;
  }
}
