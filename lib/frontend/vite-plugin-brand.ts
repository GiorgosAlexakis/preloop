import { Plugin, IndexHtmlTransformContext } from 'vite';
import * as yaml from 'js-yaml';
import * as fs from 'fs';
import * as path from 'path';
import { BrandConfig } from './src/brand-config';

/**
 * Vite plugin to inject brand-specific content and configuration
 *
 * This plugin:
 * 1. Loads brand configuration from brands.yaml
 * 2. Injects brand config as window.BRAND_CONFIG
 * 3. Transforms index.html with route-specific slotted content for SEO
 * 4. Updates meta tags with brand-specific values per route
 */
export function brandPlugin(brandName: string): Plugin {
  let brandConfig: BrandConfig;

  return {
    name: 'vite-plugin-brand',

    configResolved() {
      // Load brand configuration at build time
      const brandsYamlPath = path.resolve(__dirname, 'brands.yaml');

      if (!fs.existsSync(brandsYamlPath)) {
        throw new Error(`brands.yaml not found at ${brandsYamlPath}`);
      }

      const brandsYaml = fs.readFileSync(brandsYamlPath, 'utf-8');
      const brands = yaml.load(brandsYaml) as any;

      if (!brands || !brands.brands) {
        throw new Error('Invalid brands.yaml structure: brands.brands not found');
      }

      brandConfig = brands.brands[brandName];

      if (!brandConfig) {
        throw new Error(
          `Brand "${brandName}" not found in brands.yaml. Available brands: ${Object.keys(brands.brands).join(', ')}`
        );
      }

      console.log(`\n🎨 Building for brand: ${brandConfig.name} (${brandConfig.domain})\n`);
    },

    async generateBundle(options, bundle) {
      // Generate landing content JSON file
      const landingContent = {
        hero: brandConfig.landing.hero,
        features: brandConfig.landing.features,
        faqs: brandConfig.landing.faqs,
      };

      // Add JSON file to bundle
      this.emitFile({
        type: 'asset',
        fileName: 'landing-content.json',
        source: JSON.stringify(landingContent, null, 2),
      });

      // Generate static HTML fragments for dynamic loading
      const privacyHTML = await generatePrivacyContent(brandConfig);
      const pricingHTML = generatePricingContent(brandConfig);

      this.emitFile({
        type: 'asset',
        fileName: 'content/privacy.html',
        source: privacyHTML,
      });

      this.emitFile({
        type: 'asset',
        fileName: 'content/pricing.html',
        source: pricingHTML,
      });

      // Copy brand-specific markdown files to dist/content/ for dynamic loading
      const brandName = brandConfig.domain.split('.')[0];
      const contentFiles = ['privacy.md', 'terms.md', 'whatis-mcp.md'];

      for (const file of contentFiles) {
        const contentPath = path.resolve(__dirname, `content/${brandName}/${file}`);
        if (fs.existsSync(contentPath)) {
          const markdown = fs.readFileSync(contentPath, 'utf-8');
          this.emitFile({
            type: 'asset',
            fileName: `content/${file}`,
            source: markdown,
          });
        }
      }
    },

    async closeBundle() {
      // After all files are written, generate full HTML pages for static content
      // Read the generated index.html as a template
      const outDir = brandConfig.domain.includes('preloop') ? 'dist-preloop' : 'dist-spacebridge';
      const indexHtmlPath = path.resolve(__dirname, outDir, 'index.html');

      if (!fs.existsSync(indexHtmlPath)) {
        console.warn(`index.html not found at ${indexHtmlPath}, cannot generate standalone HTML pages`);
        return;
      }

      const indexHtml = fs.readFileSync(indexHtmlPath, 'utf-8');

      // Generate static markdown content HTML
      const brandName = brandConfig.domain.split('.')[0];
      const privacyHTML = await generatePrivacyContent(brandConfig);
      const termsHTML = await loadMarkdownContent(brandName, 'terms');
      const whatisMcpHTML = await loadMarkdownContent(brandName, 'whatis-mcp');

      // Generate privacy.html with proper meta tags and content
      const privacyPage = generateFullHtmlPage(indexHtml, '/privacy', brandConfig, privacyHTML);
      fs.writeFileSync(path.resolve(__dirname, outDir, 'privacy.html'), privacyPage);

      // Generate terms.html
      const termsPage = generateFullHtmlPage(indexHtml, '/terms', brandConfig, termsHTML);
      fs.writeFileSync(path.resolve(__dirname, outDir, 'terms.html'), termsPage);

      // Generate whatis-mcp.html
      const whatisMcpPage = generateFullHtmlPage(indexHtml, '/whatis-mcp', brandConfig, whatisMcpHTML);
      fs.writeFileSync(path.resolve(__dirname, outDir, 'whatis-mcp.html'), whatisMcpPage);

      console.log(`✓ Generated standalone HTML pages: privacy.html, terms.html, whatis-mcp.html`);
    },

    transformIndexHtml(html, ctx) {
      // Determine which route we're rendering based on the filename
      const filename = ctx.filename || '';
      const route = getRouteFromFilename(filename);

      // Get route-specific metadata
      const meta = getMetaForRoute(route, brandConfig);

      // Replace <title>
      html = html.replace(
        /<title>.*?<\/title>/,
        `<title>${meta.title}</title>`
      );

      // Replace meta description
      html = html.replace(
        /<meta name="description" content=".*?">/,
        `<meta name="description" content="${meta.description}">`
      );

      // Replace meta keywords
      html = html.replace(
        /<meta name="keywords" content=".*?">/,
        `<meta name="keywords" content="${meta.keywords}">`
      );

      // Replace Open Graph title
      html = html.replace(
        /<meta property="og:title" content=".*?">/,
        `<meta property="og:title" content="${meta.title}">`
      );

      // Replace Open Graph description
      html = html.replace(
        /<meta property="og:description" content=".*?">/,
        `<meta property="og:description" content="${meta.description}">`
      );

      // Replace Open Graph image
      html = html.replace(
        /<meta property="og:image" content=".*?">/,
        `<meta property="og:image" content="${meta.og_image}">`
      );

      // Replace Open Graph URL
      html = html.replace(
        /<meta property="og:url" content=".*?">/,
        `<meta property="og:url" content="https://${brandConfig.domain}${route}">`
      );

      // Replace Twitter card title
      html = html.replace(
        /<meta name="twitter:title" content=".*?">/,
        `<meta name="twitter:title" content="${meta.title}">`
      );

      // Replace Twitter card description
      html = html.replace(
        /<meta name="twitter:description" content=".*?">/,
        `<meta name="twitter:description" content="${meta.description}">`
      );

      // Replace Twitter card image
      html = html.replace(
        /<meta name="twitter:image" content=".*?">/,
        `<meta name="twitter:image" content="${meta.og_image}">`
      );

      // Replace Twitter site handle
      html = html.replace(
        /<meta name="twitter:site" content=".*?">/,
        `<meta name="twitter:site" content="${brandConfig.social.twitter}">`
      );

      // Replace Twitter creator handle
      html = html.replace(
        /<meta name="twitter:creator" content=".*?">/,
        `<meta name="twitter:creator" content="${brandConfig.social.twitter}">`
      );

      // Replace favicon
      html = html.replace(
        /\/images\/favicon\.png/g,
        brandConfig.branding.favicon
      );

      // Inject minimal runtime brand configuration (no content duplication)
      // Only includes styling/branding metadata, not SEO content
      const runtimeConfig = {
        name: brandConfig.name,
        domain: brandConfig.domain,
        branding: brandConfig.branding,
        social: brandConfig.social,
        company: brandConfig.company,
      };

      const brandScript = `
  <script>
    window.BRAND_CONFIG = ${JSON.stringify(runtimeConfig, null, 2)};
  </script>`;

      html = html.replace('</head>', `${brandScript}\n</head>`);

      // Inject route-specific content for SSR
      const slottedContent = generateSlottedContentForRoute(route, brandConfig);
      if (slottedContent) {
        if (route === '/') {
          // Landing page: inject landing-view with slots
          html = html.replace(
            '<lit-app></lit-app>',
            `<lit-app data-ssr-route="/"><landing-view>${slottedContent}</landing-view></lit-app>`
          );
        } else if (route === '/privacy' || route === '/pricing') {
          // Static pages: inject static-view-wrapper with content
          html = html.replace(
            '<lit-app></lit-app>',
            `<lit-app data-ssr-route="${route}"><static-view-wrapper>${slottedContent}</static-view-wrapper></lit-app>`
          );
        } else {
          // No SSR for other routes
          html = html.replace(
            '<lit-app></lit-app>',
            `<lit-app></lit-app>`
          );
        }
      }

      return html;
    },
  };
}

