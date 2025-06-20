import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { repeat } from 'lit/directives/repeat.js';
import { getApiKeys, createApiKey, deleteApiKey, ApiKey } from '../../../api';
import '@vaadin/button';
import '@vaadin/dialog';
import '@vaadin/text-field';
import '@vaadin/select';
import '@vaadin/list-box';
import '@vaadin/item';
import '@vaadin/date-picker';

@customElement('api-keys-view')
export class ApiKeysView extends LitElement {
    @state()
    private apiKeys: ApiKey[] = [];

    @state()
    private isLoading = true;

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
        try {
            this.apiKeys = await getApiKeys();
        } catch (error) {
            console.error('Failed to fetch API keys:', error);
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
        return html`
            <div class="container">
                <div class="card">
                    <div class="card-header">
                        <h3>API Keys</h3>
                        <vaadin-button theme="primary" @click=${() => { this.isCreateModalOpen = true; }}>Create New API Key</vaadin-button>
                    </div>
                    <div class="card-body">
                        ${when(
                            this.isLoading,
                            () => html`<p>Loading...</p>`,
                            () => html`
                                <table class="table">
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
                                                    <td>${key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}</td>
                                                    <td>${key.expires_at ? new Date(key.expires_at).toLocaleDateString() : 'Never'}</td>
                                                    <td>
                                                        <vaadin-button theme="error" @click=${() => this.handleDeleteApiKey(key.id)}>Revoke</vaadin-button>
                                                    </td>
                                                </tr>
                                            `
                                        )}
                                    </tbody>
                                </table>
                            `
                        )}
                    </div>
                </div>
            </div>

            <vaadin-dialog
                header-title="Create API Key"
                .opened=${this.isCreateModalOpen}
                @opened-changed=${(e: CustomEvent) => this.isCreateModalOpen = e.detail.value}
                .renderer=${(root: HTMLElement) => {
                    root.innerHTML = `
                        <div>
                            <vaadin-text-field label="Key Name" .value=${this.newKeyName} @value-changed=${(e: CustomEvent) => this.newKeyName = e.detail.value}></vaadin-text-field>
                            <vaadin-select label="Expiration" .value=${this.newKeyExpiry} @value-changed=${(e: CustomEvent) => this.newKeyExpiry = e.detail.value}>
                                <vaadin-list-box>
                                    <vaadin-item value="never">Never</vaadin-item>
                                    <vaadin-item value="7days">7 Days</vaadin-item>
                                    <vaadin-item value="30days">30 Days</vaadin-item>
                                    <vaadin-item value="90days">90 Days</vaadin-item>
                                    <vaadin-item value="custom">Custom Date</vaadin-item>
                                </vaadin-list-box>
                            </vaadin-select>
                            ${this.newKeyExpiry === 'custom' ?
                                `<vaadin-date-picker label="Custom Expiry Date" .value=${this.newCustomExpiry} @value-changed=${(e: CustomEvent) => this.newCustomExpiry = e.detail.value}></vaadin-date-picker>` : ''
                            }
                        </div>
                    `;
                }}
                .footerRenderer=${(root: HTMLElement) => {
                    root.innerHTML = `
                        <vaadin-button @click=${() => { this.isCreateModalOpen = false; }}>Cancel</vaadin-button>
                        <vaadin-button theme="primary" @click=${this.handleCreateApiKey}>Create</vaadin-button>
                    `;
                }}
            ></vaadin-dialog>

            <vaadin-dialog
                header-title="API Key Created"
                .opened=${this.isShowKeyModalOpen && this.newlyCreatedKey}
                @opened-changed=${(e: CustomEvent) => this.isShowKeyModalOpen = e.detail.value}
                .renderer=${(root: HTMLElement) => {
                    root.innerHTML = `
                        <div>
                            <p>Here is your new API key. Please copy it now, you will not be able to see it again.</p>
                            <pre><code>${this.newlyCreatedKey?.key}</code></pre>
                        </div>
                    `;
                }}
                .footerRenderer=${(root: HTMLElement) => {
                    root.innerHTML = `
                        <vaadin-button theme="primary" @click=${() => { this.isShowKeyModalOpen = false; }}>Close</vaadin-button>
                    `;
                }}
            ></vaadin-dialog>
        `;
    }

    static styles = css`
        .container {
            padding: 2rem;
        }
        .card {
            margin-top: 1rem;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
    `;
}
