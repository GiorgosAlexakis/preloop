import { LitElement, html, css } from 'lit';
import { customElement, state, property } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/tag/tag.js';
import '../../components/project-filter-modal.ts';
import { listProjects, Project } from '../../api';

// Define the structure of an issue and a duplicate pair based on the API response
interface Issue {
  id: string;
  title: string;
  description: string;
  key: string;
  status: string;
  url: string;
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

interface LlmVerdict {
  decision: 'confirmed' | 'rejected' | 'undecided' | 'checking';
  reason?: string;
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
  private _selectedProjectIds: string[] = [];

  @state()
  private _allProjects: Project[] = [];

  // WARNING: Do not hardcode tokens in production. This is for demonstration purposes only.
  // In a real application, the token should be retrieved from a secure storage like localStorage or a state management solution.
  private _apiToken = 'qybJSX1eCvHFTUvmcXpX3rmVX93uzXjAjDJbtqpz';

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
    }

    .clickable-row {
      cursor: pointer;
    }

    .detail-row > td {
      padding: 0;
      border-top: none;
    }

    .detail-view-card {
      background-color: var(--sl-color-neutral-50);
      border: 1px solid var(--sl-color-neutral-200);
      padding: var(--sl-spacing-large);
      margin: var(--sl-spacing-x-small) 0;
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
  `;

  connectedCallback() {
    super.connectedCallback();
    this.fetchInitialData();
  }

  async fetchInitialData() {
    this.fetchDuplicates();
    this.fetchProjects();
  }

  async fetchProjects() {
    try {
      this._allProjects = await listProjects();
    } catch (error) {
      console.error('Failed to fetch project list:', error);
    }
  }

  async fetchDuplicates() {
    this._loading = true;
    this._error = null;
    const skip = (this._currentPage - 1) * this._pageSize;

    try {
      const params = new URLSearchParams({
        limit: this._pageSize.toString(),
        skip: skip.toString(),
        similarity_threshold: '0.8',
      });

      this._selectedProjectIds.forEach(id => {
        params.append('project_ids', id);
      });

      const url = `/api/v1/issue-duplicates?${params.toString()}`;

      const response = await fetch(
        url,
        {
          headers: {
            Authorization: `Bearer ${this._apiToken}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: DuplicatesResponse = await response.json();
      this._duplicates = data.duplicates;
      this._hasMorePages = data.duplicates.length === this._pageSize;
      this.fetchLlmVerdicts(); // Fetch verdicts after getting duplicates
    } catch (error) {
      this._error = error instanceof Error ? error.message : 'An unknown error occurred.';
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
          const response = await fetch(
            `/api/v1/issue-duplicates/check?issue1_id=${pair.issue1.id}&issue2_id=${pair.issue2.id}`,
            {
              headers: {
                Authorization: `Bearer ${this._apiToken}`,
                'Content-Type': 'application/json',
              },
            }
          );

          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }

