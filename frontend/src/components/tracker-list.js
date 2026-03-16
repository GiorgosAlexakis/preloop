var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { fetchWithAuth } from '../api.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import './tracker-item.ts';
let TrackerList = class TrackerList extends LitElement {
    constructor() {
        super(...arguments);
        this.trackers = [];
        this.isLoading = false;
        this.error = null;
    }
    connectedCallback() {
        super.connectedCallback();
        this.fetchTrackers();
    }
    async fetchTrackers() {
        this.isLoading = true;
        this.error = null;
        try {
            const response = await fetchWithAuth('/api/v1/trackers');
            if (!response.ok) {
                throw new Error('Failed to fetch trackers');
            }
            this.trackers = await response.json();
        }
        catch (error) {
            this.error =
                error instanceof Error ? error.message : 'An unknown error occurred';
        }
        finally {
            this.isLoading = false;
        }
    }
    _handleTrackerEdit(event) {
        this.dispatchEvent(new CustomEvent('tracker-edit', {
            detail: event.detail,
            bubbles: true,
            composed: true,
        }));
    }
    async _handleTrackerDeleted(event) {
        const { id } = event.detail;
        try {
            const response = await fetchWithAuth(`/api/v1/trackers/${id}`, {
                method: 'DELETE',
            });
            if (!response.ok) {
                throw new Error('Failed to delete tracker');
            }
            await this.fetchTrackers();
        }
        catch (error) {
            this.error =
                error instanceof Error ? error.message : 'An unknown error occurred';
        }
    }
    render() {
        if (this.isLoading) {
            return html `<div class="loading-indicator">
        <sl-spinner></sl-spinner>
      </div>`;
        }
        if (this.error) {
            return html `<sl-alert variant="danger" open>
        <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
        <strong>Error:</strong> ${this.error}
      </sl-alert>`;
        }
        return html `
      <div class="tracker-grid">
        ${repeat(this.trackers, (tracker) => tracker.id, (tracker) => html `<tracker-item
              .tracker=${tracker}
              @tracker-deleted=${this._handleTrackerDeleted}
              @tracker-edit=${this._handleTrackerEdit}
            ></tracker-item>`)}
      </div>
    `;
    }
};
TrackerList.styles = css `
    .tracker-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
      gap: var(--sl-spacing-large);
      padding-top: var(--sl-spacing-medium);
    }

    .loading-indicator {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100px;
    }
  `;
__decorate([
    state()
], TrackerList.prototype, "trackers", void 0);
__decorate([
    state()
], TrackerList.prototype, "isLoading", void 0);
__decorate([
    state()
], TrackerList.prototype, "error", void 0);
TrackerList = __decorate([
    customElement('tracker-list')
], TrackerList);
export { TrackerList };
