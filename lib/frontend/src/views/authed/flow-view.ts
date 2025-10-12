import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import {
  getFlow,
  createFlow,
  updateFlow,
  getTrackers,
  getAIModels,
  getFlowPresets,
  listOrganizations,
  listProjects,
} from '../../api';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/checkbox/checkbox.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '../../components/icon-selector.ts';

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
  ai_model_id?: string;
  prompt_template?: string;
  allowed_mcp_servers?: string[];
  allowed_mcp_tools?: { server_name: string; tool_name: string }[];
  max_iterations?: number;
  max_budget?: number;
  is_preset?: boolean;
  is_enabled?: boolean;
  agent_type?: string;
}

@customElement('flow-view')
export class FlowView extends LitElement {
  // Vaadin Router lifecycle callback
  onBeforeEnter(location: any) {
    this.flowId = location.params.flowId;
  }

  static styles = css`
    :host {
      display: block;
      padding: 16px;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    sl-card {
      margin-bottom: 16px;
    }
    sl-input,
    sl-textarea,
    sl-select {
      margin-bottom: 1rem;
    }
  `;

  @property()
  flowId?: string;

  @state()
  private flow: Flow = { name: '' };

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
  private presets: any[] = [];

  @state()
  private showPresets = true;

  @state()
  private organizations: any[] = [];

  @state()
  private projects: any[] = [];

  @state()
  private recentExecutions: any[] = [];

  async connectedCallback() {
    super.connectedCallback();

    const urlParams = new URLSearchParams(window.location.search);
    const presetId = urlParams.get('preset_id');
    this.isEditing = urlParams.get('edit') === 'true';

    if (this.flowId) {
      // Viewing or editing an existing flow
      this.isNew = false;
      this.showPresets = false;
      this.flow = await getFlow(this.flowId);

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
    } else if (presetId) {
      // Creating from preset
      this.trackers = await getTrackers();
      this.models = await getAIModels();
      this.presets = await getFlowPresets();
      const preset = this.presets.find((p) => p.id === presetId);
      if (preset) {
        this.selectPreset(preset);
      }
    } else {
      // Creating new flow
      this.trackers = await getTrackers();
      this.models = await getAIModels();
      this.presets = await getFlowPresets();
    }
  }

