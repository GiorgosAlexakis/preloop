var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { when } from 'lit/directives/when.js';
import { getStatusVariant, getComplianceVariant } from '../utils/verdict';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
let SingleIssueDetailView = class SingleIssueDetailView extends LitElement {
    constructor() {
        super(...arguments);
        this.issue = null;
        this.complianceResult = null;
    }
    render() {
        if (!this.issue) {
            return nothing;
        }
        return html `
      <div class="detail-section">
        <h3>
          <span> ${this.issue.title} </span>
          <sl-badge
            variant=${getStatusVariant(this.issue.status)}
            class="issue-status"
            >${this.issue.status}</sl-badge
          >
        </h3>
        ${when(this.issue.description, () => html `<div class="issue-description">
              ${unsafeHTML(this.issue.description)}
            </div>`, () => html `<sl-alert variant="primary" open>
              <sl-icon slot="icon" name="info-circle"></sl-icon>
              No description provided.
            </sl-alert>`)}
      </div>

      <slot name="additional-info"></slot>

      ${when(this.complianceResult, () => html `
          <div class="review-section">
            <h3>${this.complianceResult.name} Review</h3>
            <sl-badge
              variant=${getComplianceVariant(this.complianceResult.compliance_factor)}
              pill
            >
              ${(this.complianceResult.compliance_factor * 100).toFixed(0)}%
            </sl-badge>
            <div class="issue-description compliance-reason">
              ${this.complianceResult.reason}
            </div>
          </div>
        `)}
    `;
    }
};
SingleIssueDetailView.styles = css `
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

    .detail-section .row {
      font-size: var(--sl-font-size-medium);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .review-section {
      margin-top: 3rem;
    }

    .issue-description {
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-700);
      background-color: var(--sl-color-neutral-100);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-medium);
      white-space: pre-line;
      overflow-wrap: break-word;
      max-height: 400px;
      overflow-y: auto;
    }
    .issue-status {
      font-size: var(--sl-font-size-x-small);
      text-transform: uppercase;
    }
    .compliance-reason {
      margin-top: var(--sl-spacing-small);
    }
    .compliance-rows {
      display: flex;
      flex-direction: column;
      gap: var(--sl-spacing-small);
    }
  `;
__decorate([
    property({ type: Object })
], SingleIssueDetailView.prototype, "issue", void 0);
__decorate([
    property({ type: Object })
], SingleIssueDetailView.prototype, "complianceResult", void 0);
SingleIssueDetailView = __decorate([
    customElement('single-issue-detail-view')
], SingleIssueDetailView);
export { SingleIssueDetailView };
