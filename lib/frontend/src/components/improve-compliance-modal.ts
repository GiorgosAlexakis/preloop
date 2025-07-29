import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import {
  Issue,
  getComplianceImprovementSuggestion,
  updateIssueContent,
} from '../api';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';

import './single-issue-detail-view.ts';
import consoleStyles from '../styles/console-styles.css?inline';

@customElement('improve-compliance-modal')
export class ImproveComplianceModal extends LitElement {
  @property({ type: Boolean }) open = false;
  @property({ type: Object }) issue: Issue | null = null;
  @property({ type: String }) promptName = '';

  @state() private _isSubmitting = false;
  @state() private _isLoadingSuggestion = false;
  @state() private _suggestionError: string | null = null;

  @state() private _suggestedTitle = '';
  @state() private _suggestedDescription = '';

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      .comparison-panel h3 {
        margin-top: 0;
        font-size: var(--sl-font-size-large);
        font-weight: var(--sl-font-weight-semibold);
      }

      .loading-suggestion {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--sl-spacing-medium);
        min-height: 200px;
        color: var(--sl-color-neutral-500);
      }
    `,
  ];

  updated(changedProperties: Map<string, unknown>) {
    if (changedProperties.has('open') && this.open) {
      this.handleOpen();
    }
  }

  private async handleOpen() {
    if (!this.issue) return;
    this._suggestionError = null;
    this._suggestedTitle = '';
    this._suggestedDescription = '';
    this.fetchSuggestion();
  }

  private handleClose() {
    this.open = false;
    this.dispatchEvent(
      new CustomEvent('close', { bubbles: true, composed: true })
    );
  }

  private async fetchSuggestion() {
    if (!this.issue) return;
    this._isLoadingSuggestion = true;
    this._suggestionError = null;
    try {
      const suggestion = await getComplianceImprovementSuggestion(
        this.issue.id,
        this.promptName
      );
      this._suggestedTitle = suggestion.title;
      this._suggestedDescription = suggestion.description;
    } catch (error) {
      this._suggestionError =
        error instanceof Error ? error.message : 'Failed to load suggestion.';
      console.error('Failed to get compliance suggestion:', error);
    } finally {
      this._isLoadingSuggestion = false;
    }
  }

  private async handleSubmit() {
    if (!this.issue) return;
    this._isSubmitting = true;
    try {
      await updateIssueContent(
        this.issue.id,
        this._suggestedTitle,
        this._suggestedDescription
      );
      this.dispatchEvent(
        new CustomEvent('on-submit', {
          bubbles: true,
          composed: true,
          detail: { issueId: this.issue.id },
        })
      );
      this.handleClose();
    } catch (error) {
      console.error('Failed to update issue:', error);
      // Consider showing a toast notification on error
    } finally {
      this._isSubmitting = false;
    }
  }

  render() {
    return html`
      <sl-dialog
        label="Improve Issue Compliance"
        class="dialog-overview large"
        .open=${this.open}
        @sl-hide=${this.handleClose}
      >
        ${this.issue
          ? html`
              <div class="comparison-container">
                <div class="comparison-panel">
                  <h3>Original Issue</h3>
                  <single-issue-detail-view
                    .issue=${this.issue}
                  ></single-issue-detail-view>
                </div>
                <div class="comparison-panel">
                  <h3>Suggested Improvement</h3>
                  ${this._isLoadingSuggestion
                    ? html`<div class="loading-suggestion">
                        <sl-spinner></sl-spinner>
                        <span>Generating suggestion...</span>
                      </div>`
                    : this._suggestionError
                      ? html`<sl-alert variant="danger" open
                          ><sl-icon
                            slot="icon"
                            name="exclamation-octagon"
                          ></sl-icon
                          >${this._suggestionError}</sl-alert
                        >`
                      : html`
                          <sl-input
                            label="Title"
                            .value=${this._suggestedTitle}
                            @sl-input=${(e: any) =>
                              (this._suggestedTitle = e.target.value)}
                          ></sl-input>
                          <br />
                          <sl-textarea
                            label="Description"
                            .value=${this._suggestedDescription}
                            @sl-input=${(e: any) =>
                              (this._suggestedDescription = e.target.value)}
                            rows="10"
                          ></sl-textarea>
                        `}
                </div>
              </div>
            `
          : ''}
        <sl-button slot="footer" @click=${this.handleClose}>Cancel</sl-button>
        <sl-button
          slot="footer"
          variant="primary"
          .loading=${this._isSubmitting}
          ?disabled=${this._isLoadingSuggestion || this._suggestionError}
          @click=${this.handleSubmit}
        >
          Update Issue
        </sl-button>
      </sl-dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'improve-compliance-modal': ImproveComplianceModal;
  }
}
