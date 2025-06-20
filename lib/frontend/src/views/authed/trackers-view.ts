import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { getTrackers } from '../../api';
import '@vaadin/grid';
import '../../components/add-tracker-modal';

interface Tracker {
  id: string;
  name: string;
  tracker_type: string;
  url: string;
  is_active: boolean;
}

@customElement('trackers-view')
export class TrackersView extends LitElement {
  @state()
  private trackers: Tracker[] = [];

  @state()
  private isModalOpened = false;

  static styles = css`
    :host {
      display: block;
      padding: 1rem;
    }
    vaadin-grid {
      height: 100%;
    }
  `;

  async firstUpdated() {
    this.fetchTrackers();
  }

  async fetchTrackers() {
    this.trackers = await getTrackers();
  }

  render() {
    return html`
      <add-tracker-modal
        .opened=${this.isModalOpened}
        @opened-changed=${(e: CustomEvent) => (this.isModalOpened = e.detail.value)}
        @save=${this.fetchTrackers}
      ></add-tracker-modal>

      <div class="p-4">
        <div class="flex justify-between items-center mb-4">
          <h1 class="text-2xl font-bold">Trackers</h1>
          <vaadin-button @click=${() => (this.isModalOpened = true)}>
            Add Tracker
          </vaadin-button>
        </div>
        <vaadin-grid .items=${this.trackers}>
          <vaadin-grid-column path="name" header="Name"></vaadin-grid-column>
          <vaadin-grid-column
            path="tracker_type"
            header="Type"
          ></vaadin-grid-column>
          <vaadin-grid-column path="url" header="URL"></vaadin-grid-column>
          <vaadin-grid-column header="Status">
            <template>
                <span class$="[[item.is_active ? 'text-green-500' : 'text-red-500']]">
                    [[item.is_active ? 'Active' : 'Inactive']]
                </span>
            </template>
          </vaadin-grid-column>
        </vaadin-grid>
      </div>
    `;
  }
}
