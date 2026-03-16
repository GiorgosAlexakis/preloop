var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/button-group/button-group.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';
import { DEFAULT_THEME } from '../theme';
let ThemeSwitcher = class ThemeSwitcher extends LitElement {
    constructor() {
        super(...arguments);
        this.selectedTheme = DEFAULT_THEME;
    }
    connectedCallback() {
        super.connectedCallback();
        const storedTheme = localStorage.getItem('theme');
        this.selectedTheme = storedTheme || DEFAULT_THEME;
    }
    handleThemeChange(newTheme) {
        this.selectedTheme = newTheme;
        localStorage.setItem('theme', newTheme);
        window.dispatchEvent(new CustomEvent('theme-change', { detail: { theme: newTheme } }));
    }
    render() {
        return html `
      <sl-button-group label="Theme">
        <sl-button
          size="small"
          variant="${this.selectedTheme === 'light' ? 'primary' : 'default'}"
          @click=${() => this.handleThemeChange('light')}
        >
          <sl-icon name="sun" label="Light theme"></sl-icon>
        </sl-button>
        <sl-button
          size="small"
          variant="${this.selectedTheme === 'dark' ? 'primary' : 'default'}"
          @click=${() => this.handleThemeChange('dark')}
        >
          <sl-icon name="moon" label="Dark theme"></sl-icon>
        </sl-button>
        <sl-button
          size="small"
          variant="${this.selectedTheme === 'system' ? 'primary' : 'default'}"
          @click=${() => this.handleThemeChange('system')}
        >
          <sl-icon name="display" label="System theme"></sl-icon>
        </sl-button>
      </sl-button-group>
    `;
    }
};
ThemeSwitcher.styles = css ``;
__decorate([
    state()
], ThemeSwitcher.prototype, "selectedTheme", void 0);
ThemeSwitcher = __decorate([
    customElement('theme-switcher')
], ThemeSwitcher);
export { ThemeSwitcher };
