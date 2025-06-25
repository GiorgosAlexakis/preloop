import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import {
  getAccountDetails,
  updateAccountDetails,
  changePassword,
} from '../../../api';
import { formStyles } from '../../../styles/form-styles';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';

@customElement('account-view')
export class AccountView extends LitElement {
  @state()
  private user: { username: string; email: string; full_name: string } | null =
    null;

  @state()
  private fullName = '';

  @state()
  private currentPassword = '';

  @state()
  private newPassword = '';

  @state()
  private confirmNewPassword = '';

  @state()
  private updateProfileMessage = '';

  @state()
  private changePasswordMessage = '';

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

  async handleChangePassword(event: Event) {
    event.preventDefault();
    if (this.newPassword !== this.confirmNewPassword) {
      this.changePasswordMessage = 'New passwords do not match.';
      return;
    }
    try {
      await changePassword({
        current_password: this.currentPassword,
        new_password: this.newPassword,
      });
      this.changePasswordMessage = 'Password changed successfully.';
      this.currentPassword = '';
      this.newPassword = '';
      this.confirmNewPassword = '';
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'An unknown error occurred.';
      this.changePasswordMessage = `Failed to change password: ${errorMessage}`;
    }
  }

  render() {
    return html`
      <div class="container">
        <h2>Account Settings</h2>

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
              <sl-button variant="primary" type="submit">Update Profile</sl-button>
              ${this.updateProfileMessage
                ? html`<p>${this.updateProfileMessage}</p>`
                : ''}
            </form>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>Change Password</h3>
          </div>
          <div class="card-body">
            <form @submit="${this.handleChangePassword}">
              <sl-input
                type="password"
                label="Current Password"
                .value="${this.currentPassword}"
                @sl-input="${(e: Event) =>
                  (this.currentPassword = (e.target as HTMLInputElement).value)}"
                required
                password-toggle
              ></sl-input>
              <sl-input
                type="password"
                label="New Password"
                .value="${this.newPassword}"
                @sl-input="${(e: Event) =>
                  (this.newPassword = (e.target as HTMLInputElement).value)}"
                required
                minlength="8"
                password-toggle
              ></sl-input>
              <sl-input
                type="password"
                label="Confirm New Password"
                .value="${this.confirmNewPassword}"
                @sl-input="${(e: Event) =>
                  (this.confirmNewPassword = (
                    e.target as HTMLInputElement
                  ).value)}"
                required
                password-toggle
              ></sl-input>
              <sl-button variant="primary" type="submit"
                >Change Password</sl-button
              >
              ${this.changePasswordMessage
                ? html`<p>${this.changePasswordMessage}</p>`
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
        max-width: 800px;
        margin: 0 auto;
        padding: 2rem;
      }
      .card {
        background-color: var(--lumo-base-color);
        border-radius: var(--lumo-border-radius);
        padding: 1.5rem;
        margin-bottom: 2rem;
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
    `,
  ];
}
