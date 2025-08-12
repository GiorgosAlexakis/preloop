import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { router } from '../../router';
import { Router } from '@vaadin/router';
import { getFlows, getFlowPresets, cloneFlowPreset } from '../../api';

interface Flow {
  id: string;
  name: string;
}

@customElement('flows-view')
export class FlowsView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: 16px;
    }
  `;

  @state()
  private flows: Flow[] = [];

  @state()
  private presets: Flow[] = [];

  async connectedCallback() {
    super.connectedCallback();
    this.flows = await getFlows();
    this.presets = await getFlowPresets();
  }

  render() {
    return html`
      <div
        style="display: flex; justify-content: space-between; align-items: center;"
      >
        <h1>Flows</h1>
        <button @click=${() => Router.go('/console/flows/new')}>
          Create New Flow
        </button>
      </div>
      <p>Manage your Agentic Flows.</p>

      <h2>Your Flows</h2>
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
      </ul>

      <h2>Presets</h2>
      <ul>
        ${this.presets.map(
          (preset) => html`
            <li>
              <span>${preset.name}</span>
              <button @click=${() => this.clonePreset(preset.id)}>Clone</button>
            </li>
          `
        )}
      </ul>
    `;
  }

  async clonePreset(presetId: string) {
    await cloneFlowPreset(presetId);
    this.flows = await getFlows();
  }
}
