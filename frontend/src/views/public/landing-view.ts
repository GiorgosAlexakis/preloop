import { LitElement, html, css, unsafeCSS } from 'lit';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';
import { getBrandConfig } from '../../brand-config';
import { customElement, state, query } from 'lit/decorators.js';
import landingStyles from '../../styles/landing.css?inline';
import './../../components/news-capsule';
import './../../components/ide-setup-tabs';
import { getIdeConfigs } from '../../utils/ide-configs';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/carousel/carousel.js';
import '@shoelace-style/shoelace/dist/components/carousel-item/carousel-item.js';
import type SlCarousel from '@shoelace-style/shoelace/dist/components/carousel/carousel.js';
import type SlCarouselItem from '@shoelace-style/shoelace/dist/components/carousel-item/carousel-item.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';
import { getFeatures } from '../../api';

interface FeatureSlide {
  title: string;
  text: string;
  videoUrl: string;
  placeholderImg: string;
}

@customElement('landing-view')
export class LandingView extends LitElement {
  @query('.feature-carousel') private _carousel!: SlCarousel;
  @state() private _showVideo: boolean[] = [false, false, false];
  @state() private _activeSlideIndex = 0;
  @state() private _featureSlides: FeatureSlide[] = [];
  @state() private _faqs: Array<{ q: string; a: string }> = [];
  @state() private _heroTitle = '';
  @state() private _heroLead = '';
  @state() private _ctaPrimary = '';
  @state() private _ctaSecondary = '';
  @state() private _ctaSecondaryUrl = '';
  @state() private _getStartedTitle = '';
  @state() private _getStartedLinkText = '';
  @state() private _getStartedLinkUrl = '';
  @state() private _getStartedFeatures: Array<{
    icon: string;
    title: string;
    text: string;
  }> = [];
  @state() private _mcpSetupTitle = '';
  @state() private _extendedDescription = '';
  @state() private _featuresLayout: 'carousel' | 'grid' = 'grid';
  @state() private _billingEnabled = false;
  @state() private _oauthSigninEnabled = false;
  @state() private _productHunt: {
    enabled: boolean;
    post_id: string;
    theme: string;
  } | null = null;
  @state() private _featuredVideo: {
    enabled: boolean;
    title: string;
    youtube_url: string;
    youtube_embed: string;
  } | null = null;

  static styles = [
    css`
      ${unsafeCSS(landingStyles)}
    `,
  ];

  async firstUpdated() {
    await this._loadContent();
    await this._checkBillingEnabled();
  }

  private async _checkBillingEnabled() {
    try {
      const features = await getFeatures();
      this._billingEnabled = features.features['billing'] === true;
      this._oauthSigninEnabled = features.features['oauth_signin'] === true;
    } catch (error) {
      console.error('Failed to check billing feature:', error);
      this._billingEnabled = false;
      this._oauthSigninEnabled = false;
    }
  }

  private async _handleSignup(e: Event) {
    e.preventDefault();

    // If OAuth is available, go to register page where users choose OAuth or email
    if (this._oauthSigninEnabled) {
      window.location.href = '/register';
      return;
    }

    if (!this._billingEnabled) {
      // No billing and no OAuth — regular registration (OSS)
      window.location.href = '/register';
      return;
    }

    // Billing enabled - redirect to Stripe checkout
    try {
      const response = await fetch('/api/v1/billing/create-checkout-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan_id: 'teams',
          interval: 'month',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create checkout session');
      }

      const result = await response.json();

      if (result.action === 'redirect' && result.url) {
        window.location.href = result.url;
      } else {
        window.location.href = '/register';
      }
    } catch (error) {
      console.error('Checkout error:', error);
      window.location.href = '/register';
    }
  }

