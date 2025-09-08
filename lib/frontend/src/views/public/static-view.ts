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
      const markdown = await response.text();
      this.content = marked(markdown) as string;
    } catch (error: any) {
      console.error('Error fetching static content:', error);
      this.error = 'There was an issue fetching the content.';
    }
  }

  render() {
    let content;
    if (this.error) {
      content = html`
        <sl-alert variant="danger" open>
          <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
          <strong>Error loading content.</strong><br />
          ${this.error}
        </sl-alert>
      `;
    } else if (this.content === null) {
      content = html`<sl-spinner></sl-spinner>`;
    } else {
      content = html`${unsafeHTML(this.content)}`;
    }

    return html`
      <app-header></app-header>
      <main>
      <div class="section-container">
      ${content}
      </div>
      </main>
      <app-footer></app-footer>
    `;
  }
}
