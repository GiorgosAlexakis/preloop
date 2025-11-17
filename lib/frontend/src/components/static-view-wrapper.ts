import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement } from 'lit/decorators.js';
import './app-header';
import './app-footer';
import landingStyles from '../styles/landing.css?inline';

/**
 * Wrapper component for static SSR content (privacy, terms, etc.)
 * Provides page structure (header, footer) around static HTML content
 */
@customElement('static-view-wrapper')
export class StaticViewWrapper extends LitElement {
  static styles = [
    unsafeCSS(landingStyles),
    css`
      :host {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
        width: 100%;
      }

      main {
        flex: 1;
        padding: 2rem;
        max-width: 800px;
        margin: 0 auto;
        width: 100%;
      }

      /* Styles for slotted article content are now in the article's inline <style> tag
         in the light DOM, since ::slotted() can't style descendants */
    `,
  ];

  render() {
    return html`
      <app-header></app-header>
      <main>
        <div class="text-section">
          <slot></slot>
        </div>
      </main>
      <app-footer></app-footer>
    `;
  }
}
