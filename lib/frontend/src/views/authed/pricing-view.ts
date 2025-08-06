import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { fetchPlans, getCurrentSubscription } from '../../api';

@customElement('pricing-view')
export class PricingView extends LitElement {
  @state()
  private _plans: any[] = [];

  @state()
  private _subscription: any = null;

  async connectedCallback() {
    super.connectedCallback();
    this._plans = await fetchPlans();
    this._subscription = await getCurrentSubscription();
  }

  static styles = css`
    .pricing-container {
      display: flex;
      justify-content: center;
      gap: 2rem;
      padding: 2rem;
    }
    .plan {
      border: 1px solid #ccc;
      border-radius: 8px;
      padding: 2rem;
      width: 300px;
      display: flex;
      flex-direction: column;
    }
    .plan h2 {
      margin-top: 0;
    }
    .plan .price {
      font-size: 2rem;
      font-weight: bold;
    }
    .plan ul {
      list-style: none;
      padding: 0;
      flex-grow: 1;
    }
    .plan li {
      margin-bottom: 0.5rem;
    }
  `;

  render() {
    return html`
      <h1>Pricing</h1>
      <div class="pricing-container">
        ${this._plans.map(
          (plan) => html`
            <div class="plan">
              <h2>${plan.name}</h2>
              <p class="price">$${plan.price_monthly}/mo</p>
              <ul>
                <li>
                  ${plan.features.api_calls_monthly.toLocaleString()} API Calls
                </li>
                <li>
                  ${plan.features.ai_calls_monthly.toLocaleString()} AI Model
                  Calls
                </li>
                <li>
                  ${plan.features.issues_ingested_monthly.toLocaleString()}
                  Issues Ingested
                </li>
                <li>
                  ${plan.features.custom_ai_models_enabled
                    ? 'Custom AI Models'
                    : 'No Custom AI Models'}
                </li>
                <li>
                  ${plan.features.custom_compliance_metrics_enabled
                    ? 'Custom Compliance Metrics'
                    : 'No Custom Compliance Metrics'}
                </li>
              </ul>
              <button ?disabled=${this._subscription?.plan_id === plan.id}>
                ${this._subscription?.plan_id === plan.id
                  ? 'Current Plan'
                  : 'Choose Plan'}
              </button>
            </div>
          `
        )}
      </div>
    `;
  }
}
