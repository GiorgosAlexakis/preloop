import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';

export interface Tracker {
  id: string;
  name: string;
  tracker_type: string;
}

@customElement('tracker-item')
export class TrackerItem extends LitElement {
  @property({ type: Object })
  tracker?: Tracker;

  static styles = css`
    sl-card {
      margin-bottom: 1rem;
    }
  `;

  private _deleteTracker() {
    if (!this.tracker) return;
    const event = new CustomEvent('tracker-deleted', {
      detail: { id: this.tracker.id },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  private _editTracker() {
    if (!this.tracker) return;
    const event = new CustomEvent('tracker-edit', {
      detail: { tracker: this.tracker },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }

  render() {
    if (!this.tracker) {
      return html``;
    }

    return html`
      <sl-card>
        <div slot="header">${this.tracker.name}</div>
        <div><strong>Type:</strong> ${this.tracker.tracker_type}</div>
        <div slot="footer">
          <sl-button variant="primary" @click=${this._editTracker}
            >Edit</sl-button
          >
          <sl-button variant="danger" @click=${this._deleteTracker}
            >Delete</sl-button
          >
        </div>
      </sl-card>
    `;
  }
}
