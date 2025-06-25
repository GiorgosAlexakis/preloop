import { LitElement, html, css } from 'lit';
import { customElement, query } from 'lit/decorators.js';
import type SlDrawer from '@shoelace-style/shoelace/dist/components/drawer/drawer.js';
import '@shoelace-style/shoelace/dist/components/drawer/drawer.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';

@customElement('console-shell')
export class ConsoleShell extends LitElement {
  @query('sl-drawer') drawer!: SlDrawer;

  static styles = css`
    :host {
      display: block;
      height: 100vh;
    }
    .main-content {
      height: 100%;
      overflow: auto;
    }
    sl-drawer::part(body) {
      padding: 0;
    }
    sl-drawer {
      --size: 280px;
    }
    .logo {
      display: flex;
      align-items: center;
      padding: 0 1rem;
      height: 64px;
      box-sizing: border-box;
    }
    .logo img {
      height: 24px;
    }
    h1 {
      font-size: var(--lumo-font-size-l);
      margin: 0;
    }
    a {
      text-decoration: none;
      color: inherit;
    }
    sl-menu-item {
      color: var(--sl-color-neutral-600);
    }
    sl-details::part(base) {
      border: none;
    }
    sl-details::part(header) {
      padding: var(--sl-spacing-x-small) var(--sl-spacing-medium);
      color: var(--sl-color-neutral-600);
    }
    sl-details [slot='summary'] sl-icon {
      margin-right: var(--sl-spacing-small);
    }
    sl-details sl-menu {
      padding-left: var(--sl-spacing-medium);
    }
  `;

  toggleDrawer() {
    this.drawer.open = !this.drawer.open;
  }

  switchToOldUI() {
    // Clear the cookie
    document.cookie =
      'ui_version=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
    // Reload the page
    window.location.reload();
  }

  render() {
    return html`
      <sl-drawer open class="drawer-navigation" no-header>
        <div class="logo">
          <img src="/static/images/logo_dark.png" alt="SpaceBridge MCP" />
        </div>
        <hr class="my-2" />
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
              <sl-icon name="file-text"></sl-icon> Issues
            </span>
            <sl-menu>
              <a href="/console/issues">
                <sl-menu-item>Overview</sl-menu-item>
              </a>
              <a href="/console/issues/duplicates">
                <sl-menu-item>Duplicates</sl-menu-item>
              </a>
            </sl-menu>
          </sl-details>

          <sl-details>
            <span slot="summary">
              <sl-icon name="gear"></sl-icon> Settings
            </span>
            <sl-menu>
              <a href="/console/settings">
                <sl-menu-item>Overview</sl-menu-item>
              </a>
              <a href="/console/settings/account">
                <sl-menu-item>Account</sl-menu-item>
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
      </sl-drawer>

      <div class="main-content">
        <app-header
          .showDrawerToggle=${true}
          @toggle-drawer=${this.toggleDrawer}
        ></app-header>
        <div class="p-4">
          <slot></slot>
        </div>
      </div>
    `;
  }
}