  render() {
    if (!this.isNew && !this.isEditing) {
      // View mode - show flow details
      return this.renderFlowDetails();
    }

    // Edit/Create mode - show form
    return html`
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
      <view-header headerText="${this.flow.name}"></view-header>
      <div class="column-layout">
        <div class="main-column">
          <!-- Actions -->
          <div style="display: flex; gap: 8px; margin-bottom: 16px;">
            <sl-button href="/console/flows">
              <sl-icon name="arrow-left"></sl-icon>
              Back to Flows
            </sl-button>
            <sl-button href="/console/flows/${this.flowId}?edit=true">
              <sl-icon name="pencil"></sl-icon>
              Edit Flow
            </sl-button>
            <sl-button variant="primary" @click=${this.testRun}>
              <sl-icon name="play-circle"></sl-icon>
              Test Run
            </sl-button>
          </div>

          <!-- Flow Info Card -->
          <sl-card style="margin-bottom: 16px;">
            <div slot="header">
              <sl-icon name="info-circle"></sl-icon>
              Flow Details
            </div>
            <div
              style="display: grid; grid-template-columns: 150px 1fr; gap: 12px;"
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
              <span
                >${this.flow.trigger_event_source} -
                ${this.flow.trigger_event_type}</span
              >

              <strong>Status:</strong>
              <sl-badge
                variant="${this.flow.is_enabled ? 'success' : 'neutral'}"
              >
                ${this.flow.is_enabled ? 'Enabled' : 'Disabled'}
              </sl-badge>
            </div>
          </sl-card>

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

  async testRun() {
    if (!this.flowId) return;
    try {
      const execution = await import('../../api').then((m) =>
        m.triggerFlowExecution(this.flowId!)
      );
      // Navigate to execution view
      window.location.href = `/console/flows/executions/${execution.id}`;
    } catch (error) {
      console.error('Failed to trigger flow execution:', error);
      alert('Failed to trigger flow execution');
    }
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
          <div slot="header">
            <sl-icon name="info-circle"></sl-icon>
            General
          </div>
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
          <icon-selector
            .selectedIcon=${this.flow.icon || 'gear'}
            @icon-change=${(e: any) => (this.flow.icon = e.detail.icon)}
          ></icon-selector>
        </sl-card>

        <sl-card>
          <div slot="header">
            <sl-icon name="calendar-event"></sl-icon>
            Trigger
          </div>
          <div class="form-grid">
            <sl-select
              label="Tracker"
              .value=${this.flow.trigger_event_source || ''}
              @sl-change=${this.handleTrackerChange}
            >
              ${this.trackers.map(
                (tracker) =>
                  html`<sl-option value=${tracker.id}
                    >${tracker.name}</sl-option
                  >`
              )}
            </sl-select>
            <sl-select
              label="Organization"
              .value=${this.flow.trigger_organization_id || ''}
              @sl-change=${this.handleOrganizationChange}
            >
              ${this.organizations.map(
                (org) =>
                  html`<sl-option value=${org.id}>${org.name}</sl-option>`
              )}
            </sl-select>
            <sl-select
              label="Project"
              .value=${this.flow.trigger_project_id || ''}
              @sl-change=${(e: any) =>
                (this.flow.trigger_project_id = e.target.value)}
            >
              ${this.projects.map(
                (proj) =>
                  html`<sl-option value=${proj.id}>${proj.name}</sl-option>`
              )}
            </sl-select>
            <sl-select
              label="Event"
              .value=${this.flow.trigger_event_type || ''}
              @sl-change=${this.handleEventChange}
            >
              ${this.getEventOptions().map(
                (event) =>
                  html`<sl-option value=${event.value}
                    >${event.name}</sl-option
                  >`
              )}
              <sl-option value="other">Other</sl-option>
            </sl-select>
            ${this.flow.trigger_event_type === 'other'
              ? html`
                  <sl-input
                    label="Custom Event"
                    .value=${this.customEventType}
                    @sl-input=${(e: any) =>
                      (this.customEventType = e.target.value)}
                  ></sl-input>
                `
              : ''}
            <sl-button @click=${() => this.openFilterModal()}
              >Add Filters</sl-button
            >
          </div>
        </sl-card>

        <sl-card>
          <div slot="header">
            <sl-icon name="robot"></sl-icon>
            Agent Configuration
          </div>
          <sl-select
            label="AI Model"
            .value=${this.flow.ai_model_id || ''}
            @sl-change=${(e: any) => (this.flow.ai_model_id = e.target.value)}
          >
            ${this.models.map(
              (model) =>
                html`<sl-option value=${model.id}>${model.name}</sl-option>`
            )}
          </sl-select>
          <sl-textarea
            label="Prompt"
            .value=${this.flow.prompt_template || ''}
            @sl-input=${(e: Event) =>
              this.handleInputChange('prompt_template', e)}
          ></sl-textarea>
        </sl-card>

        <sl-card>
          <div slot="header">
            <sl-icon name="tools"></sl-icon>
            Tools
          </div>
          <sl-select
            label="MCP Servers"
            multiple
            clearable
            .value=${this.flow.allowed_mcp_servers || []}
            @sl-change=${(e: any) =>
              (this.flow.allowed_mcp_servers = e.target.value)}
          >
            ${this.mcpServers.map(
              (server) =>
                html`<sl-option value=${server.name}>${server.name}</sl-option>`
            )}
          </sl-select>
        </sl-card>

        <sl-card>
          <div slot="header">
            <sl-icon name="gear"></sl-icon>
            Settings
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
        <sl-button type="submit" variant="primary"
          >${this.isNew ? 'Create' : 'Update'}</sl-button
        >
        <sl-button @click=${() => Router.go('/console/flows')}
          >Cancel</sl-button
        >
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
    const payload: Partial<Flow> = {};
    for (const key in this.flow) {
      const value = this.flow[key as keyof Flow];
      if (value !== null && value !== undefined && value !== '') {
        (payload as any)[key] = value;
      }
    }

    if (this.isNew) {
      const newFlow = await createFlow(payload);
      Router.go(`/console/flows/${newFlow.id}`);
    } else {
      await updateFlow(this.flowId!, payload);
      // Optionally, show a success message
    }
  }
  async handleTrackerChange(e: any) {
    const trackerId = e.target.value;
    this.flow.trigger_event_source = trackerId;
    const allOrganizations = await listOrganizations();
    this.organizations = allOrganizations.filter(
      (org: any) => org.tracker_id === trackerId
    );
  }

  async handleOrganizationChange(e: any) {
    const orgId = e.target.value;
    this.flow.trigger_organization_id = orgId;
    const allProjects = await listProjects();
    this.projects = allProjects.filter(
      (proj: any) => proj.organization_id === orgId
    );
  }

  @state()
  private customEventType = '';

  getEventOptions() {
    const tracker = this.trackers.find(
      (t) => t.id === this.flow.trigger_event_source
    );
    if (tracker) {
      switch (tracker.tracker_type) {
        case 'github':
          return [
            { name: 'Pull Request Opened', value: 'pull_request_opened' },
            { name: 'Issue Opened', value: 'issue_opened' },
            { name: 'Commit to Main', value: 'commit_to_main' },
          ];
        case 'gitlab':
          return [
            { name: 'Merge Request Opened', value: 'merge_request_opened' },
            { name: 'Issue Opened', value: 'issue_opened' },
            { name: 'Commit to Main', value: 'commit_to_main' },
          ];
        case 'jira':
          return [
            { name: 'Issue Created', value: 'issue_created' },
            { name: 'Issue Updated', value: 'issue_updated' },
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
}
