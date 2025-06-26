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
import '@shoelace-style/shoelace/dist/components/badge/badge.js';

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
      padding: var(--sl-spacing-x-large);
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: var(--sl-spacing-large);
    }
    .table-card {
    width: 100%;
      --padding: 0;
    }
    .table-card::part(body) {
      padding: 0;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th,
    td {
      padding: var(--sl-spacing-medium);
      text-align: left;
      border-bottom: 1px solid var(--sl-color-neutral-200);
    }
    th {
      background-color: var(--sl-color-neutral-50);
      font-weight: var(--sl-font-weight-semibold);
    }
    tr:last-child td {
      border-bottom: none;
    }
    th:last-child,
    td:last-child {
      text-align: right;
    }
    .actions {
      display: flex;
      gap: var(--sl-spacing-x-small);
      justify-content: flex-end;
    }
    sl-dialog::part(panel) {
      width: 620px;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
    }
    .form-grid .full-width {
      grid-column: 1 / -1;
    }
    .empty-state {
      padding: var(--sl-spacing-large);
    }
    .empty-state a {
      color: var(--sl-color-primary-600);
      text-decoration: none;
      cursor: pointer;
    }
    .empty-state a:hover {
      text-decoration: underline;
    }
    .info-header {
      margin-bottom: var(--sl-spacing-large);
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
        <div class="header">
          <h1 class="title">LLM Models</h1>
          <sl-button
            variant="primary"
            @click=${this.openAddModelModal}
          >
            <sl-icon slot="prefix" name="plus-lg"></sl-icon> Add Model
          </sl-button>
        </div>

        ${when(
          this.isLoading,
          () =>
            html`<sl-card><div style="display: flex; justify-content: center; padding: 2rem;">
              <sl-spinner></sl-spinner>
            </div></sl-card>`,
          () => this.renderModelsList()
        )}
      </div>
      ${this.renderModal()} ${this.renderDeleteConfirm()}
    `;
  }

  renderModelsList() {
    return html`
      <sl-alert class="info-header" variant="primary" open>
        <sl-icon slot="icon" name="info-circle"></sl-icon>
        LLMs enable advanced AI features such as duplicate issue detection.
      </sl-alert>
      <sl-card class="table-card">
        ${when(this.models.length === 0,
          () => html`
            <p class="empty-state">
              No LLM models configured yet.
              <a href="#" @click=${(e: Event) => { e.preventDefault(); this.openAddModelModal(); }}>Add a Model</a>
            </p>`,
          () => html`
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Provider</th>
                  <th>Model</th>
                  <th>Default</th>
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
                        ${when(
                          model.is_default,
                          () => html`<sl-badge variant="success" pill>Default</sl-badge>`,
                          () => html`
                            <sl-button
                              size="small"
                              @click=${() => this.handleSetDefault(model)}
                            >
                              Set as default
                            </sl-button>
                          `
                        )}
                      </td>
                      <td>
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
                      </td>
                    </tr>
                  `
                )}
              </tbody>
            </table>
          `
        )}
      </sl-card>
    `;
  }

  renderModal() {
    return html`
      <sl-dialog
        label="${this.isEditing ? 'Edit' : 'Add'} LLM Model"
        .open=${this.isModalOpen}
      >
        <div class="form-grid">
          <sl-input
            class="full-width"
            label="Friendly Name"
            .value=${this.currentModel.name || ''}
            @sl-input=${(e: Event) =>
              (this.currentModel.name = (e.target as HTMLInputElement).value)}
          ></sl-input>
          <sl-select
            label="Provider"
            .value=${this.currentModel.provider_name || ''}
            @sl-change=${this.handleProviderChange}
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
          ></sl-input>
          <sl-input
            class="full-width"
            label="API URL"
            .value=${this.currentModel.api_url || ''}
            @sl-input=${(e: Event) =>
              (this.currentModel.api_url = (e.target as HTMLInputElement).value)}
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

  handleProviderChange(e: CustomEvent) {
    e.stopPropagation();
    const provider = (e.target as HTMLSelectElement).value;

    const defaultUrls: { [key: string]: string } = {
      openai: 'https://api.openai.com/v1',
      anthropic: 'https://api.anthropic.com/v1',
      google: 'https://generativelanguage.googleapis.com/v1beta',
    };

    this.currentModel = {
      ...this.currentModel,
      provider_name: provider,
      api_url: defaultUrls[provider] || '',
    };
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

  async handleSetDefault(model: LlmModel) {
    try {
      await api.updateLlmModel(model.id, { is_default: true });
      await this.fetchModels();
    } catch (error) {
      console.error('Failed to set default model:', error);
    }
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
