import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import {
  DuplicatePair,
  executeResolution,
  getResolutionSuggestion,
} from '../api';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio/radio.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/tag/tag.js';

type ResolutionStep = 'initial' | 'close' | 'merge' | 'disambiguate';

@customElement('resolve-issue-modal')
export class ResolveIssueModal extends LitElement {
  @property({ type: Boolean, reflect: true }) open = false;
  @property({ type: Object }) duplicatePair: DuplicatePair | null = null;

  @state() private _isSubmitting = false;
  @state() private _resolutionStep: ResolutionStep = 'initial';
  @state() private _isLoadingSuggestion = false;
  @state() private _mergeTarget: 'A' | 'B' = 'B';
  @state() private _mergedTitle = '';
  @state() private _mergedDescription = '';

  // State for Disambiguate step
  @state() private _disambiguatedTitle1 = '';
  @state() private _disambiguatedDescription1 = '';
  @state() private _disambiguatedTitle2 = '';
  @state() private _disambiguatedDescription2 = '';

  private _handleOpen() {
    this._isSubmitting = false;
    this._resolutionStep = 'initial';
  }

  private _close() {
    this.open = false;
    this.dispatchEvent(
      new CustomEvent('closed', { bubbles: true, composed: true })
    );
  }

  private _goBack() {
    this._resolutionStep = 'initial';
  }

  private async _startResolution(step: ResolutionStep) {
    this._resolutionStep = step;

    // Reset previous suggestions
    this._mergedTitle = '';
    this._mergedDescription = '';
    this._disambiguatedTitle1 = '';
    this._disambiguatedDescription1 = '';
    this._disambiguatedTitle2 = '';
    this._disambiguatedDescription2 = '';

    if (step === 'merge' || step === 'disambiguate') {
      if (!this.duplicatePair?.issue1 || !this.duplicatePair?.issue2) return;
      this._isLoadingSuggestion = true;
      try {
        const resolutionType = step === 'merge' ? 'merged' : 'disambiguated';
        const suggestion = await getResolutionSuggestion(
          this.duplicatePair.issue1.id,
          this.duplicatePair.issue2.id,
          resolutionType
        );

        if (step === 'merge') {
          this._mergedTitle = suggestion.merged_title || '';
          this._mergedDescription = suggestion.merged_description || '';
        } else {
          this._disambiguatedTitle1 = suggestion.disambiguated_title1 || '';
          this._disambiguatedDescription1 =
            suggestion.disambiguated_description1 || '';
          this._disambiguatedTitle2 = suggestion.disambiguated_title2 || '';
          this._disambiguatedDescription2 =
            suggestion.disambiguated_description2 || '';
        }
      } catch (error) {
        console.error('Failed to get suggestion:', error);
        // Optionally, show an error message to the user
      } finally {
        this._isLoadingSuggestion = false;
      }
    }
  }

  private async _handleFinalResolve(resolution: string) {
    if (!this.duplicatePair) return;
    this._isSubmitting = true;

    const { issue1, issue2 } = this.duplicatePair;
    let resolutionData: any = {
      issue1_id: issue1.id,
      issue2_id: issue2.id,
      resolution: resolution,
    };

    if (resolution === 'MERGE') {
      const issueToKeep = this._mergeTarget === 'A' ? issue1 : issue2;
      const issueToClose = this._mergeTarget === 'A' ? issue2 : issue1;
      resolutionData.resolution_reason = `Merged ${issueToClose.key} into ${issueToKeep.key}`;
      resolutionData.resulting_issue1_id = issueToKeep.id;
      resolutionData.merged_title = this._mergedTitle;
      resolutionData.merged_description = this._mergedDescription;
    } else if (resolution === 'DISAMBIGUATE') {
      resolutionData.resolution_reason = 'Disambiguated issues';
      resolutionData.resulting_issue1_id = issue1.id;
      resolutionData.resulting_issue2_id = issue2.id;
      resolutionData.disambiguated_title1 = this._disambiguatedTitle1;
      resolutionData.disambiguated_description1 =
        this._disambiguatedDescription1;
      resolutionData.disambiguated_title2 = this._disambiguatedTitle2;
      resolutionData.disambiguated_description2 =
        this._disambiguatedDescription2;
    } else if (resolution.startsWith('CLOSE_')) {
      const issueToClose = resolution === 'CLOSE_A' ? issue1 : issue2;
      const issueToKeep = resolution === 'CLOSE_A' ? issue2 : issue1;
      resolutionData.resolution = 'CLOSE'; // The API expects 'CLOSE', not 'CLOSE_A' or 'CLOSE_B'
      resolutionData.resolution_reason = `Closed ${issueToClose.key} as duplicate of ${issueToKeep.key}`;
      resolutionData.resulting_issue1_id = issueToKeep.id;
    }

    try {
      await executeResolution(resolutionData);
      this.dispatchEvent(
        new CustomEvent('resolved', { bubbles: true, composed: true })
      );
      this._close();
    } catch (error) {
      console.error('Failed to execute resolution:', error);
      // TODO: Add a user-facing error notification (e.g., a toast)
    } finally {
      this._isSubmitting = false;
    }
  }

