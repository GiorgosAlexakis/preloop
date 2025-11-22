import { LitElement, html, css, PropertyValues, unsafeCSS } from 'lit';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { customElement, property, state } from 'lit/decorators.js';
import { marked } from 'marked';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import landingStyles from '../../styles/landing.css?inline';

@customElement('static-view')
export class StaticView extends LitElement {
  @property({ type: String }) src = '';
  @state() private content: string | null = null;
  @state() private error: string | null = null;

  static styles = [
    unsafeCSS(landingStyles),
    css`
      :host {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
      }
      main {
        flex: 1;
        padding: 2rem;
        max-width: 800px;
        margin: 0 auto;
        width: 100%;
      }

      /* Ensure slotted content is visible and styled properly */
      ::slotted(*) {
        display: block;
        line-height: 1.6;
      }

      ::slotted(h1) {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
      }

      ::slotted(h2) {
        font-size: 2rem;
        font-weight: bold;
        margin-top: 2rem;
        margin-bottom: 1rem;
      }

      ::slotted(h3) {
        font-size: 1.5rem;
        font-weight: bold;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
      }

      ::slotted(p) {
        margin-bottom: 1rem;
      }

      ::slotted(ul),
      ::slotted(ol) {
        margin-bottom: 1rem;
        padding-left: 2rem;
      }
    `,
  ];

  updated(changedProperties: PropertyValues) {
    if (changedProperties.has('src') && this.src) {
      this.fetchContent();
    }
  }

  async fetchContent() {
    this.content = null;
    this.error = null;
    try {
      const response = await fetch(this.src);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const text = await response.text();

      // Check if the file is HTML or markdown based on extension
      if (this.src.endsWith('.html')) {
        // HTML file - use as-is
        this.content = text;
      } else {
        // Markdown file - parse with marked
        this.content = marked(text) as string;
      }
    } catch (error: any) {
      console.error('Error fetching static content:', error);
      this.error = 'There was an issue fetching the content.';
    }
  }

  render() {
    return html`
      <app-header></app-header>
      <main>
        <div class="text-section">
          <!-- Slotted skeleton content for SEO - visible without JavaScript -->
          <slot name="static-content"> ${this._renderDynamicContent()} </slot>
        </div>
      </main>
      <app-footer></app-footer>
    `;
  }

  private _renderDynamicContent() {
    if (this.error) {
      return html`
        <sl-alert variant="danger" open>
          <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
          <strong>Error loading content.</strong><br />
          ${this.error}
        </sl-alert>
      `;
    } else if (this.content === null) {
      return html`<sl-spinner></sl-spinner>`;
    } else {
      return html`${unsafeHTML(this.content)}`;
    }
  }
}
