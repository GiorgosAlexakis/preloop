import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { getAccountDetails, updateAccountDetails } from '../../../api';
import { formStyles } from '../../../styles/form-styles';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';

@customElement('profile-view')
export class ProfileView extends LitElement {
  @state()
  private user: { username: string; email: string; full_name: string } | null =
    null;

  @state()
  private fullName = '';

  @state()
  private updateProfileMessage = '';

  async connectedCallback() {
    super.connectedCallback();
    await this.loadAccountDetails();
  }

  async loadAccountDetails() {
    try {
      this.user = await getAccountDetails();
      this.fullName = this.user?.full_name || '';
    } catch (error) {
      console.error('Failed to load account details', error);
      this.updateProfileMessage = 'Failed to load account details.';
    }
  }

  async handleUpdateProfile(event: Event) {
    event.preventDefault();
    try {
      await updateAccountDetails({ full_name: this.fullName });
      this.updateProfileMessage = 'Profile updated successfully.';
    } catch (error) {
      this.updateProfileMessage = 'Failed to update profile.';
    }
  }

  render() {
    return html`
      <div class="container">
        <div class="header">
          <h1 class="title">Profile</h1>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>Update Profile</h3>
          </div>
          <div class="card-body">
            <form @submit="${this.handleUpdateProfile}">
              <sl-input
                label="Username"
                .value="${this.user?.username || ''}"
                readonly
              ></sl-input>
              <sl-input
                label="Email"
                .value="${this.user?.email || ''}"
                readonly
              ></sl-input>
              <sl-input
                label="Full Name"
                .value="${this.fullName}"
                @sl-input="${(e: Event) =>
                  (this.fullName = (e.target as HTMLInputElement).value)}"
              ></sl-input>
              <sl-button variant="primary" type="submit"
                >Update Profile</sl-button
              >
              ${this.updateProfileMessage
                ? html`<p>${this.updateProfileMessage}</p>`
                : ''}
            </form>
          </div>
        </div>
      </div>
    `;
  }

  static styles = [
    formStyles,
    css`
      .container {
        max-width: var(--console-container-max-width);
        padding: var(--sl-spacing-x-large);
      }
      .card {
        background-color: var(--lumo-base-color);
        border-radius: var(--lumo-border-radius);
        padding: var(--sl-spacing-x-large);
        margin-bottom: var(--sl-spacing-x-large);
        box-shadow: var(--lumo-box-shadow-s);
      }
      .card-header {
        border-bottom: 1px solid var(--lumo-contrast-10pct);
        padding-bottom: 1rem;
        margin-bottom: 1rem;
      }
      h2,
      h3 {
        margin: 0;
      }
      form {
        display: flex;
        flex-direction: column;
        gap: 1rem;
      }

      sl-button {
        width: 12em;
      }
    `,
  ];
}
