import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { fetchWithAuth, fetchPublic } from '../../api';
import landingStyles from '../../styles/landing.css?inline';

interface Plan {
  id: string;
  name: string;
  price_monthly: number | null;
  price_annually: number | null;
  features: { [key: string]: any };
}

@customElement('public-pricing-view')
export class PublicPricingView extends LitElement {
  @state() private _plans: Plan[] = [];
  @state() private _loading = true;
  @state() private _error: string | null = null;
  @state() private _interval: 'month' | 'year' = 'month';

  private _featureOrder = [
    'api_calls_monthly',
    'ai_calls_monthly',
    'issues_ingested_monthly',
    'custom_ai_models_enabled',
    'custom_compliance_metrics_enabled',
  ];

  private _featureLabels: Record<string, string> = {
    api_calls_monthly: 'API calls / month',
    ai_calls_monthly: 'AI calls / month',
    issues_ingested_monthly: 'Issues ingested / month',
    custom_ai_models_enabled: 'Custom AI models',
    custom_compliance_metrics_enabled: 'Custom compliance metrics',
  };

  async connectedCallback() {
    super.connectedCallback();
    await this._fetchPlans();
  }

  private async _fetchPlans() {
    try {
      this._loading = true;
      const response = await fetch('/api/v1/billing/plans');
      const allPlans = await response.json();
      // Ensure "Free" plan is first
      this._plans = allPlans.sort((a: Plan, b: Plan) => {
        if (a.id === 'free') return -1;
        if (b.id === 'free') return 1;
        return 0;
      });
    } catch (error) {
      this._error = 'Failed to load pricing plans.';
      console.error(error);
    } finally {
      this._loading = false;
    }
  }

  private formatPrice(plan: Plan) {
    if (plan.id === 'enterprise') {
      return html`<div class="price-main">Custom</div>`;
    }
    const isMonthly = this._interval === 'month';
    const amount = isMonthly ? plan.price_monthly : plan.price_annually;
    const unit = isMonthly ? '/mo' : '/yr';

    if (amount === null) {
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

  private renderFeature(value: any, key: string) {
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

  private async _handleSignUp(planId: string) {
    if (planId === 'enterprise') {
      window.location.href = '/request-demo';
      return;
    }

    if (planId === 'free') {
      window.location.href = '/register';
      return;
    }

    // For all paid plans
    try {
      const isAuthenticated = !!localStorage.getItem('accessToken');
      const fetcher = isAuthenticated ? fetchWithAuth : fetchPublic;

      const response = await fetcher(
        '/api/v1/billing/create-checkout-session',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ plan_id: planId, interval: this._interval }),
        }
      );
      const data = await response.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        console.error('Checkout URL not found in response:', data);
      }
    } catch (error) {
      console.error('Failed to create checkout session:', error);
    }
  }

  static styles = [
    unsafeCSS(landingStyles),
    css`
      .billing-toggle {
        display: flex;
        gap: 0.75rem;
        align-items: center;
        justify-content: center;
        margin: 1.5rem 0 2rem 0;
        flex-wrap: wrap;
      }
      .billing-toggle .label {
        font-weight: 600;
      }
      .billing-toggle .hint {
        font-size: 0.95rem;
      }

      .loading,
      .error {
        text-align: center;
        margin: 2rem 0;
      }
      .error {
        color: var(--sl-color-danger-600);
      }

      .plans-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 1.25rem;
        align-items: stretch;
      }

      .plan-card {
        position: relative;
        display: flex;
        flex-direction: column;
        border: 1px solid var(--sl-color-neutral-600);
        border-radius: 20px;
        padding: 1.5rem;
      }

      .plan-card.popular {
        border: none;
        background: linear-gradient(
          45deg,
          hsl(220, 60%, 40%),
          hsl(260, 65%, 38%)
        );
      }

      .badge {
        position: absolute;
        top: 12px;
        right: 12px;
        background: var(--sl-color-primary-600);
        color: white;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 0.25rem 0.5rem;
        border-radius: 999px;
      }

      .badge.alt {
        background: var(--sl-color-neutral-700);
      }

      .plan-name {
        margin: 0 0 0.25rem 0;
        font-size: 1.25rem;
      }

      .price-wrap {
        margin: 0.25rem 0 0.75rem 0;
      }

      .price-main {
        font-size: 2rem;
        font-weight: 800;
      }

      .price-sub {
        color: var(--sl-color-neutral-600);
        font-size: 0.95rem;
        margin-top: 0.25rem;
      }

      .divider {
        border: none;
        height: 1px;
        background-color: var(--sl-color-neutral-600);
        margin: 1rem 0;
      }

      .plan-card.popular .divider {
        background-color: var(--sl-color-primary-500);
      }

      .features {
        list-style: none;
        padding: 0;
        margin: 0.5rem 0 1rem 0;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }

      .feat-icon {
        color: var(--sl-color-success-600);
      }
      .feature.excluded .feat-icon {
        color: var(--sl-color-neutral-400);
      }

      .cta {
        margin-top: auto;
        width: 100%;
      }

      .cta::part(label) {
        font-weight: 600;
      }
    `,
  ];

  render() {
    return html`
      <app-header></app-header>
      <main>
        <section class="main-section">
          <div class="section-container hero-inner">
            <div class="hero-content">
              <h1 class="fw-bold">
                <span class="gradient-product">Pricing</span>
              </h1>
              <p class="lead">
                Choose the plan that fits your team and scale as you grow.
              </p>
            </div>
          </div>

          <div class="section-container">
            <div class="billing-toggle">
              <sl-button-group>
                <sl-button
                  variant=${this._interval === 'month' ? 'primary' : 'default'}
                  @click=${() => (this._interval = 'month')}
                >
                  Monthly
                </sl-button>
                <sl-button
                  variant=${this._interval === 'year' ? 'primary' : 'default'}
                  @click=${() => (this._interval = 'year')}
                >
                  Yearly (Best Value)
                </sl-button>
              </sl-button-group>
            </div>

            ${this._loading
              ? html`<div class="loading">Loading plans…</div>`
              : null}
            ${this._error
              ? html`<div class="error">${this._error}</div>`
              : null}
            ${!this._loading && !this._error
              ? html`
                  <div class="plans-grid">
                    ${this._plans.map(
                      (plan) => html`
                        <div
                          class="plan-card ${plan.id === 'ultra'
                            ? 'popular'
                            : ''}"
                        >
                          ${plan.id === 'ultra'
                            ? html`<div class="badge">Most popular</div>`
                            : null}
                          ${plan.id === 'enterprise'
                            ? html`<div class="badge alt">Enterprise</div>`
                            : null}

                          <h3 class="plan-name">${plan.name}</h3>
                          <div class="price-wrap">
                            ${this.formatPrice(plan)}
                          </div>

                          <hr class="divider" />

                          <ul class="features">
                            ${this._featureOrder.map((key) =>
                              this.renderFeature(plan.features[key], key)
                            )}
                          </ul>

                          <sl-button
                            class="cta"
                            size="large"
                            variant="default"
                            @click=${() => this._handleSignUp(plan.id)}
                          >
                            ${plan.id === 'enterprise'
                              ? 'Contact Sales'
                              : plan.id === 'free'
                                ? 'Get Free'
                                : `Get ${plan.name}`}
                          </sl-button>
                        </div>
                      `
                    )}
                  </div>
                `
              : null}
          </div>
        </section>
      </main>
      <app-footer></app-footer>
    `;
  }
}
