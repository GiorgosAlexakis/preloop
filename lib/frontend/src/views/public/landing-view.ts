import { LitElement, html, css, unsafeCSS } from 'lit';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { customElement, state, query } from 'lit/decorators.js';
import landingStyles from '../../styles/landing.css?inline';
import './../../components/news-capsule';
import '@shoelace-style/shoelace/dist/components/button/button.js';
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
  @state() private _showVideo: boolean[] = [false, false, false];
  @state() private _activeSlideIndex = 0;
  @state() private _featureSlides: FeatureSlide[] = [];
  @state() private _faqs: Array<{ q: string; a: string }> = [];
  @state() private _heroTitle = '';
  @state() private _heroLead = '';
  @state() private _ctaPrimary = '';
  @state() private _ctaSecondary = '';

  static styles = [
    css`
      ${unsafeCSS(landingStyles)}
    `,
  ];

  async firstUpdated() {
    await this._loadContent();
  }

  private async _loadContent() {
    try {
      // First try to load from slotted content (SSR)
      const children = Array.from(this.children);
      const hasSlottedContent = children.some(el => el.getAttribute('slot')?.startsWith('hero-'));

      if (hasSlottedContent) {
        // Load from slotted content (SSR case - first page load)
        this._loadSlottedContent(children);
      } else {
        // Load from JSON file (client-side navigation case)
        await this._loadFromJSON();
      }
    } catch (error) {
      console.error('[landing-view] Failed to load content:', error);
      // Fallback: try loading from JSON
      await this._loadFromJSON();
    }
  }

  private _loadSlottedContent(children: Element[]) {
    // Read hero content from light DOM slots
    const heroTitle = children.find(el => el.getAttribute('slot') === 'hero-title') as HTMLElement | undefined;
    const heroLead = children.find(el => el.getAttribute('slot') === 'hero-lead') as HTMLElement | undefined;
    const ctaPrimary = children.find(el => el.getAttribute('slot') === 'cta-primary') as HTMLElement | undefined;
    const ctaSecondary = children.find(el => el.getAttribute('slot') === 'cta-secondary') as HTMLElement | undefined;

    if (heroTitle) this._heroTitle = heroTitle.innerHTML || '';
    if (heroLead) this._heroLead = heroLead.textContent || '';
    if (ctaPrimary) this._ctaPrimary = ctaPrimary.textContent || '';
    if (ctaSecondary) this._ctaSecondary = ctaSecondary.textContent || '';

    // Read feature slides from light DOM slots
    const features: FeatureSlide[] = [];

    for (let i = 0; i < 10; i++) {
      const featureWrapper = children.find(el => el.getAttribute('slot') === `feature-${i}`) as HTMLElement | undefined;

      if (featureWrapper) {
        const title = featureWrapper.getAttribute('data-title') || '';
        const text = featureWrapper.getAttribute('data-text') || '';
        const videoUrl = featureWrapper.getAttribute('data-video') || '';
        const placeholderImg = featureWrapper.getAttribute('data-img') || '';

        if (title && text) {
          features.push({ title, text, videoUrl, placeholderImg });
        }
      } else {
        break;
      }
    }

    if (features.length > 0) {
      this._featureSlides = features;
      this._showVideo = new Array(features.length).fill(false);
    }

    // Read FAQs from light DOM slots
    const faqs: Array<{ q: string; a: string }> = [];
    for (let i = 0; i < 20; i++) {
      const faqWrapper = children.find(el => el.getAttribute('slot') === `faq-${i}`) as HTMLElement | undefined;

      if (faqWrapper) {
        const q = faqWrapper.getAttribute('data-q') || '';
        const a = faqWrapper.getAttribute('data-a') || '';

        if (q && a) {
          faqs.push({ q, a });
        }
      } else {
        break;
      }
    }

    if (faqs.length > 0) {
      this._faqs = faqs;
    }

    // Hide slotted elements (they stay in light DOM for SEO but are hidden)
    children.forEach(el => {
      const slot = el.getAttribute('slot');
      if (slot && (slot.startsWith('hero-') || slot.startsWith('cta-') || slot.startsWith('feature-') || slot.startsWith('faq-'))) {
        (el as HTMLElement).style.display = 'none';
      }
    });
  }

  private async _loadFromJSON() {
    const response = await fetch('/landing-content.json');
    if (!response.ok) {
      throw new Error(`Failed to load landing content: ${response.statusText}`);
    }

    const content = await response.json();

    // Load hero content
    this._heroTitle = content.hero.title;
    this._heroLead = content.hero.lead;
    this._ctaPrimary = content.hero.cta_primary;
    this._ctaSecondary = content.hero.cta_secondary;

    // Load features
    this._featureSlides = content.features.map((f: any) => ({
      title: f.title,
      text: f.text,
      videoUrl: f.videoUrl,
      placeholderImg: f.placeholderImg,
    }));
    this._showVideo = new Array(this._featureSlides.length).fill(false);

    // Load FAQs
    this._faqs = content.faqs;
  }

  private _handleIdeTabClick(tabId: IdeTab) {
    this._activeIdeTab = tabId;
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

  private _handleFaqClick(e: Event) {
    e.preventDefault();
    const summary = e.currentTarget as HTMLElement;
    const details = summary.parentElement as HTMLDetailsElement;
    const answer = summary.nextElementSibling as HTMLElement | null;

    if (!answer) return;

    if (details.open) {
      answer.style.height = `${answer.scrollHeight}px`;
      requestAnimationFrame(() => {
        answer.style.height = '0px';
      });
      answer.addEventListener(
        'transitionend',
        () => {
          details.removeAttribute('open');
        },
        { once: true }
      );
    } else {
      details.setAttribute('open', '');
      answer.style.height = `${answer.scrollHeight}px`;
      answer.addEventListener(
        'transitionend',
        () => {
          if (details.open) {
            answer.style.height = 'auto';
          }
        },
        { once: true }
      );
    }
  }

  render() {
    return html`
      <app-header></app-header>
      <main>
        <section class="hero main-section">
          <news-capsule></news-capsule>
          <div class="section-container hero-inner">
            <div class="hero-content">
              <h1 class="fw-bold">${unsafeHTML(this._heroTitle)}</h1>
              <p class="lead">${this._heroLead}</p>
              <div class="hero-buttons">
                <sl-button variant="primary" size="large" href="/register"
                  >${this._ctaPrimary}</sl-button
                >
                <sl-button variant="text" size="large" href="/request-demo"
                  >${this._ctaSecondary}</sl-button
                >
              </div>
            </div>
          </div>
        </section>

        <section class="feature-section main-section" id="features">
          <div class="section-container text-center">
            <sl-carousel
              class="feature-carousel"
              loop
              effect="fade"
              @sl-slide-change=${this._handleSlideChange}
            >
              ${this._featureSlides.map(
                (slide, index) => html`
                  <sl-carousel-item>
                    <div class="feature-grid-2-col">
                      <div class="feature-text-content">
                        <h2>${slide.title}</h2>
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
                          <li>SpaceBridge API key (register above)</li>
                        </ul>
                        <h5>Setup</h5>
                        <p>Run the following command in your terminal:</p>
                        <div class="code-container">
                          <pre><code>claude mcp add --transport http spacebridge https://spacebridge.io/mcp/v1  
  --header "Authorization: Bearer YOUR_SPACEBRIDGE_API_KEY"</code></pre>
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
                          <li>SpaceBridge API key (register above)</li>
                        </ul>
                        <h5>Setup</h5>
                        <p>Create or edit <code>~/.cursor/mcp.json</code>:</p>
                        <div class="code-container">
                          <pre><code># Create or edit ~/.cursor/mcp.json
{
  "mcpServers": {
    "spacebridge": {
      "transport": "http",
      "url": "https://spacebridge.io/mcp/v1",
      "headers": {
        "Authorization": "Bearer YOUR_SPACEBRIDGE_API_KEY"
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
                          <li>SpaceBridge API key (register above)</li>
                        </ul>
                        <h5>Setup</h5>
                        <p>Create or edit your MCP configuration file:</p>
                        <div class="code-container">
                          <pre><code>{
  "mcpServers": {
    "spacebridge": {
        "transport": "http",
        "url": "https://spacebridge.io/mcp/v1",
        "headers": {
            "Authorization": "Bearer YOUR_SPACEBRIDGE_API_KEY"
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
              <sl-tooltip content="Linear (coming soon)">
                <img
                  src="images/logos/linear-logo-light.png"
                  alt="Linear Logo"
                  class="linear-logo tool-logo"
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
                (faq) => html`
                  <details class="faq-item">
                    <summary
                      class="faq-question"
                      @click=${this._handleFaqClick}
                    >
                      <span>${faq.q}</span>
                      <sl-icon name="chevron-down"></sl-icon>
                    </summary>
                    <div class="faq-answer">
                      <div class="faq-answer-content">${unsafeHTML(faq.a)}</div>
                    </div>
                  </details>
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
}