/**
 * Determine route from HTML filename
 */
function getRouteFromFilename(filename: string): string {
  if (filename.includes('index.html')) {
    return '/';
  } else if (filename.includes('privacy.html')) {
    return '/privacy';
  } else if (filename.includes('pricing.html')) {
    return '/pricing';
  }
  return '/';
}

/**
 * Get route-specific metadata
 */
function getMetaForRoute(route: string, config: BrandConfig) {
  switch (route) {
    case '/':
      return {
        title: config.landing.meta.title,
        description: config.landing.meta.description,
        keywords: config.landing.meta.keywords,
        og_image: config.landing.meta.og_image,
      };
    case '/privacy':
      return {
        title: `Privacy Policy - ${config.name}`,
        description: `${config.name} Privacy Policy - Learn how we protect your data.`,
        keywords: `${config.name}, Privacy Policy, Data Protection`,
        og_image: config.landing.meta.og_image,
      };
    case '/pricing':
      return {
        title: `Pricing - ${config.name}`,
        description: `${config.name} Pricing - Choose the plan that fits your team.`,
        keywords: `${config.name}, Pricing, Plans, Subscription`,
        og_image: config.landing.meta.og_image,
      };
    case '/terms':
      return {
        title: `Terms of Service - ${config.name}`,
        description: `${config.name} Terms of Service - Read our terms and conditions.`,
        keywords: `${config.name}, Terms of Service, Legal`,
        og_image: config.landing.meta.og_image,
      };
    case '/whatis-mcp':
      return {
        title: `What is MCP? - ${config.name}`,
        description: `Learn about the Model Context Protocol (MCP) and how ${config.name} leverages it.`,
        keywords: `${config.name}, MCP, Model Context Protocol, AI`,
        og_image: config.landing.meta.og_image,
      };
    default:
      return {
        title: config.landing.meta.title,
        description: config.landing.meta.description,
        keywords: config.landing.meta.keywords,
        og_image: config.landing.meta.og_image,
      };
  }
}

