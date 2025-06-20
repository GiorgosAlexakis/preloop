import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { post } from '../../api';
import { formStyles } from '../../styles/form-styles';

@customElement('login-view')
export class LoginView extends LitElement {
  @state()
  private error = '';

  static styles = [
    formStyles,
    css`
      .error-message {
        color: var(--sl-color-danger-700);
        margin-bottom: 1rem;
        text-align: center;
      }
    `,
  ];

  private async handleLogin(event: SubmitEvent) {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const formData = new FormData(form);
    const username = formData.get('username') as string;
    const password = formData.get('password') as string;

    try {
      const data = await post('/api/v1/auth/token/json', {
        username,
        password,
      });

      localStorage.setItem('accessToken', data.access_token);
      this.error = '';
      window.dispatchEvent(
        new CustomEvent('auth-change', { bubbles: true, composed: true })
      );
      Router.go('/console');
    } catch (error) {
      this.error = 'Invalid username or password';
      console.error('Login failed', error);
    }
  }

  render() {
    return html`
      <div class="form-container">
        <h2>Login</h2>
        ${this.error
          ? html`<div class="error-message">${this.error}</div>`
          : ''}
        <form @submit=${this.handleLogin}>
          <div class="form-group">
            <label for="username">Username</label>
            <input type="text" id="username" name="username" required />
          </div>
          <div class="form-group">
            <label for="password">Password</label>
            <input type="password" id="password" name="password" required />
          </div>
          <div class="form-actions">
            <button type="submit">Login</button>
          </div>
          <div class="form-links">
            <a href="/forgot-password">Forgot Password?</a> |
            <a href="/register">Sign Up</a>
          </div>
        </form>
      </div>
    `;
  }
}
