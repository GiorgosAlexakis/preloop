import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import landingStyles from '../../styles/landing.css?inline';
import '@vaadin/button';

type IdeTab = 'claude-code' | 'cursor' | 'windsurf';

@customElement('landing-view')
export class LandingView extends LitElement {
  @state() private _activeIdeTab: IdeTab = 'claude-code';
  @state() private _openFaq: number | null = null;

  static styles = [
    css`
      ${unsafeCSS(landingStyles)}
    `,
  ];

  private _handleIdeTabClick(tabId: IdeTab) {
    this._activeIdeTab = tabId;
  }

  private _toggleFaq(index: number) {
    this._openFaq = this._openFaq === index ? null : index;
  }

  private _copyCode(e: Event) {
    const button = e.currentTarget as HTMLElement;
    const pre = button.previousElementSibling;
    if (pre && pre.tagName === 'PRE') {
      const code = pre.querySelector('code');
      if (code) {
        navigator.clipboard.writeText(code.innerText).then(() => {
          const originalHTML = button.innerHTML;
          button.innerHTML =
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check" viewBox="0 0 16 16"><path d="M10.97 4.97a.75.75 0 0 1 1.07 1.05l-3.99 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 0 1 .02-.022z"/></svg>';
          setTimeout(() => {
            button.innerHTML = originalHTML;
          }, 2000);
        });
      }
    }
  }

