var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
let BillingToggle = class BillingToggle extends LitElement {
    constructor() {
        super(...arguments);
        this.interval = 'month';
        this.dark = false;
    }
    _handleIntervalChange(newInterval) {
        if (this.interval !== newInterval) {
            this.interval = newInterval;
            this.dispatchEvent(new CustomEvent('interval-change', {
                detail: { value: this.interval },
                bubbles: true,
                composed: true,
            }));
        }
    }
    render() {
        return html `
      <div class="billing-toggle ${this.dark ? 'dark' : ''}">
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
        </sl-button-group>
      </div>
    `;
    }
};
BillingToggle.styles = css `
    .billing-toggle {
      display: flex;
      justify-content: center;
      margin: 1.5rem 0 2rem 0;
    }

    .billing-toggle.dark sl-button[variant='default']::part(base) {
      background-color: transparent;
      border-color: #58a6ff;
      color: #58a6ff;
    }

    .billing-toggle.dark sl-button[variant='default']::part(base):hover {
      background-color: #58a6ff;
      color: white;
    }

    .billing-toggle.dark sl-button[variant='primary']::part(base) {
      background-color: #58a6ff;
      border-color: #58a6ff;
      color: white;
    }

    sl-button-group {
      position: relative;
      --sl-button-group-spacing: 0;
    }
  `;
__decorate([
    property({ type: String, reflect: true })
], BillingToggle.prototype, "interval", void 0);
__decorate([
    property({ type: Boolean, reflect: true })
], BillingToggle.prototype, "dark", void 0);
BillingToggle = __decorate([
    customElement('billing-toggle')
], BillingToggle);
export { BillingToggle };
