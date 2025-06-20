import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';

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

      h5 {
        color: white;
        font-size: 1.1rem;
        margin-bottom: 20px;
        font-weight: 600;
      }

      p,
      li {
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

      hr {
        margin: 30px 0;
        opacity: 0.1;
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

      .copyright-text a,
      .linkedin-icon-footer {
        color: inherit;
        text-decoration: none;
      }

      .copyright-text a:hover,
      .linkedin-icon-footer:hover {
        text-decoration: underline;
      }

      .linkedin-icon-footer svg {
        fill: currentColor;
        vertical-align: middle;
      }
      .btn-link {
        background: none;
        border: none;
        padding: 0;
        color: var(--gray-200);
        text-decoration: none;
        cursor: pointer;
      }
      .btn-link:hover {
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
            <ul style="list-style: none; padding: 0; margin: 0;">
              <li><a href="/docs">API Documentation</a></li>
              <li><a href="/register">Register</a></li>
              <li><a href="/login">Login</a></li>
              <li><a href="/privacy">Privacy Policy</a></li>
              <li><a href="/terms">Terms of Service</a></li>
              <li><a href="/whatis-mcp" target="_blank">What is MCP?</a></li>
              <li>
                <button class="btn-link" @click=${this.switchToOldUI}>
                  Switch to the old UI
                </button>
              </li>
            </ul>
          </nav>
        </div>
        <hr />
        <div class="footer-bottom">
          <span class="copyright-text"
            >&copy; 2025 <a href="https://spacecode.ai">Spacecode.AI</a>. All
            rights reserved.</span
          >
          <a
            href="https://www.linkedin.com/company/spacecode-ai/"
            target="_blank"
            rel="noopener noreferrer"
            title="LinkedIn"
            class="linkedin-icon-footer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path
                d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.761 0 5-2.239 5-5v-14c0-2.761-2.239-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"
              />
            </svg>
          </a>
        </div>
      </div>
    `;
  }
}
