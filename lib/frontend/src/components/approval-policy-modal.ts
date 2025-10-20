import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import * as api from '../api';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/checkbox/checkbox.js';
import type SlInput from '@shoelace-style/shoelace/dist/components/input/input.js';

@customElement('approval-policy-modal')
export class ApprovalPolicyModal extends LitElement {
  @property({ type: Object })
  policy: any = null;

  @property({ type: String })
  toolConfigurationId: string = '';

  /**
   * @internal
   */
  _api = api;

  @property({ type: Boolean })
  opened = true;

  @state()
  private approvalType = 'slack';

  @state()
  private channel = '';

  @state()
  private user = '';

  @state()
  private timeoutSeconds = 300;

  @state()
  private requireReason = false;

  @state()
  private isLoading = false;

  @state()
  private errorMessage = '';

  static styles = css`
    .error {
      color: var(--sl-color-danger-700);
      margin-top: 1rem;
    }
    sl-input,
    sl-select,
    sl-checkbox {
      margin-bottom: 1rem;
    }
    .help-text {
      font-size: 0.875rem;
      color: var(--sl-color-neutral-600);
      margin-top: 0.25rem;
      margin-bottom: 1rem;
    }
    .form-section {
      margin-bottom: 1.5rem;
    }
    .section-title {
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 0.75rem;
      color: var(--sl-color-neutral-900);
    }
  `;

  connectedCallback() {
    super.connectedCallback();
    if (this.policy) {
      this.approvalType = this.policy.approval_type || 'slack';
      this.channel = this.policy.channel || '';
      this.user = this.policy.user || '';
      this.timeoutSeconds = this.policy.timeout_seconds || 300;
      this.requireReason = this.policy.require_reason || false;
    }
  }

  firstUpdated() {
    this.shadowRoot?.querySelector('sl-dialog')?.show();
    setTimeout(() => {
      const input = this.shadowRoot?.querySelector<SlInput>('sl-input');
      input?.focus();
    }, 100);
  }

  render() {
    return html`
      <sl-dialog
        label="${this.policy ? 'Edit' : 'Add'} Approval Policy"
        @sl-request-close=${() => this.closeModal()}
      >
        <div class="form-section">
          <div class="section-title">Approval Method</div>

          <sl-select
            label="Approval Type"
            name="approval_type"
            .value=${this.approvalType}
            @sl-change=${(e: any) => (this.approvalType = e.target.value)}
          >
            <sl-option value="slack">Slack</sl-option>
            <sl-option value="mattermost">Mattermost</sl-option>
            <sl-option value="webhook">Webhook</sl-option>
            <sl-option value="manual">Manual</sl-option>
          </sl-select>

          ${this.approvalType === 'slack' || this.approvalType === 'mattermost'
            ? html`
                <sl-input
                  label="Channel"
                  name="channel"
                  .value=${this.channel}
                  @sl-input=${(e: any) => (this.channel = e.target.value)}
                  placeholder="e.g., #approvals or @username"
                ></sl-input>
                <div class="help-text">
                  Use #channel-name for public channels or @username for direct
                  messages
                </div>

                <sl-input
                  label="Specific User (Optional)"
                  name="user"
                  .value=${this.user}
                  @sl-input=${(e: any) => (this.user = e.target.value)}
                  placeholder="e.g., @john.doe"
                ></sl-input>
                <div class="help-text">
                  Leave empty to allow any channel member to approve
                </div>
              `
            : ''}
          ${this.approvalType === 'webhook'
            ? html`
                <sl-input
                  label="Webhook URL"
                  name="webhook_url"
                  .value=${this.channel}
                  @sl-input=${(e: any) => (this.channel = e.target.value)}
                  placeholder="https://your-webhook-url.com/approve"
                ></sl-input>
                <div class="help-text">
                  The webhook will receive approval requests as POST requests
                </div>
              `
            : ''}
        </div>

        <div class="form-section">
          <div class="section-title">Timeout Settings</div>

          <sl-input
            type="number"
            label="Timeout (seconds)"
            name="timeout"
            .value=${this.timeoutSeconds.toString()}
            @sl-input=${(e: any) =>
              (this.timeoutSeconds = parseInt(e.target.value) || 300)}
            min="30"
            max="3600"
          ></sl-input>
          <div class="help-text">
            Time to wait for approval before the tool call fails (30-3600
            seconds)
          </div>
        </div>

        <div class="form-section">
          <sl-checkbox
            .checked=${this.requireReason}
            @sl-change=${(e: any) => (this.requireReason = e.target.checked)}
          >
            Require approver to provide a reason
          </sl-checkbox>
          <div class="help-text">
            When enabled, the approver must provide a reason for their decision
          </div>
        </div>

        ${this.errorMessage
          ? html`<p class="error">${this.errorMessage}</p>`
          : ''}

        <div slot="footer">
          <sl-button @click=${() => this.closeModal()}>Cancel</sl-button>
          <sl-button
            variant="primary"
            @click=${this.handleSave}
            .loading=${this.isLoading}
          >
            ${this.policy ? 'Save' : 'Create'}
          </sl-button>
        </div>
      </sl-dialog>
    `;
  }

  async handleSave() {
    this.isLoading = true;
    this.errorMessage = '';

    // Validate required fields based on approval type
    if (
      (this.approvalType === 'slack' || this.approvalType === 'mattermost') &&
      !this.channel.trim()
    ) {
      this.errorMessage = 'Channel is required for Slack/Mattermost approvals';
      this.isLoading = false;
      return;
    }

    if (this.approvalType === 'webhook' && !this.channel.trim()) {
      this.errorMessage = 'Webhook URL is required';
      this.isLoading = false;
      return;
    }

    if (this.timeoutSeconds < 30 || this.timeoutSeconds > 3600) {
      this.errorMessage = 'Timeout must be between 30 and 3600 seconds';
      this.isLoading = false;
      return;
    }

    const policyData = {
      tool_configuration_id: this.toolConfigurationId,
      approval_type: this.approvalType,
      channel: this.channel || null,
      user: this.user || null,
      timeout_seconds: this.timeoutSeconds,
      require_reason: this.requireReason,
    };

    try {
      if (this.policy) {
        const updatedPolicy = await this._api.updateApprovalPolicy(
          this.policy.id,
          policyData
        );
        this.dispatchEvent(
          new CustomEvent('policy-updated', {
            detail: { policy: updatedPolicy },
          })
        );
      } else {
        const newPolicy = await this._api.createApprovalPolicy(policyData);
        this.dispatchEvent(
          new CustomEvent('policy-created', {
            detail: { policy: newPolicy },
          })
        );
      }
      this.closeModal(true);
    } catch (error: any) {
      this.errorMessage = error.message;
    } finally {
      this.isLoading = false;
    }
  }

  closeModal(success = false) {
    if (typeof success !== 'boolean') {
      success = false;
    }
    const event = new CustomEvent('close-modal', {
      bubbles: true,
      composed: true,
      detail: { success },
    });
    this.dispatchEvent(event);
    this.opened = false;
  }
}
