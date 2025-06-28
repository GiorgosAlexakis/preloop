import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { getAccountDetails } from '../api';

import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';

interface User {
  username: string;
  email: string;
}

@customElement('app-header')
export class AppHeader extends LitElement {
  @property({ type: Boolean })
  showDrawerToggle = false;

  @state()
  private isAuthenticated = false;

  @state()
  private user: User | null = null;

  static styles = css`
    :host {
      display: block;
    }
    .header-container {
      display: flex;
      justify-content: space-between;
      align-items: center;
      max-width: 1200px;
      margin: 0 auto;
      padding: 1rem;
    }
    nav {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .logo img {
      height: 32px;
    }
    sl-icon-button::part(base) {
      font-size: 1.5rem;
    }
  `;

  connectedCallback() {
    super.connectedCallback();
    this.checkAuth();
    window.addEventListener('auth-change', () => this.checkAuth());
    window.addEventListener('vaadin-router-location-changed', () =>
      this.requestUpdate()
    );
  }

  disconnectedCallback() {
    window.removeEventListener('auth-change', () => this.checkAuth());
    window.removeEventListener('vaadin-router-location-changed', () =>
      this.requestUpdate()
    );
    super.disconnectedCallback();
  }

  async checkAuth() {
    const token = localStorage.getItem('accessToken');
    this.isAuthenticated = !!token;
    if (this.isAuthenticated) {
      try {
        this.user = await getAccountDetails();
      } catch (error) {
        console.error('Failed to fetch user details', error);
        this.logout();
      }
    } else {
      this.user = null;
    }
  }

  logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    this.isAuthenticated = false;
    this.user = null;
    const event = new CustomEvent('auth-change', {
      bubbles: true,
      composed: true,
    });
    window.dispatchEvent(event);
    Router.go('/login');
  }

  render() {
    return html`
      <header>
        <div class="header-container">
          <div class="flex items-center">
            ${this.showDrawerToggle
              ? html`<sl-icon-button
                  name="menu"
                  @click=${() =>
                    this.dispatchEvent(
                      new CustomEvent('toggle-drawer', {
                        bubbles: true,
                        composed: true,
                      })
                    )}
                ></sl-icon-button>`
              : html`<div class="logo">
                  <a href="/">
                    <img src="/images/logo_dark.png" alt="SpaceBridge Logo" />
                  </a>
                </div>`}
          </div>
          <nav>
            <sl-button href="/docs" variant="text">Docs</sl-button>
            ${this.isAuthenticated && this.user
              ? html`
                  ${window.location.pathname === '/'
                    ? html`<sl-button href="/console">Console</sl-button>`
                    : html`<sl-button @click=${this.logout}>Logout</sl-button>`}
                `
              : html`
                  <sl-button href="/login" variant="text">Login</sl-button>
                  <sl-button href="/register" variant="primary"
                    >Sign Up</sl-button
                  >
                `}
          </nav>
        </div>
      </header>
    `;
  }
}
