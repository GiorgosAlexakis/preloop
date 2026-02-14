import { LitElement, html, css, nothing } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { post, getFeatures } from '../../api';
import { formStyles } from '../../styles/form-styles';
import { getBrandConfig } from '../../brand-config';

import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '../../components/logo-component';

const OAUTH_PROVIDER_CONFIG: Record<string, { label: string; icon: string }> = {
  github: { label: 'GitHub', icon: 'github' },
  google: { label: 'Google', icon: 'google' },
  gitlab: { label: 'GitLab', icon: 'gitlab' },
};

@customElement('register-view')
export class RegisterView extends LitElement {
  @state()
  private error = '';

  @state()
  private oauthProviders: string[] = [];

  static styles = [
    formStyles,
    css`
      .oauth-section {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
      }

      .oauth-button {
        width: 100%;
      }

      .oauth-button::part(base) {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
      }

      .divider {
        display: flex;
        align-items: center;
        margin: 1.5rem 0;
        color: var(--sl-color-neutral-500);
        font-size: var(--sl-font-size-small);
      }

      .divider::before,
      .divider::after {
        content: '';
        flex: 1;
        border-bottom: 1px solid var(--sl-color-neutral-300);
      }

      .divider::before {
        margin-right: 0.75rem;
      }

      .divider::after {
        margin-left: 0.75rem;
      }
    `,
  ];

  connectedCallback() {
    super.connectedCallback();
    this._checkFeatures();
  }

  private async _checkFeatures() {
    try {
      const features = await getFeatures();
      const providers = features.features['oauth_providers'];
      this.oauthProviders = Array.isArray(providers) ? providers : [];
    } catch (error) {
      this.oauthProviders = [];
    }
  }

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
      if (error instanceof Error) {
        this.error = error.message;
      } else {
        this.error = 'Failed to create an account';
      }
      console.error('Create account failed', error);
    }
  }

  private _renderOAuthButtons() {
    if (this.oauthProviders.length === 0) return nothing;

    return html`
      <div class="oauth-section">
        ${this.oauthProviders.map((provider) => {
          const config = OAUTH_PROVIDER_CONFIG[provider];
          if (!config) return nothing;
          return html`
            <sl-button
              class="oauth-button"
              variant="default"
              size="large"
              @click=${() => {
                window.location.href = `/api/v1/auth/oauth/${provider}/authorize`;
              }}
            >
              <sl-icon name="${config.icon}" slot="prefix"></sl-icon>
              Sign up with ${config.label}
            </sl-button>
          `;
        })}
      </div>
      <div class="divider">or sign up with email</div>
    `;
  }

  render() {
    return html`
      <div class="container">
        <div class="logo">
          <a href="/">
            <logo-component></logo-component>
          </a>
        </div>
        <div class="form-container">
          <h2>Create a ${getBrandConfig().name} account</h2>
          ${this.error
            ? html`<div class="error-message">${this.error}</div>`
            : ''}
          ${this._renderOAuthButtons()}
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
                minlength="8"
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
