var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css, unsafeCSS } from 'lit';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { customElement, property, state } from 'lit/decorators.js';
import { marked } from 'marked';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import landingStyles from '../../styles/landing.css?inline';
let StaticView = class StaticView extends LitElement {
    constructor() {
        super(...arguments);
        this.src = '';
        this.content = null;
        this.error = null;
    }
    updated(changedProperties) {
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
            }
            else {
                // Markdown file - parse with marked
                this.content = marked(text);
            }
        }
        catch (error) {
            console.error('Error fetching static content:', error);
            this.error = 'There was an issue fetching the content.';
        }
    }
    render() {
        return html `
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
    _renderDynamicContent() {
        if (this.error) {
            return html `
        <sl-alert variant="danger" open>
          <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
          <strong>Error loading content.</strong><br />
          ${this.error}
        </sl-alert>
      `;
        }
        else if (this.content === null) {
            return html `<sl-spinner></sl-spinner>`;
        }
        else {
            return html `${unsafeHTML(this.content)}`;
        }
    }
};
StaticView.styles = [
    unsafeCSS(landingStyles),
    css `
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

      /* Styles for dynamically rendered markdown content */
      .text-section h1 {
        font-size: 2.4rem;
        font-weight: 300;
        color: var(--sl-color-primary-500);
        margin-bottom: 1rem;
      }
      .text-section h2 {
        font-size: 1.8rem;
        font-weight: 300;
        color: var(--sl-color-primary-500);
        margin-top: 2rem;
        margin-bottom: 1rem;
      }
      .text-section h3 {
        font-size: 1.6rem;
        font-weight: 300;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
      }
      .text-section h4 {
        font-size: 1.3rem;
        font-weight: 500;
        margin: 0.5rem 0 0.25rem;
        color: var(--sl-color-neutral-0);
      }
      .text-section p {
        margin-bottom: 1rem;
        line-height: 1.6;
      }
      .text-section a {
        color: var(--sl-color-primary-600);
        text-decoration: underline;
      }
      .text-section a:hover {
        color: var(--sl-color-primary-700);
      }
      .text-section ul,
      .text-section ol {
        margin-bottom: 1rem;
        padding-left: 2rem;
      }
      .text-section strong {
        color: var(--sl-color-primary-400);
      }
      .text-section hr {
        border: none;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        margin: 2rem 0;
      }

      /* Team section styles */
      .team-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 2rem;
        margin: 2rem 0;
      }
      .team-member {
        text-align: center;
        padding: 1.5rem;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
      }
      .team-photo {
        width: 150px;
        height: 150px;
        border-radius: 50%;
        object-fit: cover;
        margin-bottom: 1rem;
        border: 3px solid var(--sl-color-primary-500);
      }
      .team-member p {
        font-size: 0.95rem;
        line-height: 1.5;
        text-align: left;
      }
    `,
];
__decorate([
    property({ type: String })
], StaticView.prototype, "src", void 0);
__decorate([
    state()
], StaticView.prototype, "content", void 0);
__decorate([
    state()
], StaticView.prototype, "error", void 0);
StaticView = __decorate([
    customElement('static-view')
], StaticView);
export { StaticView };
