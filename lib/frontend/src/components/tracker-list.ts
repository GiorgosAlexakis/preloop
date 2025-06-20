import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { fetchApi } from '../api.js';
import '@material/web/button/filled-button.js';
import './tracker-item.ts';
import './add-tracker-form.ts';
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
      this.trackers = await fetchApi('/api/v1/trackers');
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
      await fetchApi(`/api/v1/trackers/${id}`, {
        method: 'DELETE',
      });
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
    .error {
      color: var(--md-sys-color-error);
    }
    .controls {
      margin-bottom: 1rem;
    }
  `;

  render() {
    if (this.isLoading) {
      return html`<p>Loading...</p>`;
    }

    if (this.error) {
      return html`<p class="error">Error: ${this.error}</p>`;
    }

    return html`
      <div>
        <div class="controls">
          <md-filled-button @click=${this._toggleAddTrackerForm}>
            ${this.isAddingTracker ? 'Cancel' : 'Add New Tracker'}
          </md-filled-button>
        </div>

        ${this.isAddingTracker
          ? html`<add-tracker-form
              @tracker-added=${this._handleTrackerAdded}
            ></add-tracker-form>`
          : ''}
        ${this.editingTracker
          ? html`<add-tracker-form
              .tracker=${this.editingTracker}
              @tracker-updated=${this._handleTrackerUpdated}
            ></add-tracker-form>`
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
