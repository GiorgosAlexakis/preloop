import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface Plan {
  id: string;
  name: string;
  price_monthly: number | null;
  price_annually: number | null;
  features: { [key: string]: any };
}

@customElement('pricing-card')
export class PricingCard extends LitElement {
  @property({ type: Object }) plan!: Plan;
  @property({ type: String }) interval: 'month' | 'year' = 'month';
  @property({ type: Array }) featureOrder: string[] = [];
  @property({ type: Object }) featureLabels: Record<string, string> = {};

  private formatPrice(plan: Plan) {
    if (plan.id === 'enterprise') {
      return html`<div class="price-main">Custom</div>`;
    }
    const isMonthly = this.interval === 'month';
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

  private _formatNumber(num: number): string {
    if (num === -1) return 'Unlimited';
    if (num < 1000) return num.toString();
    return new Intl.NumberFormat('en-US', {
      notation: 'compact',
      compactDisplay: 'short',
    }).format(num);
  }

  private renderFeature(value: any, key: string) {
    const label = this.featureLabels[key] ?? key.replace(/_/g, ' ');
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
      displayValue = this._formatNumber(value);
    }

    return html`
      <li class=${included ? 'feature included' : 'feature excluded'}>
        <span class="feat-icon"
          >${included
            ? html`<sl-icon name="check-lg"></sl-icon>`
            : html`<sl-icon name="x-lg"></sl-icon>`}</span
        >
        <span class="feat-text">
          ${label}${displayValue
            ? html`<span class="feat-value">: ${displayValue}</span>`
            : ''}
        </span>
      </li>
    `;
  }

  private _handleSignUp() {
    this.dispatchEvent(
      new CustomEvent('signup-requested', {
        detail: { planId: this.plan.id, interval: this.interval },
        bubbles: true,
        composed: true,
      })
    );
  }

  static styles = css`
    :host {
      display: flex;
    }
    .plan-card {
      position: relative;
      display: flex;
      flex-direction: column;
      border: 1px solid var(--sl-color-neutral-300);
      border-radius: 20px;
      padding: 1.5rem;
      width: 100%;
    }

    .plan-card.popular {
      border: none;
      background: linear-gradient(
        45deg,
        hsl(220, 60%, 40%),
        hsl(260, 65%, 38%)
      );
      color: white;
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

    .plan-card.popular .price-sub {
      color: var(--sl-color-neutral-700);
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
  `;

  render() {
    return html`
      <div class="plan-card ${this.plan.id === 'ultra' ? 'popular' : ''}">
        ${this.plan.id === 'ultra'
          ? html`<div class="badge">Most popular</div>`
          : null}
        ${this.plan.id === 'enterprise'
          ? html`<div class="badge alt">Enterprise</div>`
          : null}

        <h3 class="plan-name">${this.plan.name}</h3>
        <div class="price-wrap">${this.formatPrice(this.plan)}</div>

        <hr class="divider" />

        <ul class="features">
          ${this.featureOrder.map((key) =>
            this.renderFeature(this.plan.features[key], key)
          )}
        </ul>

        <sl-button
          class="cta"
          size="large"
          variant="default"
          @click=${this._handleSignUp}
        >
          ${this.plan.id === 'enterprise'
            ? 'Contact Sales'
            : this.plan.id === 'free'
              ? 'Get Free'
              : `Get ${this.plan.name}`}
        </sl-button>
      </div>
    `;
  }
}