  render() {
    return html`
      <app-header></app-header>
      <main>
        <section class="hero">
          <div class="section-container hero-inner">
            <div class="hero-content">
              <h1 class="fw-bold">
                Turbocharge your<br />
                <span
                  style="display: inline-block; min-width: 220px; background: linear-gradient(to right, #ff7e5f, #feb47b, #d76d77, #9370DB); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-weight: 700;"
                  >Vibe Coding</span
                ><br />
                with Automated Issue Tracking
              </h1>
              <p class="lead">
                SpaceBridge provides an open source MCP server and a free REST
                API that can keep your issue tracker updated while you focus on
                coding.
              </p>
              <div class="hero-buttons">
                <vaadin-button
                  theme="primary large"
                  @click=${() => (window.location.href = '/register')}
                  >Get Started</vaadin-button
                >
                <vaadin-button
                  theme="tertiary"
                  @click=${() =>
                    window.open(
                      'https://github.com/SpaceBridge/spacebridge',
                      '_blank'
                    )}
                  >What is MCP?</vaadin-button
                >
              </div>
            </div>
            <div class="hero-image">
              <img
                src="/images/diagram.png"
                alt="SpaceBridge Diagram"
                class="img-fluid"
              />
            </div>
          </div>
        </section>

        <section class="feature-section" id="features">
          <div class="section-container">
            <div class="feature-grid">
              <div class="feature-box">
                <div class="feature-icon">
                  <img src="/images/similarity.png" alt="Similarity Icon" />
                </div>
                <h3>Smart Duplicate Detection</h3>
                <p>
                  Intelligent similarity search finds and prevents duplicate
                  issues, even when terminology varies.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <img src="/images/context.png" alt="Context Icon" />
                </div>
                <h3>Augment your LLM context</h3>
                <p>
                  Seamless issue data access that supercharges your AI tools'
                  effectiveness
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <img src="/images/ide.png" alt="IDE Icon" />
                </div>
                <h3>Cursor, Windsurf, Claude Code Ready</h3>
                <p>
                  Streamlined setup process. Use with any agentic system that
                  supports MCP.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section class="video-section">
          <div class="section-container">
            <div class="video-wrapper">
              <iframe
                width="560"
                height="315"
                src="https://www.youtube.com/embed/videoseries?si=qPHwJWgW3yW63Rzr&amp;list=PLr2Jp0c-Qn2itxlxK4vz8fDr7xCAUiDZw"
                title="YouTube video player"
                frameborder="0"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                referrerpolicy="strict-origin-when-cross-origin"
                allowfullscreen=""
              ></iframe>
            </div>
          </div>
        </section>

        <section class="cta-section" id="get-started">
          <div class="section-container">
            <h2>Get Started</h2>
            <div class="get-started-container">
              <div class="ide-tabs">
                <div
                  class="ide-logo-container ${this._activeIdeTab ===
                  'claude-code'
                    ? 'active'
                    : ''}"
                  @click=${() => this._handleIdeTabClick('claude-code')}
                >
                  <img
                    src="/images/Claude_AI_logo.png"
                    alt="Claude Code"
                    width="130"
                  />
                </div>
                <div
                  class="ide-logo-container ${this._activeIdeTab === 'cursor'
                    ? 'active'
                    : ''}"
                  @click=${() => this._handleIdeTabClick('cursor')}
                >
                  <img src="/images/cursor_logo.png" alt="Cursor" width="130" />
                </div>
                <div
                  class="ide-logo-container ${this._activeIdeTab === 'windsurf'
                    ? 'active'
                    : ''}"
                  @click=${() => this._handleIdeTabClick('windsurf')}
                >
                  <img
                    src="/images/windsurf_logo.png"
                    alt="Windsurf"
                    width="130"
                  />
                </div>
              </div>

              <div class="tab-content">
                ${this._activeIdeTab === 'claude-code'
                  ? html`
                      <div>
                        <h4>Install SpaceBridge for Claude Code</h4>
                        <h5>Prerequisites</h5>
                        <ul>
                          <li>Python 3.9+ installed</li>
                          <li>SpaceBridge API key (register above)</li>
                          <li>OpenAI API key for similarity search</li>
                        </ul>
                        <h5>Installation</h5>
                        <p>
                          Install SpaceBridge package and add it to Claude Code:
                        </p>
                        <div class="code-container">
                          <pre><code># First install the package
pip install spacebridge-mcp

# Then add to Claude Code
claude mcp add spacebridge $(which spacebridge-mcp-server) \\
  --scope user \\
  --env SPACEBRIDGE_API_KEY="YOUR_KEY" \\
  --env OPENAI_API_KEY="YOUR_OPENAI_KEY"</code></pre>
                          <button class="copy-btn" @click=${this._copyCode}>
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              fill="currentColor"
                              class="bi bi-clipboard"
                              viewBox="0 0 16 16"
                            >
                              <path
                                d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"
                              />
                              <path
                                d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"
                              />
                            </svg>
                          </button>
                        </div>
                      </div>
                    `
                  : ''}
                ${this._activeIdeTab === 'cursor'
                  ? html`
                      <div>
                        <h4>Install SpaceBridge for Cursor</h4>
                        <h5>Prerequisites</h5>
                        <ul>
                          <li>Python 3.9+ installed</li>
                          <li>SpaceBridge API key (register above)</li>
                          <li>OpenAI API key for similarity search</li>
                        </ul>
                        <h5>Installation</h5>
                        <p>First, install the SpaceBridge package:</p>
                        <div class="code-container">
                          <pre><code>pip install spacebridge-mcp</code></pre>
                          <button class="copy-btn" @click=${this._copyCode}>
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              fill="currentColor"
                              class="bi bi-clipboard"
                              viewBox="0 0 16 16"
                            >
                              <path
                                d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"
                              />
                              <path
                                d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"
                              />
                            </svg>
                          </button>
                        </div>
                        <p>Then configure via JSON file:</p>
                        <div class="code-container">
                          <pre><code># Create or edit ~/.cursor/mcp.json
{
  "mcpServers": {
    "spacebridge": {
      "command": "$(which spacebridge-mcp-server)",
      "env": {
        "SPACEBRIDGE_API_KEY": "YOUR_KEY",
        "OPENAI_API_KEY": "YOUR_OPENAI_KEY"
      }
    }
  }
}</code></pre>
                          <button class="copy-btn" @click=${this._copyCode}>
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              fill="currentColor"
                              class="bi bi-clipboard"
                              viewBox="0 0 16 16"
                            >
                              <path
                                d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"
                              />
                              <path
                                d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"
                              />
                            </svg>
                          </button>
                        </div>
                      </div>
                    `
                  : ''}
                ${this._activeIdeTab === 'windsurf'
                  ? html`
                      <div>
                        <h4>Install SpaceBridge for Windsurf</h4>
                        <h5>Prerequisites</h5>
                        <ul>
                          <li>Python 3.9+ installed</li>
                          <li>SpaceBridge API key (register above)</li>
                          <li>OpenAI API key for similarity search</li>
                        </ul>
                        <h5>Installation</h5>
                        <p>First, install the SpaceBridge package:</p>
                        <div class="code-container">
                          <pre><code>pip install spacebridge-mcp</code></pre>
                          <button class="copy-btn" @click=${this._copyCode}>
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              fill="currentColor"
                              class="bi bi-clipboard"
                              viewBox="0 0 16 16"
                            >
                              <path
                                d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"
                              />
                              <path
                                d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"
                              />
                            </svg>
                          </button>
                        </div>
                        <p>Then configure via JSON configuration file:</p>
                        <div class="code-container">
                          <pre><code>{
  "mcpServers": {
    "spacebridge": {
      "command": "/full/path/to/spacebridge-mcp-server",
      "args": [],
      "env": {
        "SPACEBRIDGE_API_KEY": "YOUR_KEY",
        "OPENAI_API_KEY": "YOUR_OPENAI_KEY"
      }
    }
  }
}</code></pre>
                          <button class="copy-btn" @click=${this._copyCode}>
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              width="16"
                              height="16"
                              fill="currentColor"
                              class="bi bi-clipboard"
                              viewBox="0 0 16 16"
                            >
                              <path
                                d="M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z"
                              />
                              <path
                                d="M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zm-3-1A1.5 1.5 0 0 0 5 1.5v1A1.5 1.5 0 0 0 6.5 4h3A1.5 1.5 0 0 0 11 2.5v-1A1.5 1.5 0 0 0 9.5 0h-3z"
                              />
                            </svg>
                          </button>
                        </div>
                      </div>
                    `
                  : ''}
              </div>
            </div>
          </div>
        </section>

        <section class="faq-section">
          <div class="section-container">
            <h2>FAQs</h2>
            <div class="faq-container">
              ${this.renderFaqItem(
                0,
                'What is SpaceBridge?',
                'SpaceBridge is an open-source Master Control Program (MCP) server designed to unify your issue trackers (like Jira, GitHub Issues, GitLab Issues) and enhance them with AI-powered features like similarity search for duplicate detection. It provides a consistent API for AI agents and developers to interact with issue data.'
              )}
              ${this.renderFaqItem(
                1,
                'How does SpaceBridge help with AI development?',
                "SpaceBridge provides a standardized MCP interface, allowing AI agents (like those in Claude Code, Cursor, or Windsurf) to easily access and manipulate issue tracker data. This augments the AI's context, enabling it to perform tasks like automated issue creation, updates, and intelligent searches more effectively."
              )}
              ${this.renderFaqItem(
                2,
                'Is SpaceBridge free to use?',
                'Yes, the SpaceBridge MCP server software is open-source (MIT License) and free to self-host. We also offer a free tier for our hosted REST API service, which is perfect for individual developers and small teams to get started.'
              )}
            </div>
          </div>
        </section>

        <section class="final-cta">
          <div class="section-container">
            <h2>Ready to Supercharge your AI Workflow?</h2>
            <vaadin-button
              theme="primary large"
              @click=${() => (window.location.href = '/register')}
              >Get Started For Free</vaadin-button
            >
          </div>
        </section>
      </main>
      <app-footer></app-footer>
    `;
  }

  private renderFaqItem(index: number, question: string, answer: string) {
    const isOpen = this._openFaq === index;
    return html`
      <div class="faq-item">
        <button class="faq-question" @click=${() => this._toggleFaq(index)}>
          <span>${question}</span>
          <span class="faq-icon">${isOpen ? '−' : '+'}</span>
        </button>
        ${isOpen ? html`<div class="faq-answer">${answer}</div>` : ''}
      </div>
    `;
  }
}
