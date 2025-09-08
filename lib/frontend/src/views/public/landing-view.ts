import { LitElement, html, css, unsafeCSS } from 'lit';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { customElement, state, query } from 'lit/decorators.js';
import landingStyles from '../../styles/landing.css?inline';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import type SlCarousel from '@shoelace-style/shoelace/dist/components/carousel/carousel.js';
import '@shoelace-style/shoelace/dist/components/carousel/carousel.js';
import '@shoelace-style/shoelace/dist/components/carousel-item/carousel-item.js';
import type SlCarouselItem from '@shoelace-style/shoelace/dist/components/carousel-item/carousel-item.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';

type IdeTab = 'claude-code' | 'cursor' | 'windsurf';

interface FeatureSlide {
  title: string;
  text: string;
  videoUrl: string;
  placeholderImg: string;
}

@customElement('landing-view')
export class LandingView extends LitElement {
  @query('.feature-carousel') private _carousel!: SlCarousel;
  @state() private _activeIdeTab: IdeTab = 'claude-code';
  @state() private _openFaq: number | null = null;
  @state() private _showVideo: boolean[] = [false, false, false];
  @state() private _activeSlideIndex = 0;
  @state() private _featureSlides: FeatureSlide[] = [
    {
      title: 'Eliminate Duplicates & Overlap',
      text: 'Our AI analyzes your issues and detects true duplicates beyond simple keyword matching, reveals where issues and epics intersect, and provides actionable recommendations to merge, deconflict, or link related items - cleaning your backlog with a single click.',
      videoUrl: 'https://www.youtube.com/embed/Fw6JZDK1z7M',
      placeholderImg: '/images/ui_01.png',
    },
    {
      title: 'Achieve Compliance for Every Issue',
      text: 'Get Definition of Ready scores for goal clarity and acceptance criteria, risk analysis for potential roadblocks, and AI-driven implementation complexity estimates. Our AI-powered suggestions help improve titles and descriptions, ensuring every ticket is crystal clear and development-ready.',
      videoUrl: 'https://www.youtube.com/embed/Fw6JZDK1z7M',
      placeholderImg: '/images/ui_02.png',
    },
    {
      title: 'Discover Unmapped Dependencies',
      text: "Spacebridge scans your issue tracker for hidden dependencies that haven't been mapped, helping you avoid unexpected blockers and ensure smooth sprint flow. Review AI-detected relationships and update your tracker in one tap through our intuitive interface.",
      videoUrl: 'https://www.youtube.com/embed/Fw6JZDK1z7M',
      placeholderImg: '/images/ui_03.png',
    },
  ];

  @state() private _faqs = [
    {
      q: 'What is Spacebridge?',
      a: 'Spacebridge is an AI platform that connects to your existing project management tools like Jira, GitHub, and GitLab. It acts as an intelligent governance layer for your backlog, helping you eliminate duplicate issues, ensure tickets are development-ready, and discover hidden dependencies. By automating backlog curation, you can focus on building better products, faster.',
    },
    {
      q: 'Which issue tracking and project management platforms does Spacebridge support?',
      a: 'Spacebridge offers native integrations with Jira, GitHub, and GitLab. We are continuously expanding our support for other platforms based on customer needs.',
    },
    {
      q: 'How does AI-Assisted Product Management help my team?',
      a: "AI-Assisted Product Management helps your team by automating the tedious parts of backlog curation. Spacebridge cleans your backlog by identifying true duplicate issues and thematic overlap, improves compliance with 'Definition of Ready' scores for every ticket, and prevents unexpected blockers by discovering unmapped dependencies. This allows your team to spend less time on administrative tasks and more time on strategic, high-impact work.",
    },
    {
      q: "How does Spacebridge ensure issues are 'development-ready'?",
      a: "Spacebridge provides a 'Definition of Ready' score for each issue, analyzing goal clarity and acceptance criteria. It also offers risk analysis to identify potential roadblocks and AI-driven estimates for implementation complexity. These insights, combined with AI-powered suggestions for improving titles and descriptions, help ensure every ticket is compliant and ready for development.",
    },
    {
      q: 'How does Spacebridge handle dependencies between issues?',
      a: 'Spacebridge automatically scans your issue tracker to discover hidden or unmapped dependencies that could cause unexpected blockers. It presents these AI-detected relationships in an intuitive interface, allowing you to review and update your tracker with a single click, ensuring a smoother sprint flow.',
    },
    {
      q: 'Is it secure to connect my development tools to Spacebridge?',
      a: 'Security is our top priority. Spacebridge uses industry-standard encryption for all data. We connect to your tools via secure, permission-scoped API tokens and OAuth, ensuring our platform only has the minimum access it needs to function.',
    },
  ];

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

  private _playVideo(index: number) {
    const newShowVideo = [...this._showVideo];
    newShowVideo[index] = true;
    this._showVideo = newShowVideo;
  }

  private _handleSlideChange(
    e: CustomEvent<{ index: number; slide: SlCarouselItem }>
  ) {
    this._activeSlideIndex = e.detail.index;
  }

