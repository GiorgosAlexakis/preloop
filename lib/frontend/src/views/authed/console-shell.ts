import { LitElement, html, css } from 'lit';
import { customElement, query } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';
@customElement('console-shell')
export class ConsoleShell extends LitElement {

  static styles = css`
    :host {
      display: block;
      height: 100vh;
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

    a {
      text-decoration: none;
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
    }

    sl-details::part(base) {
      width: 100%;
      border-width: 0;
      background-color: var(--sl-color-neutral-100);
    }

    sl-menu-item {
      padding: 0.25em;
    }

    sl-details {
      padding-left: 1em;
    }
  `;

  switchToOldUI() {
    // Clear the cookie
    document.cookie =
      'ui_version=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    // Reload the page
    window.location.reload();
  }

  render() {
    return html`
      <div class="console-container">
        <div class="sidebar">
          <div class="logo">
            <img src="/static/images/logo_dark.png" alt="SpaceBridge MCP" />
          </div>
          <sl-menu>
            <a href="/console">
              <sl-menu-item>
                <sl-icon name="house" slot="prefix"></sl-icon>
                Dashboard
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
                <sl-icon name="file-text" style="padding-right: 6px;"></sl-icon> Issues
              </span>
              <sl-menu>
                <a href="/console/issues/duplicates">
                  <sl-menu-item>Duplicates</sl-menu-item>
                </a>
              </sl-menu>
            </sl-details>

            <sl-details>
              <span slot="summary">
                <sl-icon name="gear" style="padding-right: 6px;"></sl-icon> Settings
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
                  <sl-menu-item>LLM Models</sl-menu-item>
                </a>
              </sl-menu>
            </sl-details>
          </sl-menu>
        </div>

        <div class="main-content">
          <slot></slot>
        </div>
      </div>
    `;
  }
}
