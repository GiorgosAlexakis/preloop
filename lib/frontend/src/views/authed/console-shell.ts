import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import '@vaadin/app-layout';
import '@vaadin/app-layout/vaadin-drawer-toggle.js';
import '@vaadin/side-nav';
import '@vaadin/icon';
import '@vaadin/icons';

@customElement('console-shell')
export class ConsoleShell extends LitElement {
  static styles = css`
    :host {
      display: block;
      height: 100vh;
    }
    vaadin-app-layout {
      height: 100%;
    }
    .logo {
      display: flex;
      align-items: center;
      padding: 0 1rem;
      height: var(--lumo-size-xl);
      box-sizing: border-box;
    }
    .logo img {
      height: 24px;
    }
    h1 {
      font-size: var(--lumo-font-size-l);
      margin: 0;
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
      <vaadin-app-layout>
        <app-header slot="navbar" .showDrawerToggle=${true}></app-header>

        <vaadin-side-nav slot="drawer">
          <div class="logo">
            <img src="/static/images/logo_dark.png" alt="SpaceBridge MCP" />
          </div>
          <hr class="my-2" />
          <vaadin-side-nav-item path="/console">
            <vaadin-icon icon="vaadin:home" slot="prefix"></vaadin-icon>
            Dashboard
          </vaadin-side-nav-item>
          <vaadin-side-nav-item path="/console/trackers">
            <vaadin-icon icon="vaadin:database" slot="prefix"></vaadin-icon>
            Trackers
          </vaadin-side-nav-item>
          <vaadin-side-nav-item>
            <vaadin-icon icon="vaadin:file-text" slot="prefix"></vaadin-icon>
            Issues
            <vaadin-side-nav-item
              path="/console/issues"
              slot="children"
            >
              Overview
            </vaadin-side-nav-item>
            <vaadin-side-nav-item
              path="/console/issues/duplicates"
              slot="children"
            >
              Duplicates
            </vaadin-side-nav-item>
          </vaadin-side-nav-item>
          <vaadin-side-nav-item>
            <vaadin-icon icon="vaadin:cog" slot="prefix"></vaadin-icon>
            Settings
            <vaadin-side-nav-item
              path="/console/settings"
              slot="children"
            >
              Overview
            </vaadin-side-nav-item>
            <vaadin-side-nav-item
              path="/console/settings/account"
              slot="children"
            >
              Account
            </vaadin-side-nav-item>
            <vaadin-side-nav-item
              path="/console/settings/api-keys"
              slot="children"
            >
              API Keys
            </vaadin-side-nav-item>
            <vaadin-side-nav-item
              path="/console/settings/llm-models"
              slot="children"
            >
              LLM Models
            </vaadin-side-nav-item>
          </vaadin-side-nav-item>
        </vaadin-side-nav>

        <div class="p-4">
          <slot></slot>
        </div>
      </vaadin-app-layout>
    `;
  }
}
