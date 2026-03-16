var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { repeat } from 'lit/directives/repeat.js';
import { getAvailableModelsForProvider, createAIModel, updateAIModel, } from '../api';
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
let AddAIModelModal = class AddAIModelModal extends LitElement {
    constructor() {
        super(...arguments);
        /** Whether the dialog is open. */
        this.open = false;
        /**
         * If provided, the dialog opens in "Edit" mode for this model.
         * Pass null / undefined for "Add" mode.
         */
        this.model = null;
        // ── internal state ───────────────────────────────────
        this._currentModel = {};
        this._formError = null;
        this._isSubmitting = false;
        this._modelSuggestions = [];
        this._isOtherModel = false;
        this._isFetchingModels = false;
        this._modelsFetchError = null;
    }
    get _isEditing() {
        return !!this.model;
    }
    // ── lifecycle ────────────────────────────────────────
    updated(changedProps) {
        if (changedProps.has('open') && this.open) {
            this._populateForm();
        }
    }
    // ── form helpers ─────────────────────────────────────
    _populateForm() {
        if (this.model) {
            this._currentModel = { ...this.model };
        }
        else {
            this._currentModel = {};
        }
        this._modelSuggestions = [];
        this._isOtherModel = false;
        this._formError = null;
        this._isSubmitting = false;
        this._isFetchingModels = false;
        this._modelsFetchError = null;
    }
    /** Read current input values directly from shadow DOM elements. */
    _syncFormFromDom() {
        const inputs = this.shadowRoot?.querySelectorAll('sl-input') ?? [];
        for (const input of inputs) {
            const label = input.getAttribute('label');
            const val = input.value;
            if (label === 'Friendly Name')
                this._currentModel.name = val || undefined;
            else if (label === 'API URL' && val)
                this._currentModel.api_endpoint = val;
            else if (label === 'API Key' && val)
                this._currentModel.api_key = val;
            else if (label === 'Custom Model Name / ID')
                this._currentModel.model_identifier = val || undefined;
        }
    }
    _handleClose() {
        this.dispatchEvent(new CustomEvent('close-modal'));
    }
    _handleRequestClose(event) {
        const source = event.detail.source;
        if (source === 'close-button' || !this._currentModel.provider_name) {
            this._handleClose();
        }
        else {
            event.preventDefault();
        }
    }
    // ── provider / model fetching ────────────────────────
    async _handleProviderChange(e) {
        const provider = e.target.value;
        const defaultUrls = {
            openai: 'https://api.openai.com/v1',
            anthropic: 'https://api.anthropic.com/v1',
            google: 'https://generativelanguage.googleapis.com/v1beta',
            qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            deepseek: 'https://api.deepseek.com/v1',
        };
        this._currentModel = {
            ...this._currentModel,
            provider_name: provider,
            api_endpoint: defaultUrls[provider] || '',
            model_identifier: '',
        };
        this._modelSuggestions = [];
        this._isOtherModel = false;
        this._modelsFetchError = null;
        this.requestUpdate();
    }
    _getProviderKeyUrl(provider) {
        switch (provider) {
            case 'openai':
                return 'https://platform.openai.com/api-keys';
            case 'anthropic':
                return 'https://console.anthropic.com/settings/keys';
            case 'google':
                return 'https://aistudio.google.com/app/apikey';
            case 'qwen':
                return 'https://dashscope.console.aliyun.com/apiKey';
            case 'deepseek':
                return 'https://platform.deepseek.com/api_keys';
            default:
                return '';
        }
    }
    async _fetchModelSuggestionsForProvider(provider, apiKey) {
        return await getAvailableModelsForProvider(provider, apiKey);
    }
    async _fetchModelsForCurrentProvider() {
        if (!this._currentModel.provider_name)
            return;
        this._isFetchingModels = true;
        this._modelsFetchError = null;
        try {
            this._modelSuggestions = await this._fetchModelSuggestionsForProvider(this._currentModel.provider_name, this._currentModel.api_key);
            if (this._modelSuggestions.length === 0) {
                this._modelsFetchError = 'No models available for this provider';
            }
        }
        catch (error) {
            console.error('Failed to fetch models:', error);
            this._modelSuggestions = [];
            this._modelsFetchError =
                error instanceof Error ? error.message : 'Failed to fetch models';
        }
        finally {
            this._isFetchingModels = false;
            this.requestUpdate();
        }
    }
    _handleModelNameChange(e) {
        const selectedValue = e.target.value;
        if (selectedValue === 'other') {
            this._isOtherModel = true;
            this._currentModel.model_identifier = '';
        }
        else {
            this._isOtherModel = false;
            this._currentModel.model_identifier = selectedValue;
        }
    }
    _handleCustomModelInput(e) {
        this._currentModel.model_identifier = e.target.value;
    }
    // ── submit ───────────────────────────────────────────
    async _handleFormSubmit(e) {
        e.preventDefault();
        this._formError = null;
        // Sync values from DOM in case event handlers missed a mutation
        this._syncFormFromDom();
        if (!this._currentModel.name ||
            !this._currentModel.provider_name ||
            !this._currentModel.model_identifier ||
            !this._currentModel.api_endpoint) {
            this._formError = 'Please fill in all required fields';
            return;
        }
        this._isSubmitting = true;
        try {
            if (this._isEditing) {
                const updated = await updateAIModel(this._currentModel.id, this._currentModel);
                this.dispatchEvent(new CustomEvent('model-updated', {
                    detail: { model: updated },
                    bubbles: true,
                    composed: true,
                }));
            }
            else {
                const created = await createAIModel(this._currentModel);
                this.dispatchEvent(new CustomEvent('model-created', {
                    detail: { model: created },
                    bubbles: true,
                    composed: true,
                }));
            }
            this._handleClose();
        }
        catch (error) {
            this._formError =
                error instanceof Error
                    ? error.message
                    : 'Failed to save model. Please try again.';
            console.error('Failed to save model:', error);
        }
        finally {
            this._isSubmitting = false;
        }
    }
    // ── render ───────────────────────────────────────────
    render() {
        if (!this.open)
            return html ``;
        return html `
      <sl-dialog
        label="${this._isEditing ? 'Edit' : 'Add'} AI Model"
        .open=${this.open}
        @sl-request-close=${this._handleRequestClose}
      >
        ${when(this._formError, () => html `
            <sl-alert variant="danger" open>
              <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
              <strong>Error:</strong> ${this._formError}
            </sl-alert>
          `)}
        <div class="form-grid">
          <sl-input
            class="full-width"
            label="Friendly Name"
            .value=${this._currentModel.name || ''}
            @sl-input=${(e) => {
            this._currentModel.name = e.target.value;
            this.requestUpdate();
        }}
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
            .value=${this._currentModel.api_endpoint || ''}
            @sl-input=${(e) => {
            this._currentModel.api_endpoint = e.target.value;
            this.requestUpdate();
        }}
            ?disabled=${this._isSubmitting}
          ></sl-input>
          <sl-input
            class="full-width"
            type="password"
            label="API Key"
            .value=${this._currentModel.api_key || ''}
            @sl-input=${(e) => {
            this._currentModel.api_key = e.target.value;
            this.requestUpdate();
        }}
            placeholder=${this._isEditing
            ? 'Leave blank to keep existing key'
            : ''}
            ?disabled=${this._isSubmitting}
          >
            ${!this._isEditing &&
            this._getProviderKeyUrl(this._currentModel.provider_name)
            ? html `
                  <div slot="help-text">
                    Enter your API key to fetch available models.
                    <a
                      href=${this._getProviderKeyUrl(this._currentModel.provider_name)}
                      target="_blank"
                      rel="noopener noreferrer"
                      >Get your API key here.</a
                    >
                  </div>
                `
            : html `
                  <div slot="help-text">
                    ${this._isEditing
                ? ''
                : 'Enter your API key to fetch available models'}
                  </div>
                `}
          </sl-input>

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
            ? html `
                  <div
                    style="color: var(--sl-color-danger-600); font-size: 0.875rem; margin-top: 0.5rem;"
                  >
                    ${this._modelsFetchError}
                  </div>
                `
            : ''}
          </div>

          ${this._modelSuggestions.length > 0
            ? html `
                <sl-select
                  class="full-width"
                  label="Model Name / ID"
                  .value=${this._isOtherModel
                ? 'other'
                : this._currentModel.model_identifier || ''}
                  @sl-change=${this._handleModelNameChange}
                  ?disabled=${this._isSubmitting}
                >
                  ${repeat(this._modelSuggestions, (s) => s, (s) => html `<sl-option value="${s}">${s}</sl-option>`)}
                  <sl-option value="other">Other...</sl-option>
                </sl-select>

                ${when(this._isOtherModel, () => html `
                    <sl-input
                      class="full-width"
                      label="Custom Model Name / ID"
                      placeholder="Enter custom model name"
                      .value=${this._currentModel.model_identifier || ''}
                      @sl-input=${this._handleCustomModelInput}
                      ?disabled=${this._isSubmitting}
                    ></sl-input>
                  `)}
              `
            : this._modelsFetchError
                ? html `
                  <sl-input
                    class="full-width"
                    label="Model Name / ID"
                    placeholder="Enter model name manually"
                    .value=${this._currentModel.model_identifier || ''}
                    @sl-input=${this._handleCustomModelInput}
                    ?disabled=${this._isSubmitting}
                    help-text="Could not fetch models. You can enter the model name manually."
                  ></sl-input>
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
};
AddAIModelModal.styles = css `
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
__decorate([
    property({ type: Boolean })
], AddAIModelModal.prototype, "open", void 0);
__decorate([
    property({ type: Object })
], AddAIModelModal.prototype, "model", void 0);
__decorate([
    state()
], AddAIModelModal.prototype, "_currentModel", void 0);
__decorate([
    state()
], AddAIModelModal.prototype, "_formError", void 0);
__decorate([
    state()
], AddAIModelModal.prototype, "_isSubmitting", void 0);
__decorate([
    state()
], AddAIModelModal.prototype, "_modelSuggestions", void 0);
__decorate([
    state()
], AddAIModelModal.prototype, "_isOtherModel", void 0);
__decorate([
    state()
], AddAIModelModal.prototype, "_isFetchingModels", void 0);
__decorate([
    state()
], AddAIModelModal.prototype, "_modelsFetchError", void 0);
AddAIModelModal = __decorate([
    customElement('add-ai-model-modal')
], AddAIModelModal);
export { AddAIModelModal };
