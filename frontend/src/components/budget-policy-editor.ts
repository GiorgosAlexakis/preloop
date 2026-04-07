import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import {
  BudgetPolicy,
  BudgetPolicyCreate,
  getBudgetPolicies,
  createBudgetPolicy,
  deleteBudgetPolicy,
} from '../api.js';

import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/checkbox/checkbox.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';

@customElement('budget-policy-editor')
export class BudgetPolicyEditor extends LitElement {
  @property({ type: String }) subjectType!: string;
  @property({ type: String }) subjectId!: string;

  @state() private policies: BudgetPolicy[] = [];
  @state() private showAddForm = false;
  @state() private error = '';

  // New Policy Form State
  @state() private newPeriod = 'monthly';
  @state() private newHardLimit = '';
  @state() private newSoftLimit = '';
  @state() private newNotifySoft = false;
  @state() private newNotifyHard = false;
  @state() private newEmails = '';

  static styles = css`
    :host {
      display: block;
      font-family: var(--sl-font-sans);
    }
    .policy-list {
      margin-top: var(--sl-spacing-medium);
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-small);
    }
    .policy-item {
      padding: var(--sl-spacing-small) var(--sl-spacing-medium);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--sl-panel-background-color);
      color: var(--sl-color-neutral-900);
    }
    .form-container {
      margin-top: var(--sl-spacing-medium);
      padding: var(--sl-spacing-medium);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      background: var(--sl-panel-background-color);
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-medium);
    }
    .form-row {
      display: flex;
      gap: var(--sl-spacing-medium);
    }
    .form-row > * {
      flex: 1;
    }
    .form-actions {
      display: flex;
      justify-content: flex-end;
      gap: var(--sl-spacing-small);
      margin-top: var(--sl-spacing-small);
    }
    .checkbox-group {
      display: flex;
      gap: var(--sl-spacing-medium);
      align-items: center;
    }
    .meta-text {
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-500);
      margin-top: var(--sl-spacing-3x-small);
    }
  `;

  async connectedCallback() {
    super.connectedCallback();
    await this.loadPolicies();
  }

  async loadPolicies() {
    try {
      const result = await getBudgetPolicies(this.subjectType, this.subjectId);
      if (Array.isArray(result)) {
        this.policies = result;
      } else {
        this.error =
          'Failed to load budget policies. Server returned an error.';
        this.policies = [];
        console.error('Non-array response:', result);
      }
    } catch (e: any) {
      this.error = 'Failed to load budget policies.';
      this.policies = [];
      console.error(e);
    }
  }

  private async handleDelete(id: string) {
    try {
      await deleteBudgetPolicy(id);
      await this.loadPolicies();
    } catch (e: any) {
      this.error = 'Failed to delete policy.';
    }
  }

  private async handleCreate() {
    this.error = '';

    // Parse emails from comma separated
    let emails: string[] = [];
    if (this.newEmails.trim()) {
      emails = this.newEmails
        .split(',')
        .map((e) => e.trim())
        .filter((e) => e);
    }

    const payload: BudgetPolicyCreate = {
      subject_type: this.subjectType,
      subject_id: this.subjectId,
      model_alias: null, // applies to all models
      period: this.newPeriod,
      hard_limit_usd: this.newHardLimit ? parseFloat(this.newHardLimit) : null,
      soft_limit_usd: this.newSoftLimit ? parseFloat(this.newSoftLimit) : null,
      notify_on_soft: this.newNotifySoft,
      notify_on_hard: this.newNotifyHard,
      notification_emails: emails.length > 0 ? emails : null,
    };

    try {
      await createBudgetPolicy(payload);
      this.showAddForm = false;
      this.resetForm();
      await this.loadPolicies();
    } catch (err: any) {
      this.error = 'Failed to create policy. ' + (err.message || '');
    }
  }

  private resetForm() {
    this.newPeriod = 'monthly';
    this.newHardLimit = '';
    this.newSoftLimit = '';
    this.newNotifySoft = false;
    this.newNotifyHard = false;
    this.newEmails = '';
  }

