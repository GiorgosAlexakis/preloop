import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, query, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '../../components/logo-component';
import '../../components/global-notice';
import '../../components/console-header';
import consoleStyles from '../../styles/console-styles.css?inline';
import { getFeatures, type FeaturesResponse } from '../../api';

// static styles = [formStyles, css`
//     h2 {}

//     `];

@customElement('console-shell')
export class ConsoleShell extends LitElement {
  @query('#upgrade-modal')
  private _upgradeModal!: HTMLElement;

  @state()
  private features: FeaturesResponse['features'] = {};

  @state()
  private hasTrackers = false;

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

      .main-view {
        flex-grow: 1;
        display: grid;
        grid-template-rows: auto 1fr; /* Header row, Content row */
        overflow-y: hidden;
      }

      .main-content {
        overflow-y: auto;
        padding: 1rem 2rem 2rem 2rem;
      }

      .logo {
        margin-left: 2px;
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

  async connectedCallback() {
    super.connectedCallback();
    window.addEventListener('show-upgrade-modal', () => {
      (this._upgradeModal as any).show();
    });

    // Fetch enabled features
    try {
      const response = await getFeatures();
      this.features = response.features;
    } catch (error) {
      console.error('Failed to fetch features:', error);
      // Default to empty features if fetch fails
      this.features = {};
    }

    // Check for trackers
    await this._checkTrackers();
  }

  private _trackerCheckInterval?: number;

  private async _checkTrackers() {
    try {
      const response = await fetch('/api/v1/trackers', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('accessToken')}`,
        },
      });
      if (response.ok) {
        const trackers = await response.json();
        this.hasTrackers = Array.isArray(trackers) && trackers.length > 0;
      }
    } catch (error) {
      // Silently fail - user might not have permission or network error
      console.debug('Could not check trackers:', error);
    }
  }

  disconnectedCallback() {
    window.removeEventListener('show-upgrade-modal', () => {
      (this._upgradeModal as any).show();
    });
    if (this._trackerCheckInterval) {
      clearInterval(this._trackerCheckInterval);
    }
    super.disconnectedCallback();
  }

  private _showFlows() {
    const hostname = window.location.hostname;
    if (hostname === 'spacebridge.io') {
      return false;
    }
    return true;
  }

  render() {
    return html`
      <sl-dialog id="upgrade-modal" label="Upgrade Your Plan">
        You have exceeded the usage limits of your current plan. Please upgrade
        to continue using this feature.
        <sl-button slot="footer" href="/console/pricing">
          View Plans
        </sl-button>
      </sl-dialog>

      <global-notice></global-notice>

      <div class="console-container">
        <div class="sidebar">
          <div class="logo">
            <logo-component></logo-component>
          </div>
          <sl-menu style="font-size: 16px;">
            <a href="/console">
              <sl-menu-item>
                <sl-icon name="house" slot="prefix"></sl-icon>
                Overview
              </sl-menu-item>
            </a>
            <a href="/console/tools">
              <sl-menu-item>
                <sl-icon name="tools" slot="prefix"></sl-icon>
                Tools
              </sl-menu-item>
            </a>
            ${this._showFlows()
              ? html`<a href="/console/flows">
                  <sl-menu-item>
                    <sl-icon name="diagram-3" slot="prefix"></sl-icon>
                    Flows
                  </sl-menu-item>
                </a>`
              : html``}
            <a href="/console/trackers">
              <sl-menu-item>
                <sl-icon name="database" slot="prefix"></sl-icon>
                Trackers
              </sl-menu-item>
            </a>
            ${this.hasTrackers
              ? html`<sl-details>
                  <span slot="summary">
                    <sl-icon
                      name="kanban"
                      style="padding-right: 6px;"
                    ></sl-icon>
                    Issues
                  </span>
                  <sl-menu>
                    <a href="/console/issues">
                      <sl-menu-item>Similarity</sl-menu-item>
                    </a>
                    <a href="/console/issues/compliance">
                      <sl-menu-item>Compliance</sl-menu-item>
                    </a>
                    <a href="/console/issues/dependencies">
                      <sl-menu-item>Dependencies</sl-menu-item>
                    </a>
                  </sl-menu>
                </sl-details>`
              : ''}

            <sl-details>
              <span slot="summary">
                <sl-icon name="gear" style="padding-right: 6px;"></sl-icon>
                Settings
              </span>
              <sl-menu>
                ${this.features.user_management
                  ? html`<a href="/console/settings/users">
                      <sl-menu-item>Users</sl-menu-item>
                    </a>`
                  : ''}
                ${this.features.team_management
                  ? html`<a href="/console/settings/teams">
                      <sl-menu-item>Teams</sl-menu-item>
                    </a>`
                  : ''}
                ${this.features.user_management || this.features.team_management
                  ? html`<a href="/console/settings/invitations">
                      <sl-menu-item>Invitations</sl-menu-item>
                    </a>`
                  : ''}
                <a href="/console/settings/subscription">
                  <sl-menu-item>Subscription</sl-menu-item>
                </a>
                <a href="/console/settings/api-keys">
                  <sl-menu-item>API Keys</sl-menu-item>
                </a>
                <a href="/console/settings/ai-models">
                  <sl-menu-item>Models</sl-menu-item>
                </a>
              </sl-menu>
            </sl-details>
          </sl-menu>
        </div>

        <div class="main-view">
          <console-header></console-header>
          <div class="main-content">
            <slot></slot>
          </div>
        </div>
      </div>
    `;
  }
}
