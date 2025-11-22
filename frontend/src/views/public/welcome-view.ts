import { LitElement, html, css } from 'lit';
import { customElement, state, query } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { fetchPublic } from '../../api';
import { formStyles } from '../../styles/form-styles';
import { getBrandConfig } from '../../brand-config';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '../../components/logo-component';

@customElement('welcome-view')
export class WelcomeView extends LitElement {
  @state() private _username = '';
  @state() private _email = '';
  @state() private _error = '';
  @state() private _loading = false;
  @query('#password') private _passwordInput!: HTMLInputElement;

  connectedCallback() {
    super.connectedCallback();
    const urlParams = new URLSearchParams(window.location.search);
    this._username = urlParams.get('username') || '';
    this._email = urlParams.get('email') || '';
    if (!this._email) {
      this._error = 'Could not retrieve your details. Please contact support.';
    }
  }

  private async _handleOnboardingSubmit(e: Event) {
    e.preventDefault();
    this._loading = true;
    this._error = '';

    const password = this._passwordInput.value;
    if (password.length < 8) {
      this._error = 'Password must be at least 8 characters long.';
      this._loading = false;
      return;
    }

    try {
      const response = await fetchPublic('/api/v1/auth/complete-onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: this._email,
          username: this._username,
          password: password,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to complete onboarding.');
      }

      const data = await response.json();
      localStorage.setItem('accessToken', data.access_token);
      localStorage.setItem('refreshToken', data.refresh_token);
      Router.go('/console');
    } catch (error: any) {
      this._error = error.message;
    } finally {
      this._loading = false;
    }
  }

  static styles = [
    formStyles,
    css`
      .success-message {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
        padding: 0.75rem 1.25rem;
        margin-bottom: 1rem;
        border-radius: 0.25rem;
        text-align: center;
      }
    `,
  ];

  render() {
    if (this._error && !this._username) {
      return html`
        <div class="container">
          <div class="logo">
            <a href="/">
              <logo-component></logo-component>
            </a>
          </div>
          <div class="form-container">
            <div class="error-message">${this._error}</div>
          </div>
        </div>
      `;
    }

    return html`
      <div class="container">
        <div class="logo">
          <a href="/">
            <logo-component></logo-component>
          </a>
        </div>
        <div class="form-container">
          <h2>Welcome to ${getBrandConfig().name}!</h2>
          <p style="text-align: center; margin-bottom: 1.5rem;">
            Your account has been created. Please set your password to continue.
          </p>
          ${this._error
            ? html`<div class="error-message">${this._error}</div>`
            : ''}
          <form @submit=${this._handleOnboardingSubmit}>
            <div class="form-group">
              <sl-input
                label="Email"
                value=${this._email}
                readonly
                disabled
              ></sl-input>
            </div>
            <div class="form-group">
              <sl-input
                label="Username"
                value=${this._username}
                @sl-change=${(e: any) => (this._username = e.target.value)}
              ></sl-input>
            </div>
            <div class="form-group">
              <sl-input
                id="password"
                type="password"
                label="Password"
                required
                password-toggle
              ></sl-input>
            </div>
            <div class="form-actions">
              <sl-button
                type="submit"
                variant="primary"
                ?loading=${this._loading}
                style="width: 100%;"
              >
                Complete Registration
              </sl-button>
            </div>
          </form>
        </div>
      </div>
    `;
  }
}
