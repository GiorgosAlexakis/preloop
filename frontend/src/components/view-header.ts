import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import consoleStyles from '../styles/console-styles.css?inline';

@customElement('view-header')
export class ViewHeader extends LitElement {
  @property({ type: String })
  headerText = '';

  @property({ type: String })
  width = '';

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: var(--sl-spacing-medium);
      }
      h1 {
        margin: 0;
        color: hsl(var(--foreground));
        font-size: clamp(1.75rem, 2vw, 2.25rem);
        font-weight: 700;
        letter-spacing: -0.035em;
      }
    `,
  ];

  render() {
    return html`
      <div class="column-layout ${this.width}">
        <div class="main-column">
          <slot name="top"></slot>
          <div class="header">
            <h1 style="display: flex; align-items: center; gap: 12px;">
              <slot name="title-prefix"></slot>${this.headerText}
            </h1>
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
