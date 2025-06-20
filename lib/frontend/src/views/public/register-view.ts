import { LitElement, html } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { post } from '../../api';
import { formStyles } from '../../styles/form-styles';

@customElement('register-view')
export class RegisterView extends LitElement {
  @state()
  private error = '';

  static styles = [formStyles];

  private async handleRegister(event: SubmitEvent) {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const formData = new FormData(form);
    const username = formData.get('username') as string;
    const email = formData.get('email') as string;
    const password = formData.get('password') as string;

    try {
      await post('/api/v1/auth/register', {
        username,
        email,
        password,
      });
      Router.go('/login');
    } catch (error) {
      this.error = 'Failed to register';
      console.error('Registration failed', error);
    }
  }

  render() {
    return html`
      <div class="form-container">
        <h2>Register</h2>
        ${this.error
          ? html`<div class="error-message">${this.error}</div>`
          : ''}
        <form @submit=${this.handleRegister}>
          <div class="form-group">
            <label for="username">Username</label>
            <input type="text" id="username" name="username" required />
          </div>
          <div class="form-group">
            <label for="email">Email</label>
            <input type="email" id="email" name="email" required />
          </div>
          <div class="form-group">
            <label for="password">Password</label>
            <input type="password" id="password" name="password" required />
          </div>
          <div class="form-actions">
            <button type="submit">Register</button>
          </div>
          <div class="form-links">
            <span>Already have an account? </span>
            <a href="/login">Login</a>
          </div>
        </form>
      </div>
    `;
  }
}
