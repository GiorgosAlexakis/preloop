var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var AIModelsView_1;
import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { repeat } from 'lit/directives/repeat.js';
import { getAIModels, getAIModelGatewayUsageSummary, getAIModelRuntimeSessions, updateAIModel, deleteAIModel, } from '../../../api';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '../../../components/add-ai-model-modal';
import { unifiedWebSocketManager } from '../../../services/unified-websocket-manager';
import consoleStyles from '../../../styles/console-styles.css?inline';
let AIModelsView = AIModelsView_1 = class AIModelsView extends LitElement {
    constructor() {
        super(...arguments);
        this.INFO_ALERT_DISMISSED_KEY = 'preloop-models-info-alert-dismissed';
        this._isInfoAlertOpen = false;
        this.models = [];
        this.isLoading = true;
        this.error = null;
        this.isModalOpen = false;
        this.editingModel = null;
        this.isDeleteConfirmOpen = false;
        this.modelToDelete = null;
        this.modelOverview = new Map();
        this.refreshTimer = null;
        this.refreshInFlight = false;
    }
    async connectedCallback() {
        super.connectedCallback();
        const isDismissed = localStorage.getItem(this.INFO_ALERT_DISMISSED_KEY);
        this._isInfoAlertOpen = isDismissed !== 'true';
        void this.fetchModels();
        this.connectRealtime();
    }
    disconnectedCallback() {
        super.disconnectedCallback();
        this.unsubscribeRealtime?.();
        if (this.refreshTimer !== null) {
            window.clearTimeout(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
    connectRealtime() {
        const scheduleRefresh = () => this.scheduleRefresh();
        const unsubscribers = [
            unifiedWebSocketManager.subscribe('gateway_activity', scheduleRefresh),
            unifiedWebSocketManager.subscribe('budget_health', scheduleRefresh),
            unifiedWebSocketManager.subscribe('runtime_sessions', scheduleRefresh),
            unifiedWebSocketManager.subscribe('managed_agents', scheduleRefresh),
            unifiedWebSocketManager.subscribe('system', scheduleRefresh, (message) => message?.type === 'authenticated'),
        ];
        this.unsubscribeRealtime = () => {
            for (const unsubscribe of unsubscribers) {
                unsubscribe();
            }
        };
        void unifiedWebSocketManager.connect();
    }
    scheduleRefresh() {
        if (this.refreshTimer !== null) {
            window.clearTimeout(this.refreshTimer);
        }
        this.refreshTimer = window.setTimeout(() => {
            this.refreshTimer = null;
            void this.fetchModels({ preserveLoadingState: true });
        }, 250);
    }
    async fetchModels(options = {}) {
        if (this.refreshInFlight) {
            return;
        }
        this.refreshInFlight = true;
        if (!options.preserveLoadingState) {
            this.isLoading = true;
        }
        this.error = null;
        try {
            this.models = await getAIModels();
            const overviewEntries = await Promise.all(this.models.map(async (model) => {
                const [summary, sessions] = await Promise.all([
                    getAIModelGatewayUsageSummary(model.id, this.getOverviewParams()),
                    getAIModelRuntimeSessions(model.id, {
                        ...this.getOverviewParams(),
                        status: 'active',
                        limit: 100,
                    }),
                ]);
                return [
                    model.id,
                    {
                        summary,
                        activeSessions: sessions.total,
                    },
                ];
            }));
            this.modelOverview = new Map(overviewEntries);
        }
        catch (error) {
            this.error =
                error instanceof Error ? error.message : 'Failed to fetch AI models';
            this.modelOverview = new Map();
        }
        finally {
            this.isLoading = false;
            this.refreshInFlight = false;
        }
    }
    getOverviewParams() {
        const endDate = new Date();
        const startDate = new Date(endDate);
        startDate.setDate(startDate.getDate() - (AIModelsView_1.FLEET_WINDOW_DAYS - 1));
        return {
            startDate: startDate.toISOString(),
            endDate: endDate.toISOString(),
        };
    }
    get overviewWindowLabel() {
        return `Last ${AIModelsView_1.FLEET_WINDOW_DAYS} days`;
    }
    get fleetRequestCount() {
        return [...this.modelOverview.values()].reduce((total, item) => total + item.summary.total_requests, 0);
    }
    get fleetSpend() {
        return [...this.modelOverview.values()].reduce((total, item) => total + item.summary.estimated_cost, 0);
    }
    get activeFleetSessions() {
        return [...this.modelOverview.values()].reduce((total, item) => total + item.activeSessions, 0);
    }
    get activeModelsCount() {
        return [...this.modelOverview.values()].filter((item) => item.summary.total_requests > 0).length;
    }
    get modelsNeedingAttentionCount() {
        return [...this.modelOverview.values()].filter((item) => item.summary.failed_requests > 0).length;
    }
    formatCurrency(value) {
        return `$${(value || 0).toFixed(2)}`;
    }
    formatNumber(value) {
        return Intl.NumberFormat().format(value || 0);
    }
    getModelOverview(modelId) {
        return this.modelOverview.get(modelId);
    }
    getHealthVariant(modelId) {
        const overview = this.getModelOverview(modelId);
        if (!overview || overview.summary.total_requests === 0) {
            return 'neutral';
        }
        if (overview.summary.failed_requests > 0) {
            return 'warning';
        }
        return 'success';
    }
    getHealthLabel(modelId) {
        const overview = this.getModelOverview(modelId);
        if (!overview || overview.summary.total_requests === 0) {
            return 'Idle';
        }
        if (overview.summary.failed_requests > 0) {
            return 'Attention';
        }
        return 'Healthy';
    }
    renderFleetOverview() {
        return html `
      <div class="summary-grid">
        <sl-card class="summary-card">
          <div class="metric-label">Configured models</div>
          <div class="metric-value">
            ${this.formatNumber(this.models.length)}
          </div>
          <div class="metric-subtext">${this.overviewWindowLabel}</div>
        </sl-card>
        <sl-card class="summary-card">
          <div class="metric-label">Models with traffic</div>
          <div class="metric-value">
            ${this.formatNumber(this.activeModelsCount)}
          </div>
          <div class="metric-subtext">
            ${this.formatNumber(this.modelsNeedingAttentionCount)} need
            attention
          </div>
        </sl-card>
        <sl-card class="summary-card">
          <div class="metric-label">Fleet requests</div>
          <div class="metric-value">
            ${this.formatNumber(this.fleetRequestCount)}
          </div>
          <div class="metric-subtext">
            ${this.formatNumber(this.activeFleetSessions)} active sessions
          </div>
        </sl-card>
        <sl-card class="summary-card">
          <div class="metric-label">Fleet spend</div>
          <div class="metric-value">
            ${this.formatCurrency(this.fleetSpend)}
          </div>
          <div class="metric-subtext">${this.overviewWindowLabel}</div>
        </sl-card>
      </div>
    `;
    }
    render() {
        const renderContent = () => {
            if (this.isLoading) {
                return html `<sl-card
          ><div style="display: flex; justify-content: center; padding: 2rem;">
            <sl-spinner></sl-spinner></div
        ></sl-card>`;
            }
            if (this.error) {
                return html `
          <sl-alert variant="danger" open>
            <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
            <strong>Error:</strong> ${this.error}
          </sl-alert>
        `;
            }
            return this.renderModelsList();
        };
        return html `
      <view-header headerText="AI Models" width="narrow">
        <div slot="main-column">
          <sl-button variant="primary" @click=${this.openAddModelModal}>
            <sl-icon slot="prefix" name="plus-lg"></sl-icon> Add Model
          </sl-button>
        </div>
      </view-header>
      <div class="column-layout narrow">
        <div class="main-column">
          <div class="page">
            ${this.isLoading || this.error ? null : this.renderFleetOverview()}
            ${renderContent()}
          </div>
        </div>
        <div class="side-column"></div>
      </div>
      <add-ai-model-modal
        ?open=${this.isModalOpen}
        .model=${this.editingModel}
        @model-created=${this._handleModelSaved}
        @model-updated=${this._handleModelSaved}
        @close-modal=${this.closeModal}
      ></add-ai-model-modal>
      ${this.renderDeleteConfirm()}
    `;
    }
    renderModelsList() {
        return html `
      <sl-card class="table-card">
        ${when(this.models.length === 0, () => html ` <sl-alert variant="primary" open>
              <sl-icon slot="icon" name="info-circle"></sl-icon>
              No AI Models configured yet.
              <a
                href="#"
                @click=${(e) => {
            e.preventDefault();
            this.openAddModelModal();
        }}
                >Add a Model</a
              >
            </sl-alert>`, () => html `
            <table class="styled-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Provider</th>
                  <th>Fleet health</th>
                  <th>Usage</th>
                  <th>Default</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${repeat(this.models, (model) => model.id, (model) => html `
                    <tr>
                      <td>
                        <a
                          class="model-link"
                          href=${`/console/settings/ai-models/${model.id}`}
                        >
                          ${model.name}
                        </a>
                        <div class="model-meta">${model.model_identifier}</div>
                      </td>
                      <td>${model.provider_name}</td>
                      <td>
                        <div class="cell-stack">
                          <div class="badge-row">
                            <sl-badge
                              variant=${this.getHealthVariant(model.id)}
                              pill
                            >
                              ${this.getHealthLabel(model.id)}
                            </sl-badge>
                            ${this.getModelOverview(model.id)?.activeSessions
            ? html `
                                  <sl-badge variant="primary" pill>
                                    ${this.formatNumber(this.getModelOverview(model.id)
                ?.activeSessions)}
                                    active sessions
                                  </sl-badge>
                                `
            : null}
                          </div>
                          <div class="cell-secondary">
                            ${this.formatNumber(this.getModelOverview(model.id)?.summary
            .successful_requests)}
                            successful ·
                            ${this.formatNumber(this.getModelOverview(model.id)?.summary
            .failed_requests)}
                            failed
                          </div>
                        </div>
                      </td>
                      <td>
                        <div class="cell-stack">
                          <div class="cell-primary">
                            ${this.formatNumber(this.getModelOverview(model.id)?.summary
            .total_requests)}
                            requests
                          </div>
                          <div class="cell-secondary">
                            ${this.formatNumber(this.getModelOverview(model.id)?.summary
            .token_usage.total_tokens)}
                            tokens ·
                            ${this.formatCurrency(this.getModelOverview(model.id)?.summary
            .estimated_cost)}
                          </div>
                        </div>
                      </td>
                      <td>
                        ${when(model.is_default, () => html `<sl-badge variant="success" pill
                              >Default</sl-badge
                            >`, () => html `
                            <sl-button
                              size="small"
                              @click=${() => this.handleSetDefault(model)}
                            >
                              Set as default
                            </sl-button>
                          `)}
                      </td>
                      <td>
                        <div class="actions">
                          <sl-button
                            size="small"
                            href=${`/console/settings/ai-models/${model.id}`}
                          >
                            View
                          </sl-button>
                          <sl-button
                            size="small"
                            circle
                            @click=${() => this.openEditModal(model)}
                          >
                            <sl-icon name="pencil"></sl-icon>
                          </sl-button>
                          <sl-button
                            variant="danger"
                            size="small"
                            circle
                            @click=${() => this.openDeleteConfirm(model)}
                          >
                            <sl-icon name="trash"></sl-icon>
                          </sl-button>
                        </div>
                      </td>
                    </tr>
                  `)}
              </tbody>
            </table>
          `)}
      </sl-card>
    `;
    }
    renderDeleteConfirm() {
        return html `
      <sl-dialog
        label="Delete Model"
        .open=${this.isDeleteConfirmOpen}
        @sl-hide=${() => (this.isDeleteConfirmOpen = false)}
      >
        Are you sure you want to delete the model "${this.modelToDelete?.name}"?
        <sl-button
          slot="footer"
          @click=${() => (this.isDeleteConfirmOpen = false)}
          >Cancel</sl-button
        >
        <sl-button slot="footer" variant="danger" @click=${this.deleteModel}
          >Delete</sl-button
        >
      </sl-dialog>
    `;
    }
    openAddModelModal() {
        this.editingModel = null;
        this.isModalOpen = true;
    }
    openEditModal(model) {
        this.editingModel = model;
        this.isModalOpen = true;
    }
    closeModal() {
        this.isModalOpen = false;
        this.editingModel = null;
    }
    async _handleModelSaved() {
        this.closeModal();
        await this.fetchModels();
    }
    openDeleteConfirm(model) {
        this.modelToDelete = model;
        this.isDeleteConfirmOpen = true;
    }
    async handleSetDefault(model) {
        try {
            await updateAIModel(model.id, { is_default: true });
            await this.fetchModels();
        }
        catch (error) {
            console.error('Failed to set default model:', error);
            this.error =
                error instanceof Error ? error.message : 'Failed to set default model';
        }
    }
    async deleteModel() {
        if (this.modelToDelete) {
            try {
                await deleteAIModel(this.modelToDelete.id);
                await this.fetchModels();
            }
            catch (error) {
                console.error('Failed to delete model:', error);
                this.error =
                    error instanceof Error ? error.message : 'Failed to delete model';
            }
        }
        this.isDeleteConfirmOpen = false;
        this.modelToDelete = null;
    }
    handleInfoAlertHide() {
        localStorage.setItem(this.INFO_ALERT_DISMISSED_KEY, 'true');
        this._isInfoAlertOpen = false;
    }
};
AIModelsView.FLEET_WINDOW_DAYS = 30;
AIModelsView.styles = [
    unsafeCSS(consoleStyles),
    css `
      table {
        width: 100%;
        border-collapse: collapse;
      }
      .page {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-large);
      }
      .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: var(--sl-spacing-medium);
      }
      .summary-card::part(base),
      .table-card::part(base) {
        height: 100%;
      }
      .metric-label {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }
      .metric-value {
        color: var(--sl-color-neutral-900);
        font-size: 1.6rem;
        font-weight: 700;
        line-height: 1.1;
        margin-top: var(--sl-spacing-2x-small);
      }
      .metric-subtext {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        margin-top: var(--sl-spacing-small);
      }
      .styled-table th,
      .styled-table td {
        padding: var(--sl-spacing-medium);
        text-align: left;
        border-bottom: 1px solid var(--sl-color-neutral-200);
      }
      .styled-table th {
        background-color: var(--sl-color-neutral-50);
        font-weight: var(--sl-font-weight-semibold);
      }
      .styled-table td {
        vertical-align: top;
      }
      .styled-table tr:last-child td {
        border-bottom: none;
      }
      .actions {
        display: flex;
        gap: var(--sl-spacing-x-small);
        justify-content: flex-end;
      }
      .empty-state a {
        color: var(--sl-color-primary-600);
        text-decoration: none;
        cursor: pointer;
      }
      .model-link {
        color: var(--sl-color-primary-700);
        text-decoration: none;
        font-weight: var(--sl-font-weight-semibold);
      }
      .model-link:hover {
        text-decoration: underline;
      }
      .empty-state a:hover {
        text-decoration: underline;
      }
      .info-header {
        margin-bottom: var(--sl-spacing-large);
      }
      .model-meta {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        margin-top: var(--sl-spacing-2x-small);
        overflow-wrap: anywhere;
      }
      .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: var(--sl-spacing-2x-small);
      }
      .cell-stack {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-2x-small);
      }
      .cell-primary {
        color: var(--sl-color-neutral-900);
        font-weight: var(--sl-font-weight-semibold);
      }
      .cell-secondary {
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }
    `,
];
__decorate([
    state()
], AIModelsView.prototype, "_isInfoAlertOpen", void 0);
__decorate([
    state()
], AIModelsView.prototype, "models", void 0);
__decorate([
    state()
], AIModelsView.prototype, "isLoading", void 0);
__decorate([
    state()
], AIModelsView.prototype, "error", void 0);
__decorate([
    state()
], AIModelsView.prototype, "isModalOpen", void 0);
__decorate([
    state()
], AIModelsView.prototype, "editingModel", void 0);
__decorate([
    state()
], AIModelsView.prototype, "isDeleteConfirmOpen", void 0);
__decorate([
    state()
], AIModelsView.prototype, "modelToDelete", void 0);
__decorate([
    state()
], AIModelsView.prototype, "modelOverview", void 0);
AIModelsView = AIModelsView_1 = __decorate([
    customElement('ai-models-view')
], AIModelsView);
export { AIModelsView };
