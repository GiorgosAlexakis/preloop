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
}

@customElement('flow-view')
export class FlowView extends LitElement {
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

  async connectedCallback() {
    super.connectedCallback();
    this.trackers = await getTrackers();
    this.models = await getAIModels();
    this.presets = await getFlowPresets();
    // this.mcpServers = await getMcpServers(); // This will be uncommented once the API function is created
    const urlParams = new URLSearchParams(window.location.search);
    const presetId = urlParams.get('preset_id');
    if (presetId) {
      const preset = this.presets.find((p) => p.id === presetId);
      if (preset) {
        this.selectPreset(preset);
      }
    } else if (this.flowId) {
      this.isNew = false;
      this.showPresets = false;
      this.flow = await getFlow(this.flowId);
    }
  }

  render() {
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
