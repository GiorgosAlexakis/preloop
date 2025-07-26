import { LitElement, html, css, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { when } from 'lit/directives/when.js';
import { getStatusVariant } from '../utils/verdict';
import { Issue } from '../api';

@customElement('single-issue-detail-view')
export class SingleIssueDetailView extends LitElement {
  @property({ type: Object }) issue: Issue | null = null;

  static styles = css`
    .detail-view-card {
      padding: var(--sl-spacing-large);
      background-color: var(--sl-color-neutral-0);
    }
    .detail-section {
      margin-bottom: var(--sl-spacing-large);
    }
    .detail-section:last-child {
      margin-bottom: 0;
    }
    .detail-section h3 {
      font-size: var(--sl-font-size-medium);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .issue-description {
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-700);
      background-color: var(--sl-color-neutral-100);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-medium);
      white-space: pre-wrap;
      word-wrap: break-word;
      max-height: 400px;
      overflow-y: auto;
    }
    .issue-status {
      font-size: var(--sl-font-size-x-small);
      text-transform: uppercase;
    }
  `;

  render() {
    if (!this.issue) {
      return nothing;
    }

    return html`
      <div class="detail-section">
        <h3>
          <span> ${this.issue.title} </span>
          <sl-badge
            variant=${getStatusVariant(this.issue.status)}
            class="issue-status"
            >${this.issue.status}</sl-badge
          >
        </h3>
        ${when(
          this.issue.description,
          () =>
            html`<div class="issue-description">
              ${unsafeHTML(this.issue.description)}
            </div>`
        )}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'single-issue-detail-view': SingleIssueDetailView;
  }
}
