import { LitElement, html, css } from 'lit';
import { customElement, state, property } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/tag/tag.js';
import '@shoelace-style/shoelace/dist/components/button-group/button-group.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '../../components/project-filter-modal.ts';
import '../../components/duplicate-stats-chart.ts';
import '../../components/resolve-issue-modal.ts';
import {
  listProjects,
  Project,
  listIssueDuplicates,
  checkLlmVerdict,
  dismissDuplicatePair,
  DuplicatePair,
  DuplicatesResponse,
  listOrganizations,
  Organization,
} from '../../api';
import { DEFAULT_SIMILARITY_THRESHOLD } from '../../config';
import { LlmVerdict, renderVerdict } from '../../utils/verdict';

// Define the structure of an issue and a duplicate pair based on the API response
interface Issue {
  project_id: string;
  id: string;
  title: string;
  description: string;
  key: string;
  status: string;
  created_at: string;
  updated_at: string;
  url: string;
  meta_data?: { [key: string]: any };
}

interface DuplicatePair {
  issue1: Issue;
  issue2: Issue;
  similarity: number;
}

interface DuplicatesResponse {
  project_ids: string[];
  model_id_used: string;
  threshold_used: number;
  duplicates: DuplicatePair[];
}

@customElement('issues-view')
export class IssuesView extends LitElement {
  @state()
  private _duplicates: DuplicatePair[] = [];

  @state()
  private _llmVerdicts: Record<string, LlmVerdict> = {};

  @state()
  private _loading = false;

  @state()
  private _error: string | null = null;

  @state()
  private _currentPage = 1;

  @state()
  private _pageSize = 10;

  @state()
  private _hasMorePages = true;

  @state()
  private _expandedRowKey: string | null = null;

  @state()
  private _isFilterModalOpen = false;

  @state()
  private _isResolveModalOpen = false;

  @state()
  private _selectedPair: DuplicatePair | null = null;

  @state()
  private _selectedProjectIds: string[] = [];

  @state()
  private _selectedStatus: 'opened' | 'closed' | 'all' = 'opened';

  private _similarityThreshold = DEFAULT_SIMILARITY_THRESHOLD;

  @state()
  private _allProjects: Project[] = [];

  @state()
  private _organizations: Organization[] = [];

  static styles = css`
    .container {
      max-width: var(--console-container-large-max-width);
      padding: var(--sl-spacing-x-large);
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: var(--sl-spacing-large);
    }
    sl-card::part(body) {
      padding: 0;
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
    .styled-table tr:last-child td {
      border-bottom: none;
    }
    .styled-table th:last-child {
      text-align: right;
    }

    .issue-key {
      color: var(--sl-color-neutral-600);
    }

    .pagination-controls {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: var(--sl-spacing-medium);
      margin-top: var(--sl-spacing-large);
    }

    .faint-row {
      opacity: 0.5;
      transition: opacity 0.3s ease-in-out;
    }

    .actions-container {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: var(--sl-spacing-x-small);
    }

    .clickable-row {
      cursor: pointer;
    }

    .detail-row > td {
      padding: 0;
      border-top: none;
    }

    .detail-view-card {
      padding: var(--sl-spacing-large);
    }

    .detail-grid {
      margin-bottom: var(--sl-spacing-large);
    }

    .detail-section h3 {
      font-size: var(--sl-font-size-medium);
      margin-top: 0;
      margin-bottom: var(--sl-spacing-small);
    }

    .detail-issue-key {
      color: var(--sl-color-neutral-600);
      font-weight: normal;
    }

    .issue-description {
      background-color: var(--sl-color-neutral-100);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-medium);
      white-space: pre-wrap;
      word-wrap: break-word;
      max-height: 200px;
      overflow-y: auto;
    }

    .active-filters {
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-x-small);
      padding: var(--sl-spacing-small) 0;
      flex-wrap: wrap;
    }

    .active-filters span {
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-600);
      margin-right: var(--sl-spacing-x-small);
    }

    .card-actions {
      display: flex;
      gap: var(--sl-spacing-x-small);
    }

    .issue-id-link {
      color: var(--sl-color-primary-600);
      text-decoration: none;
    }

    .issue-id-link:hover {
      text-decoration: underline;
    }

    .issue-id {
      font-weight: 400;
      margin-right: var(--sl-spacing-x-small);
    }

    .issue-status {
      font-size: var(--sl-font-size-x-small);
      text-transform: uppercase;
    }

    .embedding-card {
      width: 100%;
      margin-bottom: var(--sl-spacing-large);
    }
    .embedding-card::part(body) {
      padding: 0;
      height: 160px;
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
  `;