  // Step 1: Initial choice
  private renderInitialStep() {
    const actions = [
      {
        id: 'close',
        title: 'Close as Duplicate',
        description:
          'One issue will be closed, the other will remain. You will choose which one to close in the next step.',
        handler: () => this._startResolution('close'),
      },
      {
        id: 'merge',
        title: 'Merge Issues',
        description:
          'Combine both issues into a single issue. You will edit the new title and description in the next step.',
        handler: () => this._startResolution('merge'),
      },
      {
        id: 'disambiguate',
        title: 'Disambiguate Issues',
        description:
          'Edit the titles and descriptions of both issues to make them distinct. Both issues will remain open.',
        handler: () => this._startResolution('disambiguate'),
      },
      {
        id: 'unrelated',
        title: 'Not Duplicates',
        description:
          'Mark the issues as unrelated. This action is immediate and requires no further steps.',
        handler: () => this._handleFinalResolve('UNRELATED'),
      },
    ];

    return html`
      <div class="step-container">
        <div class="initial-options-group">
          ${actions.map(
            (action) => html`
              <div class="action-card" @click=${action.handler}>
                <div class="action-title">${action.title}</div>
                <div class="action-description">${action.description}</div>
              </div>
            `
          )}
        </div>
      </div>
    `;
  }

  // Step 2a: Close
  private renderCloseStep() {
    const issueA = this.duplicatePair?.issue1;
    const issueB = this.duplicatePair?.issue2;
    return html`
      <div class="step-container">
        <h2>Close Duplicate Issue</h2>
        <p>Select which issue to close. The other will remain open.</p>
        <div class="initial-options-group">
          <div
            class="action-card"
            @click=${() => this._handleFinalResolve('CLOSE_A')}
          >
            <div class="action-title">
              Close ${issueA?.key}: ${issueA?.title}
            </div>
            <div class="action-description">
              This will mark ${issueA?.key} as a duplicate of ${issueB?.key} and
              close it. ${issueB?.key} will remain open.
            </div>
          </div>
          <div
            class="action-card"
            @click=${() => this._handleFinalResolve('CLOSE_B')}
          >
            <div class="action-title">
              Close ${issueB?.key}: ${issueB?.title}
            </div>
            <div class="action-description">
              This will mark ${issueB?.key} as a duplicate of ${issueA?.key} and
              close it. ${issueA?.key} will remain open.
            </div>
          </div>
        </div>
        <div class="footer-buttons">
          <sl-button @click="${this._goBack}">Back</sl-button>
        </div>
      </div>
    `;
  }

  // Step 2b: Merge
  private renderMergeStep() {
    const issueA = this.duplicatePair?.issue1;
    const issueB = this.duplicatePair?.issue2;
    return html`
      <div class="step-container">
        <h2>Merge Issues</h2>
        <sl-radio-group
          label="Merge Direction"
          value=${this._mergeTarget}
          @sl-change=${(e: any) => (this._mergeTarget = e.target.value)}
        >
          <sl-radio value="B"
            >Merge ${issueA?.key} into ${issueB?.key}</sl-radio
          >
          <sl-radio value="A"
            >Merge ${issueB?.key} into ${issueA?.key}</sl-radio
          >
        </sl-radio-group>
        ${this._isLoadingSuggestion
          ? html`<div class="loading-suggestion">
              <sl-spinner></sl-spinner>
              <div>Generating suggestion...</div>
            </div>`
          : html`
              <div class="form-group">
                <sl-input
                  label="Merged Issue Title"
                  .value=${this._mergedTitle}
                  @sl-input=${(e: any) => (this._mergedTitle = e.target.value)}
                ></sl-input>
                <sl-textarea
                  label="Merged Issue Description"
                  .value=${this._mergedDescription}
                  @sl-input=${(e: any) =>
                    (this._mergedDescription = e.target.value)}
                  rows="8"
                ></sl-textarea>
              </div>
            `}
        <div class="footer-buttons">
          <sl-button @click="${this._goBack}">Back</sl-button>
          <sl-button
            variant="primary"
            .loading=${this._isSubmitting}
            @click="${() => this._handleFinalResolve('MERGE')}"
            >Resolve Merge</sl-button
          >
        </div>
      </div>
    `;
  }

