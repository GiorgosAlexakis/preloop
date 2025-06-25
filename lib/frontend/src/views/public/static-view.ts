import { LitElement, html, css } from 'lit';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { customElement, property, state } from 'lit/decorators.js';
import { unsafeStatic } from 'lit/static-html.js';
import { marked } from 'marked';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';

@customElement('static-view')
export class StaticView extends LitElement {
  @property({ type: String }) src = '';
  @state() private content: string | null = null;

  static styles = css`
    :host {
      display: block;
      padding: 2rem;
      max-width: 800px;
      margin: 0 auto;
    }
    h1,
    h2,
    h3 {
      color: var(--sl-color-primary-500);
    }
  `;

  async firstUpdated() {
    if (this.src) {
      try {
        const response = await fetch(this.src);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const markdown = await response.text();
        this.content = marked(markdown) as string;
      } catch (error) {
        console.error('Error fetching static content:', error);
        this.content = `
          <sl-alert variant="danger" open>
            <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
            <strong>Error loading content.</strong><br />
            There was an issue fetching the content from the specified source.
          </sl-alert>
        `;
      }
    }
  }

  render() {
    if (this.content === null) {
      return html`<sl-spinner></sl-spinner>`;
    }
    return html`${unsafeHTML(this.content)}`;
  }
}