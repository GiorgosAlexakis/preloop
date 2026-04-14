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
  @state() private _cliSetup: Array<{ step: string; command: string }> = [];
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
  @state() private _activeAnimationIndex = 0;
  private _animationsObserver?: IntersectionObserver;

  static styles = [
    css`
      ${unsafeCSS(landingStyles)}

      @keyframes marquee {
        0% {
          transform: translateX(0);
        }
        100% {
          transform: translateX(calc(-50% - 2rem));
        }
      }

      .agent-marquee-container {
        overflow: hidden;
        white-space: nowrap;
        position: relative;
        width: 100%;
      }

      .agent-marquee-content {
        display: inline-flex;
        gap: 4rem;
        align-items: center;
        opacity: 0.8;
        width: max-content;
        animation: marquee 30s linear infinite;
      }

      .agent-marquee-track {
        display: inline-flex;
        gap: 4rem;
        align-items: center;
      }

      .agent-marquee-content:hover {
        animation-play-state: paused;
      }

      .agent-marquee-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        font-weight: 500;
        font-size: 1.1rem;
        color: rgb(161, 161, 170);
      }
    `,
  ];

  async firstUpdated() {
    await this._loadContent();
    await this._checkBillingEnabled();

    // Set up bulletproof scroll intersection observer for features
    this._featuresObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const idx = Number((entry.target as HTMLElement).dataset.index);
            if (!isNaN(idx)) {
              this._activeSlideIndex = idx;
            }
          }
        });
      },
      { threshold: 0.5 }
    );

    // Set up observer for animations scroll trap
    this._animationsObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const idx = Number((entry.target as HTMLElement).dataset.animIndex);
            if (!isNaN(idx)) {
              this._activeAnimationIndex = idx;
            }
          }
        });
      },
      { threshold: 0.5 }
    );

    // Slight delay to ensure render completes before observing
    setTimeout(() => {
      const spacers = this.renderRoot?.querySelectorAll(
        '.feature-scroll-spacer'
      );
      spacers?.forEach((el) => this._featuresObserver?.observe(el));

      const animSpacers = this.renderRoot?.querySelectorAll(
        '.animation-scroll-spacer'
      );
      animSpacers?.forEach((el) => this._animationsObserver?.observe(el));
    }, 100);
  }

  connectedCallback() {
    super.connectedCallback();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._featuresObserver?.disconnect();
    this._animationsObserver?.disconnect();
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
      const postId = productHuntSlot.getAttribute('data-post-id') || '';
      const theme = productHuntSlot.getAttribute('data-theme') || 'light';
      this._productHunt = { enabled, post_id: postId, theme };
    }

    // Read Featured Video configuration from slot
    const featuredVideoSlot = children.find(
      (el) => el.getAttribute('slot') === 'featured-video'
    ) as HTMLElement | undefined;
    if (featuredVideoSlot) {
      const enabled = featuredVideoSlot.getAttribute('data-enabled') === 'true';
      const title = featuredVideoSlot.getAttribute('data-title') || '';
      const youtubeUrl =
        featuredVideoSlot.getAttribute('data-youtube-url') || '';
      const youtubeEmbed =
        featuredVideoSlot.getAttribute('data-youtube-embed') || '';
      this._featuredVideo = {
        enabled,
        title,
        youtube_url: youtubeUrl,
        youtube_embed: youtubeEmbed,
      };
    }

    // Read CLI setup configuration from slots
    const cliSetup: Array<{ step: string; command: string }> = [];
    for (let i = 0; i < 10; i++) {
      const stepWrapper = children.find(
        (el) => el.getAttribute('slot') === `cli-setup-${i}`
      ) as HTMLElement | undefined;

      if (stepWrapper) {
        const step = stepWrapper.getAttribute('data-step') || '';
        const command = stepWrapper.getAttribute('data-command') || '';

        if (step && command) {
          cliSetup.push({ step, command });
        }
      } else {
        break;
      }
    }

    if (cliSetup.length > 0) {
      this._cliSetup = cliSetup;
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
          slot === 'featured-video' ||
          slot.startsWith('cli-setup-'))
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
    this._cliSetup = getStarted.cli_setup || [];
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

        <section
          class="supported-agents-section"
          style="padding-top: 2.5rem; padding-bottom: 2.5rem;"
        >
          <div class="test-marquee agent-marquee-container">
            <div class="agent-marquee-content">
              <!-- Track 1 -->
              <div class="agent-marquee-track">
                <div
                  class="agent-marquee-item"
                  style="color: rgb(161, 161, 170); font-weight: 600; font-size: 1.1rem; margin-right: 2rem; letter-spacing: 0.5px; text-transform: uppercase;"
                >
                  secure any agent
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/openclaw.svg"
                    alt="OpenClaw"
                    style="height: 24px;"
                  />
                  OpenClaw
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/opencode.svg"
                    alt="OpenCode"
                    style="height: 24px;"
                  />
                  OpenCode
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/claude.svg"
                    alt="Claude Code"
                    style="height: 24px;"
                  />
                  Claude Code
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/codex.svg"
                    alt="Codex CLI"
                    style="height: 24px;"
                  />
                  Codex CLI
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/gemini-cli.svg"
                    alt="Gemini CLI"
                    style="height: 24px;"
                  />
                  Gemini CLI
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/cursor.svg"
                    alt="Cursor"
                    style="height: 24px;"
                  />
                  Cursor
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/Windsurf-white-symbol.svg"
                    alt="Windsurf"
                    style="height: 24px;"
                  />
                  Windsurf
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/vscode.svg"
                    alt="VSCode"
                    style="height: 24px;"
                  />
                  VSCode
                </div>
              </div>

              <!-- Track 2 -->
              <div class="agent-marquee-track" aria-hidden="true">
                <div
                  class="agent-marquee-item"
                  style="color: rgb(161, 161, 170); font-weight: 600; font-size: 1.1rem; margin-right: 2rem; letter-spacing: 0.5px; text-transform: uppercase;"
                >
                  secure any agent
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/openclaw.svg"
                    alt="OpenClaw"
                    style="height: 24px;"
                  />
                  OpenClaw
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/opencode.svg"
                    alt="OpenCode"
                    style="height: 24px;"
                  />
                  OpenCode
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/claude.svg"
                    alt="Claude Code"
                    style="height: 24px;"
                  />
                  Claude Code
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/codex.svg"
                    alt="Codex CLI"
                    style="height: 24px;"
                  />
                  Codex CLI
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/gemini-cli.svg"
                    alt="Gemini CLI"
                    style="height: 24px;"
                  />
                  Gemini CLI
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/cursor.svg"
                    alt="Cursor"
                    style="height: 24px;"
                  />
                  Cursor
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/Windsurf-white-symbol.svg"
                    alt="Windsurf"
                    style="height: 24px;"
                  />
                  Windsurf
                </div>
                <div class="agent-marquee-item">
                  <img
                    src="/images/logos/vscode.svg"
                    alt="VSCode"
                    style="height: 24px;"
                  />
                  VSCode
                </div>
              </div>
            </div>
          </div>
        </section>
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
                <section
                  class="feature-grid-fallback main-section"
                  style="padding: 0;"
                >
                  <div class="features-scroll-trap" style="position: relative;">
                    <!-- Sticky viewport for crossfading features -->
                    <div
                      style="position: sticky; top: 0; min-height: 100vh; width: 100%; overflow: hidden; background-color: rgb(33, 38, 50);"
                    >
                      ${this._featureSlides.map((slide, index) => {
                        const isActive = this._activeSlideIndex === index;
                        const opacity = isActive ? 1 : 0;
                        const scale = isActive ? 1 : 0.95;

                        return html`
                          <div
                            style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: ${opacity}; pointer-events: ${isActive
                              ? 'auto'
                              : 'none'}; transform: scale(${scale}); transition: opacity 0.6s ease-out, transform 0.6s ease-out; z-index: ${isActive
                              ? 10
                              : 1};"
                          >
                            <div
                              class="section-container"
                              style="max-width: 1200px; display: flex; flex-direction: ${index %
                                2 ===
                              0
                                ? 'row'
                                : 'row-reverse'}; align-items: center; justify-content: center; gap: 6rem; padding: 4rem 1rem; height: 100%;"
                            >
                              <div style="max-width: 450px; flex: 1;">
                                <h3
                                  style="font-size: 2.2rem; margin-bottom: 2rem; font-weight: 600; line-height: 1.3;"
                                >
                                  ${slide.title}
                                </h3>
                                <p
                                  style="font-size: 1.15rem; color: rgb(161, 161, 170); line-height: 1.7;"
                                >
                                  ${slide.text}
                                </p>
                                ${!this._showVideo[index] && slide.videoUrl
                                  ? html`<a
                                      href="javascript:void(0)"
                                      class="watch-video-link mt-3 d-inline-block"
                                      @click=${() => this._playVideo(index)}
                                      style="margin-top: 2rem; font-size: 1.1rem; color: var(--sl-color-primary-400); text-decoration: none; font-weight: 500;"
                                    >
                                      <sl-icon
                                        name="play-circle"
                                        style="vertical-align: text-bottom; margin-right: 0.5rem;"
                                      ></sl-icon>
                                      Watch Video
                                    </a>`
                                  : ''}
                              </div>
                              ${slide.placeholderImg
                                ? html`<div
                                    style="flex: 1; display: flex; justify-content: center; align-items: center;"
                                  >
                                    <img
                                      src="${slide.placeholderImg}"
                                      style="width: 100%; max-width: 650px; height: auto; box-shadow: 0 20px 40px rgba(0,0,0,0.5); border-radius: 4px; mask-image: linear-gradient(to ${index %
                                        2 ===
                                      0
                                        ? 'left'
                                        : 'right'}, black 75%, transparent 100%); -webkit-mask-image: linear-gradient(to ${index %
                                        2 ===
                                      0
                                        ? 'left'
                                        : 'right'}, black 75%, transparent 100%);"
                                      alt="${slide.title} preview"
                                    />
                                  </div>`
                                : html`<div style="flex: 1;"></div>`}
                            </div>
                          </div>
                        `;
                      })}
                    </div>

                    <!-- Invisible scroll spacers that dictate the scroll length and trigger intersection observer -->
                    <div style="margin-top: -100vh;">
                      ${this._featureSlides.map(
                        (_, index) => html`
                          <div
                            class="feature-scroll-spacer"
                            data-index="${index}"
                            style="height: 120vh; width: 100%;"
                          ></div>
                        `
                      )}
                    </div>
                  </div>
                </section>
              `
            : ''}
        ${this._extendedDescription && getBrandConfig().edition === 'saas'
          ? html`
              <section
                class="extended-description-section main-section"
                style="padding-top: 3rem;"
              >
                <div class="section-container">
                  <!-- SVG Animation Scroll Trap -->
                  <div
                    class="animations-scroll-trap"
                    style="position: relative; margin: 0 auto 4rem auto; max-width: 900px;"
                  >
                    <!-- Sticky viewport -->
                    <div
                      style="position: sticky; top: calc(50vh - 250px); width: 100%; aspect-ratio: 16/9; border-radius: 12px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); background-color: rgb(22, 27, 36);"
                    >
                      ${[
                        {
                          src: '/assets/direct.svg',
                          alt: 'Direct AI Integration',
                        },
                        {
                          src: '/assets/mcp-firewall2.svg',
                          alt: 'MCP Firewall Animation',
                        },
                        { src: '/assets/gateway.svg', alt: 'AI Agent Gateway' },
                      ].map((item, index) => {
                        const isActive = this._activeAnimationIndex === index;
                        return html`
                          <div
                            style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: ${isActive
                              ? 1
                              : 0}; transition: opacity 0.6s ease-out; pointer-events: ${isActive
                              ? 'auto'
                              : 'none'};"
                          >
                            <img
                              src="${item.src}"
                              alt="${item.alt}"
                              style="width: 100%; height: 100%; object-fit: contain;"
                            />
                          </div>
                        `;
                      })}
                    </div>

                    <!-- Invisible scroll spacers -->
                    <div style="margin-top: -30vh;">
                      ${[1, 2, 3].map(
                        (_, index) => html`
                          <div
                            class="animation-scroll-spacer"
                            data-anim-index="${index}"
                            style="height: 100vh; width: 100%;"
                          ></div>
                        `
                      )}
                    </div>
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
              ${this._cliSetup.length > 0
                ? html`
                    <div
                      style="max-width: 65rem; margin: 3rem auto 0; text-align: left;"
                    >
                      <ide-setup-tabs
                        .configs=${[
                          {
                            ide: 'cli',
                            ide_name: 'Preloop CLI',
                            logo_path: '/assets/preloop-badge.svg',
                            logo_width: '32',
                            prerequisites: [],
                            setup_instructions:
                              'Install the CLI to onboard existing agents or connect them manually.',
                            code: 'curl -fsSL https://preloop.ai/install/cli | sh',
                          },
                        ]}
                        defaultTab="cli"
                        helpText="The Preloop CLI configures your local environment and allows easy agent connecting."
                      ></ide-setup-tabs>
                    </div>
                  `
                : ''}
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
