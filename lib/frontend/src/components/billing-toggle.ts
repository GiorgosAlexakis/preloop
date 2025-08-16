import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('billing-toggle')
export class BillingToggle extends LitElement {
  @property({ type: String, reflect: true })
  interval: 'month' | 'year' = 'month';

  private _handleIntervalChange(newInterval: 'month' | 'year') {
    if (this.interval !== newInterval) {
      this.interval = newInterval;
      this.dispatchEvent(
        new CustomEvent('interval-change', {
          detail: { value: this.interval },
          bubbles: true,
          composed: true,
        })
      );
    }
  }

  static styles = css`
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
    sl-button-group {
      --sl-button-group-spacing: 0;
    }
  `;

  render() {
    return html`
      <div class="billing-toggle">
        <sl-button-group>
          <sl-button
            variant=${this.interval === 'month' ? 'primary' : 'default'}
            @click=${() => this._handleIntervalChange('month')}
          >
            Monthly
          </sl-button>
          <sl-button
            variant=${this.interval === 'year' ? 'primary' : 'default'}
            @click=${() => this._handleIntervalChange('year')}
          >
            Yearly (Best Value)
          </sl-button>
        </sl-button-group>
      </div>
    `;
  }
}
