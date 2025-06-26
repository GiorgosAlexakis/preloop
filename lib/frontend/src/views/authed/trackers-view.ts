import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import '../../components/tracker-list.ts';

@customElement('trackers-view')
export class TrackersView extends LitElement {
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

  render() {
    return html`
      <div class="container">
      <div class="header">
          <h1 class="title">Trackers</h1>
        </div>
        <tracker-list></tracker-list>
      </div>
    `;
  }
}
