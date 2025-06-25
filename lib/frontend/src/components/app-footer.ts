import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';

@customElement('app-footer')
export class AppFooter extends LitElement {
  static styles = [
    css`
      :host {
        display: block;
        background-color: var(--gray-900);
        color: var(--gray-200);
        padding: 48px 0;
        margin-top: auto;
        flex-shrink: 0;
      }

      .footer-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 16px;
      }

      .footer-main {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        flex-wrap: wrap;
        gap: 24px;
      }

      .footer-nav {
        text-align: right;
      }

      .footer-nav ul {
        list-style: none;
        padding: 0;
        margin: 0;
      }

      .footer-nav sl-button::part(label) {
        font-size: 0.9rem;
      }

      .footer-nav sl-button {
        color: var(--gray-200);
        transition: color 0.2s ease;
        margin-bottom: 10px;
      }

      .footer-nav sl-button:hover {
        color: white;
      }

      h5 {
        color: white;
        font-size: 1.1rem;
        margin-bottom: 20px;
        font-weight: 600;
      }

      p {
        font-size: 0.9rem;
        margin-bottom: 10px;
      }

      a {
        color: var(--gray-200);
        text-decoration: none;
        transition: color 0.2s ease;
      }

      a:hover {
        color: white;
      }

      sl-divider {
        margin: 30px 0;
        --color: rgba(255, 255, 255, 0.1);
      }

      .footer-bottom {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 30px;
      }

      .copyright-text {
        font-size: 0.85rem;
      }

      .copyright-text a {
        color: inherit;
        text-decoration: none;
      }

      .copyright-text a:hover {
        text-decoration: underline;
      }

      sl-icon-button {
        color: var(--gray-200);
        font-size: 1.25rem;
        transition: color 0.2s ease;
      }
      sl-icon-button:hover {
        color: white;
      }
    `,
  ];

  switchToOldUI() {
    // Set the cookie to expire in 30 days
    const d = new Date();
    d.setTime(d.getTime() + 30 * 24 * 60 * 60 * 1000);
    let expires = 'expires=' + d.toUTCString();
    document.cookie = 'ui_version=spacebridge; ' + expires + '; path=/';
    // Reload the page
    window.location.reload();
  }

  render() {
    return html`
      <div class="footer-container">
        <div class="footer-main">
          <div>
            <img
              src="/images/logo_dark.png"
              alt="SpaceBridge MCP"
              height="40"
              style="margin-bottom: 16px"
            />
            <p>
              MCP Server for unified issue tracker<br />management and
              AI-powered collaboration.
            </p>
          </div>
          <nav class="footer-nav">
            <ul>
              <li>
                <sl-button variant="text" href="/docs"
                  >API Documentation</sl-button
                >
              </li>
              <li>
                <sl-button variant="text" href="/register">Register</sl-button>
              </li>
              <li><sl-button variant="text" href="/login">Login</sl-button></li>
              <li>
                <sl-button variant="text" href="/privacy"
                  >Privacy Policy</sl-button
                >
              </li>
              <li>
                <sl-button variant="text" href="/terms"
                  >Terms of Service</sl-button
                >
              </li>
              <li>
                <sl-button variant="text" href="/whatis-mcp" target="_blank"
                  >What is MCP?</sl-button
                >
              </li>
              <li>
                <sl-button variant="text" @click=${this.switchToOldUI}>
                  Switch to the old UI
                </sl-button>
              </li>
            </ul>
          </nav>
        </div>
        <sl-divider></sl-divider>
        <div class="footer-bottom">
          <span class="copyright-text"
            >&copy; 2025 <a href="https://spacecode.ai">Spacecode.AI</a>. All
            rights reserved.</span
          >
          <sl-icon-button
            name="linkedin"
            label="LinkedIn"
            href="https://www.linkedin.com/company/spacecode-ai/"
            target="_blank"
          ></sl-icon-button>
        </div>
      </div>
    `;
  }
}
