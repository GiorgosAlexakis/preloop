import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state, query } from 'lit/decorators.js';
import '../../components/tracker-list.ts';
import '../../components/add-tracker-modal.ts';
import type { Tracker } from '../../components/tracker-item.ts';
import type { TrackerList } from '../../components/tracker-list.ts';
import consoleStyles from '../../styles/console-styles.css?inline';

@customElement('trackers-view')
export class TrackersView extends LitElement {
  @state()
  private isAddingTracker = false;

  @state()
  private editingTracker: Tracker | null = null;

  @query('tracker-list')
  private trackerListElement: TrackerList | undefined;

  static styles = [unsafeCSS(consoleStyles)];

  private _openAddTrackerForm() {
    this.isAddingTracker = true;
    this.editingTracker = null;
  }

  private _closeAddTrackerForm() {
    this.isAddingTracker = false;
    this.editingTracker = null;
  }

  private async _handleTrackerAdded(event: CustomEvent) {
    // Don't close modal if there are warnings to display
    if (!event.detail?.hasWarnings) {
      this.isAddingTracker = false;
    }
    await this.trackerListElement?.fetchTrackers();
  }

  private async _handleTrackerUpdated(event: CustomEvent) {
    // Don't close modal if there are warnings to display
    if (!event.detail?.hasWarnings) {
      this.editingTracker = null;
    }
    await this.trackerListElement?.fetchTrackers();
  }

  private _handleTrackerEdit(event: CustomEvent) {
    this.editingTracker = event.detail.tracker;
    this.isAddingTracker = false;
  }

  render() {
    return html`
      <view-header headerText="Trackers" width="narrow">
        <div slot="main-column">
          <sl-button variant="primary" @click=${this._openAddTrackerForm}>
            <sl-icon slot="prefix" name="plus-lg"></sl-icon>
            Add New Tracker
          </sl-button>
        </div>
      </view-header>
      <div class="column-layout narrow">
        <div class="main-column">
          ${this.isAddingTracker
            ? html`<add-tracker-modal
                @tracker-added=${this._handleTrackerAdded}
                @close-modal=${this._closeAddTrackerForm}
              ></add-tracker-modal>`
            : ''}
          ${this.editingTracker
            ? html`<add-tracker-modal
                .tracker=${this.editingTracker}
                @tracker-updated=${this._handleTrackerUpdated}
                @close-modal=${this._closeAddTrackerForm}
              ></add-tracker-modal>`
            : ''}
          <tracker-list @tracker-edit=${this._handleTrackerEdit}></tracker-list>
        </div>
      </div>
    `;
  }
}