  // Step 2c: Disambiguate
  private renderDisambiguateStep() {
    const issueA = this.duplicatePair?.issue1;
    const issueB = this.duplicatePair?.issue2;
    return html`
      <div class="step-container">
        <h2>Disambiguate Issues</h2>
        <p>
          Edit the titles and descriptions to make these issues distinct. Both
          will be updated.
        </p>
        ${this._isLoadingSuggestion
          ? html`<div class="loading-suggestion">
              <sl-spinner></sl-spinner>
              <div>Generating suggestion...</div>
            </div>`
          : html`
              <div class="form-group">
                <div class="sub-form-group">
                  <h3>${issueA?.key}: ${issueA?.title}</h3>
                  <sl-input
                    label="New Title"
                    .value=${this._disambiguatedTitle1}
                    @sl-input=${(e: any) =>
                      (this._disambiguatedTitle1 = e.target.value)}
                  ></sl-input>
                  <sl-textarea
                    label="New Description"
                    .value=${this._disambiguatedDescription1}
                    @sl-input=${(e: any) =>
                      (this._disambiguatedDescription1 = e.target.value)}
                    rows="6"
                  ></sl-textarea>
                </div>
                <div class="sub-form-group">
                  <h3>${issueB?.key}: ${issueB?.title}</h3>
                  <sl-input
                    label="New Title"
                    .value=${this._disambiguatedTitle2}
                    @sl-input=${(e: any) =>
                      (this._disambiguatedTitle2 = e.target.value)}
                  ></sl-input>
                  <sl-textarea
                    label="New Description"
                    .value=${this._disambiguatedDescription2}
                    @sl-input=${(e: any) =>
                      (this._disambiguatedDescription2 = e.target.value)}
                    rows="6"
                  ></sl-textarea>
                </div>
              </div>
            `}
        <div class="footer-buttons">
          <sl-button @click="${this._goBack}">Back</sl-button>
          <sl-button
            variant="primary"
            .loading=${this._isSubmitting}
            @click="${() => this._handleFinalResolve('DISAMBIGUATE')}"
            >Resolve Disambiguation</sl-button
          >
        </div>
      </div>
    `;
  }

  render() {
    let content;
    switch (this._resolutionStep) {
      case 'close':
        content = this.renderCloseStep();
        break;
      case 'merge':
        content = this.renderMergeStep();
        break;
      case 'disambiguate':
        content = this.renderDisambiguateStep();
        break;
      default:
        content = this.renderInitialStep();
    }

    const issueAKey = this.duplicatePair?.issue1?.key || 'Issue A';
    const issueBKey = this.duplicatePair?.issue2?.key || 'Issue B';

    return html`
      <sl-dialog
        label="Resolve Duplicates: ${issueAKey} & ${issueBKey}"
        .open=${this.open}
        @sl-show=${this._handleOpen}
        @sl-hide=${this._close}
      >
        ${content}
      </sl-dialog>
    `;
  }

  static styles = css`
    sl-dialog::part(panel) {
      max-width: 80ch;
    }
    sl-dialog::part(header) {
      border-bottom: 1px solid var(--sl-color-neutral-0);
    }
    p,
    ul,
    li {
      line-height: 1.6;
    }
    .step-container,
    .form-group,
    .sub-form-group {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-large);
    }
    .llm-suggestion {
      background-color: var(--sl-color-neutral-50);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-medium);
    }
    .suggestion-header {
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-small);
      margin-bottom: var(--sl-spacing-small);
      font-weight: var(--sl-font-weight-semibold);
    }
    .suggestion-reason {
      font-size: var(--sl-font-size-medium);
      color: var(--sl-color-neutral-700);
      margin: 0;
    }
    .initial-options-group {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-medium);
    }
    .action-card {
      padding: var(--sl-spacing-large);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      cursor: pointer;
      transition: all 0.2s ease-in-out;
    }
    .action-card:hover {
      border-color: var(--sl-color-primary-300);
      background-color: var(--sl-color-neutral-50);
    }
    .action-title {
      color: var(--sl-color-neutral-800);
      margin-bottom: var(--sl-spacing-x-small);
    }
    .action-description {
      color: var(--sl-color-neutral-600);
    }
    .options-group {
      display: flex;
      justify-content: center;
      gap: var(--sl-spacing-medium);
    }
    .footer-buttons {
      display: flex;
      justify-content: flex-start;
      margin-top: var(--sl-spacing-large);
    }
    .footer-buttons:not(:has(sl-button:nth-child(2))) {
      justify-content: flex-start;
    }
    .footer-buttons sl-button:first-child:not(:only-child) {
      margin-right: auto;
    }
    .sub-form-group h3 {
      margin-bottom: calc(-1 * var(--sl-spacing-small));
    }
    .loading-suggestion {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: var(--sl-spacing-medium);
      padding: var(--sl-spacing-large) 0;
    }
  `;
}
