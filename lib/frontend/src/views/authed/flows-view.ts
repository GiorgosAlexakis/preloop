import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import { router } from '../../router';
import { Router } from '@vaadin/router';
import {
  getFlows,
  getFlowPresets,
  cloneFlowPreset,
  deleteFlow,
} from '../../api';

interface Flow {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  account_id?: string;
}

@customElement('flows-view')
export class FlowsView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: 16px;
    }
    .presets-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
    }
  `;

  @state()
  private flows: Flow[] = [];

  @state()
  private presets: Flow[] = [];

  @state()
  private isAlertVisible = false;

  async connectedCallback() {
    super.connectedCallback();
    this.flows = await getFlows();
    this.presets = await getFlowPresets();
    this.isAlertVisible = !localStorage.getItem('flows-alert-dismissed');
  }

  render() {
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
              style="display: block; margin: 0 auto; max-width: 600px;"
            >
              <sl-icon slot="icon" name="info-circle"></sl-icon>

              <span style="font-size: 1.3rem;"
                ><strong>Welcome to Event-Driven Agentic Flows!</strong>
                <br />Automate your workflows by creating intelligent agents
                that respond to events in your issue tracker. Get started by
                exploring the presets below, or create a new flow from
                scratch.</span
              >
            </sl-alert>
          `
        : ''}
      ${this.flows.length > 0
        ? html`<h2>Your Flows</h2>
            <ul>
              ${this.flows.map(
                (flow) => html`
                  <li>
                    <a href=${router.urlForPath(`/console/flows/${flow.id}`)}
                      >${flow.name}</a
                    >
                  </li>
                `
              )}
            </ul> `
        : ''}
      <h2>Presets</h2>
      <div class="presets-grid">
        ${this.presets.map(
          (preset) => html`
            <sl-card class="preset-card">
              <div
                slot="header"
                style="display: flex; justify-content: space-between; align-items: center;"
              >
                <div>
                  <sl-icon name=${preset.icon || 'gear'}></sl-icon>
                  ${preset.name}
                </div>
                <div>
                  <sl-button
                    size="small"
                    @click=${() => this.clonePreset(preset.id)}
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
          `
        )}
      </div>
    `;
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