          const verdictData = await response.json();
          this._llmVerdicts = {
            ...this._llmVerdicts,
            [pairKey]: {
              decision: verdictData.decision || 'undecided',
              reason: verdictData.reason,
            },
          };
        } catch (error) {
          console.error(`Failed to fetch LLM verdict for pair ${pairKey}:`, error);
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

  private _renderDetailView(
    pair: DuplicatePair,
    verdict: LlmVerdict | undefined
  ) {
    return html`
      <tr class="detail-row">
        <td colspan="5">
          <div class="detail-view-card">
            <div class="detail-section">
              <h3><span class="detail-issue-key">${pair.issue1.key}</span><br />${pair.issue1.title}</h3>
              <p class="issue-description">${pair.issue1.description}</p>
            </div>
            <div class="detail-section">
              <h3><span class="detail-issue-key">${pair.issue2.key}</span><br />${pair.issue2.title}</h3>
              <p class="issue-description">${pair.issue2.description}</p>
            </div>
            ${verdict
              ? html`
                  <div class="detail-section">
                    <h3>LLM Review</h3>
                    <p>
                      <strong>Status:</strong>
                      ${this.renderVerdict(pair)}
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
    this._selectedProjectIds = this._selectedProjectIds.filter(id => id !== projectIdToRemove);
    this.fetchDuplicates();
  }

  private _clearAllFilters() {
    this._selectedProjectIds = [];
    this.fetchDuplicates();
  }

  private _renderActiveFilters() {
    if (this._selectedProjectIds.length === 0) {
      return html``;
    }

    const selectedProjects = this._selectedProjectIds.map(id =>
      this._allProjects.find(p => p.id.toString() === id)
    ).filter(Boolean) as Project[];

    return html`
      <div class="active-filters">
        <span>Filtered by:</span>
        ${selectedProjects.map(project => html`
          <sl-tag
            size="medium"
            removable
            @sl-remove=${() => this._removeProjectFilter(project.id.toString())}
          >
            ${project.name}
          </sl-tag>
        `)}
        <sl-button size="small" pill @click=${this._clearAllFilters}>Clear all</sl-button>
      </div>
    `;
  }

  render() {
    return html`
      <div class="container">
        <div class="header">
          <h1>Issue Clusters</h1>
          <sl-button @click=${this._openFilterModal}>
            <sl-icon slot="prefix" name="filter"></sl-icon>
            Filter
          </sl-button>
        </div>

        ${this._renderActiveFilters()}

        ${when(
          this._loading,
          () => html`<div class="loading">Loading issues...</div>`
        )}
        ${when(
          this._error,
          () => html`<div class="error">Error: ${this._error}</div>`
        )}
        ${when(
          !this._loading && !this._error,
          () =>
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
                              class="clickable-row ${verdict?.decision === 'rejected'
                                ? 'faint-row'
                                : ''}"
                              @click=${() => this._toggleRow(pairKey)}
                            >
                              <td>
                                <div class="issue-key">${pair.issue1.key}</div>
                                <div class="issue-title">
                                  ${pair.issue1.title}
                                </div>
                              </td>
                              <td>
                                <div class="issue-key">${pair.issue2.key}</div>
                                <div class="issue-title">
                                  ${pair.issue2.title}
                                </div>
                              </td>
                              <td class="text-right">
                                ${(pair.similarity * 100).toFixed(2)}%
                              </td>
                              <td class="text-right" id="verdict-${pair.issue1.id}-${pair.issue2.id}">
                                ${pair.similarity >= 0.999
                                  ? html`<sl-badge
                                      variant="warning"
                                      style="--sl-color-warning-text: var(--sl-color-orange-50); --sl-color-warning-600: var(--sl-color-orange-700);"
                                      >Identical</sl-badge
                                    >`
                                  : this.renderVerdict(pair)}
                              </td>
                              <td class="text-right">
                                <div class="card-actions">
                                  <sl-button
                                    size="small"
                                    variant=${verdict?.decision === 'rejected'
                                      ? 'default'
                                      : 'primary'}
                                    >Resolve...</sl-button
                                  >
                                  <sl-button size="small">Dismiss</sl-button>
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
        .initialSelectedProjectIds=${this._selectedProjectIds}
        @projects-selected=${this._handleProjectsSelected}
        @close-modal=${() => (this._isFilterModalOpen = false)}
      ></project-filter-modal>
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

  renderVerdict(pair: DuplicatePair) {
    const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
    const verdict = this._llmVerdicts[pairKey];

    if (verdict) {
      if (verdict.decision === 'confirmed') {
        return html`<sl-badge
          variant="warning"
          style="--sl-color-warning-text: var(--sl-color-orange-50); --sl-color-warning-600: var(--sl-color-orange-600);"
          >Confirmed</sl-badge
        >`;
      } else if (verdict.decision === 'rejected') {
        return html`<sl-badge
          variant="success"
          style="--sl-color-success-text: var(--sl-color-cyan-50); --sl-color-success-600: var(--sl-color-cyan-600);"
          >Rejected</sl-badge
        >`;
      }
    }

    return html`<span>Checking...</span>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'issues-view': IssuesView;
  }
}
