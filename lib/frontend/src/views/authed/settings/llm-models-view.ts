import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { repeat } from 'lit/directives/repeat.js';
import {
  getLlmModels,
  updateLlmModel,
  createLlmModel,
  deleteLlmModel,
} from '../../../api';
import type { LlmModel } from '../../../types';
import type { SlSelect } from '@shoelace-style/shoelace/dist/components/select/select.js';
import type { SlInput } from '@shoelace-style/shoelace/dist/components/input/input.js';

import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import consoleStyles from '../../../styles/console-styles.css?inline';

@customElement('llm-models-view')
export class LlmModelsView extends LitElement {
  private readonly INFO_ALERT_DISMISSED_KEY =
    'spacebridge-llm-models-info-alert-dismissed';

  @state()
  private _isInfoAlertOpen = false;

  @state()
  private models: LlmModel[] = [];

  @state()
  private isLoading = true;

  @state()
  private error: string | null = null;

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

  @state()
  private modelSuggestions: string[] = [];

  @state()
  private isOtherModel = false;

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      table {
        width: 100%;
        border-collapse: collapse;
      }
      .styled-table th,
      .styled-table td {
        padding: var(--sl-spacing-medium);
        text-align: left;
        border-bottom: 1px solid var(--sl-color-neutral-200);
      }
      .styled-table th {
        background-color: var(--sl-color-neutral-50);
        font-weight: var(--sl-font-weight-semibold);
      }
      .styled-table tr:last-child td {
        border-bottom: none;
      }
      .styled-table th:last-child,
      .styled-table td:last-child {
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
    `,
  ];

  async connectedCallback() {
    super.connectedCallback();
    const isDismissed = localStorage.getItem(this.INFO_ALERT_DISMISSED_KEY);
    this._isInfoAlertOpen = isDismissed !== 'true';
    await this.fetchModels();
  }

  async fetchModels() {
    this.isLoading = true;
    this.error = null;
    try {
      this.models = await getLlmModels();
    } catch (error) {
      this.error =
        error instanceof Error ? error.message : 'Failed to fetch LLM models';
    } finally {
      this.isLoading = false;
    }
  }

  render() {
    const renderContent = () => {
      if (this.isLoading) {
        return html`<sl-card
          ><div style="display: flex; justify-content: center; padding: 2rem;">
            <sl-spinner></sl-spinner></div
        ></sl-card>`;
      }

      if (this.error) {
        return html`
          <sl-alert variant="danger" open>
            <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
            <strong>Error:</strong> ${this.error}
          </sl-alert>
        `;
      }

      return this.renderModelsList();
    };

    return html`
      <view-header headerText="Models">
        <div slot="main-column">
          <sl-button variant="primary" @click=${this.openAddModelModal}>
            <sl-icon slot="prefix" name="plus-lg"></sl-icon> Add Model
          </sl-button>
        </div>
        <div slot="side-column">
          <theme-switcher></theme-switcher>
        </div>
      </view-header>
      <div class="column-layout">
        <div class="main-column">
          ${renderContent()}
        </div>
        <div class="side-column"></div>
      </div>
      ${this.renderModal()} ${this.renderDeleteConfirm()}
    `;
  }

  renderModelsList() {
    return html`
      <sl-alert
        class="info-header"
        variant="primary"
        ?open=${this._isInfoAlertOpen}
        closable
        @sl-hide=${this.handleInfoAlertHide}
      >
        <sl-icon slot="icon" name="info-circle"></sl-icon>
        Models enable advanced AI features such as improved duplicate issue
        detection accuracy.
      </sl-alert>
      <sl-card class="table-card">
        ${when(
          this.models.length === 0,
          () =>
            html` <sl-alert variant="primary" open>
              <sl-icon slot="icon" name="info-circle"></sl-icon>
              No Models configured yet.
              <a
                href="#"
                @click=${(e: Event) => {
                  e.preventDefault();
                  this.openAddModelModal();
                }}
                >Add a Model</a
              >
            </sl-alert>`,
          () => html`
            <table class="styled-table">
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
                          () =>
                            html`<sl-badge variant="success" pill
                              >Default</sl-badge
                            >`,
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
        label="${this.isEditing ? 'Edit' : 'Add'} a Model"
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
          <sl-select
            label="Model Name / ID"
            .value=${this.isOtherModel
              ? 'other'
              : this.currentModel.model_name || ''}
            @sl-change=${this._handleModelNameChange}
          >
            ${repeat(
              this.modelSuggestions,
              (s) => s,
              (s) => html`<sl-option value="${s}">${s}</sl-option>`
            )}
            <sl-option value="other">Other...</sl-option>
          </sl-select>

          ${when(
            this.isOtherModel,
            () => html`
              <sl-input
                label="Custom Model Name / ID"
                placeholder="Enter custom model name"
                .value=${this.currentModel.model_name || ''}
                @sl-input=${this._handleCustomModelInput}
              ></sl-input>
            `
          )}

          <sl-input
            class="full-width"
            label="API URL"
            .value=${this.currentModel.api_url || ''}
            @sl-input=${(e: Event) =>
              (this.currentModel.api_url = (
                e.target as HTMLInputElement
              ).value)}
          ></sl-input>
          <sl-input
            class="full-width"
            type="password"
            label="API Key"
            .value=${this.currentModel.api_key || ''}
            @sl-input=${(e: Event) =>
              (this.currentModel.api_key = (
                e.target as HTMLInputElement
              ).value)}
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
        Are you sure you want to delete the model "${this.modelToDelete?.name}"?
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
    this.modelSuggestions = [];
    this.isOtherModel = false;
    this.isModalOpen = true;
  }

  openEditModal(model: LlmModel) {
    this.isEditing = true;
    this.currentModel = { ...model };
    this.modelSuggestions = this.getModelSuggestionsForProvider(
      this.currentModel.provider_name || ''
    );
    this.isOtherModel = !this.modelSuggestions.includes(
      this.currentModel.model_name || ''
    );
    this.isModalOpen = true;
  }

  closeModal() {
    this.isModalOpen = false;
  }

  private _handleModelNameChange(e: Event) {
    const selectedValue = (e.target as SlSelect).value;
    if (selectedValue === 'other') {
      this.isOtherModel = true;
      this.currentModel.model_name = '';
    } else {
      this.isOtherModel = false;
      this.currentModel.model_name = selectedValue;
    }
  }

  private _handleCustomModelInput(e: Event) {
    this.currentModel.model_name = (e.target as SlInput).value;
  }

  private getModelSuggestionsForProvider(provider: string): string[] {
    switch (provider) {
      case 'openai':
        return ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'];
      case 'anthropic':
        return [
          'claude-3-opus-20240229',
          'claude-3-sonnet-20240229',
          'claude-3-haiku-20240307',
        ];
      case 'google':
        return [
          'gemini-1.5-pro-latest',
          'gemini-1.0-pro',
          'gemini-1.5-flash-latest',
        ];
      default:
        return [];
    }
  }

  handleProviderChange(e: Event) {
    const provider = (e.target as SlSelect).value;

    const defaultUrls: { [key: string]: string } = {
      openai: 'https://api.openai.com/v1',
      anthropic: 'https://api.anthropic.com/v1',
      google: 'https://generativelanguage.googleapis.com/v1beta',
    };

    this.currentModel = {
      ...this.currentModel,
      provider_name: provider,
      api_url: defaultUrls[provider] || '',
      model_name: '',
    };
    this.modelSuggestions = this.getModelSuggestionsForProvider(provider);
    this.isOtherModel = false;
    this.requestUpdate();
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
      await updateLlmModel(this.currentModel.id!, this.currentModel);
    } else {
      await createLlmModel(this.currentModel);
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
      await updateLlmModel(model.id, { is_default: true });
      await this.fetchModels();
    } catch (error) {
      console.error('Failed to set default model:', error);
    }
  }

  async deleteModel() {
    if (this.modelToDelete) {
      await deleteLlmModel(this.modelToDelete.id);
      await this.fetchModels();
    }
    this.isDeleteConfirmOpen = false;
    this.modelToDelete = null;
  }

  private handleInfoAlertHide() {
    localStorage.setItem(this.INFO_ALERT_DISMISSED_KEY, 'true');
    this._isInfoAlertOpen = false;
  }
}