/**
 * Generate route-specific slotted HTML content for SEO
 * Content uses named slots that web components can consume
 */
function generateSlottedContentForRoute(route: string, config: BrandConfig): string {
  switch (route) {
    case '/':
      // Landing page - generate slotted content for landing-view component
      return `
    <!-- SEO Content - Slotted for web components to consume -->
    <!-- Landing-view component will read and display this content -->

    <!-- Hero content slots -->
    <h1 slot="hero-title">${config.landing.hero.title}</h1>
    <p slot="hero-lead">${config.landing.hero.lead}</p>
    <span slot="cta-primary">${config.landing.hero.cta_primary}</span>
    <span slot="cta-secondary">${config.landing.hero.cta_secondary}</span>

    <!-- Feature slots -->
    ${config.landing.features
      .map(
        (feature, idx) => `
    <div slot="feature-${idx}" data-title="${feature.title}" data-text="${feature.text}" data-video="${feature.videoUrl}" data-img="${feature.placeholderImg}">
      <h3>${feature.title}</h3>
      <p>${feature.text}</p>
    </div>`
      )
      .join('\n')}

    <!-- FAQ slots -->
    ${config.landing.faqs
      .map(
        (faq, idx) => `
    <div slot="faq-${idx}" data-q="${faq.q}" data-a="${faq.a}">
      <h3>${faq.q}</h3>
      <p>${faq.a}</p>
    </div>`
      )
      .join('\n')}
  `;

    case '/privacy':
      // Privacy page - will load markdown content
      return generatePrivacyContent(config);

    case '/pricing':
      // Pricing page - will load markdown content
      return generatePricingContent(config);

    default:
      return '';
  }
}

