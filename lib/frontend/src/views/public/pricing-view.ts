import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { fetchWithAuth, fetchPublic, getFeatures } from '../../api';
import landingStyles from '../../styles/landing.css?inline';
import pricingStyles from '../../styles/pricing-styles.css?inline';
import '../../components/billing-toggle';
import '../../components/pricing-card';

interface Plan {
  id: string;
  name: string;
  price_monthly: number | null;
  price_annually: number | null;
  features: string[];
  badge?: string;
}

@customElement('public-pricing-view')
export class PublicPricingView extends LitElement {
  @state() private _interval: 'month' | 'year' = 'year';
  @state() private _billingEnabled = false;

  // Hardcoded plans - Teams and Enterprise only
  private _plans: Plan[] = [
    {
      id: 'teams',
      name: 'Teams',
      price_monthly: 29,
      price_annually: 290, // ~24/mo when billed annually
      features: [
        '30-day free trial',
        'No credit card required',
        'Email support',
      ],
    },
    {
      id: 'enterprise',
      name: 'Enterprise',
      price_monthly: null,
      price_annually: null,
      features: [
        'Model/provider limits & controls',
        'Comprehensive audit logs',
        'SSO, OIDC, SCIM support',
        'SLA commitments',
        'Dedicated support channels',
        'Custom integrations & flow presets',
        'On-premise deployment options',
        'Priority feature requests',
      ],
    },
  ];

  async connectedCallback() {
    super.connectedCallback();
    await this._checkBillingEnabled();
  }

  private async _checkBillingEnabled() {
    try {
      const features = await getFeatures();
      this._billingEnabled = features.features['billing'] === true;
    } catch (error) {
      console.error('Failed to check billing feature:', error);
      this._billingEnabled = false;
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

    if (planId === 'teams') {
      if (!this._billingEnabled) {
        // No billing, use regular registration
        window.location.href = '/register';
        return;
      }

      // Billing enabled - redirect to Stripe checkout
      try {
        const response = await fetch(
          '/api/v1/billing/create-checkout-session',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              plan_id: 'teams',
              interval: this._interval,
            }),
          }
        );

        if (!response.ok) {
          throw new Error('Failed to create checkout session');
        }

        const result = await response.json();

        if (result.action === 'redirect' && result.url) {
          window.location.href = result.url;
        } else {
          // Fallback to register if no URL
          window.location.href = '/register';
        }
      } catch (error) {
        console.error('Checkout error:', error);
        // Fallback to register on error
        window.location.href = '/register';
      }
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
        display: none; /* Hidden by default on mobile */
        width: 80%;
        margin: 0 auto;
        table-layout: fixed;
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

      .pricing-table th,
      .pricing-table td {
        width: 25%;
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
        text-align: center;
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

      .hero-content .lead {
        margin: 0 auto;
        text-align: center;
      }

      /* Desktop view */
      @media (min-width: 860px) {
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
              .dark=${true}
            ></pricing-card>
          `
        )}
      </div>
    `;
  }

  private _renderTable() {
    const maxFeatures = Math.max(
      ...this._plans.map((p) => (p.features as string[]).length)
    );

    return html`
      <table class="pricing-table">
        <thead>
          <tr>
            ${this._plans.map(
              (plan) =>
                html`<th class="${plan.id === 'teams' ? 'popular' : ''}">
                  <div class="plan-name">${plan.name}</div>
                  ${plan.badge
                    ? html`<div class="badge">${plan.badge}</div>`
                    : ''}
                </th>`
            )}
          </tr>
        </thead>
        <tbody>
          <!-- Price Row -->
          <tr>
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

                const unit = isMonthly ? ' /user/month' : ' /user/year';
                const perMo = !isMonthly ? Math.round(amount / 12) : null;

                priceHtml = html`
                  <div class="price">
                    $${amount}
                    <p style="font-size: 1rem; font-weight: 400;">${unit}</p>
                  </div>
                `;
              }
              return html`<td class="${plan.id === 'teams' ? 'popular' : ''}">
                ${priceHtml}
              </td>`;
            })}
          </tr>

          <!-- Features Rows -->
          ${Array.from({ length: maxFeatures }).map((_, idx) => {
            return html`
              <tr>
                ${this._plans.map((plan) => {
                  const features = plan.features as string[];
                  const feature = features[idx];
                  return html`<td
                    class="${plan.id === 'teams' ? 'popular' : ''}"
                    style="text-align: left; padding-left: 2rem;"
                  >
                    ${feature
                      ? html`<span class="check-mark"
                            ><sl-icon name="check-lg"></sl-icon
                          ></span>
                          ${feature}`
                      : ''}
                  </td>`;
                })}
              </tr>
            `;
          })}

          <!-- Button Row -->
          <tr>
            ${this._plans.map(
              (plan) => html`
                <td class="${plan.id === 'teams' ? 'popular' : ''}">
                  <sl-button
                    class="pricing-button"
                    style="width: 100%;"
                    variant="default"
                    size="large"
                    @click=${() => this._handleSignUp(plan.id)}
                  >
                    ${plan.id === 'enterprise'
                      ? 'Contact Sales'
                      : 'Start Free Trial'}
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
                Start your 30-day free trial today. No credit card required.
                After your trial, choose the plan that fits your team.
              </p>
            </div>
          </div>

          <div class="section-container">
            <billing-toggle
              .dark=${true}
              .interval=${this._interval}
              @interval-change=${(e: CustomEvent) =>
                (this._interval = e.detail.value)}
            ></billing-toggle>

            ${this._renderCards()} ${this._renderTable()}
          </div>
        </section>
      </main>
      <app-footer></app-footer>
    `;
  }
}
