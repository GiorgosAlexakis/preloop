import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { getAvailableModelsForProvider, createAIModel } from '../api';
import type { SlSelect } from '@shoelace-style/shoelace/dist/components/select/select.js';

import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';

@customElement('add-ai-model-modal')
export class AddAIModelModal extends LitElement {
  static styles = css`
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
    }
    .full-width {
      grid-column: 1 / -1;
    }
  `;

  @property({ type: Boolean })
  open = false;

  @state()
  private currentModel: any = {};

  @state()
  private formError: string | null = null;

  @state()
  private isSubmitting = false;

  @state()
  private modelSuggestions: string[] = [];

  @state()
  private isOtherModel = false;

  @state()
  private isFetchingModels = false;

  @state()
  private modelsFetchError: string | null = null;

  private modelFetchTimeout?: number;

  disconnectedCallback() {
    super.disconnectedCallback();
    // Clean up timeout
    if (this.modelFetchTimeout) {
      clearTimeout(this.modelFetchTimeout);
    }
  }

  render() {
    if (!this.open) return html``;

    return html`
      <sl-dialog
        label="Add AI Model"
        .open=${this.open}
        @sl-request-close=${this.handleRequestClose}
      >
        ${this.formError
          ? html`
              <sl-alert variant="danger" open>
                <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                <strong>Error:</strong> ${this.formError}
              </sl-alert>
            `
          : ''}
        <div class="form-grid">
          <sl-input
            class="full-width"
            label="Friendly Name"
            .value=${this.currentModel.name || ''}
            @sl-input=${(e: Event) => {
              this.currentModel.name = (e.target as HTMLInputElement).value;
            }}
            ?disabled=${this.isSubmitting}
          ></sl-input>
          <sl-select
            label="Provider"
            .value=${this.currentModel.provider_name || ''}
            @sl-change=${this.handleProviderChange}
            ?disabled=${this.isSubmitting}
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
            .value=${this.currentModel.api_url || ''}
            @sl-input=${(e: Event) => {
              this.currentModel.api_url = (e.target as HTMLInputElement).value;
            }}
            ?disabled=${this.isSubmitting}
          ></sl-input>
          <sl-input
            class="full-width"
            type="password"
            label="API Key"
            .value=${this.currentModel.api_key || ''}
            @sl-input=${(e: Event) => {
              this.currentModel.api_key = (e.target as HTMLInputElement).value;
              this.requestUpdate();

              // Clear existing timeout
              if (this.modelFetchTimeout) {
                clearTimeout(this.modelFetchTimeout);
              }

              // Auto-fetch models after 1 second of no typing
              if (
                this.currentModel.api_key &&
                this.currentModel.provider_name
              ) {
                this.modelFetchTimeout = window.setTimeout(() => {
                  this.fetchModelsForCurrentProvider();
                }, 1000);
              }
            }}
            ?disabled=${this.isSubmitting}
            help-text="Models will be fetched automatically"
          ></sl-input>

          ${this.isFetchingModels
            ? html`
                <div
                  class="full-width"
                  style="text-align: center; padding: 1rem; background: var(--sl-color-primary-50); border-radius: 4px;"
                >
                  <sl-spinner style="font-size: 2rem;"></sl-spinner>
                  <div
                    style="margin-top: 0.5rem; color: var(--sl-color-primary-700);"
                  >
                    Validating API key and fetching models...
                  </div>
                </div>
              `
            : this.modelsFetchError
              ? html`
                  <div class="full-width">
                    <sl-alert variant="danger" open>
                      <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                      <strong>Authentication Failed</strong>
                      <div style="margin-top: 0.5rem;">
                        ${this.modelsFetchError}
                      </div>
                      <sl-button
                        slot="footer"
                        variant="danger"
                        size="small"
                        @click=${this.fetchModelsForCurrentProvider}
                      >
                        <sl-icon slot="prefix" name="arrow-clockwise"></sl-icon>
                        Retry
                      </sl-button>
                    </sl-alert>
                  </div>
                `
              : this.modelSuggestions.length > 0
                ? html`
                    <div class="full-width">
                      <sl-alert variant="success" open closable>
                        <sl-icon slot="icon" name="check-circle"></sl-icon>
                        <strong>API Key Valid!</strong> Found
                        ${this.modelSuggestions.length} available models.
                      </sl-alert>
                    </div>
                  `
                : ''}
          ${this.modelSuggestions.length > 0
            ? html`
                <sl-select
                  class="full-width"
                  label="Model Name / ID"
                  .value=${this.isOtherModel
                    ? 'other'
                    : this.currentModel.model_identifier || ''}
                  @sl-change=${this.handleModelNameChange}
                  ?disabled=${this.isSubmitting}
                >
                  ${this.modelSuggestions.map(
                    (s) => html`<sl-option value="${s}">${s}</sl-option>`
                  )}
                  <sl-option value="other">Other...</sl-option>
                </sl-select>

                ${this.isOtherModel
                  ? html`
                      <sl-input
                        class="full-width"
                        label="Custom Model Name / ID"
                        placeholder="Enter custom model name"
                        .value=${this.currentModel.model_identifier || ''}
                        @sl-input=${(e: Event) => {
                          this.currentModel.model_identifier = (
                            e.target as HTMLInputElement
                          ).value;
                        }}
                        ?disabled=${this.isSubmitting}
                      ></sl-input>
                    `
                  : ''}
              `
            : ''}
        </div>
        <sl-button
          slot="footer"
          @click=${this.handleClose}
          ?disabled=${this.isSubmitting}
          >Cancel</sl-button
        >
        <sl-button
          slot="footer"
          variant="primary"
          @click=${this.handleFormSubmit}
          ?loading=${this.isSubmitting}
          ?disabled=${this.isSubmitting}
          >Save</sl-button
        >
      </sl-dialog>
    `;
  }