  private async _loadContent() {
    try {
      // First try to load from slotted content (SSR)
      const children = Array.from(this.children);
      const hasSlottedContent = children.some((el) =>
        el.getAttribute('slot')?.startsWith('hero-')
      );

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
    const heroTitle = children.find(
      (el) => el.getAttribute('slot') === 'hero-title'
    ) as HTMLElement | undefined;
    const heroLead = children.find(
      (el) => el.getAttribute('slot') === 'hero-lead'
    ) as HTMLElement | undefined;
    const ctaPrimary = children.find(
      (el) => el.getAttribute('slot') === 'cta-primary'
    ) as HTMLElement | undefined;
    const ctaSecondary = children.find(
      (el) => el.getAttribute('slot') === 'cta-secondary'
    ) as HTMLElement | undefined;
    const ctaSecondaryUrl = children.find(
      (el) => el.getAttribute('slot') === 'cta-secondary-url'
    ) as HTMLElement | undefined;

    if (heroTitle) this._heroTitle = heroTitle.innerHTML || '';
    if (heroLead) this._heroLead = heroLead.textContent || '';
    if (ctaPrimary) this._ctaPrimary = ctaPrimary.textContent || '';
    if (ctaSecondary) this._ctaSecondary = ctaSecondary.textContent || '';
    if (ctaSecondaryUrl)
      this._ctaSecondaryUrl = ctaSecondaryUrl.textContent || '';

    // Read extended description from light DOM slot
    const extendedDescription = children.find(
      (el) => el.getAttribute('slot') === 'extended-description'
    ) as HTMLElement | undefined;
    if (extendedDescription)
      this._extendedDescription = extendedDescription.textContent || '';

    // Read features layout from light DOM slot
    const featuresLayout = children.find(
      (el) => el.getAttribute('slot') === 'features-layout'
    ) as HTMLElement | undefined;
    if (featuresLayout) {
      const layout = featuresLayout.textContent?.trim() as 'carousel' | 'grid';
      if (layout === 'carousel' || layout === 'grid') {
        this._featuresLayout = layout;
      }
    }

    // Read feature slides from light DOM slots
    const features: FeatureSlide[] = [];

    for (let i = 0; i < 10; i++) {
      const featureWrapper = children.find(
        (el) => el.getAttribute('slot') === `feature-${i}`
      ) as HTMLElement | undefined;

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
      const faqWrapper = children.find(
        (el) => el.getAttribute('slot') === `faq-${i}`
      ) as HTMLElement | undefined;

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

    // Read get-started content from light DOM slots
    const getStartedTitle = children.find(
      (el) => el.getAttribute('slot') === 'get-started-title'
    ) as HTMLElement | undefined;
    const getStartedLinkText = children.find(
      (el) => el.getAttribute('slot') === 'get-started-link-text'
    ) as HTMLElement | undefined;
    const getStartedLinkUrl = children.find(
      (el) => el.getAttribute('slot') === 'get-started-link-url'
    ) as HTMLElement | undefined;

    if (getStartedTitle)
      this._getStartedTitle = getStartedTitle.textContent || '';
    if (getStartedLinkText)
      this._getStartedLinkText = getStartedLinkText.textContent || '';
    if (getStartedLinkUrl)
      this._getStartedLinkUrl = getStartedLinkUrl.textContent || '';

    // Read get-started features from light DOM slots
    const getStartedFeatures: Array<{
      icon: string;
      title: string;
      text: string;
    }> = [];
    for (let i = 0; i < 10; i++) {
      const featureWrapper = children.find(
        (el) => el.getAttribute('slot') === `get-started-feature-${i}`
      ) as HTMLElement | undefined;

      if (featureWrapper) {
        const icon = featureWrapper.getAttribute('data-icon') || '';
        const title = featureWrapper.getAttribute('data-title') || '';
        const text = featureWrapper.getAttribute('data-text') || '';

        if (icon && title && text) {
          getStartedFeatures.push({ icon, title, text });
        }
      } else {
        break;
      }
    }

    if (getStartedFeatures.length > 0) {
      this._getStartedFeatures = getStartedFeatures;
    }

    // Read MCP setup title
    const mcpSetupTitle = children.find(
      (el) => el.getAttribute('slot') === 'mcp-setup-title'
    ) as HTMLElement | undefined;
    if (mcpSetupTitle) this._mcpSetupTitle = mcpSetupTitle.textContent || '';

    // Read Product Hunt configuration from slot
    const productHuntSlot = children.find(
      (el) => el.getAttribute('slot') === 'product-hunt'
    ) as HTMLElement | undefined;
    if (productHuntSlot) {
      const enabled = productHuntSlot.getAttribute('data-enabled') === 'true';
      if (enabled) {
        this._productHunt = {
          enabled: true,
          post_id: productHuntSlot.getAttribute('data-post-id') || '',
          theme: productHuntSlot.getAttribute('data-theme') || 'light',
        };
      }
    }

    // Read Featured Video configuration from slot
    const featuredVideoSlot = children.find(
      (el) => el.getAttribute('slot') === 'featured-video'
    ) as HTMLElement | undefined;
    if (featuredVideoSlot) {
      const enabled = featuredVideoSlot.getAttribute('data-enabled') === 'true';
      if (enabled) {
        this._featuredVideo = {
          enabled: true,
          title: featuredVideoSlot.getAttribute('data-title') || '',
          youtube_url: featuredVideoSlot.getAttribute('data-youtube-url') || '',
          youtube_embed:
            featuredVideoSlot.getAttribute('data-youtube-embed') || '',
        };
      }
    }

    // Hide slotted elements (they stay in light DOM for SEO but are hidden)
    children.forEach((el) => {
      const slot = el.getAttribute('slot');
      if (
        slot &&
        (slot.startsWith('hero-') ||
          slot.startsWith('cta-') ||
          slot === 'extended-description' ||
          slot === 'features-layout' ||
          slot.startsWith('feature-') ||
          slot.startsWith('faq-') ||
          slot.startsWith('get-started-') ||
          slot === 'mcp-setup-title' ||
          slot === 'product-hunt' ||
          slot === 'featured-video')
      ) {
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

    // Load hero content with safe defaults
    const hero = content.hero || {};
    this._heroTitle = hero.title || '';
    this._heroLead = hero.lead || '';
    this._ctaPrimary = hero.cta_primary || '';
    this._ctaSecondary = hero.cta_secondary || '';
    this._ctaSecondaryUrl = hero.cta_secondary_url || '';
    this._extendedDescription = content.extended_description || '';
    this._featuresLayout = content.features_layout || 'grid';

    // Load Product Hunt configuration
    if (content.product_hunt?.enabled) {
      this._productHunt = content.product_hunt;
    }

    // Load featured video configuration
    if (content.featured_video?.enabled) {
      this._featuredVideo = content.featured_video;
    }

    // Load features with safe defaults
    const features = content.features || [];
    this._featureSlides = features.map((f: any) => ({
      title: f.title || '',
      text: f.text || '',
      videoUrl: f.videoUrl || '',
      placeholderImg: f.placeholderImg || '',
    }));
    this._showVideo = new Array(this._featureSlides.length).fill(false);

    // Load FAQs with safe defaults
    this._faqs = content.faqs || [];

    // Load get-started content with safe defaults
    const getStarted = content.get_started || {};
    this._getStartedTitle = getStarted.title || '';
    this._getStartedLinkText = getStarted.link_text || '';
    this._getStartedLinkUrl = getStarted.link_url || '';
    this._getStartedFeatures = getStarted.features || [];
    this._mcpSetupTitle = getStarted.mcp_setup_title || '';
  }

  private _playVideo(index: number) {
    const newShowVideo = [...this._showVideo];
    if (this._featureSlides[index].videoUrl) {
      newShowVideo[index] = true;
    }
    this._showVideo = newShowVideo;
  }

  private _handleSlideChange(
    e: CustomEvent<{ index: number; slide: SlCarouselItem }>
  ) {
    this._activeSlideIndex = e.detail.index;
  }

  private _getYouTubeEmbedUrl(url: string): string {
    // Convert YouTube URLs to embed format
    // Handles: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID
    try {
      const urlObj = new URL(url);
      let videoId = '';

      if (urlObj.hostname.includes('youtu.be')) {
        // Format: https://youtu.be/VIDEO_ID
        videoId = urlObj.pathname.slice(1);
      } else if (urlObj.hostname.includes('youtube.com')) {
        // Format: https://www.youtube.com/watch?v=VIDEO_ID
        videoId = urlObj.searchParams.get('v') || '';

        // Already in embed format
        if (urlObj.pathname.includes('/embed/')) {
          return url;
        }
      }

      if (videoId) {
        return `https://www.youtube.com/embed/${videoId}`;
      }
    } catch (e) {
      console.error('Failed to parse YouTube URL:', url, e);
    }

    return url;
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
          <!-- <news-capsule></news-capsule> -->
          <div class="section-container hero-inner">
            <div class="hero-content">
              ${this._productHunt?.enabled
                ? html`
                    <div class="product-hunt-badge">
                      <a
                        href="https://www.producthunt.com/products/preloop?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-preloop"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <img
                          alt="Preloop - The MCP Governance Layer | Product Hunt"
                          width="250"
                          height="54"
                          src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=${this
                            ._productHunt.post_id}&amp;theme=${this._productHunt
                            .theme}&amp;t=${Date.now()}"
                        />
                      </a>
                    </div>
                  `
                : ''}
              <h1 class="fw-bold">${unsafeHTML(this._heroTitle)}</h1>
              <p class="lead">${this._heroLead}</p>
              <div class="hero-buttons">
                <sl-button
                  variant="primary"
                  size="large"
                  @click=${this._handleSignup}
                  >${this._ctaPrimary}</sl-button
                >
                <sl-button
                  variant="text"
                  size="large"
                  href=${this._ctaSecondaryUrl}
                  target=${this._ctaSecondaryUrl.startsWith('http')
                    ? '_blank'
                    : '_self'}
                  >${this._ctaSecondary}</sl-button
                >
              </div>
            </div>
          </div>
        </section>

        ${this._extendedDescription
          ? html`
              <section class="extended-description-section main-section">
                <div class="section-container">
                  <p class="lead text-center">${this._extendedDescription}</p>
                  <img src="/assets/mcp-firewall.svg" />
                </div>
              </section>
            `
          : ''}
        ${this._featuredVideo?.enabled
          ? html`
              <section class="featured-video-section main-section">
                <div class="section-container text-center">
                  ${this._featuredVideo.title
                    ? html`<h2>${this._featuredVideo.title}</h2>`
                    : ''}
                  <div class="featured-video-wrapper">
                    <iframe
                      width="560"
                      height="315"
                      src="${this._featuredVideo.youtube_embed}"
                      title="YouTube video player"
                      frameborder="0"
                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                      referrerpolicy="strict-origin-when-cross-origin"
                      allowfullscreen
                    ></iframe>
                  </div>
                </div>
              </section>
            `
          : ''}
        ${this._featureSlides.length > 0 && this._featuresLayout === 'carousel'
          ? html`
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
                              ${!this._showVideo[index] && slide.videoUrl
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
                              ${this._showVideo[index] && slide.videoUrl
                                ? html`
                                    <div class="video-wrapper">
                                      <iframe
                                        width="560"
                                        height="315"
                                        src=${`${this._getYouTubeEmbedUrl(slide.videoUrl)}?autoplay=1`}
                                        title="YouTube video player"
                                        frameborder="0"
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                                        allowfullscreen
                                      ></iframe>
                                    </div>
                                  `
                                : html`
                                    <div
                                      class="image-placeholder"
                                      @click=${() =>
                                        slide.videoUrl
                                          ? this._playVideo(index)
                                          : null}
                                    >
                                      ${slide.placeholderImg
                                        ? html`
                                            <img
                                              src=${slide.placeholderImg}
                                              alt=${slide.title}
                                            />
                                            ${slide.videoUrl
                                              ? html`<div
                                                  class="play-button"
                                                ></div>`
                                              : ''}
                                          `
                                        : ''}
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
            `
          : this._featureSlides.length > 0
            ? html`
                <section class="feature-section main-section" id="features">
                  <div class="section-container">
                    <h2 class="text-center">Features</h2>
                    <div class="feature-grid three-col">
                      ${this._featureSlides.map(
                        (slide) => html`
                          <div class="feature-box">
                            ${slide.placeholderImg
                              ? html`<img
                                  src=${slide.placeholderImg}
                                  alt=${slide.title}
                                />`
                              : ''}
                            <h3>${slide.title}</h3>
                            <p>${slide.text}</p>
                            ${slide.videoUrl
                              ? html`<a
                                  href=${slide.videoUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  class="video-link"
                                >
                                  <sl-icon name="play-circle"></sl-icon> Watch
                                  Video
                                </a>`
                              : ''}
                          </div>
                        `
                      )}
                    </div>
                  </div>
                </section>
              `
            : ''}
        ${html`
          <section class="feature-section main-section" id="get-started">
            <div class="section-container">
              <div class="title-container">
                <h2>
                  ${this._getStartedTitle ||
                  'Turbocharge your AI Workflow with MCP'}
                </h2>
                <a
                  class="main-link"
                  href="${this._getStartedLinkUrl || '/whatis-mcp'}"
                  >${this._getStartedLinkText || 'What is MCP?'}</a
                >
              </div>

              ${this._getStartedFeatures.length > 0
                ? html`<div class="feature-grid three-col">
                    ${this._getStartedFeatures.map(
                      (feature) => html`
                        <div class="feature-box">
                          <div class="feature-icon">
                            <sl-icon name="${feature.icon}"></sl-icon>
                          </div>
                          <h3>${feature.title}</h3>
                          <p>${feature.text}</p>
                        </div>
                      `
                    )}
                  </div>`
                : ``}
              <ide-setup-tabs
                .configs=${getIdeConfigs()}
                defaultTab="claude-code"
                helpText="The built-in MCP server provides access to all your enabled tools, including tools from external MCP servers."
              ></ide-setup-tabs>
            </div>
          </section>
        `}
        ${html`
          <section class="tools-section main-section">
            <div class="section-container">
              <h2 class="text-center">Works with the tools you use</h2>
              <div class="tool-logos">
                <sl-tooltip content="GitHub">
                  <img
                    src="/images/logos/github-mark-white.svg"
                    alt="GitHub Logo"
                    class="github-logo tool-logo"
                  />
                </sl-tooltip>
                <sl-tooltip content="GitLab">
                  <img
                    src="/images/logos/gitlab-logo-700-rgb.svg"
                    alt="GitLab Logo"
                    class="gitlab-logo tool-logo"
                  />
                </sl-tooltip>
                <sl-tooltip content="Jira">
                  <img
                    src="/images/logos/jira.webp"
                    alt="Jira Logo"
                    class="jira-logo tool-logo"
                  />
                </sl-tooltip>
                <sl-tooltip content="Slack">
                  <img
                    src="/images/logos/slack-logo.svg"
                    alt="Slack Logo"
                    class="slack-logo tool-logo"
                  />
                </sl-tooltip>
                <sl-tooltip content="Microsoft Teams">
                  <img
                    src="/images/logos/teams-logo.svg"
                    alt="Microsoft Teams Logo"
                    class="teams-logo tool-logo"
                  />
                </sl-tooltip>
                <sl-tooltip content="Discord">
                  <img
                    src="/images/logos/discord-logo.svg"
                    alt="Discord Logo"
                    class="discord-logo tool-logo"
                  />
                </sl-tooltip>
                <sl-tooltip content="Mattermost">
                  <img
                    src="/images/logos/mattermost-logo.svg"
                    alt="Mattermost Logo"
                    class="mattermost-logo tool-logo"
                  />
                </sl-tooltip>
              </div>
            </div>
          </section>
        `}
        ${this._faqs.length > 0
          ? html`
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
                            <div class="faq-answer-content">
                              ${unsafeHTML(faq.a)}
                            </div>
                          </div>
                        </details>
                      `
                    )}
                  </div>
                </div>
              </section>
            `
          : ''}
        ${this._faqs.length > 0 || this._featureSlides.length > 0
          ? html`
              <section class="final-cta main-section special-cta">
                <div class="section-container">
                  <h2>Move fast. Stay safe.</h2>
                  <div class="hero-buttons">
                    <sl-button
                      variant="primary"
                      size="large"
                      @click=${this._handleSignup}
                      >Get Started for Free</sl-button
                    >
                    <sl-button variant="text" size="large" href="/request-demo"
                      >Request a Demo</sl-button
                    >
                  </div>
                </div>
              </section>
            `
          : ''}
      </main>
      <app-footer></app-footer>
    `;
  }
}