  render() {
    return html`
      <app-header></app-header>
      <main>
        <section class="hero main-section">
          <div class="section-container hero-inner">
            <div class="hero-content">
              <h1 class="fw-bold">
                Drive your <span class="gradient-product">Product</span> with
                <span class="gradient-ai">AI</span>
              </h1>
              <p class="lead">
                Eliminate duplicates, ensure compliance, and map dependencies—so
                you can ship faster.
              </p>
              <div class="hero-buttons">
                <sl-button variant="primary" size="large" href="/register"
                  >Get Started</sl-button
                >
                <sl-button variant="text" size="large" href="/request-demo"
                  >Request a Demo</sl-button
                >
              </div>
            </div>
          </div>
        </section>

        <section class="feature-section main-section" id="features">
          <div class="section-container text-center">
            <div class="title-container">
              <h2>Automate Software Project Management</h2>
            </div>
            <sl-carousel
              class="feature-carousel"
              loop
              effect="slide"
              mouse-dragging
              @sl-slide-change=${this._handleSlideChange}
            >
              ${this._featureSlides.map(
                (slide, index) => html`
                  <sl-carousel-item>
                    <div class="feature-grid-2-col">
                      <div class="feature-text-content">
                        <h3>${slide.title}</h3>
                        <p>${slide.text}</p>
                        ${!this._showVideo[index]
                          ? html`
                              <sl-button
                                variant="primary"
                                class="watch-video-btn"
                                @click=${() => this._playVideo(index)}
                              >
                                <sl-icon
                                  name="play-circle"
                                  slot="prefix"
                                ></sl-icon>
                                Watch Video
                              </sl-button>
                            `
                          : ''}
                        <div class="carousel-navigation">
                          <sl-button
                            variant="text"
                            class="carousel-nav carousel-nav--prev"
                            @click=${() => this._carousel.previous()}
                          >
                            <sl-icon name="chevron-left"></sl-icon>
                          </sl-button>
                          <span class="slide-indicator">
                            ${this._activeSlideIndex + 1} /
                            ${this._featureSlides.length}
                          </span>
                          <sl-button
                            variant="text"
                            class="carousel-nav carousel-nav--next"
                            @click=${() => this._carousel.next()}
                          >
                            <sl-icon name="chevron-right"></sl-icon>
                          </sl-button>
                        </div>
                      </div>

                      <div class="feature-video-content">
                        ${this._showVideo[index]
                          ? html`
                              <div class="video-wrapper">
                                <iframe
                                  width="560"
                                  height="315"
                                  src=${`${slide.videoUrl}?autoplay=1`}
                                  title="YouTube video player"
                                  frameborder="0"
                                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                                  allowfullscreen
                                ></iframe>
                              </div>
                            `
                          : html`
                              <div
                                class="video-placeholder"
                                @click=${() => this._playVideo(index)}
                              >
                                <img
                                  src=${slide.placeholderImg}
                                  alt="Video Preview"
                                />
                                <div class="play-button"></div>
                              </div>
                            `}
                      </div>
                    </div>
                  </sl-carousel-item>
                `
              )}
            </sl-carousel>
          </div>
        </section>

        <section class="feature-section main-section" id="get-started">
          <div class="section-container">
            <div class="title-container">
              <h2>Turbocharge your AI Workflow with MCP</h2>
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
                <h3>Augment your AI context</h3>
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
            <h3>Get Started with Spacebridge MCP</h3>
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
                        <p>Then add to Claude Code:</p>
                        <div class="code-container">
                          <pre><code>claude mcp add spacebridge $(which spacebridge-mcp-server) \\
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

        <section class="tools-section main-section">
          <div class="section-container">
            <h2 class="text-center">Works with the tools you use</h2>
            <div class="tool-logos">
              <sl-tooltip content="GitHub">
                <img
                  src="images/logos/github-mark-white.svg"
                  alt="GitHub Logo"
                  class="github-logo tool-logo"
                />
              </sl-tooltip>
              <sl-tooltip content="GitLab">
                <img
                  src="images/logos/gitlab-logo-700-rgb.svg"
                  alt="GitLab Logo"
                  class="gitlab-logo tool-logo"
                />
              </sl-tooltip>
              <sl-tooltip content="Jira">
                <img
                  src="images/logos/jira.webp"
                  alt="Jira Logo"
                  class="jira-logo tool-logo"
                />
              </sl-tooltip>
            </div>
          </div>
        </section>

        <section class="faq-section main-section">
          <div class="section-container">
            <h2 class="text-center">Frequently Asked Questions</h2>
            <div class="faq-list">
              ${this._faqs.map(
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
            <h2>Stop curating. Start creating.</h2>
            <div class="hero-buttons">
              <sl-button variant="primary" size="large" href="/register"
                >Get Started for Free</sl-button
              >
              <sl-button variant="text" size="large" href="/request-demo"
                >Request a Demo</sl-button
              >
            </div>
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
