import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, query } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';
import consoleStyles from '../../styles/console-styles.css?inline';

// static styles = [formStyles, css`
//     h2 {}

//     `];

@customElement('console-shell')
export class ConsoleShell extends LitElement {
  static styles = [
    unsafeCSS(consoleStyles),
    css`
      :host {
        display: block;
        height: 100vh;
      }

      a:hover {
        text-decoration: none;
      }

      .console-container {
        display: flex;
        flex-direction: row;
        height: 100%;
      }

      .sidebar {
        width: 250px;
        flex-shrink: 0;
        display: flex;
        flex-direction: column;
      }

      .sign-out-menu {
        flex-grow: 0;
      }

      .sign-out-menu sl-menu-item::part(base) {
        background-color: var(--sl-color-neutral-100);
        color: var(--sl-color-primary-500);
      }

      .sign-out-menu sl-menu-item:hover::part(base) {
        background-color: var(--sl-color-neutral-100);
        color: var(--sl-color-primary-700);
      }

      .main-content {
        flex-grow: 1;
        overflow-y: auto;
        padding: 2rem;
      }

      .logo {
        text-align: center;
        padding: 1rem;
        background-color: var(--sl-color-neutral-100);
      }

      .logo img {
        max-width: 150px;
      }

      sl-menu {
        flex-grow: 1;
        border-width: 0;
        background-color: var(--sl-color-neutral-100);
        padding: 0;
      }

      sl-details::part(base) {
        width: 100%;
        border-width: 0;
        background-color: var(--sl-color-neutral-100);
      }

      sl-details::part(content) {
        padding-top: 0;
        padding-left: 1.5rem;
      }

      sl-menu-item {
        padding: 0.25em;
      }

      sl-details {
        padding-left: 1em;
      }
    `,
  ];

  switchToOldUI() {
    // Clear the cookie
    document.cookie =
      'ui_version=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    // Reload the page
    window.location.reload();
  }

  async signOut() {
    // The primary sign-out action is to remove the tokens from local storage.
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');

    // Dispatch an event to let other parts of the app know the user has signed out.
    window.dispatchEvent(
      new CustomEvent('auth-change', { bubbles: true, composed: true })
    );

    // Redirect to the landing page.
    window.location.href = '/';

    // We can also make a request to the server's /logout endpoint.
    // This can be useful for server-side session cleanup or logging.
    // We'll do this in the background and not let it block the redirect.
    fetch('/logout', { method: 'GET' }).catch((error) => {
      console.error('Logout request to server failed:', error);
    });
  }

  render() {
    return html`
      <div class="console-container">
        <div class="sidebar">
          <div class="logo">
            <img src="/images/logo_dark.png" alt="SpaceBridge.io" />
          </div>
          <sl-menu style="font-size: 16px;">
            <a href="/console">
              <sl-menu-item>
                <sl-icon name="house" slot="prefix"></sl-icon>
                Overview
              </sl-menu-item>
            </a>
            <a href="/console/trackers">
              <sl-menu-item>
                <sl-icon name="database" slot="prefix"></sl-icon>
                Trackers
              </sl-menu-item>
            </a>

            <sl-details>
              <span slot="summary">
                <sl-icon name="kanban" style="padding-right: 6px;"></sl-icon>
                Issues
              </span>
              <sl-menu>
                <a href="/console/issues">
                  <sl-menu-item>Similar Issues</sl-menu-item>
                </a>
              </sl-menu>
            </sl-details>

            <sl-details>
              <span slot="summary">
                <sl-icon name="gear" style="padding-right: 6px;"></sl-icon>
                Settings
              </span>
              <sl-menu>
                <a href="/console/settings/profile">
                  <sl-menu-item>Profile</sl-menu-item>
                </a>
                <a href="/console/settings/security">
                  <sl-menu-item>Security</sl-menu-item>
                </a>
                <a href="/console/settings/api-keys">
                  <sl-menu-item>API Keys</sl-menu-item>
                </a>
                <a href="/console/settings/llm-models">
                  <sl-menu-item>Models</sl-menu-item>
                </a>
                <a href="/console/settings/appearance">
                  <sl-menu-item>Appearance</sl-menu-item>
                </a>
              </sl-menu>
            </sl-details>
          </sl-menu>

          <sl-menu class="sign-out-menu">
            <sl-menu-item @click=${this.signOut}>
              <sl-icon name="box-arrow-right" slot="prefix"></sl-icon>
              Sign Out
            </sl-menu-item>
          </sl-menu>
        </div>

        <div class="main-content">
          <slot></slot>
        </div>
      </div>
    `;
  }
}
