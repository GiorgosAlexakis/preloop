import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import { router } from '../../router';
import { Router } from '@vaadin/router';
import {
  getFlows,
  getFlowPresets,
  cloneFlowPreset,
  deleteFlow,
  getFlowExecutions,
  triggerFlowExecution,
} from '../../api';

interface Flow {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  account_id?: string;
}

interface FlowExecution {
  id: string;
  flow_id: string;
  status: string;
  start_time: string;
  end_time?: string;
}

@customElement('flows-view')
export class FlowsView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: 16px;
    }
    .flows-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }
    .presets-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
    }
    .flow-card {
      cursor: pointer;
      transition:
        transform 0.2s,
        box-shadow 0.2s;
    }
    .flow-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
    }
    .flow-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .flow-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 1.2rem;
      font-weight: 600;
    }
    .flow-description {
      color: var(--sl-color-neutral-600);
      margin-bottom: 12px;
      font-size: 0.9rem;
    }
    .flow-stats {
      display: flex;
      gap: 16px;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--sl-color-neutral-200);
    }
    .stat-item {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 0.85rem;
      color: var(--sl-color-neutral-600);
    }
    .active-executions {
      margin-bottom: 32px;
    }
    .executions-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 12px;
    }
    .execution-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px;
      background: var(--sl-color-neutral-50);
      border-radius: 4px;
      transition: background 0.2s;
    }
    .execution-item:hover {
      background: var(--sl-color-neutral-100);
    }
    .execution-info {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 24px 0 16px 0;
    }
    .empty-state {
      text-align: center;
      padding: 48px 16px;
      color: var(--sl-color-neutral-500);
    }
  `;

  @state()
  private flows: Flow[] = [];

  @state()
  private presets: Flow[] = [];

  @state()
  private executions: FlowExecution[] = [];

  @state()
  private isAlertVisible = false;

  @state()
  private isLoading = true;

  @state()
  private triggeringFlowId: string | null = null;

  async connectedCallback() {
    super.connectedCallback();
    await this.loadData();
    this.isAlertVisible = !localStorage.getItem('flows-alert-dismissed');

    // Refresh executions every 10 seconds
    setInterval(() => this.refreshExecutions(), 10000);
  }

  async loadData() {
    this.isLoading = true;
    try {
      [this.flows, this.presets, this.executions] = await Promise.all([
        getFlows(),
        getFlowPresets(),
        getFlowExecutions(),
      ]);
    } finally {
      this.isLoading = false;
    }
  }

  async refreshExecutions() {
    this.executions = await getFlowExecutions();
  }

  render() {
    if (this.isLoading) {
      return html`
        <view-header headerText="Flows"></view-header>
        <div style="display: flex; justify-content: center; padding: 48px;">
          <sl-spinner style="font-size: 3rem;"></sl-spinner>
        </div>
      `;
    }

    const activeExecutions = this.executions.filter(
      (e) => e.status === 'RUNNING' || e.status === 'STARTING'
    );

    return html`
      <view-header headerText="Flows">
        <div slot="main-column">
          <sl-button
            variant="primary"
            @click=${() => Router.go('/console/flows/new')}
          >
            <sl-icon slot="prefix" name="plus-lg"></sl-icon>
            Create New Flow
          </sl-button>
        </div>
      </view-header>

      ${this.isAlertVisible
        ? html`
            <sl-alert
              open
              closable
              variant="success"
              @sl-after-hide=${this.handleAlertDismiss}
              style="display: block; margin: 0 auto; max-width: 600px; margin-bottom: 24px;"
            >
              <sl-icon slot="icon" name="info-circle"></sl-icon>
              <span style="font-size: 1.3rem;">
                <strong>Welcome to Event-Driven Agentic Flows!</strong>
                <br />Automate your workflows by creating intelligent agents
                that respond to events in your issue tracker. Get started by
                exploring the presets below, or create a new flow from scratch.
              </span>
            </sl-alert>
          `
        : ''}
      ${activeExecutions.length > 0
        ? html`
            <div class="active-executions">
              <div class="section-header">
                <h2>
                  <sl-icon name="lightning-fill"></sl-icon>
                  Active Executions
                </h2>
                <sl-button
                  size="small"
                  href=${router.urlForPath('/console/flows/executions')}
                >
                  View All
                </sl-button>
              </div>
              <div class="executions-list">
                ${activeExecutions
                  .slice(0, 5)
                  .map((exec) => this.renderExecutionItem(exec))}
              </div>
            </div>
          `
        : ''}
      ${this.flows.length > 0
        ? html`
            <div class="section-header">
              <h2>Your Flows</h2>
            </div>
            <div class="flows-grid">
              ${this.flows.map((flow) => this.renderFlowCard(flow))}
            </div>
          `
        : html`
            <div class="empty-state">
              <sl-icon
                name="inbox"
                style="font-size: 3rem; opacity: 0.3;"
              ></sl-icon>
              <p>
                No flows yet. Create your first flow or clone a preset below.
              </p>
            </div>
          `}

      <sl-divider></sl-divider>

      <div class="section-header">
        <h2>Presets</h2>
      </div>
      <div class="presets-grid">
        ${this.presets.map((preset) => this.renderPresetCard(preset))}
      </div>
    `;
  }

  renderFlowCard(flow: Flow) {
    const flowExecutions = this.executions.filter((e) => e.flow_id === flow.id);
    const activeCount = flowExecutions.filter(
      (e) => e.status === 'RUNNING' || e.status === 'STARTING'
    ).length;
    const totalCount = flowExecutions.length;

    return html`
      <sl-card class="flow-card">
        <div slot="header" class="flow-header">
          <div class="flow-title">
            <sl-icon name=${flow.icon || 'gear'}></sl-icon>
            ${flow.name}
          </div>
          ${activeCount > 0
            ? html`<sl-badge variant="primary" pulse
                >${activeCount} active</sl-badge
              >`
            : ''}
        </div>

        ${flow.description
          ? html`<div class="flow-description">${flow.description}</div>`
          : ''}

        <div class="flow-stats">
          <div class="stat-item">
            <sl-icon name="play-circle"></sl-icon>
            <span>${totalCount} executions</span>
          </div>
        </div>

        <div
          slot="footer"
          style="display: flex; gap: 8px; justify-content: space-between;"
        >
          <sl-button
            size="small"
            href=${router.urlForPath(`/console/flows/${flow.id}`)}
          >
            <sl-icon slot="prefix" name="pencil"></sl-icon>
            Edit
          </sl-button>
          <sl-button
            size="small"
            variant="primary"
            @click=${() => this.triggerTestRun(flow.id)}
            ?loading=${this.triggeringFlowId === flow.id}
          >
            <sl-icon slot="prefix" name="play-fill"></sl-icon>
            Test Run
          </sl-button>
        </div>
      </sl-card>
    `;
  }

  renderPresetCard(preset: Flow) {
    return html`
      <sl-card class="preset-card">
        <div
          slot="header"
          style="display: flex; justify-content: space-between; align-items: center;"
        >
          <div style="display: flex; align-items: center; gap: 8px;">
            <sl-icon name=${preset.icon || 'gear'}></sl-icon>
            ${preset.name}
          </div>
          <div style="display: flex; gap: 4px;">
            <sl-button size="small" @click=${() => this.clonePreset(preset.id)}
              >Clone</sl-button
            >
            ${preset.account_id
              ? html`
                  <sl-button
                    size="small"
                    variant="danger"
                    @click=${() => this.removePreset(preset.id)}
                    >Remove</sl-button
                  >
                `
              : ''}
          </div>
        </div>
        ${preset.description}
      </sl-card>
    `;
  }

  renderExecutionItem(exec: FlowExecution) {
    const flow = this.flows.find((f) => f.id === exec.flow_id);
    return html`
      <div
        class="execution-item"
        @click=${() => Router.go(`/console/flows/executions/${exec.id}`)}
        style="cursor: pointer;"
      >
        <div class="execution-info">
          <sl-badge variant=${this.getStatusVariant(exec.status)}>
            ${exec.status}
          </sl-badge>
          <div>
            <strong>${flow?.name || 'Unknown Flow'}</strong>
            <div
              style="font-size: 0.85rem; color: var(--sl-color-neutral-600);"
            >
              Started ${new Date(exec.start_time).toLocaleString()}
            </div>
          </div>
        </div>
        <sl-button size="small">
          <sl-icon name="arrow-right"></sl-icon>
        </sl-button>
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
      case 'STARTING':
        return 'primary';
      default:
        return 'neutral';
    }
  }

  async triggerTestRun(flowId: string) {
    this.triggeringFlowId = flowId;
    try {
      const execution = await triggerFlowExecution(flowId);
      Router.go(`/console/flows/executions/${execution.id}`);
    } catch (error) {
      console.error('Failed to trigger test run:', error);
      // TODO: Show error notification
    } finally {
      this.triggeringFlowId = null;
    }
  }

  handleAlertDismiss() {
    this.isAlertVisible = false;
    localStorage.setItem('flows-alert-dismissed', 'true');
  }

  async clonePreset(presetId: string) {
    Router.go(`/console/flows/new?preset_id=${presetId}`);
  }

  async removePreset(presetId: string) {
    await deleteFlow(presetId);
    this.presets = await getFlowPresets();
  }
}
