import { html, TemplateResult } from 'lit';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';

export interface LlmVerdict {
  decision:
    | 'duplicate'
    | 'overlapping'
    | 'undecided'
    | 'checking'
    | 'unrelated';
  reason?: string;
}

export function renderVerdict(verdict: LlmVerdict | undefined): TemplateResult {
  if (!verdict || verdict.decision === 'checking') {
    return html`
      <sl-badge variant="neutral" pill>
        <sl-spinner style="font-size: 0.8em; margin-right: 4px;"></sl-spinner>
        Checking...
      </sl-badge>
    `;
  }

  switch (verdict.decision) {
    case 'duplicate':
      return html`
        <sl-badge
          variant="success"
          style="--sl-color-success-text: var(--sl-color-pink-50); --sl-color-success-600: var(--sl-color-pink-600);"
          pill
        >
          <sl-icon
            name="check-circle"
            style="margin-right: var(--sl-spacing-2x-small);"
          ></sl-icon>
          Confirmed
        </sl-badge>
      `;
    case 'overlapping':
      return html`
        <sl-badge
          variant="primary"
          style="--sl-color-primary-text: var(--sl-color-orange-50); --sl-color-primary-600: var(--sl-color-orange-600);"
          pill
        >
          <sl-icon
            name="intersect"
            style="margin-right: var(--sl-spacing-2x-small);"
          ></sl-icon>
          Overlapping
        </sl-badge>
      `;
    case 'unrelated':
      return html`
        <sl-badge
          variant="danger"
          style="--sl-color-danger-text: var(--sl-color-cyan-50); --sl-color-danger-600: var(--sl-color-cyan-600);"
          pill
        >
          <sl-icon
            name="x-circle"
            style="margin-right: var(--sl-spacing-2x-small);"
          ></sl-icon>
          Unrelated
        </sl-badge>
      `;
    default:
      return html`
        <sl-badge variant="neutral" pill>
          <sl-icon name="question-circle"></sl-icon>
          Undecided
        </sl-badge>
      `;
  }
}
