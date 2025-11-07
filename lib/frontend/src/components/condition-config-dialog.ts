import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import * as api from '../api';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/switch/switch.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';

export interface Tool {
  config_id: string;
  name: string;
}

export interface ApprovalCondition {
  id: string;
  name?: string;
  description?: string;
  is_enabled: boolean;
  condition_type: string;
  condition_expression?: string;
  condition_config?: any;
}

@customElement('condition-config-dialog')
export class ConditionConfigDialog extends LitElement {
  @property({ type: Object })
  tool?: Tool;

  @property({ type: Boolean })
  open = false;

  @state()
  private name = '';

  @state()
  private description = '';

  @state()
  private isEnabled = true;

  @state()
  private conditionType = 'argument';

  @state()
  private conditionExpression = '';

  @state()
  private sampleArgs = '{\n  "example_arg": "value"\n}';

  @state()
  private testResult: { matches: boolean; error?: string } | null = null;

  @state()
  private isLoading = false;

  @state()
  private isTesting = false;

  @state()
  private errorMessage = '';

  @state()
  private condition: ApprovalCondition | null = null;

  /**
   * @internal
   */
  _api = api;

  static styles = css`
    .dialog-content {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-medium);
    }

    .form-field {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-2x-small);
    }

    .form-label {
      font-size: var(--sl-font-size-small);
      font-weight: var(--sl-font-weight-semibold);
      color: var(--sl-color-neutral-700);
    }

    .help-text {
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-600);
      margin-top: var(--sl-spacing-2x-small);
    }

    .section-title {
      font-size: var(--sl-font-size-medium);
      font-weight: var(--sl-font-weight-semibold);
      margin: var(--sl-spacing-medium) 0 var(--sl-spacing-small) 0;
      color: var(--sl-color-neutral-900);
    }

    .control-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .test-section {
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-medium);
      background: var(--sl-color-neutral-50);
    }

    .test-result {
      margin-top: var(--sl-spacing-medium);
      padding: var(--sl-spacing-medium);
      border-radius: var(--sl-border-radius-medium);
    }

    .test-result.success {
      background: var(--sl-color-success-50);
      border: 1px solid var(--sl-color-success-200);
      color: var(--sl-color-success-700);
    }

    .test-result.failure {
      background: var(--sl-color-danger-50);
      border: 1px solid var(--sl-color-danger-200);
      color: var(--sl-color-danger-700);
    }

    .test-result-header {
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-small);
      font-weight: var(--sl-font-weight-semibold);
      margin-bottom: var(--sl-spacing-small);
    }

    .error-message {
      color: var(--sl-color-danger-700);
      font-size: var(--sl-font-size-small);
      margin-top: var(--sl-spacing-small);
    }

    .info-box {
      background: var(--sl-color-primary-50);
      border: 1px solid var(--sl-color-primary-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-medium);
      margin-bottom: var(--sl-spacing-medium);
    }

    .info-box h4 {
      margin: 0 0 var(--sl-spacing-small) 0;
      font-size: var(--sl-font-size-small);
      font-weight: var(--sl-font-weight-semibold);
      color: var(--sl-color-primary-700);
    }

    .info-box p {
      margin: 0;
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-primary-700);
      line-height: 1.5;
    }

    .code-example {
      background: var(--sl-color-neutral-900);
      color: var(--sl-color-neutral-100);
      padding: var(--sl-spacing-small);
      border-radius: var(--sl-border-radius-small);
      font-family: var(--sl-font-mono);
      font-size: var(--sl-font-size-x-small);
      margin-top: var(--sl-spacing-small);
      white-space: pre;
      overflow-x: auto;
    }
  `;

  async connectedCallback() {
    super.connectedCallback();
    if (this.tool?.config_id) {
      await this.loadCondition();
    }
  }

