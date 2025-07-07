import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import { listIssueDuplicates, DuplicatePair, checkLlmVerdict } from '../api';
import { LlmVerdict, renderVerdict } from '../utils/verdict';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';

@customElement('similar-issues-widget')
export class SimilarIssuesWidget extends LitElement {
  @state() private _topSuggestions: DuplicatePair[] = [];
  @state() private _totalSuggestions = 0;
  @state() private _loading = true;
  @state() private _error: string | null = null;
  @state() private _llmVerdicts: Record<string, LlmVerdict> = {};

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
    .verdict-container {
      margin-left: var(--sl-spacing-medium);
      display: inline-flex;
      align-items: center;
    }
    .see-all-container {
      text-align: center;
      margin-top: var(--sl-spacing-medium);
      padding-top: var(--sl-spacing-medium);
      border-top: 1px solid var(--sl-color-neutral-200);
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
      await this.fetchLlmVerdicts();
    } catch (error) {
      console.error('Failed to fetch similar issues:', error);
      this._error = 'Could not load suggestions.';
    } finally {
      this._loading = false;
    }
  }

  async fetchLlmVerdicts() {
    // 1. Set all to 'checking' and update the UI once.
    const initialVerdicts: Record<string, LlmVerdict> = {};
    const pairsToFetch: DuplicatePair[] = [];

    for (const pair of this._topSuggestions) {
      if (pair.similarity < 0.999) {
        const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
        initialVerdicts[pairKey] = { decision: 'checking' };
        pairsToFetch.push(pair);
      }
    }
    this._llmVerdicts = initialVerdicts;

    // 2. Create an array of promises for all the API calls.
    const verdictPromises = pairsToFetch.map((pair) =>
      checkLlmVerdict(pair.issue1.id, pair.issue2.id).catch((error) => {
        console.error(
          `[similar-issues-widget] fetchLlmVerdicts: API call failed for pair ${pair.issue1.id}-${pair.issue2.id}`,
          error
        );
        // Return a specific error object so Promise.all doesn't fail completely
        return { error: true, pairKey: `${pair.issue1.id}-${pair.issue2.id}` };
      })
    );

    if (verdictPromises.length === 0) {
      return;
    }

    // 3. Wait for all promises to settle.
    const results = await Promise.all(verdictPromises);

    // 4. Process the results and update the state a final time.
    const finalVerdicts = { ...this._llmVerdicts };
    results.forEach((result, index) => {
      const pair = pairsToFetch[index];
      const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;

      if (result.error) {
        finalVerdicts[pairKey] = {
          decision: 'undecided',
          reason: 'Failed to load',
        };
      } else {
        finalVerdicts[pairKey] = {
          decision: result.decision || 'undecided',
          reason: result.reason,
        };
      }
    });

    this._llmVerdicts = finalVerdicts;
  }

  render() {
    return html`
      <sl-card>
        <div slot="header">Similar Issue Suggestions</div>

        ${when(this._loading, () => html`<div>Loading...</div>`)}
        ${when(this._error, () => html`<div>${this._error}</div>`)}
        ${when(
          !this._loading && !this._error,
          () => html`
            <p>
              You have
              <a href="/console/issues"
                ><strong
                  >${this._totalSuggestions > 100
                    ? '100+'
                    : this._totalSuggestions}</strong
                >
                unresolved suggestions</a
              >. Here are the top 3:
            </p>
            <ul class="suggestion-list">
              ${this._topSuggestions.map((pair) => {
                const pairKey = `${pair.issue1.id}-${pair.issue2.id}`;
                return html`
                  <li class="suggestion-item">
                    <div
                      class="issue-titles"
                      title="${pair.issue1.title} vs ${pair.issue2.title}"
                    >
                      <strong>${pair.issue1.key}</strong> vs
                      <strong>${pair.issue2.key}</strong>
                    </div>
                    <div>
                      <sl-badge variant="neutral"
                        >${(pair.similarity * 100).toFixed(0)}%</sl-badge
                      >
                      <div class="verdict-container">
                        ${pair.similarity > 0.999
                          ? html`<sl-badge
                              variant="warning"
                              style="--sl-color-warning-text: var(--sl-color-orange-50); --sl-color-warning-600: var(--sl-color-orange-700);"
                              pill
                              >Identical</sl-badge
                            >`
                          : renderVerdict(this._llmVerdicts[pairKey])}
                      </div>
                    </div>
                  </li>
                `;
              })}
            </ul>
            <div class="see-all-container">
              <a href="/console/issues">See all...</a>
            </div>
          `
        )}
      </sl-card>
    `;
  }
}