/**
 * Generate a full standalone HTML page for a route
 * Takes the base index.html and replaces meta tags and content for the route
 */
function generateFullHtmlPage(
  indexHtml: string,
  route: string,
  config: BrandConfig,
  content: string
): string {
  const meta = getMetaForRoute(route, config);
  let html = indexHtml;

  // Replace <title>
  html = html.replace(
    /<title>.*?<\/title>/,
    `<title>${meta.title}</title>`
  );

  // Replace meta description
  html = html.replace(
    /<meta name="description" content=".*?">/,
    `<meta name="description" content="${meta.description}">`
  );

  // Replace meta keywords
  html = html.replace(
    /<meta name="keywords" content=".*?">/,
    `<meta name="keywords" content="${meta.keywords}">`
  );

  // Replace Open Graph title
  html = html.replace(
    /<meta property="og:title" content=".*?">/,
    `<meta property="og:title" content="${meta.title}">`
  );

  // Replace Open Graph description
  html = html.replace(
    /<meta property="og:description" content=".*?">/,
    `<meta property="og:description" content="${meta.description}">`
  );

  // Replace Open Graph image
  html = html.replace(
    /<meta property="og:image" content=".*?">/,
    `<meta property="og:image" content="${meta.og_image}">`
  );

  // Replace Open Graph URL
  html = html.replace(
    /<meta property="og:url" content=".*?">/,
    `<meta property="og:url" content="https://${config.domain}${route}">`
  );

  // Replace Twitter card title
  html = html.replace(
    /<meta name="twitter:title" content=".*?">/,
    `<meta name="twitter:title" content="${meta.title}">`
  );

  // Replace Twitter card description
  html = html.replace(
    /<meta name="twitter:description" content=".*?">/,
    `<meta name="twitter:description" content="${meta.description}">`
  );

  // Replace Twitter card image
  html = html.replace(
    /<meta name="twitter:image" content=".*?">/,
    `<meta name="twitter:image" content="${meta.og_image}">`
  );

  // Replace <lit-app> with content-wrapped version
  // Handle both empty <lit-app></lit-app> and <lit-app>...</lit-app> with existing content
  html = html.replace(
    /<lit-app[^>]*>[\s\S]*?<\/lit-app>/,
    `<lit-app data-ssr-route="${route}"><static-view-wrapper>${content}</static-view-wrapper></lit-app>`
  );

  return html;
}

/**
 * Load and convert markdown file to HTML using marked
 */
async function loadMarkdownContent(brandName: string, filename: string): Promise<string> {
  const contentPath = path.resolve(__dirname, `content/${brandName}/${filename}.md`);

  if (!fs.existsSync(contentPath)) {
    console.warn(`Warning: Markdown file not found at ${contentPath}`);
    return `<article class="container py-5"><h1>Content Not Found</h1><p>The requested content could not be loaded.</p></article>`;
  }

  const markdown = fs.readFileSync(contentPath, 'utf-8');

  // Dynamically import marked (ESM module)
  const { marked } = await import('marked');
  const html = await marked.parse(markdown);

  // Add inline styles to match landing.css .text-section styles
  // These styles are needed because slotted content is in light DOM
  const styledArticle = `<article class="container py-5">
    <style>
      article h1 {
        font-size: 2.4rem;
        font-weight: 300;
        color: var(--sl-color-primary-500);
        margin-bottom: 1rem;
      }
      article h2 {
        font-size: 1.8rem;
        font-weight: 300;
        color: var(--sl-color-primary-500);
        margin-top: 2rem;
        margin-bottom: 1rem;
      }
      article h3 {
        font-size: 1.6rem;
        font-weight: 300;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
      }
      article p {
        margin-bottom: 1rem;
        line-height: 1.6;
      }
      article a {
        color: var(--sl-color-primary-600);
        text-decoration: underline;
      }
      article a:hover {
        color: var(--sl-color-primary-700);
      }
      article ul, article ol {
        margin-bottom: 1rem;
        padding-left: 2rem;
      }
    </style>
    ${html}
  </article>`;

  return styledArticle;
}

