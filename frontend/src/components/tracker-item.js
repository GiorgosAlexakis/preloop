var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
let TrackerItem = class TrackerItem extends LitElement {
    constructor() {
        super(...arguments);
        this.isConfirmingDelete = false;
    }
    _requestDeleteConfirmation() {
        this.isConfirmingDelete = true;
    }
    _cancelDelete() {
        this.isConfirmingDelete = false;
    }
    _confirmDelete() {
        if (!this.tracker)
            return;
        const event = new CustomEvent('tracker-deleted', {
            detail: { id: this.tracker.id },
            bubbles: true,
            composed: true,
        });
        this.dispatchEvent(event);
        this.isConfirmingDelete = false;
    }
    _editTracker() {
        if (!this.tracker)
            return;
        const event = new CustomEvent('tracker-edit', {
            detail: { tracker: this.tracker },
            bubbles: true,
            composed: true,
        });
        this.dispatchEvent(event);
    }
    getTrackerIcon(tracker) {
        const type = tracker.tracker_type?.toLowerCase() || '';
        const name = tracker.name?.toLowerCase() || '';
        if (type.includes('jira') || name.includes('jira')) {
            return { name: 'git', library: 'default' };
        }
        if (type.includes('github') || name.includes('github')) {
            return { name: 'github', library: 'default' };
        }
        if (type.includes('gitlab') || name.includes('gitlab')) {
            return { name: 'gitlab', library: 'default' };
        }
        return { name: 'box-seam', library: 'default' };
    }
    render() {
        if (!this.tracker) {
            return html ``;
        }
        const createdAt = new Date(this.tracker.created).toLocaleDateString();
        const icon = this.getTrackerIcon(this.tracker);
        return html `
      <sl-dialog
        label="Confirm Deletion"
        ?open=${this.isConfirmingDelete}
        @sl-hide=${this._cancelDelete}
      >
        Are you sure you want to delete the tracker "${this.tracker?.name}"?
        <sl-button slot="footer" @click=${this._cancelDelete}>Cancel</sl-button>
        <sl-button slot="footer" variant="danger" @click=${this._confirmDelete}
          >Delete</sl-button
        >
      </sl-dialog>

      <sl-card class="tracker-card">
        <div class="card-content">
          <sl-icon
            class="tracker-icon"
            name=${icon.name}
            library=${icon.library}
          ></sl-icon>
          <h3 class="tracker-name">${this.tracker.name}</h3>
          <p class="tracker-type">${this.tracker.tracker_type}</p>
          <div class="tracker-created">Created: ${createdAt}</div>
        </div>
        <div slot="footer">
          <sl-button size="small" @click=${this._editTracker} pill
            >Edit</sl-button
          >
          <sl-button
            size="small"
            variant="danger"
            @click=${this._requestDeleteConfirmation}
            pill
            >Delete</sl-button
          >
        </div>
      </sl-card>
    `;
    }
};
TrackerItem.styles = css `
    .tracker-card {
      width: 250px;
      height: 320px;
      display: flex;
      flex-direction: column;
    }

    .card-content {
      flex-grow: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: var(--sl-spacing-large);
      text-align: center;
    }

    .tracker-icon {
      font-size: 4rem;
      margin-bottom: var(--sl-spacing-medium);
      color: var(--sl-color-primary-600);
    }

    .tracker-name {
      font-size: var(--sl-font-size-large);
      font-weight: var(--sl-font-weight-semibold);
      margin: 0 0 var(--sl-spacing-x-small) 0;
    }

    .tracker-type {
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-600);
      text-transform: capitalize;
      margin: 0;
    }

    .tracker-created {
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-500);
      margin-top: var(--sl-spacing-medium);
    }

    sl-card::part(footer) {
      display: flex;
      justify-content: space-evenly;
      padding: var(--sl-spacing-small);
      border-top: 1px solid var(--sl-color-neutral-200);
    }

    sl-button {
      flex: 1 1 50%;
      margin: 0 var(--sl-spacing-small);
    }
  `;
__decorate([
    property({ type: Object })
], TrackerItem.prototype, "tracker", void 0);
__decorate([
    state()
], TrackerItem.prototype, "isConfirmingDelete", void 0);
TrackerItem = __decorate([
    customElement('tracker-item')
], TrackerItem);
export { TrackerItem };
