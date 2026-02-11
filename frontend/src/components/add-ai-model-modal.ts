import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { repeat } from 'lit/directives/repeat.js';
import {
  getAvailableModelsForProvider,
  createAIModel,
  updateAIModel,
} from '../api';
import type { AIModel } from '../types';
import type SlSelect from '@shoelace-style/shoelace/dist/components/select/select.js';
import type SlInput from '@shoelace-style/shoelace/dist/components/input/input.js';

import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';

/**
 * Reusable AI model add/edit dialog.
 *
 * Usage:
 *   <add-ai-model-modal
 *     ?open=${this.isOpen}
 *     .model=${modelToEdit}        <!-- null/undefined for "Add" mode -->
 *     @model-created=${handler}     <!-- detail: { model } -->
 *     @model-updated=${handler}     <!-- detail: { model } -->
 *     @close-modal=${handler}
 *   ></add-ai-model-modal>
 */
@customElement('add-ai-model-modal')
export class AddAIModelModal extends LitElement {
  static styles = css`
    sl-dialog::part(panel) {
      width: 620px;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
    }
    .full-width {
      grid-column: 1 / -1;
    }
  `;

  /** Whether the dialog is open. */
  @property({ type: Boolean })
  open = false;

  /**
   * If provided, the dialog opens in "Edit" mode for this model.
   * Pass null / undefined for "Add" mode.
   */
  @property({ type: Object })
  model: AIModel | null = null;

  // ── internal state ───────────────────────────────────

  @state() private _currentModel: Partial<AIModel> = {};
  @state() private _formError: string | null = null;
  @state() private _isSubmitting = false;
  @state() private _modelSuggestions: string[] = [];
  @state() private _isOtherModel = false;
  @state() private _isFetchingModels = false;
  @state() private _modelsFetchError: string | null = null;

  private get _isEditing(): boolean {
    return !!this.model;
  }

  // ── lifecycle ────────────────────────────────────────

  updated(changedProps: Map<string, unknown>) {
    if (changedProps.has('open') && this.open) {
      this._populateForm();
    }
  }

  // ── form helpers ─────────────────────────────────────

  private _populateForm() {
    if (this.model) {
      this._currentModel = { ...this.model };
    } else {
      this._currentModel = {};
    }
    this._modelSuggestions = [];
    this._isOtherModel = false;
    this._formError = null;
    this._isSubmitting = false;
    this._isFetchingModels = false;
    this._modelsFetchError = null;
  }

  private _handleClose() {
    this.dispatchEvent(new CustomEvent('close-modal'));
  }

  private _handleRequestClose(event: CustomEvent) {
    const source = (event.detail as any).source;
    if (source === 'close-button' || !this._currentModel.provider_name) {
      this._handleClose();
    } else {
      event.preventDefault();
    }
  }

  // ── provider / model fetching ────────────────────────

  private async _handleProviderChange(e: Event) {
    const provider = (e.target as SlSelect).value as string;

    const defaultUrls: Record<string, string> = {
      openai: 'https://api.openai.com/v1',
      anthropic: 'https://api.anthropic.com/v1',
      google: 'https://generativelanguage.googleapis.com/v1beta',
      qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      deepseek: 'https://api.deepseek.com/v1',
    };

    this._currentModel = {
      ...this._currentModel,
      provider_name: provider,
      api_url: defaultUrls[provider] || '',
      model_identifier: '',
    };

    this._modelSuggestions = [];
    this._isOtherModel = false;
    this._modelsFetchError = null;
    this.requestUpdate();
  }

  private async _fetchModelSuggestionsForProvider(
    provider: string,
    apiKey?: string
  ): Promise<string[]> {
    try {
      return await getAvailableModelsForProvider(provider, apiKey);
    } catch (error) {
      console.error(`Failed to fetch models for ${provider}:`, error);
      // Return fallback list on error
      switch (provider) {
        case 'openai':
          return [
            'gpt-4o',
            'gpt-4o-mini',
            'gpt-4-turbo',
            'gpt-4',
            'gpt-3.5-turbo',
          ];
        case 'anthropic':
          return [
            'claude-3-7-sonnet-20250219',
            'claude-3-5-sonnet-20241022',
            'claude-3-5-haiku-20241022',
            'claude-3-opus-20240229',
            'claude-3-sonnet-20240229',
            'claude-3-haiku-20240307',
          ];
        case 'google':
          return [
            'gemini-2.0-flash-exp',
            'gemini-1.5-pro-latest',
            'gemini-1.5-flash-latest',
            'gemini-1.5-flash-8b-latest',
            'gemini-1.0-pro',
          ];
        case 'qwen':
          return ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwq-32b-preview'];
        case 'deepseek':
          return ['deepseek-chat', 'deepseek-reasoner'];
        default:
          return [];
      }
    }
  }

