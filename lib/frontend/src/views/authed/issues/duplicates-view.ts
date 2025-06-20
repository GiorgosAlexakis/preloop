import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { getDuplicateIssues } from '../../../api';

@customElement('duplicates-view')
export class DuplicatesView extends LitElement {
  static styles = css`
    :host {
      display: block;
    }
  `;

  @state()
  private issues: any[] = [];

  async connectedCallback() {
    super.connectedCallback();
    this.issues = await getDuplicateIssues();
  }

  render() {
    return html`
      <h1>Duplicate Issues</h1>
      ${this.issues.length > 0
        ? html`
            <ul>
              ${this.issues.map((issue) => html`<li>${issue.title}</li>`)}
            </ul>
          `
        : html` <p>No duplicate issues found.</p> `}
    `;
  }
}
