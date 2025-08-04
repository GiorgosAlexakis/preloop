import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import { router } from '../router';
import './logo-component';

@customElement('app-footer')
export class AppFooter extends LitElement {
  static styles = [
    css`
      :host {
        display: block;
        color: rgb(161, 161, 170);
        padding: 0 0 48px 0;
        flex-shrink: 0;
      }

      p {
        line-height: 1.6;
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

      .footer-nav li {
        margin-bottom: 10px;
      }

      .footer-nav a {
        font-size: 0.9rem;
        color: rgb(161, 161, 170);
        transition: color 0.2s ease;
        text-decoration: none;
        cursor: pointer;
      }

      .footer-nav a:hover {
        color: rgb(178, 178, 182);
      }

      .divider {
        margin: 30px 0;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
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
    `,
  ];

  handleLinkClick(event: MouseEvent) {
    event.preventDefault();
    const target = event.target as HTMLAnchorElement;
    const path = target.getAttribute('href');
    if (path) {
      router.navigate(path);
    }
  }

  switchToOldUI(event: MouseEvent) {
    event.preventDefault();
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
        <div class="divider"></div>
        <div class="footer-main">
          <div>
            <logo-component
              override-theme="dark"
            ></logo-component>
          </div>
          <nav class="footer-nav">
            <ul>
              <li><a href="/docs">API Documentation</a></li>
              <li><a href="/register">Register</a></li>
              <li><a href="/login">Sign in</a></li>
              <li><a href="/privacy">Privacy Policy</a></li>
              <li><a href="/terms">Terms of Service</a></li>
              <li><a href="/whatis-mcp" target="_blank">What is MCP?</a></li>
            </ul>
          </nav>
        </div>
        <div class="divider"></div>
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
