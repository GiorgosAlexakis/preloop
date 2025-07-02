import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';

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
  private _hasMorePages = false;

  // WARNING: Do not hardcode tokens in production. This is for demonstration purposes only.
  // In a real application, the token should be retrieved from a secure storage like localStorage or a state management solution.
  private _apiToken = 'qybJSX1eCvHFTUvmcXpX3rmVX93uzXjAjDJbtqpz';

  static styles = css`
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
    .styled-table th:last-child,
    .styled-table td:last-child {
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
  `; 

  connectedCallback() {
    super.connectedCallback();
    this.fetchDuplicates();
  }

  async fetchDuplicates() {
    this._loading = true;
    this._error = null;
    const skip = (this._currentPage - 1) * this._pageSize;

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/v1/issue-duplicates?limit=${this._pageSize}&skip=${skip}&similarity_threshold=0.8`,
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
            `http://127.0.0.1:8000/api/v1/issue-duplicates/check?issue1_id=${pair.issue1.id}&issue2_id=${pair.issue2.id}`,
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

  render() {
    return html`
      <div class="page-container">
        <div class="page-header">
          <h1>Issue Clusters</h1>
        </div>

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
                              class=${verdict?.decision === 'rejected'
                                ? 'faint-row'
                                : ''}
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
                                          variant="success"
                                          style="--sl-color-success-text: var(--sl-color-cyan-50); --sl-color-success-600: var(--sl-color-cyan-600);"
                                          >Identical</sl-badge
                                      >`
                                    : this.renderVerdict(pair)}
                              </td>
                              <td class="text-right">
                                <div class="actions-container">
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

    if (!verdict || verdict.decision === 'checking') {
      return html`<span>Checking...</span>`;
    }

    switch (verdict.decision) {
      case 'confirmed':
        return html`<sl-badge variant="success">Confirmed</sl-badge>`;
      case 'rejected':
        return html`<sl-badge variant="danger">Rejected</sl-badge>`;
      default:
        return html`<sl-badge variant="neutral">Undecided</sl-badge>`;
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'issues-view': IssuesView;
  }
}
