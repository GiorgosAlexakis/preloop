import { LitElement, html, css, unsafeCSS, render } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { fetchWithAuth } from '../../../api';
import consoleStyles from '../../../styles/console-styles.css?inline';
import pricingStyles from '../../../styles/pricing-styles.css?inline';
import '../../../components/billing-toggle';

interface Plan {
  id: string;
  name: string;
  price_monthly: number | null;
  price_annually: number | null;
  features: { [key: string]: any };
}

interface Subscription {
  plan_id: string;
  status: string;
  current_period_end: string;
}

@customElement('subscription-view')
export class SubscriptionView extends LitElement {
  @state() private subscription: Subscription | null = null;
  @state() private _publicPlans: Plan[] = [];
  @state() private _customPlans: Plan[] = [];
  @state() private _loading = true;
  @state() private _error: string | null = null;
  @state() private _interval: 'month' | 'year' = 'month';

  // Human-readable labels for common feature keys
  private _featureLabels: Record<string, string> = {
    api_calls_monthly: 'API calls / month',
    ai_calls_monthly: 'AI calls / month',
    issues_ingested_monthly: 'Issues ingested / month',
    custom_ai_models_enabled: 'Custom AI models',
    custom_compliance_metrics_enabled: 'Custom compliance metrics',
  };

  async connectedCallback() {
    super.connectedCallback();
    await this._fetchData();
  }

  private async _fetchData() {
    this._loading = true;
    try {
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
      } else if (subRes.ok) {
        this.subscription = await subRes.json();
      } else {
        throw new Error('Failed to load subscription details.');
      }

      if (publicPlansRes.ok) {
        const allPlans = await publicPlansRes.json();
        this._publicPlans = allPlans.filter(
          (p: Plan) => p.price_monthly !== null && p.price_monthly > 0
        );
      } else {
        throw new Error('Failed to load public plans.');
      }

      if (customPlansRes.ok) {
        this._customPlans = await customPlansRes.json();
      } else {
        throw new Error('Failed to load custom plans.');
      }
    } catch (error) {
      this._error = (error as Error).message;
      console.error(error);
    } finally {
      this._loading = false;
    }
  }

  private formatPrice(plan: Plan) {
    const isMonthly = this._interval === 'month';
    const amount = isMonthly ? plan.price_monthly : plan.price_annually;
    const unit = isMonthly ? '/mo' : '/yr';

    if (plan.id === 'enterprise' || amount === null) {
      return html`<div class="price-main">Custom</div>`;
    }

    const perMo =
      !isMonthly && typeof plan.price_annually === 'number'
        ? Math.round((plan.price_annually as number) / 12)
        : null;

    return html`
      <div class="price-main">$${amount}${unit}</div>
      ${!isMonthly && perMo !== null
        ? html`<div class="price-sub">~$${perMo}/mo billed annually</div>`
        : null}
    `;
  }

  private renderFeature([key, value]: [string, any]) {
    const label = this._featureLabels[key] ?? key.replace(/_/g, ' ');
    let included = false;
    let displayValue: string | null = null;

    if (value === true) {
      included = true;
    } else if (value === false) {
      included = false;
    } else if (value === -1) {
      included = true;
      displayValue = 'Unlimited';
    } else if (typeof value === 'number') {
      included = true;
      displayValue = String(value);
    } else if (typeof value === 'string') {
      included = true;
      displayValue = value;
    }

    return html`
      <li class=${included ? 'feature included' : 'feature excluded'}>
        <span class="feat-icon">${included ? '✓' : '✗'}</span>
        <span class="feat-text">
          ${label}${displayValue
            ? html`<span class="feat-value">: ${displayValue}</span>`
            : ''}
        </span>
      </li>
    `;
  }

  private async _handleManageSubscription() {
    this._error = null;
    try {
      const response = await fetchWithAuth(
        '/api/v1/billing/create-portal-session',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ return_url: window.location.href }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({
          detail:
            'Failed to create portal session. Please check configuration and try again.',
        }));
        throw new Error(errorData.detail);
      }

      const { url } = await response.json();
      if (url) {
        window.location.href = url;
      } else {
        throw new Error('Could not retrieve the subscription management URL.');
      }
    } catch (error) {
      this._error = (error as Error).message;
      console.error('Failed to create portal session:', error);
    }
  }

  private async _handleUpgrade(planId: string) {
    this._error = null;
    try {
      const response = await fetchWithAuth(
        '/api/v1/billing/create-checkout-session',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            plan_id: planId,
            interval: this._interval,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ detail: 'Failed to process subscription change.' }));
        throw new Error(errorData.detail);
      }

      const result = await response.json();

      if (result.action === 'redirect') {
        window.location.href = result.url;
      } else if (result.action === 'refresh') {
        await this._fetchData();
      }
    } catch (error) {
      this._error = (error as Error).message;
      console.error('Failed to change subscription:', error);
    }
  }

  static styles = [
    unsafeCSS(pricingStyles),
    unsafeCSS(consoleStyles),
    css`
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

  render() {
    if (this._loading) {
      return html`<div class="loading">Loading…</div>`;
    }

    if (this._error) {
      return html`<div class="error">${this._error}</div>`;
    }

    const availablePlans = [...this._customPlans, ...this._publicPlans];
    const currentPlanName = this.subscription?.plan_id
      ? (availablePlans.find((p) => p.id === this.subscription?.plan_id)
          ?.name ?? 'Free')
      : 'Free';

    return html`
      <view-header headerText="Your Subscriptions">
        <div slot="side-column">
          <theme-switcher></theme-switcher>
        </div>
      </view-header>
      <div class="column-layout">
        <div class="main-column">
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
              ? html`
                  <div class="date">
                    ${this.subscription.status === 'pending_cancellation'
                      ? 'Cancels on'
                      : 'Renews on'}
                    ${new Date(
                      this.subscription.current_period_end
                    ).toLocaleDateString()}
                  </div>
                `
              : html`<div class="date">
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
              @interval-change=${(e: CustomEvent) =>
                (this._interval = e.detail.value)}
            ></billing-toggle>

            <div class="plans-grid">
              ${availablePlans
                .filter((p) => p.id !== this.subscription?.plan_id)
                .map((plan) => {
                  const featureEntries = Object.entries(plan.features || {});
                  const visible = featureEntries.slice(0, 6);
                  const remaining = featureEntries.length - visible.length;

                  return html`
                    <div class="plan-card">
                      <h3 class="plan-name">${plan.name}</h3>
                      <div class="price-wrap">${this.formatPrice(plan)}</div>

                      <ul class="features">
                        ${visible.map((entry) => this.renderFeature(entry))}
                        ${remaining > 0
                          ? html`<li class="more">
                              + ${remaining} more features
                            </li>`
                          : null}
                      </ul>

                      <sl-button
                        class="cta"
                        size="large"
                        variant="default"
                        @click=${() => this._handleUpgrade(plan.id)}
                      >
                        ${this.subscription?.plan_id === 'free'
                          ? 'Upgrade'
                          : 'Change'}
                        to ${plan.name}
                      </sl-button>
                    </div>
                  `;
                })}
            </div>
          </div>
        </div>
      </div>
    `;
  }
}