  connectedCallback() {
    super.connectedCallback();
    this.fetchInitialData();
  }

  async fetchInitialData() {
    this.fetchDuplicates();
    this.fetchProjects();
    this.fetchOrganizations();
  }

  async fetchProjects() {
    try {
      this._allProjects = await listProjects();
    } catch (error) {
      console.error('Failed to fetch project list:', error);
    }
  }

  async fetchOrganizations() {
    try {
      this._organizations = await listOrganizations();
    } catch (error) {
      console.error('Failed to fetch organization list:', error);
    }
  }

  async fetchDuplicates() {
    this._loading = true;
    this._error = null;
    const skip = (this._currentPage - 1) * this._pageSize;

    try {
      const data: DuplicatesResponse = await listIssueDuplicates({
        limit: this._pageSize,
        skip: skip,
        project_ids: this._selectedProjectIds,
        status: this._selectedStatus,
        similarity_threshold: this._similarityThreshold,
      });

      this._duplicates = data.duplicates;
      this._hasMorePages = data.duplicates.length === this._pageSize;
      this.fetchLlmVerdicts(); // Fetch verdicts after getting duplicates
    } catch (error) {
      this._error =
        error instanceof Error ? error.message : 'An unknown error occurred.';
      console.error('Failed to fetch duplicate issues:', error);
    } finally {
      this._loading = false;
    }
  }

  async fetchLlmVerdicts() {
    for (const pair of this._duplicates) {
      if (pair.similarity < 0.999) {
        const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
        // Set initial state to 'checking'
        this._llmVerdicts = {
          ...this._llmVerdicts,
          [pairKey]: { decision: 'checking' },
        };

        try {
          const verdictData = await checkLlmVerdict(
            pair.issue1.id,
            pair.issue2.id
          );

          this._llmVerdicts = {
            ...this._llmVerdicts,
            [pairKey]: {
              decision: verdictData.decision || 'undecided',
              reason: verdictData.reason,
            },
          };
        } catch (error) {
          console.error(
            `Failed to fetch LLM verdict for pair ${pairKey}:`,
            error
          );
          this._llmVerdicts = {
            ...this._llmVerdicts,
            [pairKey]: { decision: 'undecided', reason: 'Failed to load' },
          };
        }
      }
    }
  }

  private _toggleRow(pairKey: string) {
    if (this._expandedRowKey === pairKey) {
      this._expandedRowKey = null;
    } else {
      this._expandedRowKey = pairKey;
    }
  }

  private _openResolveModal(pair: DuplicatePair) {
    this._selectedPair = pair;
    this._isResolveModalOpen = true;
  }

  private async _handleDismiss(pair: DuplicatePair) {
    // Optimistically remove the pair from the list for a responsive UI
    const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
    const originalDuplicates = [...this._duplicates];
    this._duplicates = this._duplicates.filter(
      (p) => `${p.issue1.id}-${p.issue2.id}` !== pairKey
    );

    try {
      await dismissDuplicatePair(pair.issue1.id, pair.issue2.id);
    } catch (error) {
      console.error('Failed to dismiss pair:', error);
      // If the API call fails, revert the UI change
      this._duplicates = originalDuplicates;
      // Optionally, show an error toast to the user here
    }
  }

  private _handleModalClose() {
    this._isResolveModalOpen = false;
    this._selectedPair = null;
  }

  private _handleResolved() {
    this._isResolveModalOpen = false;
    this._selectedPair = null;
    // Refresh the data
    this.fetchDuplicates();
  }

  private _renderDetailView(
    pair: DuplicatePair,
    verdict: LlmVerdict | undefined
  ) {
    return html`
      <tr class="detail-row">
        <td colspan="5">
          <div class="detail-view-card">
            <div class="detail-section">
              <h3>
                <span class="detail-issue-key">${pair.issue1.key}</span
                ><br />${pair.issue1.title}
              </h3>
              <p class="issue-description">${pair.issue1.description}</p>
            </div>
            <div class="detail-section">
              <h3>
                <span class="detail-issue-key">${pair.issue2.key}</span
                ><br />${pair.issue2.title}
              </h3>
              <p class="issue-description">${pair.issue2.description}</p>
            </div>
            ${verdict
              ? html`
                  <div class="detail-section">
                    <h3>LLM Review</h3>
                    <p>
                      <strong>Status:</strong>
                      ${renderVerdict(verdict)}
                    </p>
                    <p>
                      <strong>Reasoning:</strong>
                      ${verdict.reason || 'No reasoning provided.'}
                    </p>
                  </div>
                `
              : ''}
          </div>
        </td>
      </tr>
    `;
  }

