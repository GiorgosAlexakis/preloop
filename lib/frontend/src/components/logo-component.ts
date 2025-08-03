import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Theme } from '../theme';

@customElement('logo-component')
export class LogoComponent extends LitElement {
  @property({ type: String })
  alt = 'SpaceBridge.io';

  @state()
  private theme: Theme = 'dark';

  static styles = css`
    :host {
      display: block;
      height: 35px;
    }

    img {
      height: 100%;
    }
  `;

  connectedCallback() {
    super.connectedCallback();
    this.setThemeFromClass();
    window.addEventListener('theme-change', this.handleThemeChange);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('theme-change', this.handleThemeChange);
  }

  private handleThemeChange = (event: CustomEvent) => {
    this.setTheme(event.detail.theme);
  };

  private setTheme(theme: Theme) {
    if (theme === 'system') {
      const prefersDark = window.matchMedia(
        '(prefers-color-scheme: dark)'
      ).matches;
      this.theme = prefersDark ? 'dark' : 'light';
    } else {
      this.theme = theme;
    }
  }

  private setThemeFromClass() {
    if (document.documentElement.classList.contains('sl-theme-dark')) {
      this.theme = 'dark';
    } else if (document.documentElement.classList.contains('sl-theme-light')) {
      this.theme = 'light';
    } else {
      // Fallback to system preference if no class is set
      this.setTheme('system');
    }
  }

  render() {
    const logoSrc =
      this.theme === 'dark'
        ? '/images/logo_dark.png'
        : '/images/logo_light.png';
    return html`<img src="${logoSrc}" alt=${this.alt} />`;
  }
}
