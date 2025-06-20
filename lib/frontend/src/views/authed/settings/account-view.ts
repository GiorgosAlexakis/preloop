import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import {
  getAccountDetails,
  updateAccountDetails,
  changePassword,
} from '../../../api';
import { formStyles } from '../../../styles/form-styles';
import '@vaadin/text-field';
import '@vaadin/password-field';
import '@vaadin/button';

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
              <vaadin-text-field
                label="Username"
                .value="${this.user?.username || ''}"
                readonly
              ></vaadin-text-field>
              <vaadin-text-field
                label="Email"
                .value="${this.user?.email || ''}"
                readonly
              ></vaadin-text-field>
              <vaadin-text-field
                label="Full Name"
                .value="${this.fullName}"
                @value-changed="${(e: CustomEvent) =>
                  (this.fullName = e.detail.value)}"
              ></vaadin-text-field>
              <vaadin-button theme="primary" type="submit"
                >Update Profile</vaadin-button
              >
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
              <vaadin-password-field
                label="Current Password"
                .value="${this.currentPassword}"
                @value-changed="${(e: CustomEvent) =>
                  (this.currentPassword = e.detail.value)}"
                required
              ></vaadin-password-field>
              <vaadin-password-field
                label="New Password"
                .value="${this.newPassword}"
                @value-changed="${(e: CustomEvent) =>
                  (this.newPassword = e.detail.value)}"
                required
                minlength="8"
              ></vaadin-password-field>
              <vaadin-password-field
                label="Confirm New Password"
                .value="${this.confirmNewPassword}"
                @value-changed="${(e: CustomEvent) =>
                  (this.confirmNewPassword = e.detail.value)}"
                required
              ></vaadin-password-field>
              <vaadin-button theme="primary" type="submit"
                >Change Password</vaadin-button
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
