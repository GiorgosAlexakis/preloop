import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { getFlow, createFlow, updateFlow } from '../../api';

interface Flow {
  id?: string;
  name: string;
  description?: string;
  // Add other flow properties here as needed
}

@customElement('flow-view')
export class FlowView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: 16px;
    }
    form {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .form-field {
      display: flex;
      flex-direction: column;
    }
  `;

  @property()
  flowId?: string;

  @state()
  private flow: Flow = { name: '' };

  @state()
  private isNew = true;

  async connectedCallback() {
    super.connectedCallback();
    if (this.flowId) {
      this.isNew = false;
      this.flow = await getFlow(this.flowId);
    }
  }

  render() {
    return html`
      <h1>${this.isNew ? 'Create Flow' : 'Edit Flow'}</h1>
      <form @submit=${this.handleSubmit}>
        <div class="form-field">
          <label for="name">Name</label>
          <input
            id="name"
            .value=${this.flow.name}
            @input=${(e: Event) => this.handleInputChange('name', e)}
            required
          />
        </div>
        <div class="form-field">
          <label for="description">Description</label>
          <textarea
            id="description"
            .value=${this.flow.description || ''}
            @input=${(e: Event) => this.handleInputChange('description', e)}
          ></textarea>
        </div>

        <!-- More form fields will be added here -->

        <button type="submit">${this.isNew ? 'Create' : 'Update'}</button>
      </form>
    `;
  }

  handleInputChange(field: keyof Flow, e: Event) {
    const target = e.target as HTMLInputElement | HTMLTextAreaElement;
    this.flow = { ...this.flow, [field]: target.value };
  }

  async handleSubmit(e: Event) {
    e.preventDefault();
    if (this.isNew) {
      const newFlow = await createFlow(this.flow);
      Router.go(`/console/flows/${newFlow.id}`);
    } else {
      await updateFlow(this.flowId!, this.flow);
      // Optionally, show a success message
    }
  }
}
