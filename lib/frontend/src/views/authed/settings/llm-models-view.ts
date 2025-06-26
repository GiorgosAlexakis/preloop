import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { repeat } from 'lit/directives/repeat.js';
import * as api from '../../../api';
import { LlmModel } from '../../../types';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';

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

  @state()
  private isDeleteConfirmOpen = false;

  @state()
  private modelToDelete: LlmModel | null = null;

  static styles = css`
    .container {
      max-width: var(--console-container-max-width);
      padding: 2rem;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    sl-card::part(base) {
      margin-bottom: 1rem;
    }
    .model-card-body {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr auto;
      gap: 1rem;
      align-items: center;
    }
    .actions {
      display: flex;
      gap: 0.5rem;
    }
    sl-dialog::part(panel) {
      max-width: 600px;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
    }
    .form-grid .full-width {
      grid-column: 1 / -1;
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
    <div class="p-4">
          <h1 class="text-2xl font-bold mb-4">LLM Models</h1>
        </div>
      <div class="container">
        <sl-card>
          <div slot="header" class="card-header">
            <span>LLM Models</span>
            <sl-button
              variant="primary"
              size="small"
              @click=${this.openAddModelModal}
            >
              <sl-icon slot="prefix" name="plus-lg"></sl-icon> Add Model
            </sl-button>
          </div>
          ${when(
            this.isLoading,
            () =>
              html`<div
                style="display: flex; justify-content: center; padding: 2rem;"
              >
                <sl-spinner></sl-spinner>
              </div>`,
            () => this.renderModelsList()
          )}
        </sl-card>
      </div>
      ${this.renderModal()} ${this.renderDeleteConfirm()}
    `;
  }

  renderModelsList() {
    if (this.models.length === 0) {
      return html`<p>
        No LLM models configured yet. Click 'Add Model' to get started.
      </p>`;
    }

    return html`
      <div>
        ${repeat(
          this.models,
          (model) => model.id,
          (model) => html`
            <sl-card>
              <div class="model-card-body">
                <div><strong>Name:</strong> ${model.name}</div>
                <div><strong>Provider:</strong> ${model.provider_name}</div>
                <div><strong>Model:</strong> ${model.model_name}</div>
                <div class="actions">
                  <sl-button
                    size="small"
                    circle
                    @click=${() => this.openEditModal(model)}
                  >
                    <sl-icon name="pencil"></sl-icon>
                  </sl-button>
                  <sl-button
                    variant="danger"
                    size="small"
                    circle
                    @click=${() => this.openDeleteConfirm(model)}
                  >
                    <sl-icon name="trash"></sl-icon>
                  </sl-button>
                </div>
              </div>
            </sl-card>
          `
        )}
      </div>
    `;
  }

  renderModal() {
    return html`
      <sl-dialog
        label="${this.isEditing ? 'Edit' : 'Add'} LLM Model"
        .open=${this.isModalOpen}
        @sl-hide=${this.closeModal}
      >
        <div class="form-grid">
          <sl-input
            class="full-width"
            label="Friendly Name"
            .value=${this.currentModel.name || ''}
            @sl-input=${(e: Event) =>
              (this.currentModel.name = (e.target as HTMLInputElement).value)}
            required
          ></sl-input>
          <sl-select
            label="Provider"
            .value=${this.currentModel.provider_name || ''}
            @sl-change=${(e: CustomEvent) =>
              (this.currentModel.provider_name = (
                e.target as HTMLSelectElement
              ).value)}
            required
          >
            <sl-option value="openai">OpenAI</sl-option>
            <sl-option value="anthropic">Anthropic</sl-option>
            <sl-option value="google">Google</sl-option>
            <sl-option value="custom">Custom</sl-option>
          </sl-select>
          <sl-input
            label="Model Name / ID"
            .value=${this.currentModel.model_name || ''}
            @sl-input=${(e: Event) =>
              (this.currentModel.model_name = (
                e.target as HTMLInputElement
              ).value)}
            required
          ></sl-input>
          <sl-input
            class="full-width"
            label="API URL"
            .value=${this.currentModel.api_url || ''}
            @sl-input=${(e: Event) =>
              (this.currentModel.api_url = (e.target as HTMLInputElement).value)}
            required
          ></sl-input>
          <sl-input
            class="full-width"
            type="password"
            label="API Key"
            @sl-input=${(e: Event) =>
              (this.currentModel.api_key = (e.target as HTMLInputElement).value)}
            placeholder=${this.isEditing
              ? 'Leave blank to keep existing key'
              : ''}
          ></sl-input>
        </div>
        <sl-button slot="footer" @click=${this.closeModal}>Cancel</sl-button>
        <sl-button
          slot="footer"
          variant="primary"
          @click=${this.handleFormSubmit}
          >Save</sl-button
        >
      </sl-dialog>
    `;
  }

  renderDeleteConfirm() {
    return html`
      <sl-dialog
        label="Delete Model"
        .open=${this.isDeleteConfirmOpen}
        @sl-hide=${() => (this.isDeleteConfirmOpen = false)}
      >
        Are you sure you want to delete the model
        "${this.modelToDelete?.name}"?
        <sl-button
          slot="footer"
          @click=${() => (this.isDeleteConfirmOpen = false)}
          >Cancel</sl-button
        >
        <sl-button slot="footer" variant="danger" @click=${this.deleteModel}
          >Delete</sl-button
        >
      </sl-dialog>
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
    // Basic validation
    if (
      !this.currentModel.name ||
      !this.currentModel.provider_name ||
      !this.currentModel.model_name ||
      !this.currentModel.api_url
    ) {
      // In a real app, show a user-friendly error.
      console.error('Validation failed');
      return;
    }

    if (this.isEditing) {
      await api.updateLlmModel(this.currentModel.id!, this.currentModel);
    } else {
      await api.createLlmModel(this.currentModel);
    }
    this.closeModal();
    await this.fetchModels();
  }

  openDeleteConfirm(model: LlmModel) {
    this.modelToDelete = model;
    this.isDeleteConfirmOpen = true;
  }

  async deleteModel() {
    if (this.modelToDelete) {
      await api.deleteLlmModel(this.modelToDelete.id);
      await this.fetchModels();
    }
    this.isDeleteConfirmOpen = false;
    this.modelToDelete = null;
  }
}
