import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { listIssueDuplicates, DuplicateGroup, DuplicatePair } from '../api';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';

@customElement('similar-issues-widget')
export class SimilarIssuesWidget extends LitElement {
  @state() private _topSuggestions: DuplicatePair[] = [];
  @state() private _totalSuggestions = 0;
  @state() private _loading = true;
  @state() private _error: string | null = null;

  static styles = css`
    :host {
      display: flex; /* Use flexbox to control child layout */
    }
    a {
      color: var(--sl-color-primary-600);
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    sl-card {
      flex-grow: 1; /* Allow the card to grow and fill the available space */
    }
    sl-card::part(base) {
      height: 100%;
    }
    .suggestion-list {
      list-style: none;
      padding: 0;
      margin: 0;
    }
    .suggestion-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: var(--sl-spacing-x-small) 0;
      border-bottom: 1px solid var(--sl-color-neutral-200);
    }
    .suggestion-item:last-child {
      border-bottom: none;
    }
    .issue-titles {
      font-size: var(--sl-font-size-small);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .review-button {
      margin-left: var(--sl-spacing-medium);
    }
  `;

  async connectedCallback() {
    super.connectedCallback();
    this.fetchTopSuggestions();
  }

  async fetchTopSuggestions() {
    this._loading = true;
    try {
      const response = await listIssueDuplicates({ limit: 101 }); // Fetch 101 to check for >100
      const allPairs = response.duplicates;

      allPairs.sort((a, b) => b.similarity - a.similarity);

      this._topSuggestions = allPairs.slice(0, 3);
      this._totalSuggestions = allPairs.length;
      this._error = null;
    } catch (error) {
      console.error('Failed to fetch similar issues:', error);
      this._error = 'Could not load suggestions.';
    } finally {
      this._loading = false;
    }
  }

  render() {
    return html`
      <sl-card>
        <div slot="header">
          Similar Issue Suggestions
        </div>

        ${when(this._loading, () => html`<div>Loading...</div>`)}
        ${when(this._error, () => html`<div>${this._error}</div>`)}

        ${when(!this._loading && !this._error, () => html`
          <p>You have <a href="/console/issues"><strong>${this._totalSuggestions > 100 ? '100+' : this._totalSuggestions}</strong> unresolved suggestions</a>. Here are the top 3:</p>
          <ul class="suggestion-list">
            ${this._topSuggestions.map(pair => html`
              <li class="suggestion-item">
                <div class="issue-titles" title="${pair.issue1.title} vs ${pair.issue2.title}">
                  <strong>${pair.issue1.key}</strong> vs <strong>${pair.issue2.key}</strong>
                </div>
                <div>
                  <sl-badge variant="neutral">${(pair.similarity * 100).toFixed(0)}%</sl-badge>
                  <a href="/console/issues" class="review-button">
                    <sl-button size="small">Review</sl-button>
                  </a>
                </div>
              </li>
            `)}
          </ul>
        `)}
      </sl-card>
    `;
  }
}