  private _openFilterModal() {
    this._isFilterModalOpen = true;
  }

  private _closeFilterModal() {
    this._isFilterModalOpen = false;
  }

  private _handleProjectsSelected(event: CustomEvent) {
    this._selectedProjectIds = event.detail.projectIds;
    this._isFilterModalOpen = false;
    this.fetchDuplicates(); // Re-fetch data with the new filter
  }

  private _removeProjectFilter(projectIdToRemove: string) {
    this._selectedProjectIds = this._selectedProjectIds.filter(
      (id) => id !== projectIdToRemove
    );
    this.fetchDuplicates();
  }

  private _clearAllFilters() {
    this._selectedProjectIds = [];
    this.fetchDuplicates();
  }

  private _handleProjectSelectedFromChart(event: CustomEvent) {
    const { projectId } = event.detail;
    if (projectId && !this._selectedProjectIds.includes(projectId)) {
      this._selectedProjectIds = [...this._selectedProjectIds, projectId];
      this.fetchDuplicates();
    }
  }

  private _renderActiveFilters() {
    if (
      this._selectedProjectIds.length === 0 &&
      this._selectedStatus === 'opened'
    ) {
      return html``;
    }

    const selectedProjects = this._selectedProjectIds
      .map((id) => this._allProjects.find((p) => p.id.toString() === id))
      .filter(Boolean) as Project[];

    return html`
      <div class="active-filters">
        <span>Filtered by:</span>
        ${selectedProjects.map(
          (project) => html`
            <sl-tag
              size="medium"
              removable
              @sl-remove=${() =>
                this._removeProjectFilter(project.id.toString())}
            >
              ${project.name}
            </sl-tag>
          `
        )}
        ${this._selectedStatus !== 'opened'
          ? html`
              <sl-tag
                size="medium"
                removable
                @sl-remove=${() => this._clearStatusFilter()}
              >
                ${this._selectedStatus === 'closed' ? 'Closed' : 'All'}
              </sl-tag>
            `
          : ''}
        <sl-button size="small" pill @click=${this._clearAllFilters}
          >Clear all</sl-button
        >
      </div>
    `;
  }

  private _clearStatusFilter() {
    this._selectedStatus = 'opened';
    this.fetchDuplicates();
  }

  private getStatusVariant(
    status: string
  ): 'primary' | 'success' | 'neutral' | 'warning' | 'danger' {
    const lowerCaseStatus = status.toLowerCase();
    if (['closed', 'done', 'resolved'].includes(lowerCaseStatus)) {
      return 'success';
    }
    if (['open', 'opened', 'to do', 'in progress'].includes(lowerCaseStatus)) {
      return 'primary';
    }
    return 'neutral';
  }

