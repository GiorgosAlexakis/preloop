import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

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
    :host {
      display: block;
      border: 1px solid #ccc;
      padding: 16px;
      margin-bottom: 8px;
      border-radius: 4px;
    }
    button {
      background-color: #ff4d4d;
      color: white;
      border: none;
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      margin-top: 8px;
      margin-right: 8px;
    }
    button:hover {
      background-color: #e60000;
    }
    .edit-button {
      background-color: #4d4dff;
    }
    .edit-button:hover {
      background-color: #0000e6;
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
      <div><strong>Name:</strong> ${this.tracker.name}</div>
      <div><strong>Type:</strong> ${this.tracker.tracker_type}</div>
      <button @click=${this._deleteTracker}>Delete</button>
      <button class="edit-button" @click=${this._editTracker}>Edit</button>
    `;
  }
}
