import { html, TemplateResult } from 'lit';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';

export interface LlmVerdict {
  decision: 'confirmed' | 'rejected' | 'undecided' | 'checking';
  reason?: string;
}

export function renderVerdict(verdict: LlmVerdict | undefined): TemplateResult {
  if (!verdict || verdict.decision === 'checking') {
    return html`
      <sl-spinner style="font-size: 14px; --track-width: 2px;"></sl-spinner>
      <span style="margin-left: var(--sl-spacing-2x-small);">Checking...</span>
    `;
  }

  let icon, variant, text;
  switch (verdict.decision) {
    case 'confirmed':
      icon = 'check-circle';
      variant = 'success';
      text = 'Confirmed';
      break;
    case 'rejected':
      icon = 'x-circle';
      variant = 'danger';
      text = 'Rejected';
      break;
    default:
      icon = 'question-circle';
      variant = 'neutral';
      text = 'Undecided';
  }

  return html`
    <sl-badge .variant=${variant} pill>
      <sl-icon name=${icon}></sl-icon>
      ${text}
    </sl-badge>
  `;
}