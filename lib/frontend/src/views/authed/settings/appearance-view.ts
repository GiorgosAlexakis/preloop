import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio-button/radio-button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import { Theme, DEFAULT_THEME } from '../../../theme';

type Theme = 'light' | 'dark' | 'system';

@customElement('appearance-view')
export class AppearanceView extends LitElement {
  @state()
  private selectedTheme: Theme = DEFAULT_THEME;

  static styles = css`
    :host {
      display: block;
    }
    sl-card {
      max-width: 600px;
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
  `;

  connectedCallback() {
    super.connectedCallback();
    const storedTheme = localStorage.getItem('theme') as Theme | null;
    this.selectedTheme = storedTheme || DEFAULT_THEME;
  }

  private handleThemeChange(event: CustomEvent) {
    const newTheme = event.target.value as Theme;
    this.selectedTheme = newTheme;
    localStorage.setItem('theme', newTheme);
    window.dispatchEvent(
      new CustomEvent('theme-change', { detail: { theme: newTheme } })
    );
  }

  render() {
    return html`
      <div class="container">
        <h1 class="title">Appearance</h1>
        <p class="description">
          Customize the look and feel of the application.
        </p>
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
    `;
  }
}
