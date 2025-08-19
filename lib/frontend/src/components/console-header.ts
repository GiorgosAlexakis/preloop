import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/dropdown/dropdown.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import './theme-switcher.ts';
import * as api from '../api.ts';

interface UserDetails {
  username: string;
  email: string;
  full_name: string;
}

@customElement('console-header')
export class ConsoleHeader extends LitElement {
  @state()
  private _user: UserDetails | null = null;

  static styles = css`
    :host {
      display: block;
    }
    .header-container {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      padding: 0.4rem;
      border-bottom: 1px solid var(--sl-color-neutral-200);
    }
    .user-menu {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .user-menu sl-icon-button {
      font-size: 1.8rem;
    }
    .theme-switcher-container {
      padding: 0.5rem 1rem;
    }
    .user-info {
      padding: 0.5rem 1rem;
      line-height: 1.4;
    }
    .user-name {
      font-weight: bold;
    }
    .user-email {
      color: var(--sl-color-neutral-500);
    }
  `;

  async connectedCallback() {
    super.connectedCallback();
    this.fetchUserDetails();
  }

  async fetchUserDetails() {
    try {
      this._user = await api.getAccountDetails();
    } catch (error) {
      console.error('Failed to fetch user details', error);
    }
  }

  async signOut() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    window.dispatchEvent(
      new CustomEvent('auth-change', { bubbles: true, composed: true })
    );
    window.location.href = '/';
    fetch('/logout', { method: 'GET' }).catch((error) => {
      console.error('Logout request to server failed:', error);
    });
  }

  render() {
    return html`
      <div class="header-container">
        <div class="user-menu">
          <sl-dropdown distance="8">
            <sl-icon-button
              name="person-circle"
              slot="trigger"
              label="User Menu"
            ></sl-icon-button>
            <sl-menu>
              <div class="user-info">
                <div class="user-name">
                  ${this._user?.full_name || this._user?.username}
                </div>
                <div class="user-email">${this._user?.email}</div>
              </div>
              <sl-divider></sl-divider>
              <div class="theme-switcher-container">
                <theme-switcher></theme-switcher>
              </div>
              <sl-divider></sl-divider>
              <sl-menu-item @click=${this.signOut}>
                <sl-icon name="box-arrow-right" slot="prefix"></sl-icon>
                Sign Out
              </sl-menu-item>
            </sl-menu>
          </sl-dropdown>
        </div>
      </div>
    `;
  }
}
