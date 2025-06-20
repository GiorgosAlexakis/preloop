import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { getAccountDetails } from '../api';

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
      background: white;
      border-bottom: 1px solid rgba(0, 0, 0, 0.03);
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
    }
    nav a,
    nav button {
      color: var(--gray-700);
      text-decoration: none;
      margin-left: 1.5rem;
      background: none;
      border: none;
      cursor: pointer;
      font-size: 1rem;
      font-family: inherit;
      transition: color 0.2s ease-in-out;
    }
    nav a:hover {
      color: var(--primary-color);
    }
    .logo img {
      height: 32px;
    }
    .signup-button {
      border: 1px solid var(--gray-300);
      border-radius: 0.375rem;
      padding: 0.5rem 1rem;
      color: var(--primary-color);
      font-weight: 500;
    }
    .signup-button:hover {
      background-color: var(--primary-light);
      border-color: var(--primary-color);
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
              ? html`<vaadin-drawer-toggle></vaadin-drawer-toggle>`
              : html`<div class="logo">
              <a href="/">
                <img src="/images/logo.png" alt="SpaceBridge Logo" />
              </a>
            </div>`}
            
          </div>
          <nav>
            <a href="/docs">Docs</a>
            ${this.isAuthenticated && this.user
              ? html`
                  ${window.location.pathname === '/'
                    ? html`<a href="/console">Console</a>`
                    : html`<button @click=${this.logout}>Logout</button>`}
                `
              : html`
                  <a href="/login">Login</a>
                  <a href="/register" class="signup-button">Sign Up</a>
                `}
          </nav>
        </div>
      </header>
    `;
  }
}
