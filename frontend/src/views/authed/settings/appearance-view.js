var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio-button/radio-button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import consoleStyles from '../../../styles/console-styles.css?inline';
import { DEFAULT_THEME } from '../../../theme';
let AppearanceView = class AppearanceView extends LitElement {
    constructor() {
        super(...arguments);
        this.selectedTheme = DEFAULT_THEME;
    }
    connectedCallback() {
        super.connectedCallback();
        const storedTheme = localStorage.getItem('theme');
        this.selectedTheme = storedTheme || DEFAULT_THEME;
    }
    handleThemeChange(event) {
        const newTheme = event.target.value;
        this.selectedTheme = newTheme;
        localStorage.setItem('theme', newTheme);
        window.dispatchEvent(new CustomEvent('theme-change', { detail: { theme: newTheme } }));
    }
    render() {
        return html `
      <view-header headerText="Appearance" width="narrow"> </view-header>
      <div class="column-layout narrow">
        <div class="main-column">
          <sl-card>
            <sl-radio-group
              label="Theme"
              value=${this.selectedTheme}
              @sl-change=${this.handleThemeChange}
            >
              <sl-radio-button value="light">Light</sl-radio-button>
              <sl-radio-button value="dark">Dark</sl-radio-button>
              <sl-radio-button value="system">System</sl-radio-button>
            </sl-radio-group>
          </sl-card>
        </div>
        <div class="side-column"></div>
      </div>
    `;
    }
};
AppearanceView.styles = [
    unsafeCSS(consoleStyles),
    css `
      :host {
        display: block;
      }
      sl-card {
        width: 100%;
      }
      h1 {
        font-size: var(--sl-font-size-x-large);
        font-weight: var(--sl-font-weight-bold);
        margin-bottom: var(--sl-spacing-large);
      }
      .description {
        margin-bottom: var(--sl-spacing-large);
        color: var(--sl-color-neutral-600);
      }
      sl-radio-group::part(label) {
        font-size: var(--sl-font-size-medium);
        font-weight: var(--sl-font-weight-semibold);
        margin-bottom: var(--sl-spacing-medium);
      }
    `,
];
__decorate([
    state()
], AppearanceView.prototype, "selectedTheme", void 0);
AppearanceView = __decorate([
    customElement('appearance-view')
], AppearanceView);
export { AppearanceView };