  private async loadCondition() {
    if (!this.tool?.config_id) return;

    try {
      const response = await this._api.fetchWithAuth(
        `/api/v1/tool-configurations/${this.tool.config_id}/approval-condition`
      );

      if (response.ok) {
        this.condition = await response.json();
        this.name = this.condition?.name || '';
        this.description = this.condition?.description || '';
        this.isEnabled = this.condition?.is_enabled ?? true;
        this.conditionType = this.condition?.condition_type || 'argument';
        this.conditionExpression = this.condition?.condition_expression || '';
      }
    } catch (error) {
      // Condition doesn't exist yet, that's okay
      console.log('No existing condition found');
    }
  }

  private async handleTest() {
    if (!this.tool?.config_id || !this.conditionExpression.trim()) {
      this.errorMessage = 'Please enter a condition expression';
      return;
    }

    try {
      this.isTesting = true;
      this.errorMessage = '';

      // Parse sample args
      let sampleArgsObj: any;
      try {
        sampleArgsObj = JSON.parse(this.sampleArgs);
      } catch (e) {
        this.errorMessage = 'Invalid JSON in sample arguments';
        this.isTesting = false;
        return;
      }

      const response = await this._api.fetchWithAuth(
        `/api/v1/tool-configurations/${this.tool.config_id}/approval-condition/test`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expression: this.conditionExpression,
            sample_args: sampleArgsObj,
          }),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        this.errorMessage = error.detail || 'Test failed';
        this.testResult = null;
      } else {
        this.testResult = await response.json();
      }
    } catch (error: any) {
      this.errorMessage = error.message || 'Test request failed';
      this.testResult = null;
    } finally {
      this.isTesting = false;
    }
  }

  private async handleSave() {
    if (!this.tool?.config_id) return;

    try {
      this.isLoading = true;
      this.errorMessage = '';

      const conditionData = {
        tool_configuration_id: this.tool.config_id,
        name: this.name || undefined,
        description: this.description || undefined,
        is_enabled: this.isEnabled,
        condition_type: this.conditionType,
        condition_expression: this.conditionExpression || undefined,
        condition_config: {},
      };

      const response = await this._api.fetchWithAuth(
        `/api/v1/tool-configurations/${this.tool.config_id}/approval-condition`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(conditionData),
        }
      );

      if (!response.ok) {
        const error = await response.json();
        this.errorMessage = error.detail || 'Failed to save condition';
        return;
      }

      // Success! Close dialog and notify parent
      this.dispatchEvent(
        new CustomEvent('condition-saved', {
          bubbles: true,
          composed: true,
        })
      );
      this.handleClose();
    } catch (error: any) {
      this.errorMessage = error.message || 'Save request failed';
    } finally {
      this.isLoading = false;
    }
  }

  private async handleDelete() {
    if (!this.tool?.config_id || !this.condition) return;

    if (!confirm('Are you sure you want to delete this condition?')) {
      return;
    }

    try {
      this.isLoading = true;
      this.errorMessage = '';

      const response = await this._api.fetchWithAuth(
        `/api/v1/tool-configurations/${this.tool.config_id}/approval-condition`,
        {
          method: 'DELETE',
        }
      );

      if (!response.ok) {
        const error = await response.json();
        this.errorMessage = error.detail || 'Failed to delete condition';
        return;
      }

      // Success! Close dialog and notify parent
      this.dispatchEvent(
        new CustomEvent('condition-deleted', {
          bubbles: true,
          composed: true,
        })
      );
      this.handleClose();
    } catch (error: any) {
      this.errorMessage = error.message || 'Delete request failed';
    } finally {
      this.isLoading = false;
    }
  }

  private handleClose() {
    this.dispatchEvent(
      new CustomEvent('close', {
        bubbles: true,
        composed: true,
      })
    );
  }

  render() {
    return html`
      <sl-dialog
        label="Configure Approval Condition"
        ?open=${this.open}
        @sl-request-close=${this.handleClose}
        style="--width: 700px;"
      >
        <div class="dialog-content">
          <div class="info-box">
            <h4>
              <sl-icon name="lightbulb"></sl-icon>
              About Approval Conditions
            </h4>
            <p>
              Approval conditions use CEL (Common Expression Language) to
              determine when approval is required. If the condition matches, the
              tool execution will require approval before proceeding.
            </p>
            <div class="code-example">
              Examples: • args.danger_level > 5 • args.environment ==
              "production" • args.file_path.startsWith("/etc/")
            </div>
          </div>

          <div class="form-field">
            <label class="form-label">Condition Name (Optional)</label>
            <sl-input
              placeholder="e.g., Production Environment Check"
              value=${this.name}
              @sl-input=${(e: any) => (this.name = e.target.value)}
            ></sl-input>
          </div>

          <div class="form-field">
            <label class="form-label">Description (Optional)</label>
            <sl-textarea
              placeholder="Describe when this condition should trigger approval"
              value=${this.description}
              @sl-input=${(e: any) => (this.description = e.target.value)}
              rows="2"
            ></sl-textarea>
          </div>

          <div class="form-field">
            <div class="control-row">
              <label class="form-label">Enabled</label>
              <sl-switch
                ?checked=${this.isEnabled}
                @sl-change=${(e: any) => (this.isEnabled = e.target.checked)}
              ></sl-switch>
            </div>
            <div class="help-text">
              Disabled conditions will cause all tool executions to require
              approval
            </div>
          </div>

          <div class="form-field">
            <label class="form-label">CEL Expression *</label>
            <sl-textarea
              placeholder="args.environment == 'production'"
              value=${this.conditionExpression}
              @sl-input=${(e: any) =>
                (this.conditionExpression = e.target.value)}
              rows="3"
              help-text="Use 'args' to access tool arguments (e.g., args.file_path, args.danger_level)"
            ></sl-textarea>
          </div>

          <div class="test-section">
            <h3 class="section-title">Test Expression</h3>
            <div class="form-field">
              <label class="form-label">Sample Arguments (JSON)</label>
              <sl-textarea
                placeholder='{"example_arg": "value"}'
                value=${this.sampleArgs}
                @sl-input=${(e: any) => (this.sampleArgs = e.target.value)}
                rows="4"
                help-text="Enter JSON object representing tool arguments to test against"
              ></sl-textarea>
            </div>

            <sl-button
              @click=${this.handleTest}
              ?loading=${this.isTesting}
              ?disabled=${!this.conditionExpression.trim()}
            >
              <sl-icon slot="prefix" name="play-circle"></sl-icon>
              Test Expression
            </sl-button>

            ${this.testResult
              ? html`
                  <div
                    class="test-result ${this.testResult.matches
                      ? 'success'
                      : 'failure'}"
                  >
                    <div class="test-result-header">
                      <sl-icon
                        name=${this.testResult.matches
                          ? 'check-circle-fill'
                          : 'x-circle-fill'}
                      ></sl-icon>
                      ${this.testResult.matches
                        ? 'Condition Matches - Approval Required'
                        : 'Condition Does Not Match - No Approval Required'}
                    </div>
                    ${this.testResult.error
                      ? html`<div>Error: ${this.testResult.error}</div>`
                      : ''}
                  </div>
                `
              : ''}
          </div>

          ${this.errorMessage
            ? html`<div class="error-message">${this.errorMessage}</div>`
            : ''}
        </div>

        <div
          slot="footer"
          style="display: flex; justify-content: space-between; width: 100%;"
        >
          <div>
            ${this.condition
              ? html`
                  <sl-button
                    variant="danger"
                    @click=${this.handleDelete}
                    ?loading=${this.isLoading}
                  >
                    <sl-icon slot="prefix" name="trash"></sl-icon>
                    Delete
                  </sl-button>
                `
              : ''}
          </div>
          <div style="display: flex; gap: var(--sl-spacing-small);">
            <sl-button @click=${this.handleClose} ?disabled=${this.isLoading}>
              Cancel
            </sl-button>
            <sl-button
              variant="primary"
              @click=${this.handleSave}
              ?loading=${this.isLoading}
              ?disabled=${!this.conditionExpression.trim()}
            >
              <sl-icon slot="prefix" name="check-lg"></sl-icon>
              Save Condition
            </sl-button>
          </div>
        </div>
      </sl-dialog>
    `;
  }
}
