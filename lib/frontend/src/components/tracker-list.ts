import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { fetchWithAuth } from '../api.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import './tracker-item.ts';
import './add-tracker-modal.ts';
import type { Tracker } from './tracker-item.ts';

@customElement('tracker-list')
export class TrackerList extends LitElement {
  @state()
  private trackers: Tracker[] = [];

  @state()
  private isLoading = false;

  @state()
  private error: string | null = null;

  @state()
  private isAddingTracker = false;

  @state()
  private editingTracker: Tracker | null = null;

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
    } catch (error) {
      this.error =
        error instanceof Error ? error.message : 'An unknown error occurred';
    } finally {
      this.isLoading = false;
    }
  }

  private _toggleAddTrackerForm() {
    this.isAddingTracker = !this.isAddingTracker;
    if (this.isAddingTracker) {
      this.editingTracker = null;
    }
  }

  private async _handleTrackerAdded() {
    this.isAddingTracker = false;
    await this.fetchTrackers();
  }

  private async _handleTrackerUpdated() {
    this.editingTracker = null;
    await this.fetchTrackers();
  }

  private _handleTrackerEdit(event: CustomEvent) {
    this.editingTracker = event.detail.tracker;
    this.isAddingTracker = false;
  }

  private async _handleTrackerDeleted(event: CustomEvent) {
    const { id } = event.detail;
    try {
      const response = await fetchWithAuth(`/api/v1/trackers/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error('Failed to delete tracker');
      }
      await this.fetchTrackers();
    } catch (error) {
      this.error =
        error instanceof Error ? error.message : 'An unknown error occurred';
    }
  }

  static styles = css`
    :host {
      display: block;
      max-width: 800px;
      margin: 0 auto;
      padding: 2rem;
    }
    .controls {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 1rem;
    }
    .loading-indicator {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100px;
    }
  `;

  render() {
    if (this.isLoading) {
      return html`<div class="loading-indicator"><sl-spinner></sl-spinner></div>`;
    }

    if (this.error) {
      return html`<sl-alert variant="danger" open>
        <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
        <strong>Error:</strong> ${this.error}
      </sl-alert>`;
    }

    return html`
      <div>
        <div class="controls">
          <sl-button variant="primary" @click=${this._toggleAddTrackerForm}>
            ${this.isAddingTracker ? 'Cancel' : 'Add New Tracker'}
          </sl-button>
        </div>

        ${this.isAddingTracker
          ? html`<add-tracker-modal
              @tracker-added=${this._handleTrackerAdded}
            ></add-tracker-modal>`
          : ''}
        ${this.editingTracker
          ? html`<add-tracker-modal
              .tracker=${this.editingTracker}
              @tracker-updated=${this._handleTrackerUpdated}
            ></add-tracker-modal>`
          : ''}
        ${repeat(
          this.trackers,
          (tracker) => tracker.id,
          (tracker) =>
            html`<tracker-item
              .tracker=${tracker}
              @tracker-deleted=${this._handleTrackerDeleted}
              @tracker-edit=${this._handleTrackerEdit}
            ></tracker-item>`
        )}
      </div>
    `;
  }
}
