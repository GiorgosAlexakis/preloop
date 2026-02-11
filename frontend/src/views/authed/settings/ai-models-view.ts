import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { repeat } from 'lit/directives/repeat.js';
import { getAIModels, updateAIModel, deleteAIModel } from '../../../api';
import type { AIModel } from '../../../types';

import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '../../../components/add-ai-model-modal';
import consoleStyles from '../../../styles/console-styles.css?inline';

@customElement('ai-models-view')
export class AIModelsView extends LitElement {
  private readonly INFO_ALERT_DISMISSED_KEY =
    'preloop-models-info-alert-dismissed';

  @state()
  private _isInfoAlertOpen = false;

  @state()
  private models: AIModel[] = [];

  @state()
  private isLoading = true;

  @state()
  private error: string | null = null;

  @state()
  private isModalOpen = false;

  @state()
  private editingModel: AIModel | null = null;

  @state()
  private isDeleteConfirmOpen = false;

  @state()
  private modelToDelete: AIModel | null = null;

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
      .actions {
        display: flex;
        gap: var(--sl-spacing-x-small);
        justify-content: flex-end;
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
      this.models = await getAIModels();
    } catch (error) {
      this.error =
        error instanceof Error ? error.message : 'Failed to fetch AI models';
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
      <view-header headerText="AI Models" width="narrow">
        <div slot="main-column">
          <sl-button variant="primary" @click=${this.openAddModelModal}>
            <sl-icon slot="prefix" name="plus-lg"></sl-icon> Add Model
          </sl-button>
        </div>
      </view-header>
      <div class="column-layout narrow">
        <div class="main-column">${renderContent()}</div>
        <div class="side-column"></div>
      </div>
      <add-ai-model-modal
        ?open=${this.isModalOpen}
        .model=${this.editingModel}
        @model-created=${this._handleModelSaved}
        @model-updated=${this._handleModelSaved}
        @close-modal=${this.closeModal}
      ></add-ai-model-modal>
      ${this.renderDeleteConfirm()}
    `;
  }

  renderModelsList() {
    return html`
      <sl-card class="table-card">
        ${when(
          this.models.length === 0,
          () =>
            html` <sl-alert variant="primary" open>
              <sl-icon slot="icon" name="info-circle"></sl-icon>
              No AI Models configured yet.
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
                      <td>${model.model_identifier}</td>
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
    this.editingModel = null;
    this.isModalOpen = true;
  }

  openEditModal(model: AIModel) {
    this.editingModel = model;
    this.isModalOpen = true;
  }

  closeModal() {
    this.isModalOpen = false;
    this.editingModel = null;
  }

  private async _handleModelSaved() {
    this.closeModal();
    await this.fetchModels();
  }

  openDeleteConfirm(model: AIModel) {
    this.modelToDelete = model;
    this.isDeleteConfirmOpen = true;
  }

  async handleSetDefault(model: AIModel) {
    try {
      await updateAIModel(model.id, { is_default: true });
      await this.fetchModels();
    } catch (error) {
      console.error('Failed to set default model:', error);
      this.error =
        error instanceof Error ? error.message : 'Failed to set default model';
    }
  }

  async deleteModel() {
    if (this.modelToDelete) {
      try {
        await deleteAIModel(this.modelToDelete.id);
        await this.fetchModels();
      } catch (error) {
        console.error('Failed to delete model:', error);
        this.error =
          error instanceof Error ? error.message : 'Failed to delete model';
      }
    }
    this.isDeleteConfirmOpen = false;
    this.modelToDelete = null;
  }

  private handleInfoAlertHide() {
    localStorage.setItem(this.INFO_ALERT_DISMISSED_KEY, 'true');
    this._isInfoAlertOpen = false;
  }
}
