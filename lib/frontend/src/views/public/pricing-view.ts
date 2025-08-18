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

      .pricing-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        border-radius: 16px;
        background-color: #21262f; /* Dark background from landing page */
        color: #e6edf3; /* Light text color from landing page */
        border: 1px solid #161b22; /* Subtle border from landing page */
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
      }

      .pricing-table th,
      .pricing-table td {
        font-size: 1rem;
        padding: 1rem;
        text-align: center;
        vertical-align: middle;
      }

      .pricing-table tr:last-child td {
        border-bottom: none; /* Remove border for the last row */
      }

      .pricing-table th {
        padding: 2rem 0 0.5rem 0;
        font-size: 1.1rem;
        font-weight: 600;
        border-bottom: 2px solid #58a6ff; /* Header underline inspired by landing page */
      }

      .pricing-table td:first-child {
        text-align: left;
        font-weight: 500;
      }

      .pricing-table th {
        font-weight: 600;
        font-size: 1.1rem;
      }

      .pricing-table .price {
        font-size: 2.4rem;
        font-weight: 700;
      }

      /* Popular column styles */
      .popular {
        position: relative;
        background: linear-gradient(
          90deg,
          hsl(220, 60%, 40%),
          hsl(260, 65%, 38%)
        );
        color: white;
      }

      .pricing-table th.popular {
        border-bottom-color: #a777ff;
      }

      /* Rounded corners for table cells */
      .pricing-table th:first-child {
        border-top-left-radius: 12px;
      }

      .pricing-table th:last-child {
        border-top-right-radius: 12px;
      }

      .pricing-table tr:last-child td:first-child {
        border-bottom-left-radius: 12px;
      }

      .pricing-table tr:last-child td:last-child {
        border-bottom-right-radius: 12px;
      }

      .badge {
        position: absolute;
        top: -15px;
        left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(45deg, #a777ff, #f777ff);
        color: white;
        padding: 0.4rem 1rem;
        border-radius: 16px;
        font-size: 0.9rem;
        font-weight: 700;
        white-space: nowrap;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        z-index: 1;
      }

      /* Default outlined button style */
      .pricing-button::part(base) {
        background-color: transparent;
        border: 1px solid #58a6ff;
        color: #58a6ff;
        font-size: 1rem;
        font-weight: 600;
        transition: all 0.2s ease-in-out;
      }

      .pricing-button::part(base):hover {
        background-color: #58a6ff;
        color: white;
      }

      /* Solid, gradient button for the popular plan */
      .popular .pricing-button::part(base) {
        background: linear-gradient(45deg, #a777ff, #f777ff);
        border: none;
        color: white;
        font-weight: 600;
      }

      .popular .pricing-button::part(base):hover {
        filter: brightness(1.1);
      }

      .check-mark sl-icon {
        color: #58a6ff; /* Icon color from landing page */
        font-size: 1.2rem;
      }

      .popular .check-mark sl-icon {
        color: white;
      }

      /* Desktop view */
      @media (min-width: 992px) {
        .plans-grid {
          display: none;
        }
        .pricing-table {
          display: table;
        }
      }
    `,
  ];

  private _renderCards() {
    return html`
      <div class="plans-grid" @signup-requested=${this._handleSignUpRequest}>
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
    `;
  }

  private _renderTable() {
    return html`
      <table class="pricing-table">
        <thead>
          <tr>
            <th></th>
            ${this._plans.map(
              (plan) =>
                html`<th class="${plan.id === 'ultra' ? 'popular' : ''}">
                  <div class="plan-name">${plan.name}</div>
                  ${plan.id === 'ultra'
                    ? html`<div class="badge">Most Popular</div>`
                    : ''}
                </th>`
            )}
          </tr>
        </thead>
        <tbody>
          <!-- Price Row -->
          <tr>
            <td>Price</td>
            ${this._plans.map((plan) => {
              let priceHtml;
              if (plan.id === 'enterprise') {
                priceHtml = html`<div class="price">Custom</div>`;
              } else if (
                plan.price_monthly !== null &&
                plan.price_annually !== null
              ) {
                const isMonthly = this._interval === 'month';
                const amount = isMonthly
                  ? plan.price_monthly
                  : plan.price_annually;
                const unit = isMonthly ? '/mo' : '/yr';
                const perMo = !isMonthly
                  ? Math.round(plan.price_annually / 12)
                  : null;

                priceHtml = html`
                  <div class="price">
                    $${amount}<span style="font-size: 1rem; font-weight: 400;"
                      >${unit}</span
                    >
                  </div>
                  ${perMo
                    ? html`<div class="price-sub">billed annually</div>`
                    : ''}
                `;
              } else {
                priceHtml = html`<div class="price">Free</div>`;
              }
              return html`<td class="${plan.id === 'ultra' ? 'popular' : ''}">
                ${priceHtml}
              </td>`;
            })}
          </tr>

          <!-- Features Rows -->
          ${this._featureOrder.map((featureKey) => {
            return html`
              <tr>
                <td class="feature-label">
                  ${this._featureLabels[featureKey]}
                </td>
                ${this._plans.map((plan) => {
                  const feature = plan.features[featureKey];
                  let value = '';
                  if (typeof feature === 'boolean') {
                    value = feature
                      ? html`<span class="check-mark"
                          ><sl-icon name="check-lg"></sl-icon
                        ></span>`
                      : '—';
                  } else if (feature) {
                    value =
                      feature === -1 ? 'Unlimited' : feature.toLocaleString();
                  } else {
                    value = '—';
                  }
                  return html`<td
                    class="${plan.id === 'ultra' ? 'popular' : ''}"
                  >
                    ${value}
                  </td>`;
                })}
              </tr>
            `;
          })}

          <!-- Button Row -->
          <tr>
            <td></td>
            ${this._plans.map(
              (plan) => html`
                <td class="${plan.id === 'ultra' ? 'popular' : ''}">
                  <sl-button
                    class="pricing-button"
                    style="width: 100%;"
                    variant="default"
                    @click=${() => this._handleSignUp(plan.id)}
                  >
                    ${plan.id === 'enterprise'
                      ? 'Contact Sales'
                      : plan.id === 'free'
                        ? 'Get Free'
                        : `Get ${plan.name}`}
                  </sl-button>
                </td>
              `
            )}
          </tr>
        </tbody>
      </table>
    `;
  }

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
              ? html` ${this._renderCards()} ${this._renderTable()} `
              : null}
          </div>
        </section>
      </main>
      <app-footer></app-footer>
    `;
  }
}