  private async _fetchModelsForCurrentProvider() {
    if (!this._currentModel.provider_name) return;

    this._isFetchingModels = true;
    this._modelsFetchError = null;

    try {
      this._modelSuggestions = await this._fetchModelSuggestionsForProvider(
        this._currentModel.provider_name,
        this._currentModel.api_key
      );
      if (this._modelSuggestions.length === 0) {
        this._modelsFetchError = 'No models available for this provider';
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
      this._modelsFetchError =
        error instanceof Error ? error.message : 'Failed to fetch models';
    } finally {
      this._isFetchingModels = false;
      this.requestUpdate();
    }
  }

  private _handleModelNameChange(e: Event) {
    const selectedValue = (e.target as SlSelect).value as string;
    if (selectedValue === 'other') {
      this._isOtherModel = true;
      this._currentModel.model_identifier = '';
    } else {
      this._isOtherModel = false;
      this._currentModel.model_identifier = selectedValue;
    }
  }

  private _handleCustomModelInput(e: Event) {
    this._currentModel.model_identifier = (e.target as SlInput).value;
  }

  // ── submit ───────────────────────────────────────────

  private async _handleFormSubmit(e: Event) {
    e.preventDefault();
    this._formError = null;

    if (
      !this._currentModel.name ||
      !this._currentModel.provider_name ||
      !this._currentModel.model_identifier ||
      !this._currentModel.api_url
    ) {
      this._formError = 'Please fill in all required fields';
      return;
    }

    this._isSubmitting = true;

    try {
      if (this._isEditing) {
        const updated = await updateAIModel(
          this._currentModel.id!,
          this._currentModel
        );
        this.dispatchEvent(
          new CustomEvent('model-updated', {
            detail: { model: updated },
            bubbles: true,
            composed: true,
          })
        );
      } else {
        const created = await createAIModel(this._currentModel);
        this.dispatchEvent(
          new CustomEvent('model-created', {
            detail: { model: created },
            bubbles: true,
            composed: true,
          })
        );
      }
      this._handleClose();
    } catch (error) {
      this._formError =
        error instanceof Error
          ? error.message
          : 'Failed to save model. Please try again.';
      console.error('Failed to save model:', error);
    } finally {
      this._isSubmitting = false;
    }
  }

  // ── render ───────────────────────────────────────────

  render() {
    if (!this.open) return html``;

    return html`
      <sl-dialog
        label="${this._isEditing ? 'Edit' : 'Add'} AI Model"
        .open=${this.open}
        @sl-request-close=${this._handleRequestClose}
      >
        ${when(
          this._formError,
          () => html`
            <sl-alert variant="danger" open>
              <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
              <strong>Error:</strong> ${this._formError}
            </sl-alert>
          `
        )}
        <div class="form-grid">
          <sl-input
            class="full-width"
            label="Friendly Name"
            .value=${this._currentModel.name || ''}
            @sl-input=${(e: Event) =>
              (this._currentModel.name = (e.target as HTMLInputElement).value)}
            ?disabled=${this._isSubmitting}
          ></sl-input>
          <sl-select
            label="Provider"
            .value=${this._currentModel.provider_name || ''}
            @sl-change=${this._handleProviderChange}
            ?disabled=${this._isSubmitting}
          >
            <sl-option value="openai">OpenAI</sl-option>
            <sl-option value="anthropic">Anthropic</sl-option>
            <sl-option value="google">Google</sl-option>
            <sl-option value="qwen">Qwen</sl-option>
            <sl-option value="deepseek">DeepSeek</sl-option>
            <sl-option value="custom">Custom</sl-option>
          </sl-select>

          <sl-input
            class="full-width"
            label="API URL"
            .value=${this._currentModel.api_url || ''}
            @sl-input=${(e: Event) =>
              (this._currentModel.api_url = (
                e.target as HTMLInputElement
              ).value)}
            ?disabled=${this._isSubmitting}
          ></sl-input>
          <sl-input
            class="full-width"
            type="password"
            label="API Key"
            .value=${this._currentModel.api_key || ''}
            @sl-input=${(e: Event) => {
              this._currentModel.api_key = (e.target as HTMLInputElement).value;
              this.requestUpdate();
            }}
            placeholder=${this._isEditing
              ? 'Leave blank to keep existing key'
              : ''}
            ?disabled=${this._isSubmitting}
            help-text=${this._isEditing
              ? ''
              : 'Enter your API key to fetch available models'}
          ></sl-input>

          <div class="full-width">
            <sl-button
              @click=${this._fetchModelsForCurrentProvider}
              ?loading=${this._isFetchingModels}
              ?disabled=${this._isSubmitting || this._isFetchingModels}
              style="width: 100%;"
            >
              ${this._modelSuggestions.length > 0
                ? 'Refresh Models'
                : 'Fetch Available Models'}
            </sl-button>
            ${this._modelsFetchError
              ? html`
                  <div
                    style="color: var(--sl-color-danger-600); font-size: 0.875rem; margin-top: 0.5rem;"
                  >
                    ${this._modelsFetchError}
                  </div>
                `
              : ''}
          </div>

          ${this._modelSuggestions.length > 0
            ? html`
                <sl-select
                  class="full-width"
                  label="Model Name / ID"
                  .value=${this._isOtherModel
                    ? 'other'
                    : this._currentModel.model_identifier || ''}
                  @sl-change=${this._handleModelNameChange}
                  ?disabled=${this._isSubmitting}
                >
                  ${repeat(
                    this._modelSuggestions,
                    (s) => s,
                    (s) => html`<sl-option value="${s}">${s}</sl-option>`
                  )}
                  <sl-option value="other">Other...</sl-option>
                </sl-select>

                ${when(
                  this._isOtherModel,
                  () => html`
                    <sl-input
                      class="full-width"
                      label="Custom Model Name / ID"
                      placeholder="Enter custom model name"
                      .value=${this._currentModel.model_identifier || ''}
                      @sl-input=${this._handleCustomModelInput}
                      ?disabled=${this._isSubmitting}
                    ></sl-input>
                  `
                )}
              `
            : ''}
        </div>
        <sl-button
          slot="footer"
          @click=${this._handleClose}
          ?disabled=${this._isSubmitting}
          >Cancel</sl-button
        >
        <sl-button
          slot="footer"
          variant="primary"
          @click=${this._handleFormSubmit}
          ?loading=${this._isSubmitting}
          ?disabled=${this._isSubmitting}
          >Save</sl-button
        >
      </sl-dialog>
    `;
  }
}
