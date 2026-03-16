var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/tag/tag.js';
import '@shoelace-style/shoelace/dist/components/button-group/button-group.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';
import '../../components/project-filter-modal.ts';
import '../../components/duplicate-stats-chart.ts';
import '../../components/resolve-issue-modal.ts';
import '../../components/issue-detail-view.ts';
import '../../components/pagination-controls.ts';
import '../../components/view-header.ts';
import { listProjects, listIssueDuplicates, checkAIVerdict, dismissDuplicatePair, listOrganizations, } from '../../api';
import { DEFAULT_SIMILARITY_THRESHOLD, DEFAULT_SIMILARITY_THRESHOLD_CHARTS, } from '../../config';
import { renderVerdict, getStatusVariant, } from '../../utils/verdict';
import consoleStyles from '../../styles/console-styles.css?inline';
let IssuesView = class IssuesView extends LitElement {
    constructor() {
        super(...arguments);
        this.INFO_ALERT_DISMISSED_KEY = 'preloop-issues-info-alert-dismissed';
        this._isInfoAlertOpen = false;
        this._duplicates = [];
        this._aiVerdicts = {};
        this._loadingVerdicts = {};
        this._loading = false;
        this._error = null;
        this._currentPage = 1;
        this._pageSize = 10;
        this._hasMorePages = true;
        this._expandedRowKey = null;
        this._isFilterModalOpen = false;
        this._resolutionSummary = null;
        this._isResolveModalOpen = false;
        this._selectedPair = null;
        this._selectedProjectIds = [];
        this._selectedStatus = 'opened';
        this._selectedResolutionStatus = 'all';
        this._similarityThreshold = DEFAULT_SIMILARITY_THRESHOLD;
        this._similarityThresholdCharts = DEFAULT_SIMILARITY_THRESHOLD_CHARTS;
        this._allProjects = [];
        this._hasProjects = true;
        this._organizations = [];
        this._initialLoadComplete = false;
        this.handlePopState = () => {
            this.parseUrlAndUpdateState();
            this.fetchDuplicates();
        };
    }
    async connectedCallback() {
        super.connectedCallback();
        const isDismissed = localStorage.getItem(this.INFO_ALERT_DISMISSED_KEY);
        this._isInfoAlertOpen = isDismissed !== 'true';
        // Fetch projects first so we can map short IDs from the URL to full IDs.
        await this.fetchProjects();
        this.parseUrlAndUpdateState();
        this.fetchDuplicates();
        this.fetchOrganizations();
        this._initialLoadComplete = true;
        window.addEventListener('popstate', this.handlePopState);
    }
    disconnectedCallback() {
        super.disconnectedCallback();
        window.removeEventListener('popstate', this.handlePopState);
        // Check if we are still on the issues path before cleaning up.
        // This prevents a race condition where the URL of the *next* page is cleaned.
        if (window.location.pathname.includes('/issues')) {
            window.history.replaceState({}, '', window.location.pathname);
        }
    }
    parseUrlAndUpdateState() {
        const params = new URLSearchParams(window.location.search);
        this._currentPage = parseInt(params.get('page') || '1', 10);
        this._selectedStatus = (params.get('status') || 'opened');
        this._selectedResolutionStatus = (params.get('resolution') || 'all');
        const shortProjectIds = params.get('projects');
        if (shortProjectIds && this._allProjects.length > 0) {
            const shortIdSet = new Set(shortProjectIds.split(','));
            this._selectedProjectIds = this._allProjects
                .filter((p) => shortIdSet.has(p.id.split('-')[0]))
                .map((p) => p.id);
        }
        else {
            this._selectedProjectIds = [];
        }
        this._expandedRowKey = params.get('selectedPair') || null;
    }
    _updateUrl() {
        // Only update the URL if we are on the issues page.
        if (!window.location.pathname.includes('/issues')) {
            return;
        }
        const params = new URLSearchParams();
        params.set('page', this._currentPage.toString());
        params.set('status', this._selectedStatus);
        if (this._selectedResolutionStatus !== 'all') {
            params.set('resolution', this._selectedResolutionStatus);
        }
        if (this._selectedProjectIds.length > 0) {
            const shortProjectIds = this._selectedProjectIds.map((id) => id.split('-')[0]);
            params.set('projects', shortProjectIds.join(','));
        }
        if (this._expandedRowKey) {
            params.set('selectedPair', this._expandedRowKey);
        }
        else {
            params.delete('selectedPair');
        }
        const newUrl = `${window.location.pathname}?${params.toString()}`;
        window.history.pushState({}, '', newUrl);
    }
    async fetchInitialData() {
        this.fetchDuplicates();
        this.fetchProjects();
        this.fetchOrganizations();
    }
    async fetchProjects() {
        try {
            this._allProjects = await listProjects();
            this._hasProjects = this._allProjects.length > 0;
        }
        catch (error) {
            console.error('Failed to fetch project list:', error);
            this._hasProjects = false; // Set to false on error
        }
    }
    async fetchOrganizations() {
        try {
            this._organizations = await listOrganizations();
        }
        catch (error) {
            console.error('Failed to fetch organization list:', error);
        }
    }
    async fetchDuplicates() {
        this._loading = true;
        this._error = null;
        const skip = (this._currentPage - 1) * this._pageSize;
        try {
            const data = await listIssueDuplicates({
                limit: this._pageSize,
                skip: skip,
                project_ids: this._selectedProjectIds,
                status: this._selectedStatus,
                resolution: this._selectedResolutionStatus,
                similarity_threshold: this._similarityThreshold,
            });
            this._duplicates = data.duplicates;
            this._hasMorePages = data.duplicates.length === this._pageSize;
            this._updateUrl(); // Update URL after fetching
            this.fetchAIModelVerdicts(); // Fetch verdicts after getting duplicates
        }
        catch (error) {
            this._error =
                error instanceof Error ? error.message : 'An unknown error occurred.';
            console.error('Failed to fetch duplicate issues:', error);
        }
        finally {
            this._loading = false;
        }
    }
    async fetchAIModelVerdicts() {
        const newVerdicts = { ...this._aiVerdicts };
        const newLoadingVerdicts = { ...this._loadingVerdicts };
        const promises = this._duplicates.map((pair) => {
            const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
            if (newVerdicts[pairKey]) {
                return Promise.resolve();
            }
            newLoadingVerdicts[pairKey] = true;
            return checkAIVerdict(pair.issue1.id, pair.issue2.id)
                .then((verdict) => {
                newVerdicts[pairKey] = verdict;
            })
                .catch((error) => {
                console.error(`Failed to fetch AI verdict for ${pairKey}:`, error);
                // Store a failed state if needed, or just remove loading indicator
            })
                .finally(() => {
                newLoadingVerdicts[pairKey] = false;
            });
        });
        this._loadingVerdicts = newLoadingVerdicts;
        await Promise.all(promises);
        this._aiVerdicts = newVerdicts;
    }
    _toggleRow(pairKey) {
        if (this._expandedRowKey === pairKey) {
            this._expandedRowKey = null;
        }
        else {
            this._expandedRowKey = pairKey;
        }
        this._updateUrl();
    }
    _openResolveModal(pair) {
        this._selectedPair = pair;
        this._isResolveModalOpen = true;
    }
    async _handleDismiss(pair) {
        // Optimistically remove the pair from the list for a responsive UI
        const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
        const originalDuplicates = [...this._duplicates];
        this._duplicates = this._duplicates.filter((p) => `${p.issue1.id}-${p.issue2.id}` !== pairKey);
        try {
            await dismissDuplicatePair(pair.issue1.id, pair.issue2.id);
        }
        catch (error) {
            console.error('Failed to dismiss pair:', error);
            // If the API call fails, revert the UI change
            this._duplicates = originalDuplicates;
            // Optionally, show an error toast to the user here
        }
    }
    _handleModalClose() {
        this._isResolveModalOpen = false;
        this._selectedPair = null;
    }
    async handleResolution(e) {
        if (e.detail.summary) {
            this._resolutionSummary = e.detail.summary;
        }
        this.fetchDuplicates();
    }
    renderDetailRow(pair) {
        const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
        const aiVerdict = this._aiVerdicts[pairKey];
        const loadingVerdict = this._loadingVerdicts[pairKey];
        return html `
      <issue-detail-view
        .pair=${pair}
        .aiVerdict=${aiVerdict}
        .loadingVerdict=${loadingVerdict}
        @resolve=${() => this._openResolveModal(pair)}
        @dismiss=${() => this._handleDismiss(pair)}
      ></issue-detail-view>
    `;
    }
    _openFilterModal() {
        this._isFilterModalOpen = true;
    }
    _removeProjectFilter(projectIdToRemove) {
        this._selectedProjectIds = this._selectedProjectIds.filter((id) => id !== projectIdToRemove);
        this.fetchDuplicates();
    }
    _clearAllFilters() {
        this._selectedProjectIds = [];
        this.fetchDuplicates();
    }
    _handleProjectSelectedFromChart(event) {
        const { projectId } = event.detail;
        if (projectId && !this._selectedProjectIds.includes(projectId)) {
            this._selectedProjectIds = [...this._selectedProjectIds, projectId];
            this.fetchDuplicates();
        }
    }
    _renderActiveFilters() {
        if (this._selectedProjectIds.length === 0 &&
            this._selectedStatus === 'opened' &&
            this._selectedResolutionStatus === 'all') {
            return html ``;
        }
        const selectedProjects = this._selectedProjectIds
            .map((id) => this._allProjects.find((p) => p.id.toString() === id))
            .filter(Boolean);
        return html `
      <div class="active-filters">
        <span>Filtered by:</span>
        ${selectedProjects.map((project) => html `
            <sl-tag
              size="medium"
              removable
              @sl-remove=${() => this._removeProjectFilter(project.id.toString())}
            >
              ${project.name}
            </sl-tag>
          `)}
        ${this._selectedStatus !== 'opened'
            ? html `
              <sl-tag
                size="medium"
                removable
                @sl-remove=${() => this._clearStatusFilter()}
              >
                ${this._selectedStatus === 'closed' ? 'Closed' : 'All'}
              </sl-tag>
            `
            : ''}
        ${this._selectedResolutionStatus !== 'all'
            ? html `
              <sl-tag
                size="medium"
                removable
                @sl-remove=${() => this._clearResolutionFilter()}
              >
                ${this._selectedResolutionStatus === 'resolved'
                ? 'Resolved'
                : 'Unresolved'}
              </sl-tag>
            `
            : ''}
        <sl-button size="small" pill @click=${this._clearAllFilters}
          >Clear all</sl-button
        >
      </div>
    `;
    }
    _clearStatusFilter() {
        this._selectedStatus = 'opened';
        this.fetchDuplicates();
    }
    _clearResolutionFilter() {
        this._selectedResolutionStatus = 'all';
        this.fetchDuplicates();
    }
    handleInfoAlertHide() {
        localStorage.setItem(this.INFO_ALERT_DISMISSED_KEY, 'true');
        this._isInfoAlertOpen = false;
    }
    _goToPreviousPage() {
        if (this._currentPage > 1) {
            this._currentPage--;
            this.fetchDuplicates();
        }
    }
    _goToNextPage() {
        this._currentPage++;
        this.fetchDuplicates();
    }
    render() {
        return html `
      <view-header headerText="Issue Similarity" width="wide">
        <div slot="main-column">
          <sl-button @click=${this._openFilterModal}>
            <sl-icon slot="prefix" name="filter"></sl-icon>
            Filter
          </sl-button>
        </div>
      </view-header>
      <div class="column-layout wide">
        <div class="main-column">
          <div class="container">
            <sl-alert
              variant="primary"
              ?open=${this._isInfoAlertOpen}
              closable
              @sl-hide=${this.handleInfoAlertHide}
            >
              <sl-icon slot="icon" name="info-circle"></sl-icon>
              <strong>Find similar issues and resolve duplicates</strong><br />
              Identify similar and potential duplicate issues across your
              projects. Review each suggested pair, check the similarity score,
              and use the AI review to resolve or dismiss the suggestion.
            </sl-alert>

            ${when(this._initialLoadComplete && this._hasProjects, () => html `
                <sl-card class="embedding-card">
                  <div slot="header" class="chart-header">
                    Similar Issues per Project
                    <sl-tooltip
                      content="Showing issues with a similarity score of ${this
            ._similarityThresholdCharts * 100}% or higher."
                    >
                      <sl-icon name="question-circle"></sl-icon>
                    </sl-tooltip>
                  </div>
                  <duplicate-stats-chart
                    .hasProjects=${this._hasProjects}
                    .projectIds=${this._selectedProjectIds}
                    .selectedStatus=${this._selectedStatus}
                    .selectedResolution=${this._selectedResolutionStatus}
                    .similarityThreshold=${this._similarityThresholdCharts}
                    ?interactive=${true}
                    @project-selected=${this._handleProjectSelectedFromChart}
                  ></duplicate-stats-chart>
                </sl-card>
              `)}
            ${when(this._resolutionSummary, () => html `
                <sl-alert
                  variant="success"
                  open
                  closable
                  @sl-after-hide=${() => (this._resolutionSummary = null)}
                >
                  <sl-icon slot="icon" name="check-circle"></sl-icon>
                  ${this._resolutionSummary}
                </sl-alert>
              `)}
            ${this._renderActiveFilters()}
            ${when(this._loading, () => html `<div class="loading-overlay">
                  <sl-spinner></sl-spinner>
                  <span>Loading issues...</span>
                </div>`)}
            ${when(this._error, () => html `<div class="error">Error: ${this._error}</div>`)}
            ${when(!this._loading && !this._error, () => this._duplicates.length > 0
            ? html `
                    <sl-card class="table-card">
                      <table class="styled-table">
                        <thead>
                          <tr>
                            <th>Issue 1</th>
                            <th>Issue 2</th>
                            <th class="text-right">Similarity</th>
                            <th class="text-right">AI Review</th>
                            <th class="text-right">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          ${this._duplicates.map((pair) => {
                const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
                const verdict = this._aiVerdicts[pairKey];
                const isFaint = this._loadingVerdicts[pairKey];
                const isExpanded = this._expandedRowKey === pairKey;
                return html `
                              <tr
                                class="clickable-row ${isFaint
                    ? 'faint-row'
                    : ''} ${isExpanded ? 'row-expanded' : ''}"
                                @click=${() => this._toggleRow(pairKey)}
                              >
                                <td>
                                  <a
                                    href="${pair.issue1.meta_data?.url ||
                    pair.issue1.url}"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="issue-id-link"
                                    @click=${(e) => e.stopPropagation()}
                                  >
                                    <strong class="issue-id"
                                      >${pair.issue1.key}</strong
                                    >
                                    <sl-badge
                                      pill
                                      variant=${getStatusVariant(pair.issue1.status)}
                                      >${pair.issue1.status}</sl-badge
                                    >
                                  </a>
                                  <div class="issue-title">
                                    ${pair.issue1.title}
                                  </div>
                                </td>
                                <td>
                                  <a
                                    href="${pair.issue2.meta_data?.url ||
                    pair.issue2.url}"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    class="issue-id-link"
                                    @click=${(e) => e.stopPropagation()}
                                  >
                                    <strong class="issue-id"
                                      >${pair.issue2.key}</strong
                                    >
                                    <sl-badge
                                      pill
                                      variant=${getStatusVariant(pair.issue2.status)}
                                      >${pair.issue2.status}</sl-badge
                                    >
                                  </a>
                                  <div class="issue-title">
                                    ${pair.issue2.title}
                                  </div>
                                </td>
                                <td class="text-right">
                                  ${(pair.similarity * 100).toFixed(2)}%
                                </td>
                                <td
                                  class="text-right"
                                  id="verdict-${pair.issue1.id}-${pair.issue2
                    .id}"
                                >
                                  ${pair.similarity >= 0.999
                    ? html `<sl-badge
                                        variant="warning"
                                        style="--sl-color-warning-text: var(--sl-color-orange-50); --sl-color-warning-600: var(--sl-color-orange-700);"
                                        >Identical</sl-badge
                                      >`
                    : renderVerdict(verdict)}
                                </td>
                                <td>
                                  <div class="actions-container">
                                    ${when(!verdict?.resolution, () => html `
                                        <sl-button
                                          size="small"
                                          variant="primary"
                                          @click=${(e) => {
                    e.stopPropagation();
                    this._openResolveModal(pair);
                }}
                                          >Resolve</sl-button
                                        >
                                        <sl-tooltip
                                          content="Dismiss this suggestion"
                                        >
                                          <sl-icon-button
                                            name="x-circle"
                                            label="Dismiss"
                                            @click=${(e) => {
                    e.stopPropagation();
                    this._handleDismiss(pair);
                }}
                                          ></sl-icon-button>
                                        </sl-tooltip>
                                      `)}
                                  </div>
                                </td>
                              </tr>
                              ${when(isExpanded, () => html `
                                  <tr class="inline-detail-row">
                                    <td colspan="5">
                                      ${this.renderDetailRow(pair)}
                                    </td>
                                  </tr>
                                `)}
                            `;
            })}
                        </tbody>
                      </table>
                    </sl-card>
                    <pagination-controls
                      .currentPage=${this._currentPage}
                      .hasMorePages=${this._hasMorePages}
                      .loading=${this._loading}
                      @prev-page=${this._goToPreviousPage}
                      @next-page=${this._goToNextPage}
                    ></pagination-controls>
                  `
            : html `
                    <sl-alert variant="primary" open>
                      <sl-icon slot="icon" name="info-circle"></sl-icon>
                      ${this._hasProjects
                ? 'No duplicate issues found for the current filters.'
                : unsafeHTML('No projects found. Did you <a href="/console/trackers">add a tracker</a>?')}
                    </sl-alert>
                  `)}
          </div>
        </div>
        <div class="side-column">
          ${when(this._expandedRowKey, () => {
            const expandedPair = this._duplicates.find((p) => `${p.issue1.id}-${p.issue2.id}` === this._expandedRowKey);
            return expandedPair
                ? html `
                    <div class="side-column-detail">
                      <sl-card>
                        <div slot="header">Issue Pair Details</div>
                        ${this.renderDetailRow(expandedPair)}
                      </sl-card>
                    </div>
                  `
                : '';
        }, () => html `
              <div class="side-column-detail">
                <sl-card class="full-width">
                  <div slot="header">Issue Pair Details</div>
                  <div class="placeholder-content">
                    <sl-icon name="info-circle"></sl-icon>
                    <p>Select an issue pair to see the details here.</p>
                  </div>
                </sl-card>
              </div>
            `)}
        </div>
      </div>
      <project-filter-modal
        .isOpen=${this._isFilterModalOpen}
        .allProjects=${this._allProjects}
        .organizations=${this._organizations}
        .projects=${this._allProjects}
        .selectedProjectIds=${this._selectedProjectIds}
        .selectedStatus=${this._selectedStatus}
        .selectedResolution=${this._selectedResolutionStatus}
        @on-close=${() => (this._isFilterModalOpen = false)}
        @on-apply=${this._applyFilters}
      ></project-filter-modal>
      <resolve-issue-modal
        .isOpen=${this._isResolveModalOpen}
        .duplicatePair=${this._selectedPair}
        @on-close=${() => (this._isResolveModalOpen = false)}
        @on-resolved=${this.handleResolution}
      ></resolve-issue-modal>
    `;
    }
    _applyFilters(event) {
        this._selectedProjectIds = event.detail.projectIds;
        this._selectedStatus = event.detail.status;
        this._selectedResolutionStatus = event.detail.resolution;
        this._isFilterModalOpen = false;
        this._currentPage = 1; // Reset to first page
        this.fetchDuplicates();
    }
};
IssuesView.styles = [
    unsafeCSS(consoleStyles),
    css `
      .table-card {
        width: 100%;
        --padding: 0;
        border-spacing: 0;
      }

      .styled-table th,
      .styled-table td {
        padding: var(--sl-spacing-medium);
        border-bottom: 1px solid var(--sl-color-neutral-200);
      }

      .styled-table .issue-id {
        font-weight: var(--sl-font-weight-semibold);
      }

      .issue-key {
        color: var(--sl-color-neutral-600);
      }

      .faint-row {
        opacity: 0.5;
        transition: opacity 0.3s ease-in-out;
      }

      .clickable-row {
        cursor: pointer;
      }
      .row-expanded {
        background-color: var(--sl-color-primary-50);
      }

      .loading-overlay {
        color: white;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        gap: var(--sl-spacing-medium);
        z-index: 10000;
      }

      sl-icon {
        font-size: 1rem;
      }

      .placeholder-content {
        text-align: center;
      }
    `,
];
__decorate([
    state()
], IssuesView.prototype, "_isInfoAlertOpen", void 0);
__decorate([
    state()
], IssuesView.prototype, "_duplicates", void 0);
__decorate([
    state()
], IssuesView.prototype, "_aiVerdicts", void 0);
__decorate([
    state()
], IssuesView.prototype, "_loadingVerdicts", void 0);
__decorate([
    state()
], IssuesView.prototype, "_loading", void 0);
__decorate([
    state()
], IssuesView.prototype, "_error", void 0);
__decorate([
    state()
], IssuesView.prototype, "_currentPage", void 0);
__decorate([
    state()
], IssuesView.prototype, "_pageSize", void 0);
__decorate([
    state()
], IssuesView.prototype, "_hasMorePages", void 0);
__decorate([
    state()
], IssuesView.prototype, "_expandedRowKey", void 0);
__decorate([
    state()
], IssuesView.prototype, "_isFilterModalOpen", void 0);
__decorate([
    state()
], IssuesView.prototype, "_resolutionSummary", void 0);
__decorate([
    state()
], IssuesView.prototype, "_isResolveModalOpen", void 0);
__decorate([
    state()
], IssuesView.prototype, "_selectedPair", void 0);
__decorate([
    state()
], IssuesView.prototype, "_selectedProjectIds", void 0);
__decorate([
    state()
], IssuesView.prototype, "_selectedStatus", void 0);
__decorate([
    state()
], IssuesView.prototype, "_selectedResolutionStatus", void 0);
__decorate([
    state()
], IssuesView.prototype, "_allProjects", void 0);
__decorate([
    state()
], IssuesView.prototype, "_hasProjects", void 0);
__decorate([
    state()
], IssuesView.prototype, "_organizations", void 0);
__decorate([
    state()
], IssuesView.prototype, "_initialLoadComplete", void 0);
IssuesView = __decorate([
    customElement('issues-view')
], IssuesView);
export { IssuesView };