  render() {
    return html`
      <div class="container">
        <div class="header">
          <h1>Similar Issues</h1>
          <sl-button @click=${this._openFilterModal}>
            <sl-icon slot="prefix" name="filter"></sl-icon>
            Filter
          </sl-button>
        </div>

        <sl-alert
          variant="primary"
          open
          style="margin-bottom: var(--sl-spacing-large);"
        >
          <sl-icon slot="icon" name="info-circle"></sl-icon>
          <strong>Find similar issues and resolve duplicates</strong><br />
          Identify similar and potential duplicate issues across your projects.
          Review each suggested pair, check the similarity score, and use the
          LLM review to resolve or dismiss the suggestion.
        </sl-alert>

        ${this._renderActiveFilters()}

        <sl-card class="embedding-card">
          <duplicate-stats-chart
            .projectIds=${this._selectedProjectIds}
            .selectedStatus=${this._selectedStatus}
            .similarityThreshold=${this._similarityThreshold}
            ?interactive=${true}
            ?no-padding=${true}
            @project-selected=${this._handleProjectSelectedFromChart}
          ></duplicate-stats-chart>
        </sl-card>

        ${when(
          this._loading,
          () =>
            html`<div class="loading-overlay">
              <sl-spinner></sl-spinner>
              <span>Loading issues...</span>
            </div>`
        )}
        ${when(
          this._error,
          () => html`<div class="error">Error: ${this._error}</div>`
        )}
        ${when(!this._loading && !this._error, () =>
          this._duplicates.length > 0
            ? html`
                <sl-card class="table-card">
                  <table class="styled-table">
                    <thead>
                      <tr>
                        <th>Issue 1</th>
                        <th>Issue 2</th>
                        <th class="text-right">Similarity</th>
                        <th class="text-right">LLM Review</th>
                        <th class="text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${this._duplicates.map((pair) => {
                        const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
                        const verdict = this._llmVerdicts[pairKey];

                        return html`
                          <tr
                            class="clickable-row ${verdict?.decision ===
                            'rejected'
                              ? 'faint-row'
                              : ''}"
                            @click=${() => this._toggleRow(pairKey)}
                          >
                            <td>
                              <a
                                href="${pair.issue1.meta_data?.url ||
                                pair.issue1.url}"
                                target="_blank"
                                rel="noopener noreferrer"
                                class="issue-id-link"
                                @click=${(e: Event) => e.stopPropagation()}
                              >
                                <strong class="issue-id"
                                  >${pair.issue1.key}</strong
                                >
                                <sl-badge
                                  pill
                                  variant=${this.getStatusVariant(
                                    pair.issue1.status
                                  )}
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
                                @click=${(e: Event) => e.stopPropagation()}
                              >
                                <strong class="issue-id"
                                  >${pair.issue2.key}</strong
                                >
                                <sl-badge
                                  pill
                                  variant=${this.getStatusVariant(
                                    pair.issue2.status
                                  )}
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
                              id="verdict-${pair.issue1.id}-${pair.issue2.id}"
                            >
                              ${pair.similarity >= 0.999
                                ? html`<sl-badge
                                    variant="warning"
                                    style="--sl-color-warning-text: var(--sl-color-orange-50); --sl-color-warning-600: var(--sl-color-orange-700);"
                                    >Identical</sl-badge
                                  >`
                                : renderVerdict(verdict)}
                            </td>
                            <td>
                              <div class="actions-container">
                                <sl-button
                                  size="small"
                                  variant="primary"
                                  @click=${(e: Event) => {
                                    e.stopPropagation();
                                    this._openResolveModal(pair);
                                  }}
                                  >Resolve</sl-button
                                >
                                <sl-icon-button
                                  name="x-circle"
                                  label="Dismiss"
                                  @click=${(e: Event) => {
                                    e.stopPropagation();
                                    this._handleDismiss(pair);
                                  }}
                                ></sl-icon-button>
                              </div>
                            </td>
                          </tr>
                          ${this._expandedRowKey === pairKey
                            ? this._renderDetailView(pair, verdict)
                            : ''}
                        `;
                      })}
                    </tbody>
                  </table>
                </sl-card>
                <div class="pagination-controls">
                  <sl-button
                    size="small"
                    @click=${this._previousPage}
                    ?disabled=${this._currentPage === 1}
                    >Previous</sl-button
                  >
                  <span>Page ${this._currentPage}</span>
                  <sl-button
                    size="small"
                    @click=${this._nextPage}
                    ?disabled=${!this._hasMorePages}
                    >Next</sl-button
                  >
                </div>
              `
            : html`
                <sl-alert variant="primary" open>
                  <sl-icon slot="icon" name="info-circle"></sl-icon>
                  No duplicate issues found.
                </sl-alert>
              `
        )}
      </div>
      <project-filter-modal
        .open=${this._isFilterModalOpen}
        .organizations=${this._organizations}
        .projects=${this._allProjects}
        .selectedProjectIds=${this._selectedProjectIds}
        .selectedStatus=${this._selectedStatus}
        @close-modal=${() => (this._isFilterModalOpen = false)}
        @apply-filters=${(event: CustomEvent) => {
          const { selectedProjectIds, selectedStatus } = event.detail;
          this._selectedProjectIds = selectedProjectIds;
          this._selectedStatus = selectedStatus;
          this.fetchDuplicates(); // Re-fetch data with new filters
          this._isFilterModalOpen = false;
        }}
      ></project-filter-modal>
      <resolve-issue-modal
        .open=${this._isResolveModalOpen}
        .duplicatePair=${this._selectedPair}
        @closed=${this._handleModalClose}
        @resolved=${this._handleResolved}
      ></resolve-issue-modal>
    `;
  }

  private _previousPage() {
    if (this._currentPage > 1) {
      this._currentPage--;
      this.fetchDuplicates();
    }
  }

  private _nextPage() {
    this._currentPage++;
    this.fetchDuplicates();
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'issues-view': IssuesView;
  }
}
