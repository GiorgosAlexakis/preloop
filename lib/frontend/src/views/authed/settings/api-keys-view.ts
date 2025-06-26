import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { repeat } from 'lit/directives/repeat.js';
import { getApiKeys, createApiKey, deleteApiKey, ApiKey } from '../../../api';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';

@customElement('api-keys-view')
export class ApiKeysView extends LitElement {
  @state()
  private apiKeys: ApiKey[] = [];

  @state()
  private isLoading = true;

  @state()
  private error: string | null = null;

  @state()
  private isCreateModalOpen = false;

  @state()
  private isShowKeyModalOpen = false;

  @state()
  private newKeyName = '';

  @state()
  private newKeyExpiry = 'never';

  @state()
  private newCustomExpiry = '';

  @state()
  private newlyCreatedKey: ApiKey | null = null;

  async connectedCallback() {
    super.connectedCallback();
    await this.fetchApiKeys();
  }

  async fetchApiKeys() {
    this.isLoading = true;
    this.error = null;
    try {
      this.apiKeys = await getApiKeys();
    } catch (error) {
      this.error =
        error instanceof Error ? error.message : 'Failed to fetch API keys';
    } finally {
      this.isLoading = false;
    }
  }

  async handleCreateApiKey() {
    let expires_at: string | null = null;
    if (this.newKeyExpiry !== 'never') {
      const now = new Date();
      if (this.newKeyExpiry === 'custom') {
        expires_at = new Date(this.newCustomExpiry).toISOString();
      } else {
        const days = parseInt(this.newKeyExpiry.replace('days', ''));
        now.setDate(now.getDate() + days);
        expires_at = now.toISOString();
      }
    }

    try {
      const newKey = await createApiKey(this.newKeyName, expires_at);
      this.newlyCreatedKey = newKey;
      this.isCreateModalOpen = false;
      this.isShowKeyModalOpen = true;
      await this.fetchApiKeys();
    } catch (error) {
      console.error('Failed to create API key:', error);
    }
  }

  async handleDeleteApiKey(keyId: string) {
    if (confirm('Are you sure you want to revoke this API key?')) {
      try {
        await deleteApiKey(keyId);
        await this.fetchApiKeys();
      } catch (error) {
        console.error('Failed to delete API key:', error);
      }
    }
  }

  render() {
    const renderContent = () => {
      if (this.isLoading) {
        return html`<div class="loading-indicator">
          <sl-spinner></sl-spinner>
        </div>`;
      }
      if (this.error) {
        return html`
          <sl-alert variant="danger" open>
            <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
            <strong>Error:</strong> ${this.error}
          </sl-alert>
        `;
      }
      return html`
        <sl-card class="table-card">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Created</th>
                <th>Last Used</th>
                <th>Expires</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${repeat(
                this.apiKeys,
                (key) => key.id,
                (key) => html`
                  <tr>
                    <td>${key.name}</td>
                    <td>${new Date(key.created_at).toLocaleDateString()}</td>
                    <td>
                      ${key.last_used_at
                        ? new Date(key.last_used_at).toLocaleDateString()
                        : 'Never'}
                    </td>
                    <td>
                      ${key.expires_at
                        ? new Date(key.expires_at).toLocaleDateString()
                        : 'Never'}
                    </td>
                    <td>
                      <sl-button
                        variant="danger"
                        size="small"
                        @click=${() => this.handleDeleteApiKey(key.id)}
                        >Revoke</sl-button
                      >
                    </td>
                  </tr>
                `
              )}
            </tbody>
          </table>
        </sl-card>
      `;
    };

    return html`
      <div class="container">
        <div class="header">
          <h1 class="title">API Keys</h1>
          <sl-button
            variant="primary"
            @click=${() => {
              this.isCreateModalOpen = true;
            }}
            >Create New API Key</sl-button
          >
        </div>

        ${renderContent()}
      </div>

      <sl-dialog
        label="Create API Key"
        .open=${this.isCreateModalOpen}
        @sl-hide=${() => (this.isCreateModalOpen = false)}
      >
        <sl-input
          style="margin-bottom: 1rem;"
          label="Key Name"
          .value=${this.newKeyName}
          @sl-input=${(e: Event) =>
            (this.newKeyName = (e.target as HTMLInputElement).value)}
        ></sl-input>
        <sl-select
          style="margin-bottom: 1rem;"
          label="Expiration"
          .value=${this.newKeyExpiry}
          @sl-change=${(e: { target: { value: string } }) =>
            (this.newKeyExpiry = e.target.value)}
        >
          <sl-menu-item value="never">Never</sl-menu-item>
          <sl-menu-item value="7days">7 Days</sl-menu-item>
          <sl-menu-item value="30days">30 Days</sl-menu-item>
          <sl-menu-item value="90days">90 Days</sl-menu-item>
          <sl-menu-item value="custom">Custom Date</sl-menu-item>
        </sl-select>
        ${when(
          this.newKeyExpiry === 'custom',
          () => html`
            <sl-input
              type="date"
              label="Custom Expiry Date"
              .value=${this.newCustomExpiry}
              @sl-change=${(e: { target: { value: string } }) =>
                (this.newCustomExpiry = e.target.value)}
            ></sl-input>
          `
        )}
        <sl-button
          slot="footer"
          @click=${() => {
            this.isCreateModalOpen = false;
          }}
          >Cancel</sl-button
        >
        <sl-button
          slot="footer"
          variant="primary"
          @click=${this.handleCreateApiKey}
          >Create</sl-button
        >
      </sl-dialog>

      <sl-dialog
        label="API Key Created"
        .open=${this.isShowKeyModalOpen && this.newlyCreatedKey}
        @sl-hide=${() => (this.isShowKeyModalOpen = false)}
      >
        <p>
          Here is your new API key. Please copy it now, you will not be able to
          see it again.
        </p>
        <pre><code>${this.newlyCreatedKey?.key}</code></pre>
        <sl-button
          slot="footer"
          variant="primary"
          @click=${() => {
            this.isShowKeyModalOpen = false;
          }}
          >Close</sl-button
        >
      </sl-dialog>
    `;
  }

  static styles = css`
    .container {
      max-width: var(--console-container-max-width);
      padding: var(--sl-spacing-x-large);
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: var(--sl-spacing-large);
    }
    .loading-indicator {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100px;
    }
    .table-card {
      width: 100%;
      --padding: 0;
    }
    .table-card::part(body) {
      padding: 0;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th,
    td {
      padding: var(--sl-spacing-medium);
      text-align: left;
      border-bottom: 1px solid var(--sl-color-neutral-200);
    }
    th {
      background-color: var(--sl-color-neutral-50);
      font-weight: var(--sl-font-weight-semibold);
    }
    tr:last-child td {
      border-bottom: none;
    }
    th:last-child,
    td:last-child {
      text-align: right;
    }
  `;
}
