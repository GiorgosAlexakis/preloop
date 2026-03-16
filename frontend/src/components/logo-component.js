var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { getBrandConfig } from '../brand-config';
let LogoComponent = class LogoComponent extends LitElement {
    constructor() {
        super(...arguments);
        this.alt = getBrandConfig().name;
        this.theme = 'dark';
        this.handleThemeChange = (event) => {
            this.setTheme(event.detail.theme);
        };
    }
    connectedCallback() {
        super.connectedCallback();
        if (this.themeOverride) {
            this.setTheme(this.themeOverride);
        }
        else {
            this.setThemeFromClass();
            window.addEventListener('theme-change', this.handleThemeChange);
        }
    }
    disconnectedCallback() {
        super.disconnectedCallback();
        window.removeEventListener('theme-change', this.handleThemeChange);
    }
    setTheme(theme) {
        if (theme === 'system') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.theme = prefersDark ? 'dark' : 'light';
        }
        else if (theme === 'dark' || theme === 'light') {
            this.theme = theme;
        }
    }
    setThemeFromClass() {
        if (document.documentElement.classList.contains('sl-theme-dark')) {
            this.theme = 'dark';
        }
        else if (document.documentElement.classList.contains('sl-theme-light')) {
            this.theme = 'light';
        }
        else {
            // Fallback to system preference if no class is set
            this.setTheme('system');
        }
    }
    render() {
        const brandConfig = getBrandConfig();
        const logoSrc = this.theme === 'dark'
            ? brandConfig.branding.logo_dark
            : brandConfig.branding.logo_light;
        return html `<img src="${logoSrc}" alt=${this.alt} />`;
    }
};
LogoComponent.styles = css `
    :host {
      display: block;
      height: 35px;
    }

    img {
      height: 100%;
    }
  `;
__decorate([
    property({ type: String })
], LogoComponent.prototype, "alt", void 0);
__decorate([
    property({ type: String, attribute: 'override-theme' })
], LogoComponent.prototype, "themeOverride", void 0);
__decorate([
    state()
], LogoComponent.prototype, "theme", void 0);
LogoComponent = __decorate([
    customElement('logo-component')
], LogoComponent);
export { LogoComponent };
