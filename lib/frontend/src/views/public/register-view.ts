import { LitElement, html } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { post } from '../../api';
import { formStyles } from '../../styles/form-styles';

import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';

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
      Router.go('/login?registered=true');
    } catch (error) {
      this.error = 'Failed to create an account';
      console.error('Create account failed', error);
    }
  }

  render() {
    return html`
      <div class="container">
        <div class="logo">
          <a href="/">
            <img src="/images/logo_dark.png" alt="SpaceBridge MCP" />
          </a>
        </div>
        <div class="form-container">
          <h2>Create a Spacebridge account</h2>
          ${this.error
            ? html`<div class="error-message">${this.error}</div>`
            : ''}
          <form @submit=${this.handleRegister}>
            <div class="form-group">
              <sl-input
                label="Username"
                id="username"
                name="username"
                required
              ></sl-input>
            </div>
            <div class="form-group">
              <sl-input
                type="email"
                label="Email"
                id="email"
                name="email"
                required
              ></sl-input>
            </div>
            <div class="form-group">
              <sl-input
                type="password"
                label="Password"
                id="password"
                name="password"
                required
                password-toggle
              ></sl-input>
            </div>
            <div class="form-actions">
              <sl-button type="submit" variant="primary"
                >Create account</sl-button
              >
            </div>
            <div class="form-links">
              <a href="/login">Already have an account? Sign In</a>
            </div>
          </form>
        </div>
      </div>
    `;
  }
}
