import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import '../../components/tracker-list.ts';

@customElement('trackers-view')
export class TrackersView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: 1rem;
    }
  `;

  render() {
    return html`
      <div class="p-4">
        <h1 class="text-2xl font-bold mb-4">Trackers</h1>
        <tracker-list></tracker-list>
      </div>
    `;
  }
}
