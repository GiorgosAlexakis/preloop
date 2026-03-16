var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { formStyles } from '../../styles/form-styles';
import { post } from '../../api';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '../../components/logo-component';
let ForgotPasswordView = class ForgotPasswordView extends LitElement {
    constructor() {
        super(...arguments);
        this.message = '';
        this.error = '';
    }
    async handleForgotPassword(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        const email = formData.get('email');
        try {
            await post('/api/v1/auth/forgot-password', { email });
            this.message =
                'If an account with that email exists, a password reset link has been sent.';
            this.error = '';
        }
        catch (error) {
            // Extract the error message from the Error object
            if (error instanceof Error) {
                this.error = error.message;
            }
            else {
                this.error = 'An unexpected error occurred. Please try again.';
            }
            console.error('Forgot password failed', error);
        }
    }
    render() {
        return html `
      <div class="container">
        <div class="logo">
          <a href="/">
            <logo-component></logo-component>
          </a>
        </div>
        <div class="form-container">
          <h2>Forgot Password</h2>
          ${this.message
            ? html `<sl-alert
                variant="success"
                open
                closable
                @sl-after-hide=${() => (this.message = '')}
              >
                <sl-icon slot="icon" name="check-circle"></sl-icon>
                ${this.message}
              </sl-alert>`
            : ''}
          ${this.error
            ? html `<sl-alert
                variant="danger"
                open
                closable
                @sl-after-hide=${() => (this.error = '')}
              >
                <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                ${this.error}
              </sl-alert>`
            : ''}
          <form @submit=${this.handleForgotPassword}>
            <sl-input
              type="email"
              label="Email"
              name="email"
              required
            ></sl-input>
            <div class="form-actions">
              <sl-button type="submit" variant="primary"
                >Send Reset Link</sl-button
              >
            </div>
            <div class="form-links">
              <a href="/login">Back to Sign in</a>
            </div>
          </form>
        </div>
      </div>
    `;
    }
};
ForgotPasswordView.styles = [formStyles];
__decorate([
    state()
], ForgotPasswordView.prototype, "message", void 0);
__decorate([
    state()
], ForgotPasswordView.prototype, "error", void 0);
ForgotPasswordView = __decorate([
    customElement('forgot-password-view')
], ForgotPasswordView);
export { ForgotPasswordView };
