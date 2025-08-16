import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import consoleStyles from '../styles/console-styles.css?inline';

@customElement('view-header')
export class ViewHeader extends LitElement {
  @property({ type: String })
  headerText = '';

  static styles = [unsafeCSS(consoleStyles), css``];

  render() {
    return html`
      <div class="column-layout">
        <div class="main-column">
          <div class="header">
            <h1>${this.headerText}</h1>
            <slot name="main-column"></slot>
          </div>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'view-header': ViewHeader;
  }
}
