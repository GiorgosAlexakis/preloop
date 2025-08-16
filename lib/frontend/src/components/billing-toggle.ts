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
      justify-content: center;
      margin: 1.5rem 0 2rem 0;
    }

    sl-button-group {
      position: relative;
      --sl-button-group-spacing: 0;
    }

    .hint {
      position: absolute;
      left: 100%;
      top: 50%;
      transform: translateY(-50%);
      margin-left: 0.75rem;

      /* New gradient border style */
      border: 1px solid transparent;
      background:
        linear-gradient(#222244, #222244) padding-box,
        linear-gradient(45deg, #3b82f6, #8b5cf6) border-box;
      color: #e5e7eb; /* Light gray for soft text */

      font-size: 0.85rem;
      font-weight: 400; /* Lighter font weight */
      padding: 0.25rem 0.6rem;
      border-radius: 999px;
      line-height: 1;
      white-space: nowrap;
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
            Yearly
          </sl-button>
          <span class="hint">Best Value</span>
        </sl-button-group>
      </div>
    `;
  }
}
