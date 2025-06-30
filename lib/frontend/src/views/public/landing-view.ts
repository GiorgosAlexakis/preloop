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
              <h1 class="fw-bold">The Trust Layer for Your AI Workforce</h1>
              <p class="lead">
                SpaceBridge governs your AI agents, closing the alignment gap
                between autonomous operations and critical business context.
                Deploy AI with confidence.
              </p>
              <div class="hero-buttons">
                <sl-button
                  variant="primary"
                  size="large"
                  @click=${() => (window.location.href = '/contact')}
                  >Request a Demo</sl-button
                >
              </div>
            </div>
          </div>
        </section>

        <section class="feature-section main-section">
          <div class="section-container text-center">
            <h2>Ground Your AI with Context</h2>
            <div class="feature-grid">
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="plug-fill"></sl-icon>
                </div>
                <h3>A Single Source of Truth</h3>
                <p>
                  Our hub syncs with Jira, GitHub, and GitLab to create a
                  flawless source of 'ground truth' for your AI agents.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="gear-wide-connected"></sl-icon>
                </div>
                <h3>Prevent Context Drift</h3>
                <p>
                  We provide the AI with a long-term memory of business goals,
                  ensuring it solves the right problem, not just the technical
                  one.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="people"></sl-icon>
                </div>
                <h3>Deeper Understanding</h3>
                <p>
                  By de-duplicating issues and understanding project history,
                  the AI operates with full context.
                </p>
              </div>
            </div>
          </div>
          <div class="section-container">
            <img
              src="/images/ui_2.png"
              alt="SpaceBridge UI showing intelligent issue management"
              width="1200"
              height="264"
              class="ui-shot"
            />
          </div>
        </section>

        <section class="feature-section main-section">
          <div class="section-container text-center">
            <h2>Automate Routine Work with Confidence</h2>
            <div class="feature-grid">
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="intersect"></sl-icon>
                </div>
                <h3>High-Value, Low-Risk Tasks</h3>
                <p>
                  With grounded context, our agentic flows can safely handle
                  routine work, like drafting documentation.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="clock-history"></sl-icon>
                </div>
                <h3>Initial Diagnostics</h3>
                <p>
                  Automatically run initial diagnostics on a service outage or
                  suggest test coverage for a new feature.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="flag"></sl-icon>
                </div>
                <h3>Free Up Your Best People</h3>
                <p>
                  Deliver immediate productivity wins and free up your senior
                  developers from tedious toil, building trust in the system.
                </p>
              </div>
            </div>
          </div>
          <div class="section-container">
            <img
              src="/images/ui_1.png"
              alt="SpaceBridge UI showing intelligent issue management"
              width="1200"
              height="224"
              class="ui-shot"
            />
          </div>
        </section>

        <section class="feature-section main-section">
          <div class="section-container text-center">
            <h2>Safeguard Every Critical Action</h2>
            <div class="feature-grid">
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="sliders"></sl-icon>
                </div>
                <h3>The Ultimate Safety Switch</h3>
                <p>
                  For any high-risk action, our Preloop™ Human Approval Layer
                  intercepts the command before it executes.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="eye"></sl-icon>
                </div>
                <h3>Intelligent Notifications</h3>
                <p>
                  The right people are instantly notified on Slack, SMS, or our
                  app to provide a simple 'Approve/Deny'.
                </p>
              </div>
              <div class="feature-box">
                <div class="feature-icon">
                  <sl-icon name="shield-check"></sl-icon>
                </div>
                <h3>Solve the Judgment Deficit</h3>
                <p>
                  Preloop™ makes it possible to use AI for high-stakes tasks
                  like server rollbacks, with complete human oversight.
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
            <h3>Get Started with MCP</h3>
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
                  a: 'Preloop™ is a human approval step for your most critical automations. If an automated process wants to do something high-stakes, like roll back a production server, you can create a policy that requires two senior engineers to approve it via Slack or email before the action proceeds. It prevents costly mistakes by ensuring a human is always in the loop for key decisions.',
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
                      class="faq-answer ${this._openFaq === index
                        ? 'open'
                        : ''}"
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
            <h2>Your Foundation for Enterprise-Grade AI</h2>
            <sl-button
              variant="primary"
              size="large"
              @click=${() => (window.location.href = '/contact')}
              >Request a Demo</sl-button
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