/**
 * Generate privacy policy content
 */
async function generatePrivacyContent(config: BrandConfig): Promise<string> {
  return await loadMarkdownContent(config.domain.split('.')[0], 'privacy');
}

/**
 * Generate pricing content
 * TODO: Load from markdown file for production
 */
function generatePricingContent(config: BrandConfig): string {
  return `
    <article class="container py-5">
      <h1 class="text-center mb-5">Pricing</h1>
      <p class="lead text-center mb-5">Choose the plan that fits your team</p>

      <div class="row g-4 mb-5">
        <div class="col-md-4">
          <div class="card h-100">
            <div class="card-header bg-primary text-white">
              <h3 class="h5 mb-0">Starter</h3>
            </div>
            <div class="card-body">
              <div class="display-4 mb-3">$49<small class="text-muted fs-6">/mo</small></div>
              <ul class="list-unstyled">
                <li>✓ Up to 5 users</li>
                <li>✓ 1 issue tracker integration</li>
                <li>✓ Basic AI features</li>
                <li>✓ Email support</li>
              </ul>
              <a href="/register" class="btn btn-primary w-100">Get Started</a>
            </div>
          </div>
        </div>

        <div class="col-md-4">
          <div class="card h-100 border-primary">
            <div class="card-header bg-primary text-white">
              <h3 class="h5 mb-0">Professional</h3>
              <small>Most Popular</small>
            </div>
            <div class="card-body">
              <div class="display-4 mb-3">$149<small class="text-muted fs-6">/mo</small></div>
              <ul class="list-unstyled">
                <li>✓ Up to 25 users</li>
                <li>✓ Unlimited integrations</li>
                <li>✓ Advanced AI features</li>
                <li>✓ Priority support</li>
                <li>✓ Custom workflows</li>
              </ul>
              <a href="/register" class="btn btn-primary w-100">Get Started</a>
            </div>
          </div>
        </div>

        <div class="col-md-4">
          <div class="card h-100">
            <div class="card-header bg-secondary text-white">
              <h3 class="h5 mb-0">Enterprise</h3>
            </div>
            <div class="card-body">
              <div class="display-4 mb-3">Custom</div>
              <ul class="list-unstyled">
                <li>✓ Unlimited users</li>
                <li>✓ Unlimited integrations</li>
                <li>✓ All AI features</li>
                <li>✓ Dedicated support</li>
                <li>✓ Custom deployment</li>
                <li>✓ SLA guarantee</li>
              </ul>
              <a href="/request-demo" class="btn btn-secondary w-100">Contact Sales</a>
            </div>
          </div>
        </div>
      </div>

      <section class="mt-5">
        <h2 class="text-center mb-4">Frequently Asked Questions</h2>
        <div class="row">
          <div class="col-lg-8 mx-auto">
            <div class="mb-4">
              <h3 class="h5 fw-bold">Can I change plans later?</h3>
              <p>Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately.</p>
            </div>
            <div class="mb-4">
              <h3 class="h5 fw-bold">What payment methods do you accept?</h3>
              <p>We accept all major credit cards and can invoice for annual plans.</p>
            </div>
            <div class="mb-4">
              <h3 class="h5 fw-bold">Is there a free trial?</h3>
              <p>Yes, all plans come with a 14-day free trial. No credit card required.</p>
            </div>
          </div>
        </div>
      </section>
    </article>
  `;
}
