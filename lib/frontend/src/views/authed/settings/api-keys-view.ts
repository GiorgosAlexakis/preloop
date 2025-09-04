import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { getApiKeys, createApiKey, deleteApiKey } from '../../../api';
import type { ApiKey } from '../../../types';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import type { SlMenuItem } from '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/dropdown/dropdown.js';
import consoleStyles from '../../../styles/console-styles.css?inline';

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
  private newKeyExpiryLabel = 'Never';

  @state()
  private newlyCreatedKey: ApiKey | null = null;

  @state()
  private isSelectOpen = false;

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
    if (!this.newKeyName) {
      return;
    }

    let expires_at: string | null = null;
    if (this.newKeyExpiry !== 'never') {
      const now = new Date();
      const days = parseInt(this.newKeyExpiry.replace('days', ''));
      now.setDate(now.getDate() + days);
      expires_at = now.toISOString();
    }

    try {
      const newKey = await createApiKey(this.newKeyName, expires_at);
      this.newlyCreatedKey = newKey;
      this.isCreateModalOpen = false;
      this.isShowKeyModalOpen = true;
      this.newKeyName = ''; // Reset for next time
      this.newKeyExpiry = 'never'; // Reset for next time
      this.newKeyExpiryLabel = 'Never'; // Reset for next time
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

  private _copyKey(e: Event) {
    const button = e.currentTarget as HTMLElement;
    const pre = button.previousElementSibling;
    if (pre && pre.tagName === 'PRE') {
      const code = pre.querySelector('code');
      if (code) {
        navigator.clipboard.writeText(code.innerText).then(() => {
          const originalHTML = button.innerHTML;
          button.innerHTML =
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check" viewBox="0 0 16 16"><path d="M10.97 4.97a.75.75 0 0 1 1.07 1.05l-3.99 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 0 1 .02-.022z"/></svg>';
          setTimeout(() => {
            button.innerHTML = originalHTML;
          }, 2000);
        });
      }
    }
  }

  private _handleExpirySelect(e: CustomEvent) {
    const item = e.detail.item as SlMenuItem;
    this.newKeyExpiry = item.value;
    this.newKeyExpiryLabel = item.textContent?.trim() ?? 'Never';
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

      if (this.apiKeys.length === 0) {
        return html`
          <sl-alert variant="primary" open>
            <sl-icon slot="icon" name="info-circle"></sl-icon>
            No API keys created yet.
            <a
              href="#"
              @click=${(e: Event) => {
                e.preventDefault();
                this.isCreateModalOpen = true;
              }}
              >Add an API Key</a
            >
          </sl-alert>
        `;
      }

      return html`
        <sl-card class="table-card">
          <table class="styled-table">
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
      <view-header headerText="API Keys">
        <div slot="main-column">
          <sl-button
            variant="primary"
            @click=${() => {
              this.isCreateModalOpen = true;
            }}
            >Create New API Key</sl-button
          >
        </div>
      </view-header>
      <div class="column-layout">
        <div class="main-column">${renderContent()}</div>
        <div class="side-column"></div>
      </div>

      <sl-dialog label="Create API Key" .open=${this.isCreateModalOpen}>
        <sl-input
          autofocus
          style="margin-bottom: 1rem;"
          label="Key Name"
          placeholder="Enter a name for your key"
          .value=${this.newKeyName}
          @sl-input=${(e: Event) =>
            (this.newKeyName = (e.target as HTMLInputElement).value)}
          @keydown=${(e: KeyboardEvent) => {
            if (e.key === 'Enter' && this.newKeyName) {
              this.handleCreateApiKey();
            }
          }}
        ></sl-input>
        <label class="form-label">Key Expiry</label>
        <sl-dropdown class="expiry-dropdown">
          <sl-button slot="trigger" caret>${this.newKeyExpiryLabel}</sl-button>
          <sl-menu @sl-select=${this._handleExpirySelect}>
            <sl-menu-item value="never">Never</sl-menu-item>
            <sl-menu-item value="7days">7 Days</sl-menu-item>
            <sl-menu-item value="30days">30 Days</sl-menu-item>
            <sl-menu-item value="90days">90 Days</sl-menu-item>
          </sl-menu>
        </sl-dropdown>
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
          .disabled=${!this.newKeyName}
          >Create</sl-button
        >
      </sl-dialog>

      <sl-dialog
        label="API Key Created"
        .open=${this.isShowKeyModalOpen && this.newlyCreatedKey}
        @sl-hide=${() => (this.isShowKeyModalOpen = false)}
      >
        <p>Here is your new API key:</p>
        <div class="code-container">
          <pre><code>${this.newlyCreatedKey?.key}</code></pre>
          <button class="copy-btn" @click=${this._copyKey}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              fill="currentColor"
              class="bi bi-clipboard"
              viewBox="0 0 16 16"
            >
              <path
                d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"
              />
              <path
                d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"
              />
            </svg>
          </button>
        </div>
        <div class="warning-text">
          <sl-icon name="exclamation-triangle"></sl-icon>
          <span>Please copy it now. You will not be able to see it again.</span>
        </div>
        <sl-button
          slot="footer"
          variant="primary"
          autofocus
          @click=${() => (this.isShowKeyModalOpen = false)}
          >I have copied my key</sl-button
        >
      </sl-dialog>
    `;
  }

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      .loading-indicator {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
      }
      .form-label {
        font-size: var(--sl-input-label-font-size-medium);
        display: inline-block;
        color: var(--sl-input-label-color);
        margin-bottom: var(--sl-spacing-3x-small);
      }
      .expiry-dropdown {
        display: block;
        margin-bottom: 1rem;
      }
      .expiry-dropdown::part(trigger) {
        width: 100%;
      }
      .expiry-dropdown sl-button {
        width: 100%;
        text-align: left;
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
      .code-container {
        position: relative;
        background-color: var(--sl-color-neutral-100);
        border-radius: var(--sl-border-radius-medium);
        margin: 1rem 0;
      }
      .code-container pre {
        margin: 0;
        padding: var(--sl-spacing-medium);
        white-space: pre-wrap;
        word-break: break-all;
      }
      .copy-btn {
        position: absolute;
        top: var(--sl-spacing-x-small);
        right: var(--sl-spacing-x-small);
        background: none;
        border: none;
        color: var(--sl-color-neutral-600);
        cursor: pointer;
        padding: var(--sl-spacing-2x-small);
        border-radius: var(--sl-border-radius-circle);
      }
      .copy-btn:hover {
        background-color: var(--sl-color-neutral-200);
      }
      .warning-text {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-x-small);
        color: var(--sl-color-neutral-600);
        margin-top: var(--sl-spacing-medium);
        font-size: var(--sl-font-size-small);
      }
    `,
  ];
}
