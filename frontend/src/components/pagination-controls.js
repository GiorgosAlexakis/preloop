var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
let PaginationControls = class PaginationControls extends LitElement {
    constructor() {
        super(...arguments);
        this.currentPage = 1;
        this.hasMorePages = false;
        this.loading = false;
    }
    _onPrevClick() {
        this.dispatchEvent(new CustomEvent('prev-page'));
    }
    _onNextClick() {
        this.dispatchEvent(new CustomEvent('next-page'));
    }
    render() {
        return html `
      <div class="pagination-controls">
        <sl-button
          @click=${this._onPrevClick}
          ?disabled=${this.currentPage <= 1 || this.loading}
        >
          Previous
        </sl-button>
        <span class="page-number">Page ${this.currentPage}</span>
        <sl-button
          @click=${this._onNextClick}
          ?disabled=${!this.hasMorePages || this.loading}
        >
          Next
        </sl-button>
      </div>
    `;
    }
};
PaginationControls.styles = css `
    .pagination-controls {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: var(--sl-spacing-medium);
      margin-top: var(--sl-spacing-medium);
    }
    .page-number {
      font-weight: var(--sl-font-weight-semibold);
    }
  `;
__decorate([
    property({ type: Number })
], PaginationControls.prototype, "currentPage", void 0);
__decorate([
    property({ type: Boolean })
], PaginationControls.prototype, "hasMorePages", void 0);
__decorate([
    property({ type: Boolean })
], PaginationControls.prototype, "loading", void 0);
PaginationControls = __decorate([
    customElement('pagination-controls')
], PaginationControls);
export { PaginationControls };
