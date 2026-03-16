var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { getDuplicateIssues } from '../../../api';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
let DuplicatesView = class DuplicatesView extends LitElement {
    constructor() {
        super(...arguments);
        this.issues = [];
    }
    async connectedCallback() {
        super.connectedCallback();
        this.issues = await getDuplicateIssues();
    }
    render() {
        return html `
      <div class="container">
        <div class="header">
          <h1 class="title">Issues Dashboard</h1>
        </div>
        <div class="container">
          ${this.issues.length > 0
            ? html `
                <sl-menu>
                  ${this.issues.map((issue) => html `<sl-menu-item>${issue.title}</sl-menu-item>`)}
                </sl-menu>
              `
            : html `
                <sl-alert variant="primary" open>
                  <sl-icon slot="icon" name="info-circle"></sl-icon>
                  No duplicate issues found.
                </sl-alert>
              `}
        </div>
      </div>
    `;
    }
};
DuplicatesView.styles = css `
    :host {
      display: block;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: var(--sl-spacing-large);
    }

    .container {
      max-width: var(--console-container-max-width);
      padding: var(--sl-spacing-x-large);
    }
  `;
__decorate([
    state()
], DuplicatesView.prototype, "issues", void 0);
DuplicatesView = __decorate([
    customElement('duplicates-view')
], DuplicatesView);
export { DuplicatesView };
