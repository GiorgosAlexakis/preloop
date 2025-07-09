import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { DuplicatePair, executeResolution } from '../api';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio/radio.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';

@customElement('resolve-issue-modal')
export class ResolveIssueModal extends LitElement {
  @property({ type: Boolean, reflect: true }) open = false;
  @property({ type: Object }) duplicatePair: DuplicatePair | null = null;

  @state() private _selectedAction: string | null = null;
  @state() private _isSubmitting = false;

  static styles = css`
    sl-dialog::part(panel) {
      max-width: 65ch;
    }

    .suggestions-group {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-small);
    }

    sl-radio {
      display: block;
      padding: var(--sl-spacing-medium);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      transition: all 0.2s ease-in-out;
      cursor: pointer;
    }

    sl-radio:hover {
      border-color: var(--sl-color-primary-300);
      background-color: var(--sl-color-neutral-50);
    }

    sl-radio[checked] {
      border-color: var(--sl-color-primary-600);
      background-color: var(--sl-color-primary-50);
    }

    sl-radio::part(base) {
      align-items: flex-start;
    }

    sl-radio::part(label) {
      display: flex;
      flex-direction: column;
      line-height: var(--sl-line-height-normal);
      user-select: none;
    }

    .suggestion-title {
      font-weight: var(--sl-font-weight-semibold);
      color: var(--sl-color-neutral-800);
      margin-bottom: var(--sl-spacing-3x-small);
    }

    sl-radio[checked] .suggestion-title {
      color: var(--sl-color-primary-700);
    }

    .suggestion-description {
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-600);
    }
  `;

  private _handleOpen() {
    // Reset state when modal opens
    this._selectedAction = null;
    this._isSubmitting = false;
  }

  private _close() {
    this.open = false;
    this.dispatchEvent(
      new CustomEvent('closed', { bubbles: true, composed: true })
    );
  }

  private async _handleResolve() {
    if (!this._selectedAction || !this.duplicatePair) return;

    this._isSubmitting = true;
    try {
      await executeResolution(
        this._selectedAction,
        this.duplicatePair.issue1.id,
        this.duplicatePair.issue2.id
      );
      this.dispatchEvent(
        new CustomEvent('resolved', { bubbles: true, composed: true })
      );
      this._close();
    } catch (error) {
      console.error('Failed to execute resolution:', error);
      // You could add a user-facing error message here
    } finally {
      this._isSubmitting = false;
    }
  }

  render() {
    const issueAKey = this.duplicatePair?.issue1.key || 'Issue A';
    const issueBKey = this.duplicatePair?.issue2.key || 'Issue B';

    const actions = [
      {
        action_id: `CLOSE_${issueAKey}_AS_DUPLICATE_OF_${issueBKey}`,
        title: `Close ${issueAKey} as duplicate of ${issueBKey}`,
        description: `This will close ${issueAKey} and add a comment linking to ${issueBKey}.`,
      },
      {
        action_id: `CLOSE_${issueBKey}_AS_DUPLICATE_OF_${issueAKey}`,
        title: `Close ${issueBKey} as duplicate of ${issueAKey}`,
        description: `This will close ${issueBKey} and add a comment linking to ${issueAKey}.`,
      },
      {
        action_id: `MERGE_${issueAKey}_INTO_${issueBKey}`,
        title: `Merge ${issueAKey} into ${issueBKey}`,
        description: `Merge content from ${issueAKey} into ${issueBKey}, then close ${issueAKey}.`,
      },
      {
        action_id: 'MARK_AS_UNRELATED',
        title: 'Not duplicates',
        description: 'Mark these two issues as unrelated.',
      },
    ];

    return html`
      <sl-dialog
        label="Resolve Duplicate Issues"
        .open=${this.open}
        @sl-show=${this._handleOpen}
        @sl-hide=${this._close}
      >
        <sl-radio-group
          @sl-change=${(e: Event) =>
            (this._selectedAction = (e.target as HTMLInputElement).value)}
        >
          <div class="suggestions-group">
            ${actions.map(
              (action) => html`
                <sl-radio value=${action.action_id}>
                  <span class="suggestion-title">${action.title}</span>
                  <span class="suggestion-description"
                    >${action.description}</span
                  >
                </sl-radio>
              `
            )}
          </div>
        </sl-radio-group>
        <sl-button slot="footer" @click=${this._close}>Cancel</sl-button>
        <sl-button
          slot="footer"
          variant="primary"
          .loading=${this._isSubmitting}
          .disabled=${!this._selectedAction}
          @click=${this._handleResolve}
          >Resolve</sl-button
        >
      </sl-dialog>
    `;
  }
}
