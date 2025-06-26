import { LitElement, html, css } from 'lit';
import { customElement, state, query } from 'lit/decorators.js';
import '../../components/tracker-list.ts';
import '../../components/add-tracker-modal.ts';
import type { Tracker } from '../../components/tracker-item.ts';
import type { TrackerList } from '../../components/tracker-list.ts';

@customElement('trackers-view')
export class TrackersView extends LitElement {
  @state()
  private isAddingTracker = false;

  @state()
  private editingTracker: Tracker | null = null;

  @query('tracker-list')
  private trackerListElement: TrackerList | undefined;

  static styles = css`
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

  private _toggleAddTrackerForm() {
    this.isAddingTracker = !this.isAddingTracker;
    if (this.isAddingTracker) {
      this.editingTracker = null;
    }
  }

  private async _handleTrackerAdded() {
    this.isAddingTracker = false;
    await this.trackerListElement?.fetchTrackers();
  }

  private async _handleTrackerUpdated() {
    this.editingTracker = null;
    await this.trackerListElement?.fetchTrackers();
  }

  private _handleTrackerEdit(event: CustomEvent) {
    this.editingTracker = event.detail.tracker;
    this.isAddingTracker = false;
  }

  render() {
    return html`
      <div class="container">
        <div class="header">
          <h1 class="title">Trackers</h1>
          <sl-button variant="primary" @click=${this._toggleAddTrackerForm}>
            <sl-icon slot="prefix" name="plus-lg"></sl-icon>
            ${this.isAddingTracker || this.editingTracker
              ? 'Cancel'
              : 'Add New Tracker'}
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
        <tracker-list @tracker-edit=${this._handleTrackerEdit}></tracker-list>
      </div>
    `;
  }
}
