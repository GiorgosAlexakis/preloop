import { LitElement, html } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { formStyles } from '../../styles/form-styles';
import { post } from '../../api';

@customElement('forgot-password-view')
export class ForgotPasswordView extends LitElement {
  @state()
  private message = '';

  @state()
  private error = '';

  static styles = [formStyles];

  private async handleForgotPassword(event: SubmitEvent) {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const formData = new FormData(form);
    const email = formData.get('email') as string;

    try {
      await post('/api/v1/auth/forgot-password', { email });
      this.message =
        'If an account with that email exists, a password reset link has been sent.';
      this.error = '';
    } catch (error) {
      this.error = 'An unexpected error occurred. Please try again.';
      console.error('Forgot password failed', error);
    }
  }

  render() {
    return html`
      <div class="form-container">
        <h2>Forgot Password</h2>
        ${this.message
          ? html`<div class="success-message">${this.message}</div>`
          : ''}
        ${this.error
          ? html`<div class="error-message">${this.error}</div>`
          : ''}
        <form @submit=${this.handleForgotPassword}>
          <div class="form-group">
            <label for="email">Email</label>
            <input type="email" id="email" name="email" required />
          </div>
          <div class="form-actions">
            <button type="submit">Send Reset Link</button>
          </div>
          <div class="form-links">
            <a href="/login">Back to Login</a>
          </div>
        </form>
      </div>
    `;
  }
}