  render() {
    return html`
      <div>
        <div
          style="display: flex; justify-content: space-between; align-items: center;"
        >
          <h4
            style="margin: 0; font-size: var(--sl-font-size-large); font-weight: var(--sl-font-weight-semibold); color: var(--sl-color-neutral-900);"
          >
            Budget Policies
          </h4>
          ${!this.showAddForm
            ? html`
                <sl-button
                  size="small"
                  variant="primary"
                  @click=${() => (this.showAddForm = true)}
                >
                  <sl-icon slot="prefix" name="plus"></sl-icon>
                  Add Policy
                </sl-button>
              `
            : ''}
        </div>

        ${this.error
          ? html`
              <sl-alert
                variant="danger"
                open
                style="margin-top: var(--sl-spacing-medium);"
              >
                <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                ${this.error}
              </sl-alert>
            `
          : ''}

        <div class="policy-list">
          ${this.policies.length === 0 && !this.showAddForm
            ? html`<div
                style="color: var(--sl-color-neutral-500); font-size: var(--sl-font-size-small);"
              >
                No budget policies configured.
              </div>`
            : this.policies.map(
                (p) => html`
                  <div class="policy-item">
                    <div>
                      <strong style="color: var(--sl-color-neutral-900);"
                        >${p.period.charAt(0).toUpperCase() +
                        p.period.slice(1)}</strong
                      >
                      Limit:
                      ${p.hard_limit_usd
                        ? html`Hard: $${p.hard_limit_usd.toFixed(2)}`
                        : 'No Hard Limit'}
                      ${p.soft_limit_usd
                        ? html`| Soft: $${p.soft_limit_usd.toFixed(2)}`
                        : ''}
                      <div class="meta-text">
                        Notifications to:
                        ${p.notification_emails?.join(', ') || 'None'}
                      </div>
                    </div>
                    <sl-icon-button
                      name="trash"
                      style="color: var(--sl-color-danger-600);"
                      @click=${() => this.handleDelete(p.id)}
                    ></sl-icon-button>
                  </div>
                `
              )}
        </div>

        ${this.showAddForm
          ? html`
              <div class="form-container">
                <sl-select
                  label="Period"
                  value=${this.newPeriod}
                  @sl-change=${(e: any) => (this.newPeriod = e.target.value)}
                >
                  <sl-option value="hourly">Hourly</sl-option>
                  <sl-option value="daily">Daily</sl-option>
                  <sl-option value="weekly">Weekly</sl-option>
                  <sl-option value="monthly">Monthly</sl-option>
                  <sl-option value="yearly">Yearly</sl-option>
                  <sl-option value="all_time">All Time</sl-option>
                </sl-select>

                <div class="form-row">
                  <sl-input
                    label="Hard Limit (USD)"
                    type="number"
                    step="0.0001"
                    .value=${this.newHardLimit}
                    @sl-input=${(e: any) =>
                      (this.newHardLimit = e.target.value)}
                  ></sl-input>
                  <sl-input
                    label="Soft Limit (USD)"
                    type="number"
                    step="0.0001"
                    .value=${this.newSoftLimit}
                    @sl-input=${(e: any) =>
                      (this.newSoftLimit = e.target.value)}
                  ></sl-input>
                </div>

                <sl-input
                  label="Notification Emails"
                  help-text="Comma separated list of emails"
                  placeholder="admin@example.com"
                  .value=${this.newEmails}
                  @sl-input=${(e: any) => (this.newEmails = e.target.value)}
                ></sl-input>

                <div class="checkbox-group">
                  <sl-checkbox
                    ?checked=${this.newNotifySoft}
                    @sl-change=${(e: any) =>
                      (this.newNotifySoft = e.target.checked)}
                  >
                    Send email on Soft Limit
                  </sl-checkbox>
                  <sl-checkbox
                    ?checked=${this.newNotifyHard}
                    @sl-change=${(e: any) =>
                      (this.newNotifyHard = e.target.checked)}
                  >
                    Send email on Hard Limit
                  </sl-checkbox>
                </div>

                <div class="form-actions">
                  <sl-button @click=${() => (this.showAddForm = false)}
                    >Cancel</sl-button
                  >
                  <sl-button variant="primary" @click=${this.handleCreate}
                    >Save Policy</sl-button
                  >
                </div>
              </div>
            `
          : ''}
      </div>
    `;
  }
}