  private handleRequestClose(event: CustomEvent) {
    // Only close the dialog for certain reasons
    // Prevent closing when clicking outside or pressing escape if form has data
    const source = (event.detail as any).source;

    // Allow closing via close button, cancel button, or when no data is entered
    if (source === 'close-button' || !this.currentModel.provider_name) {
      this.dispatchEvent(new CustomEvent('close-modal'));
    } else {
      // Prevent closing for other reasons (overlay click, escape) when form has data
      event.preventDefault();
    }
  }

  private handleClose() {
    // Programmatically close the modal after successful form submission
    this.dispatchEvent(new CustomEvent('close-modal'));
  }

  private async fetchModelSuggestionsForProvider(
    provider: string,
    apiKey?: string
  ): Promise<string[]> {
    // Fetch available models from the provider
    // Pass API key to validate it and get live models
    // Let errors propagate so we can show proper feedback to the user
    const models = await getAvailableModelsForProvider(provider, apiKey);
    return models;
  }

  private async fetchModelsForCurrentProvider() {
    if (!this.currentModel.provider_name) {
      return;
    }

    this.isFetchingModels = true;
    this.modelsFetchError = null;

    try {
      this.modelSuggestions = await this.fetchModelSuggestionsForProvider(
        this.currentModel.provider_name,
        this.currentModel.api_key
      );
      if (this.modelSuggestions.length === 0) {
        this.modelsFetchError = 'No models available for this provider';
      } else {
        // Clear any previous errors on success
        this.modelsFetchError = null;
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
      this.modelsFetchError =
        error instanceof Error ? error.message : 'Failed to fetch models';
      // Clear suggestions on error
      this.modelSuggestions = [];
    } finally {
      this.isFetchingModels = false;
      this.requestUpdate();
    }
  }

  private async handleProviderChange(e: Event) {
    const provider = (e.target as SlSelect).value;

    const defaultUrls: { [key: string]: string } = {
      openai: 'https://api.openai.com/v1',
      anthropic: 'https://api.anthropic.com/v1',
      google: 'https://generativelanguage.googleapis.com/v1beta',
      qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      deepseek: 'https://api.deepseek.com/v1',
    };

    this.currentModel = {
      ...this.currentModel,
      provider_name: provider,
      api_url: defaultUrls[provider] || '',
      model_identifier: '',
    };

    // Reset model suggestions and errors
    this.modelSuggestions = [];
    this.isOtherModel = false;
    this.modelsFetchError = null;
    this.requestUpdate();
  }

  private handleModelNameChange(e: Event) {
    const selectedValue = (e.target as SlSelect).value;
    if (selectedValue === 'other') {
      this.isOtherModel = true;
      this.currentModel.model_identifier = '';
    } else {
      this.isOtherModel = false;
      this.currentModel.model_identifier = selectedValue;
    }
  }

  private async handleFormSubmit(e: Event) {
    e.preventDefault();

    this.formError = null;

    // Basic validation
    if (
      !this.currentModel.name ||
      !this.currentModel.provider_name ||
      !this.currentModel.model_identifier ||
      !this.currentModel.api_url ||
      !this.currentModel.api_key
    ) {
      this.formError = 'Please fill in all required fields';
      return;
    }

    this.isSubmitting = true;

    try {
      const newModel = await createAIModel(this.currentModel);
      this.dispatchEvent(
        new CustomEvent('model-created', {
          detail: { model: newModel },
        })
      );
      this.resetForm();
      this.handleClose();
    } catch (error) {
      if (error instanceof Error) {
        this.formError = error.message;
      } else {
        this.formError = 'Failed to save model. Please try again.';
      }
      console.error('Failed to save model:', error);
    } finally {
      this.isSubmitting = false;
    }
  }

  private resetForm() {
    this.currentModel = {};
    this.modelSuggestions = [];
    this.isOtherModel = false;
    this.formError = null;
    this.isSubmitting = false;
    this.isFetchingModels = false;
    this.modelsFetchError = null;
  }
}
