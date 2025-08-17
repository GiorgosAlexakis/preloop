import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { fetchWithAuth, fetchPublic } from '../../api';
import landingStyles from '../../styles/landing.css?inline';
import pricingStyles from '../../styles/pricing-styles.css?inline';
import '../../components/billing-toggle';
import '../../components/pricing-card';

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

  private _handleSignUpRequest(e: CustomEvent) {
    this._handleSignUp(e.detail.planId);
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
    unsafeCSS(pricingStyles),
    unsafeCSS(landingStyles),
    css`
      .loading,
      .error {
        text-align: center;
        margin: 2rem 0;
      }
      .error {
        color: var(--sl-color-danger-600);
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
            <billing-toggle
              .interval=${this._interval}
              @interval-change=${(e: CustomEvent) =>
                (this._interval = e.detail.value)}
            ></billing-toggle>

            ${this._loading
              ? html`<div class="loading">Loading plans…</div>`
              : null}
            ${this._error
              ? html`<div class="error">${this._error}</div>`
              : null}
            ${!this._loading && !this._error
              ? html`
                  <div
                    class="plans-grid"
                    @signup-requested=${this._handleSignUpRequest}
                  >
                    ${this._plans.map(
                      (plan) => html`
                        <pricing-card
                          .plan=${plan}
                          .interval=${this._interval}
                          .featureOrder=${this._featureOrder}
                          .featureLabels=${this._featureLabels}
                        ></pricing-card>
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
