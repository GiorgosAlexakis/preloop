var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { fetchWithAuth, getAccountOrganization, updateAccountOrganization, getFeatures, } from '../../../api';
import consoleStyles from '../../../styles/console-styles.css?inline';
import pricingStyles from '../../../styles/pricing-styles.css?inline';
import '../../../components/billing-toggle';
import '../../../components/pricing-card';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
let AccountView = class AccountView extends LitElement {
    constructor() {
        super(...arguments);
        this.accountOrganization = null;
        this.features = null;
        this.organizationName = '';
        this.isSavingOrg = false;
        this.orgSuccessMessage = '';
        this.orgErrorMessage = '';
        this.subscription = null;
        this._publicPlans = [];
        this._customPlans = [];
        this._loading = true;
        this._error = null;
        this._interval = 'month';
        this._featureOrder = [
            'api_calls_monthly',
            'ai_calls_monthly',
            'issues_ingested_monthly',
            'custom_ai_models_enabled',
            'custom_compliance_metrics_enabled',
        ];
        // Human-readable labels for common feature keys
        this._featureLabels = {
            api_calls_monthly: 'API calls / month',
            ai_calls_monthly: 'AI calls / month',
            issues_ingested_monthly: 'Issues ingested / month',
            custom_ai_models_enabled: 'Custom AI models',
            custom_compliance_metrics_enabled: 'Custom compliance metrics',
        };
    }
    async connectedCallback() {
        super.connectedCallback();
        await this._fetchData();
    }
    async _fetchData() {
        this._loading = true;
        try {
            // Fetch account details and features
            const [accountOrganization, features] = await Promise.all([
                getAccountOrganization(),
                getFeatures(),
            ]);
            this.accountOrganization = accountOrganization;
            this.features = features;
            this.organizationName = accountOrganization.organization_name || '';
            // Only fetch billing data for proprietary version
            const isProprietary = features.features['billing'] === true;
            if (isProprietary) {
                await fetchWithAuth('/api/v1/billing/sync-subscription', {
                    method: 'POST',
                });
                const [subRes, publicPlansRes, customPlansRes] = await Promise.all([
                    fetchWithAuth('/api/v1/billing/subscription'),
                    fetchWithAuth('/api/v1/billing/plans'),
                    fetchWithAuth('/api/v1/billing/custom-plans'),
                ]);
                if (subRes.status === 404) {
                    this.subscription = null;
                }
                else if (subRes.ok) {
                    this.subscription = await subRes.json();
                }
                else {
                    throw new Error('Failed to load subscription details.');
                }
                if (publicPlansRes.ok) {
                    const allPlans = await publicPlansRes.json();
                    this._publicPlans = allPlans.filter((p) => p.price_monthly !== null && p.price_monthly > 0);
                }
                else {
                    throw new Error('Failed to load public plans.');
                }
                if (customPlansRes.ok) {
                    this._customPlans = await customPlansRes.json();
                }
                else {
                    throw new Error('Failed to load custom plans.');
                }
            }
        }
        catch (error) {
            this._error = error.message;
            console.error(error);
        }
        finally {
            this._loading = false;
        }
    }
    async _handleSaveOrganization() {
        this.isSavingOrg = true;
        this.orgSuccessMessage = '';
        this.orgErrorMessage = '';
        try {
            const updated = await updateAccountOrganization({
                organization_name: this.organizationName || null,
            });
            this.accountOrganization = updated;
            this.orgSuccessMessage = 'Organization name saved successfully';
            setTimeout(() => (this.orgSuccessMessage = ''), 3000);
        }
        catch (error) {
            this.orgErrorMessage = error.message;
        }
        finally {
            this.isSavingOrg = false;
        }
    }
    async _handleManageSubscription() {
        this._error = null;
        try {
            const response = await fetchWithAuth('/api/v1/billing/create-portal-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ return_url: window.location.href }),
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({
                    detail: 'Failed to create portal session. Please check configuration and try again.',
                }));
                throw new Error(errorData.detail);
            }
            const { url } = await response.json();
            if (url) {
                window.location.href = url;
            }
            else {
                throw new Error('Could not retrieve the subscription management URL.');
            }
        }
        catch (error) {
            this._error = error.message;
            console.error('Failed to create portal session:', error);
        }
    }
    _handleUpgradeRequest(e) {
        this._handleUpgrade(e.detail.planId);
    }
    async _handleUpgrade(planId) {
        this._error = null;
        try {
            const response = await fetchWithAuth('/api/v1/billing/create-checkout-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    plan_id: planId,
                    interval: this._interval,
                }),
            });
            if (!response.ok) {
                const errorData = await response
                    .json()
                    .catch(() => ({ detail: 'Failed to process subscription change.' }));
                throw new Error(errorData.detail);
            }
            const result = await response.json();
            if (result.action === 'redirect') {
                window.location.href = result.url;
            }
            else if (result.action === 'refresh') {
                await this._fetchData();
            }
        }
        catch (error) {
            this._error = error.message;
            console.error('Failed to change subscription:', error);
        }
    }
    render() {
        if (this._loading) {
            return html `
        <view-header headerText="Account" width="narrow"></view-header>
        <div class="column-layout narrow">
          <div class="main-column">
            <div class="loading">
              <sl-spinner style="font-size: 3rem;"></sl-spinner>
            </div>
          </div>
        </div>
      `;
        }
        if (this._error) {
            return html `
        <view-header headerText="Account" width="narrow"></view-header>
        <div class="column-layout narrow">
          <div class="main-column">
            <sl-alert variant="danger" open>
              <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
              ${this._error}
            </sl-alert>
          </div>
        </div>
      `;
        }
        const isProprietary = this.features?.features['billing'] === true;
        const availablePlans = [...this._customPlans, ...this._publicPlans];
        const currentPlanName = this.subscription?.plan_id
            ? (availablePlans.find((p) => p.id === this.subscription?.plan_id)
                ?.name ?? 'Free')
            : 'Free';
        return html `
      <view-header headerText="Account" width="narrow"></view-header>
      <div class="column-layout narrow">
        <div class="main-column">
          <!-- Organization Details Section -->
          <sl-card style="margin-bottom: 2rem;">
            <h2 slot="header" style="margin: 0; font-size: 1.25rem;">
              Organization Details
            </h2>

            ${this.orgSuccessMessage
            ? html `
                  <sl-alert variant="success" open closable>
                    <sl-icon slot="icon" name="check-circle"></sl-icon>
                    ${this.orgSuccessMessage}
                  </sl-alert>
                `
            : ''}
            ${this.orgErrorMessage
            ? html `
                  <sl-alert variant="danger" open closable>
                    <sl-icon slot="icon" name="exclamation-triangle"></sl-icon>
                    ${this.orgErrorMessage}
                  </sl-alert>
                `
            : ''}

            <div style="display: flex; flex-direction: column; gap: 1rem;">
              <sl-input
                label="Organization Name"
                placeholder="Enter your organization name"
                value=${this.organizationName}
                @sl-input=${(e) => (this.organizationName = e.target.value)}
                ?disabled=${this.isSavingOrg}
              >
                <span slot="help-text">
                  This name will be displayed across the application
                </span>
              </sl-input>

              <div>
                <sl-button
                  variant="primary"
                  @click=${this._handleSaveOrganization}
                  ?loading=${this.isSavingOrg}
                >
                  Save Organization Name
                </sl-button>
              </div>
            </div>
          </sl-card>

          ${isProprietary
            ? html `
                <!-- Subscription Section (Proprietary Only) -->
                <div class="card current-plan">
                  <div class="current-row">
                    <span class="plan-name">${currentPlanName}</span>
                    <span
                      class="status-chip ${this.subscription?.status ===
                'pending_cancellation'
                ? 'pending'
                : ''}"
                    >
                      ${this.subscription
                ? this.subscription.status === 'pending_cancellation'
                    ? 'Pending cancellation'
                    : this.subscription.status
                : 'Free'}
                    </span>
                  </div>
                  ${this.subscription
                ? html `
                        <div class="date">
                          ${this.subscription.status === 'pending_cancellation'
                    ? 'Cancels on'
                    : 'Renews on'}
                          ${new Date(this.subscription.current_period_end).toLocaleDateString()}
                        </div>
                      `
                : html `<div class="date">
                        You are currently on the Free plan.
                      </div>`}
                  <div class="actions">
                    <sl-button
                      size="medium"
                      variant="primary"
                      @click=${this._handleManageSubscription}
                    >
                      Manage in Stripe
                    </sl-button>
                  </div>
                </div>

                <div>
                  <billing-toggle
                    .interval=${this._interval}
                    @interval-change=${(e) => (this._interval = e.detail.value)}
                  ></billing-toggle>

                  <div
                    class="plans-grid"
                    @signup-requested=${this._handleUpgradeRequest}
                  >
                    ${availablePlans
                .filter((p) => p.id !== this.subscription?.plan_id)
                .map((plan) => html `
                          <pricing-card
                            .plan=${plan}
                            .interval=${this._interval}
                            .featureOrder=${this._featureOrder}
                            .featureLabels=${this._featureLabels}
                          ></pricing-card>
                        `)}
                  </div>
                </div>
              `
            : ''}
        </div>
      </div>
    `;
    }
};
AccountView.styles = [
    unsafeCSS(pricingStyles),
    unsafeCSS(consoleStyles),
    css `
      .status-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.25rem 0.5rem;
        border-radius: 999px;
        background: var(--sl-color-neutral-200);
        color: var(--sl-color-neutral-800);
        font-weight: 600;
        font-size: 0.85rem;
      }
      .status-chip.pending {
        background: var(--sl-color-warning-200);
        color: var(--sl-color-warning-800);
      }

      .card {
        border: 1px solid var(--sl-color-neutral-300);
        border-radius: 16px;
        padding: 1rem 1.25rem;
      }

      .plan-name {
        font-weight: 700;
      }

      .actions {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-top: 0.5rem;
      }

      .billing-toggle {
        margin-bottom: 1rem;
      }

      .features {
        list-style: none;
        padding: 0;
        margin: 0.5rem 0 1rem 0;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }
      .feature {
        display: flex;
        gap: 0.5rem;
        align-items: baseline;
        color: var(--sl-color-neutral-800);
      }
      .feature.excluded {
        color: var(--sl-color-neutral-500);
      }
      .feat-icon {
        color: var(--sl-color-success-600);
      }
      .feature.excluded .feat-icon {
        color: var(--sl-color-neutral-400);
      }
      .feat-text {
        flex: 1;
      }
      .feat-value {
        color: var(--sl-color-neutral-700);
      }
      .more {
        color: var(--sl-color-neutral-600);
        font-size: 0.95rem;
      }

      .cta {
        margin-top: auto;
        width: 100%;
      }

      .loading,
      .error {
        text-align: center;
        margin: 1rem 0;
        color: var(--sl-color-danger-600);
      }
    `,
];
__decorate([
    state()
], AccountView.prototype, "accountOrganization", void 0);
__decorate([
    state()
], AccountView.prototype, "features", void 0);
__decorate([
    state()
], AccountView.prototype, "organizationName", void 0);
__decorate([
    state()
], AccountView.prototype, "isSavingOrg", void 0);
__decorate([
    state()
], AccountView.prototype, "orgSuccessMessage", void 0);
__decorate([
    state()
], AccountView.prototype, "orgErrorMessage", void 0);
__decorate([
    state()
], AccountView.prototype, "subscription", void 0);
__decorate([
    state()
], AccountView.prototype, "_publicPlans", void 0);
__decorate([
    state()
], AccountView.prototype, "_customPlans", void 0);
__decorate([
    state()
], AccountView.prototype, "_loading", void 0);
__decorate([
    state()
], AccountView.prototype, "_error", void 0);
__decorate([
    state()
], AccountView.prototype, "_interval", void 0);
AccountView = __decorate([
    customElement('account-view')
], AccountView);
export { AccountView };
