import { LitElement, html, css, unsafeCSS } from 'lit';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { customElement, state } from 'lit/decorators.js';
import landingStyles from '../../styles/landing.css?inline';
import '@shoelace-style/shoelace/dist/components/button/button.js';

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
        <section class="hero main-section">
          <div class="section-container hero-inner">
            <div class="hero-content text-center">
              <h1 class="fw-bold">
                Ship <span class="gradient-faster">Faster</span> and
                <span class="gradient-safer">Safer</span> with an AI Co-pilot for
                Your Entire Team.
              </h1>
              <p class="lead">
                SpaceBridge.io integrates with your existing tools (GitHub, Jira,
                GitLab) to intelligently manage issues, automate routine tasks,
                and put a human safety net around your most critical operations.
              </p>
              <div class="hero-buttons">
                <sl-button
                  variant="primary"
                  size="large"
                  @click=${() => (window.location.href = '/register')}
                  >Get Started</sl-button
                >
              </div>
            </div>
          </div>
        </section>

        <section class="feature-section main-section">
          <div class="section-container text-center">
            <h2>Agentic Flows</h2>
            <div class="feature-grid">
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="plug-fill"></sl-icon>
                </div>
                <h3>Seamless Access</h3>
                <p>
                  Empower AI agents with direct access to your development
                  workflows.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="gear-wide-connected"></sl-icon>
                </div>
                <h3>Robust Systems</h3>
                <p>
                  Build autonomous systems that can manage issues and report
                  progress.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="people"></sl-icon>
                </div>
                <h3>Team Collaboration</h3>
                <p>
                  Enable agents to collaborate with your team by creating and
                  updating tasks.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section class="feature-section main-section">
          <div class="section-container text-center">
            <h2>Preloop™, HITL Safety Layer</h2>
            <div class="feature-grid">
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="sliders"></sl-icon>
                </div>
                <h3>Full Control</h3>
                <p>
                  Maintain full control with our human-in-the-loop safety
                  layer.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="eye"></sl-icon>
                </div>
                <h3>Intercept & Review</h3>
                <p>
                  Intercept, review, and approve any AI-driven action before
                  it's executed.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="shield-check"></sl-icon>
                </div>
                <h3>Ensure Safety</h3>
                <p>
                  Guarantee that your AI co-pilot operates safely and to your
                  standards.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section class="feature-section main-section">
          <div class="section-container text-center">
            <h2>Intelligent Automation</h2>
            <div class="feature-grid">
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="intersect"></sl-icon>
                </div>
                <h3>Merge Duplicates</h3>
                <p>
                  Find and merge duplicate issues to reduce clutter and save
                  time.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="clock-history"></sl-icon>
                </div>
                <h3>Auto-Estimate Effort</h3>
                <p>
                  Get consistent, AI-powered effort estimates to improve
                  planning.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="flag"></sl-icon>
                </div>
                <h3>Flag Unready Tickets</h3>
                <p>
                  Ensure tickets meet your 'Definition of Ready' before
                  assignment.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section class="feature-section main-section" id="get-started">
          <div class="section-container">
          <div class="title-container">
            <h2>SpaceBridge MCP Server</h2>
            <a class="main-link" href="/whatis-mcp">What is MCP?</a>
          </div>
            
              <div class="feature-grid">
                <div class="feature-box">
                  <div class="feature-icon">
                    <sl-icon name="search"></sl-icon>
                  </div>
                  <h3>Smart Duplicate Detection</h3>
                  <p>
                    Intelligent similarity search finds and prevents duplicate
                    issues, even when terminology varies.
                  </p>
                </div>
                <div class="feature-box">
                  <div class="feature-icon">
                    <sl-icon name="journal-plus"></sl-icon>
                  </div>
                  <h3>Augment your LLM context</h3>
                  <p>
                    Seamless issue data access that supercharges your AI tools'
                    effectiveness
                  </p>
                </div>
                <div class="feature-box">
                  <div class="feature-icon">
                    <sl-icon name="code-slash"></sl-icon>
                  </div>
                  <h3>Cursor, Windsurf, Claude Code Ready</h3>
                  <p>
                    Streamlined setup process. Use with any agentic system that
                    supports MCP.
                  </p>
                </div>
              </div>
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
                        <h5>Prerequisites</h5>
                        <ul>
                          <li>Python 3.9+ installed</li>
                          <li>SpaceBridge API key (register above)</li>
                          <li>OpenAI API key for similarity search</li>
                        </ul>
                        <h5>Installation</h5>
                        <p>
                          First, install the SpaceBridge package:
                        </p>
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
                        <h5>Prerequisites</h5>
                        <ul>
                          <li>Python 3.9+ installed</li>
                          <li>SpaceBridge API key (register above)</li>
                          <li>OpenAI API key for similarity search</li>
                        </ul>
                        <h5>Installation</h5>
                        <p>
                          First, install the SpaceBridge package:
                        </p>
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
                        <p>
                          Then configure via JSON configuration file:
                        </p>
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

        <section class="video-section main-section">
          <div class="section-container">
            <h2>Demo</h2>
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

        <section class="faq-section main-section">
          <div class="section-container">
            <h2 class="text-center">Frequently Asked Questions</h2>
            <div class="faq-list">
              ${[
                {
                  q: 'What is SpaceBridge?',
                  a: 'SpaceBridge is a smart layer that connects to your existing software development tools (like Jira, GitHub, and GitLab). It helps your team work more efficiently by automating complex tasks and providing a safety net for critical operations, all powered by AI.',
                },
                {
                  q: 'Do I need to replace my issue tracker like Jira or GitHub?',
                  a: 'Absolutely not. SpaceBridge integrates <strong>with</strong> your existing tools. You keep your current workflow, and SpaceBridge enhances it with intelligent features and cross-platform automation, acting as a central hub.',
                },
                {
                  q: 'What can the Intelligent Automation actually do for me?',
                  a: 'It handles tedious but important tasks. For example, it can automatically find and suggest merging duplicate issues across trackers, provide AI-based time estimates for new tickets, or check if a new pull request is missing documentation updates and flag it for review.',
                },
                {
                  q: 'How does the Preloop™ safety feature work?',
                  a: "Preloop™ is a human approval step for your most critical automations. If an automated process wants to do something high-stakes, like roll back a production server, you can create a policy that requires two senior engineers to approve it via Slack or email before the action proceeds. It prevents costly mistakes by ensuring a human is always in the loop for key decisions.",
                },
                {
                  q: 'Is it secure to connect my development tools to SpaceBridge?',
                  a: 'Security is our top priority. SpaceBridge uses industry-standard encryption for all data. We connect to your tools via secure, permission-scoped API tokens and OAuth, ensuring our platform only has the minimum access it needs to function.',
                },
              ].map(
                (faq, index) => html`
                  <div class="faq-item">
                    <div
                      class="faq-question"
                      @click=${() => this._toggleFaq(index)}
                    >
                      <span>${faq.q}</span>
                      <sl-icon
                        name=${this._openFaq === index
                          ? 'chevron-up'
                          : 'chevron-down'}
                      ></sl-icon>
                    </div>
                    <div
                      class="faq-answer ${this._openFaq === index ? 'open' : ''}"
                    >
                      <p>${unsafeHTML(faq.a)}</p>
                    </div>
                  </div>
                `
              )}
            </div>
          </div>
        </section>

        <section class="final-cta main-section special-cta">
          <div class="section-container">
            <h2>Ready to Supercharge your AI Workflow?</h2>
            <sl-button
              variant="primary"
              size="large"
              @click=${() => (window.location.href = '/register')}
              >Get Started For Free</sl-button
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
