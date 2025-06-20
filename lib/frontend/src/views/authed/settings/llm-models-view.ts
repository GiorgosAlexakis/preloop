import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { repeat } from 'lit/directives/repeat.js';
import * as api from '../../../api';
import { LlmModel } from '../../../types';
import '@vaadin/button';
import '@vaadin/dialog';
import '@vaadin/text-field';
import '@vaadin/password-field';
import '@vaadin/select';
import '@vaadin/list-box';
import '@vaadin/item';

@customElement('llm-models-view')
export class LlmModelsView extends LitElement {
  @state()
  private models: LlmModel[] = [];

  @state()
  private isLoading = true;

  @state()
  private isModalOpen = false;

  @state()
  private isEditing = false;

  @state()
  private currentModel: Partial<LlmModel> = {};

  static styles = css`
    .container {
      padding: 2rem;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  `;

  async connectedCallback() {
    super.connectedCallback();
    await this.fetchModels();
  }

  async fetchModels() {
    this.isLoading = true;
    try {
      this.models = await api.getLlmModels();
    } catch (error) {
      console.error('Failed to fetch LLM models:', error);
    } finally {
      this.isLoading = false;
    }
  }

  render() {
    return html`
      <div class="container">
        <div class="card">
          <div class="card-header">
            <span>LLM Models</span>
            <vaadin-button theme="primary small" @click=${this.openAddModelModal}>
              <i class="bi bi-plus-lg"></i> Add Model
            </vaadin-button>
          </div>
          <div class="card-body">
            ${when(
              this.isLoading,
              () => html`<p>Loading...</p>`,
              () => this.renderModelsTable()
            )}
          </div>
        </div>
      </div>
      ${this.renderModal()}
    `;
  }

  renderModelsTable() {
    if (this.models.length === 0) {
      return html`<p>No LLM models configured yet. Click 'Add Model' to get started.</p>`;
    }

    return html`
      <table class="table table-hover">
        <thead>
          <tr>
            <th>Name</th>
            <th>Provider</th>
            <th>Model Name</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${repeat(
            this.models,
            (model) => model.id,
            (model) => html`
              <tr>
                <td>${model.name}</td>
                <td>${model.provider_name}</td>
                <td>${model.model_name}</td>
                <td>
                  <vaadin-button theme="tertiary-inline small" @click=${() => this.openEditModal(model)}>
                    <i class="bi bi-pencil"></i>
                  </vaadin-button>
                  <vaadin-button theme="tertiary-inline small error" @click=${() => this.deleteModel(model.id)}>
                    <i class="bi bi-trash"></i>
                  </vaadin-button>
                </td>
              </tr>
            `
          )}
        </tbody>
      </table>
    `;
  }

  renderModal() {
    return html`
      <vaadin-dialog
        header-title="${this.isEditing ? 'Edit' : 'Add'} LLM Model"
        .opened=${this.isModalOpen}
        @opened-changed=${(e: CustomEvent) => this.isModalOpen = e.detail.value}
        .renderer=${(root: HTMLElement) => {
          root.innerHTML = `
            <div>
              <vaadin-text-field label="Friendly Name" .value=${this.currentModel.name || ''} @value-changed=${(e: CustomEvent) => this.currentModel.name = e.detail.value} required></vaadin-text-field>
              <vaadin-select label="Provider" .value=${this.currentModel.provider_name || ''} @value-changed=${(e: CustomEvent) => this.currentModel.provider_name = e.detail.value} required>
                <vaadin-list-box>
                  <vaadin-item value="openai">OpenAI</vaadin-item>
                  <vaadin-item value="anthropic">Anthropic</vaadin-item>
                  <vaadin-item value="google">Google</vaadin-item>
                  <vaadin-item value="custom">Custom</vaadin-item>
                </vaadin-list-box>
              </vaadin-select>
              <vaadin-text-field label="Model Name / ID" .value=${this.currentModel.model_name || ''} @value-changed=${(e: CustomEvent) => this.currentModel.model_name = e.detail.value} required></vaadin-text-field>
              <vaadin-text-field label="API URL" .value=${this.currentModel.api_url || ''} @value-changed=${(e: CustomEvent) => this.currentModel.api_url = e.detail.value} required></vaadin-text-field>
              <vaadin-password-field label="API Key" @value-changed=${(e: CustomEvent) => this.currentModel.api_key = e.detail.value} placeholder=${this.isEditing ? 'Leave blank to keep existing key' : ''}></vaadin-password-field>
            </div>
          `;
        }}
        .footerRenderer=${(root: HTMLElement) => {
          root.innerHTML = `
            <vaadin-button @click=${this.closeModal}>Cancel</vaadin-button>
            <vaadin-button theme="primary" @click=${this.handleFormSubmit}>Save</vaadin-button>
          `;
        }}
      ></vaadin-dialog>
    `;
  }

  openAddModelModal() {
    this.isEditing = false;
    this.currentModel = {};
    this.isModalOpen = true;
  }

  openEditModal(model: LlmModel) {
    this.isEditing = true;
    this.currentModel = { ...model };
    this.isModalOpen = true;
  }

  closeModal() {
    this.isModalOpen = false;
  }

  async handleFormSubmit(e: Event) {
    e.preventDefault();
    if (this.isEditing) {
      await api.updateLlmModel(this.currentModel.id!, this.currentModel);
    } else {
      await api.createLlmModel(this.currentModel);
    }
    this.closeModal();
    await this.fetchModels();
  }

  async deleteModel(id: string) {
    if (confirm('Are you sure you want to delete this model?')) {
      await api.deleteLlmModel(id);
      await this.fetchModels();
    }
  }
}
