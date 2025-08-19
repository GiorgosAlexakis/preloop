import { LitElement, html, css } from 'lit';
import { customElement, state, query } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { fetchPublic } from '../../api';

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

  static styles = css`
    .container {
      max-width: 400px;
      margin: 50px auto;
      padding: 20px;
      border-radius: 5px;
      text-align: center;
    }
    .error {
      color: red;
      margin-bottom: 1rem;
    }
    form > * {
      display: block;
      margin-bottom: 1rem;
      width: 100%;
    }
  `;

  render() {
    if (this._loading) {
      return html`<div class="container"><p>Loading...</p></div>`;
    }

    if (this._error && !this._username) {
      return html`<div class="container">
        <p class="error">${this._error}</p>
      </div>`;
    }

    return html`
      <div class="container">
        <h1>Welcome to SpaceBridge!</h1>
        <p>
          Your account has been created. Please set your password to continue.
        </p>
        <form @submit=${this._handleOnboardingSubmit}>
          <sl-input label="Email" value=${this._email} readonly></sl-input>
          <sl-input
            label="Username"
            value=${this._username}
            @sl-change=${(e: any) => (this._username = e.target.value)}
          ></sl-input>
          <sl-input
            id="password"
            type="password"
            label="Password"
            required
          ></sl-input>
          ${this._error ? html`<p class="error">${this._error}</p>` : ''}
          <sl-button type="submit" variant="primary" ?loading=${this._loading}>
            Complete Registration
          </sl-button>
        </form>
      </div>
    `;
  }
}
