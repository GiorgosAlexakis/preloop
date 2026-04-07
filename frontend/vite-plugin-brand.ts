import { Plugin, IndexHtmlTransformContext } from 'vite';
import * as yaml from 'js-yaml';
import * as fs from 'fs';
import * as path from 'path';
import { BrandConfig } from './src/brand-config';
import {
  get_canonical_url,
  get_meta_for_route,
  get_route_from_filename,
  get_static_routes_with_options,
  get_structured_data_for_route,
} from './src/brand-seo';

/**
 * Options for the brand plugin
 */
export interface BrandPluginOptions {
  /** Path to brands.yaml file (default: ./brands.yaml relative to this plugin) */
  configPath?: string;
  /** Path to content directory (default: ./content relative to this plugin) */
  contentPath?: string;
  /** Output directory name (default: 'dist') */
  outDir?: string;
}

/**
 * Vite plugin to inject brand-specific content and configuration
 *
 * This plugin:
 * 1. Loads brand configuration from brands.yaml
 * 2. Injects brand config as window.BRAND_CONFIG
 * 3. Transforms index.html with route-specific slotted content for SEO
 * 4. Updates meta tags with brand-specific values per route
 *
 * @param brandKey - The brand key to use from brands.yaml (e.g., 'preloop')
 * @param options - Optional configuration for custom paths
 */
export function brandPlugin(brandKey: string, options: BrandPluginOptions = {}): Plugin {
  let brandConfig: BrandConfig;

  // Resolve paths - use options or defaults
  const configPath = options.configPath || path.resolve(__dirname, 'brands.yaml');
  const contentBasePath = options.contentPath || path.resolve(__dirname, 'content');
  const outDirPath = options.outDir || path.resolve(__dirname, 'dist');

  return {
    name: 'vite-plugin-brand',

    configResolved() {
      // Load brand configuration at build time
      if (!fs.existsSync(configPath)) {
        throw new Error(`brands.yaml not found at ${configPath}`);
      }

      const brandsYaml = fs.readFileSync(configPath, 'utf-8');
      const brands = yaml.load(brandsYaml) as any;

      if (!brands || !brands.brands) {
        throw new Error('Invalid brands.yaml structure: brands.brands not found');
      }

      brandConfig = brands.brands[brandKey];

      if (!brandConfig) {
        throw new Error(
          `Brand "${brandKey}" not found in brands.yaml. Available brands: ${Object.keys(brands.brands).join(', ')}`
        );
      }

      // Apply defaults for missing optional fields
      brandConfig.company = brandConfig.company || {};
      brandConfig.social = brandConfig.social || {};
      brandConfig.landing = brandConfig.landing || {} as any;
      brandConfig.landing.meta = brandConfig.landing.meta || {} as any;
      brandConfig.landing.hero = brandConfig.landing.hero || {} as any;
      brandConfig.landing.features = brandConfig.landing.features || [];
      brandConfig.landing.faqs = brandConfig.landing.faqs || [];
      brandConfig.landing.get_started = brandConfig.landing.get_started || {} as any;
      brandConfig.landing.get_started.features = brandConfig.landing.get_started.features || [];
      brandConfig.landing.get_started.mcp_configs = brandConfig.landing.get_started.mcp_configs || [];

      console.log(`\n🎨 Building for brand: ${brandConfig.name} (${brandConfig.domain})\n`);
    },

    async generateBundle(options, bundle) {
      // Generate landing content JSON file with safe defaults
      const landingContent = {
        hero: brandConfig.landing.hero || {},
        extended_description: brandConfig.landing.meta?.extended_description || '',
        features_layout: brandConfig.landing.features_layout || 'grid',
        features: brandConfig.landing.features || [],
        faqs: brandConfig.landing.faqs || [],
        get_started: brandConfig.landing.get_started || {},
        product_hunt: (brandConfig.landing as any).product_hunt || null,
        featured_video: (brandConfig.landing as any).featured_video || null,
      };
      const aiActReadinessMdPath = path.resolve(
        contentBasePath,
        `${brandKey}/ai-act-readiness.md`
      );
      const hasAiActReadinessPage = fs.existsSync(aiActReadinessMdPath);

      // Add JSON file to bundle
      this.emitFile({
        type: 'asset',
        fileName: 'landing-content.json',
        source: JSON.stringify(landingContent, null, 2),
      });

      this.emitFile({
        type: 'asset',
        fileName: 'sitemap.xml',
        source: generateSitemapXml(brandConfig, hasAiActReadinessPage),
      });

      this.emitFile({
        type: 'asset',
        fileName: 'robots.txt',
        source: generateRobotsTxt(brandConfig),
      });

      this.emitFile({
        type: 'asset',
        fileName: 'llms.txt',
        source: generateLlmsTxt(brandConfig, hasAiActReadinessPage),
      });

      // Generate static HTML fragments for dynamic loading
      const privacyHTML = await loadMarkdownContent(contentBasePath, brandKey, 'privacy');

      this.emitFile({
        type: 'asset',
        fileName: 'content/privacy.html',
        source: privacyHTML,
      });

      // Only generate pricing content for SaaS editions
      const edition = (brandConfig as any).edition || 'saas';
      if (edition === 'saas') {
        const pricingHTML = generatePricingContent(brandConfig);
        this.emitFile({
          type: 'asset',
          fileName: 'content/pricing.html',
          source: pricingHTML,
        });
      }

      // Copy brand-specific markdown files to dist/content/ for dynamic loading
      // Use the brand key (e.g., 'preloop') to find content folder
      const contentFiles = [
        'privacy.md',
        'terms.md',
        'whatis-mcp.md',
        'ai-act-readiness.md',
      ];

      for (const file of contentFiles) {
        const contentFilePath = path.resolve(contentBasePath, `${brandKey}/${file}`);
        if (fs.existsSync(contentFilePath)) {
          const markdown = fs.readFileSync(contentFilePath, 'utf-8');
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
      // Use the configured output directory
      const indexHtmlPath = path.resolve(outDirPath, 'index.html');

      if (!fs.existsSync(indexHtmlPath)) {
        console.warn(`index.html not found at ${indexHtmlPath}, cannot generate standalone HTML pages`);
        return;
      }

      const indexHtml = fs.readFileSync(indexHtmlPath, 'utf-8');

      // Generate static markdown content HTML
      // Use brandKey for content folder lookup
      const privacyHTML = await loadMarkdownContent(contentBasePath, brandKey, 'privacy');
      const termsHTML = await loadMarkdownContent(contentBasePath, brandKey, 'terms');
      const whatisMcpHTML = await loadMarkdownContent(contentBasePath, brandKey, 'whatis-mcp');
      const edition = (brandConfig as any).edition || 'saas';
      const aiActReadinessMdPath = path.resolve(
        contentBasePath,
        `${brandKey}/ai-act-readiness.md`
      );
      const hasAiActReadinessPage = fs.existsSync(aiActReadinessMdPath);
      const aiActReadinessHTML = hasAiActReadinessPage
        ? await loadMarkdownContent(contentBasePath, brandKey, 'ai-act-readiness')
        : '';

      // Generate privacy.html with proper meta tags and content
      const privacyPage = generateFullHtmlPage(indexHtml, '/privacy', brandConfig, privacyHTML);
      fs.writeFileSync(path.resolve(outDirPath, 'privacy.html'), privacyPage);

      // Generate terms.html
      const termsPage = generateFullHtmlPage(indexHtml, '/terms', brandConfig, termsHTML);
      fs.writeFileSync(path.resolve(outDirPath, 'terms.html'), termsPage);

      // Generate whatis-mcp.html
      const whatisMcpPage = generateFullHtmlPage(indexHtml, '/whatis-mcp', brandConfig, whatisMcpHTML);
      fs.writeFileSync(path.resolve(outDirPath, 'whatis-mcp.html'), whatisMcpPage);

      if (edition === 'saas' && hasAiActReadinessPage) {
        // Generate ai-act-readiness.html
        const aiActReadinessPage = generateFullHtmlPage(
          indexHtml,
          '/ai-act-readiness',
          brandConfig,
          aiActReadinessHTML
        );
        fs.writeFileSync(
          path.resolve(outDirPath, 'ai-act-readiness.html'),
          aiActReadinessPage
        );
      }

      // Generate additional pages for SaaS editions
      const generatedPages = ['privacy.html', 'terms.html', 'whatis-mcp.html'];
      if (edition === 'saas' && hasAiActReadinessPage) {
        generatedPages.push('ai-act-readiness.html');
      }

      if (edition === 'saas') {
        // Generate pricing.html
        const pricingHTML = generatePricingContent(brandConfig);
        const pricingPage = generateFullHtmlPage(indexHtml, '/pricing', brandConfig, pricingHTML);
        fs.writeFileSync(path.resolve(outDirPath, 'pricing.html'), pricingPage);
        generatedPages.push('pricing.html');

        // Generate about.html
        const aboutHTML = await loadMarkdownContent(contentBasePath, brandKey, 'about');
        if (aboutHTML) {
          const aboutPage = generateFullHtmlPage(indexHtml, '/about', brandConfig, aboutHTML);
          fs.writeFileSync(path.resolve(outDirPath, 'about.html'), aboutPage);
          generatedPages.push('about.html');

          // Also copy about.md to content folder for client-side navigation
          const aboutMdPath = path.resolve(contentBasePath, brandKey, 'about.md');
          if (fs.existsSync(aboutMdPath)) {
            const contentDir = path.resolve(outDirPath, 'content');
            fs.copyFileSync(aboutMdPath, path.resolve(contentDir, 'about.md'));
          }
        }

        if (hasAiActReadinessPage) {
          const contentDir = path.resolve(outDirPath, 'content');
          fs.copyFileSync(
            aiActReadinessMdPath,
            path.resolve(contentDir, 'ai-act-readiness.md')
          );
        }
      }

      console.log(`✓ Generated standalone HTML pages: ${generatedPages.join(', ')}`);
    },

    async transformIndexHtml(html, ctx) {
      // Determine which route we're rendering based on the filename
      const filename = ctx.filename || '';
      const route = get_route_from_filename(filename);

      // Get route-specific metadata
      const meta = get_meta_for_route(route, brandConfig);
      const canonicalUrl = get_canonical_url(route, brandConfig);

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
        `<meta property="og:title" content="${meta.og_title}">`
      );

      // Replace Open Graph description
      html = html.replace(
        /<meta property="og:description" content=".*?">/,
        `<meta property="og:description" content="${meta.og_description}">`
      );

      // Replace Open Graph image
      html = html.replace(
        /<meta property="og:image" content=".*?">/,
        `<meta property="og:image" content="${meta.og_image}">`
      );

      // Replace Open Graph URL
      html = html.replace(
        /<meta property="og:url" content=".*?">/,
        `<meta property="og:url" content="${canonicalUrl}">`
      );

      html = upsertHeadTag(
        html,
        /<link rel="canonical" href=".*?">/,
        `<link rel="canonical" href="${canonicalUrl}">`
      );

      html = upsertHeadTag(
        html,
        /<meta name="robots" content=".*?">/,
        '<meta name="robots" content="index, follow">'
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

      html = upsertStructuredDataTag(html, route, brandConfig);

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
        edition: (brandConfig as any).edition || 'saas',  // Default to 'saas' for backwards compatibility
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
      const slottedContent = await generateSlottedContentForRoute(route, brandConfig, brandKey, contentBasePath);
      if (slottedContent) {
        if (route === '/') {
          // Landing page: inject landing-view with slots
          html = html.replace(
            '<lit-app></lit-app>',
            `<lit-app data-ssr-route="/"><landing-view>${slottedContent}</landing-view></lit-app>`
          );
        } else if (
          route === '/privacy' ||
          route === '/pricing' ||
          route === '/ai-act-readiness'
        ) {
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
 * Generate route-specific slotted HTML content for SEO
 * Content uses named slots that web components can consume
 */
async function generateSlottedContentForRoute(route: string, config: BrandConfig, brandKey: string, contentBasePath: string): Promise<string> {
  // Safe accessors with defaults
  const hero = config.landing?.hero || {};
  const meta = config.landing?.meta || {};
  const features = config.landing?.features || [];
  const faqs = config.landing?.faqs || [];
  const getStarted = config.landing?.get_started || {};
  const getStartedFeatures = getStarted.features || [];
  const mcpConfigs = getStarted.mcp_configs || [];

  switch (route) {
    case '/':
      // Landing page - generate slotted content for landing-view component
      return `
    <!-- SEO Content - Slotted for web components to consume -->
    <!-- Landing-view component will read and display this content -->

    <!-- Hero content slots -->
    <h1 slot="hero-title">${hero.title || ''}</h1>
    <p slot="hero-lead">${hero.lead || ''}</p>
    <span slot="cta-primary">${hero.cta_primary || ''}</span>
    <span slot="cta-secondary">${hero.cta_secondary || ''}</span>
    <span slot="cta-secondary-url">${hero.cta_secondary_url || ''}</span>

    <!-- Extended description slot (only if exists) -->
    ${meta.extended_description ? `<p slot="extended-description">${meta.extended_description}</p>` : ''}

    <!-- Features layout slot -->
    <span slot="features-layout">${config.landing?.features_layout || 'grid'}</span>

    <!-- Feature slots -->
    ${features
          .map(
            (feature, idx) => `
    <div slot="feature-${idx}" data-title="${feature.title || ''}" data-text="${feature.text || ''}" data-video="${feature.videoUrl || ''}" data-img="${feature.placeholderImg || ''}">
      <h3>${feature.title || ''}</h3>
      <p>${feature.text || ''}</p>
    </div>`
          )
          .join('\n')}

    <!-- FAQ slots -->
    ${faqs
          .map(
            (faq, idx) => `
    <div slot="faq-${idx}" data-q="${faq.q || ''}" data-a="${faq.a || ''}">
      <h3>${faq.q || ''}</h3>
      <p>${faq.a || ''}</p>
    </div>`
          )
          .join('\n')}

    <!-- Get Started section slots -->
    <span slot="get-started-title">${getStarted.title || ''}</span>
    <span slot="get-started-link-text">${getStarted.link_text || ''}</span>
    <span slot="get-started-link-url">${getStarted.link_url || ''}</span>

    <!-- Get Started feature slots -->
    ${getStartedFeatures
          .map(
            (feature, idx) => `
    <div slot="get-started-feature-${idx}" data-icon="${feature.icon || ''}" data-title="${feature.title || ''}" data-text="${feature.text || ''}">
      <h3>${feature.title || ''}</h3>
      <p>${feature.text || ''}</p>
    </div>`
          )
          .join('\n')}

    <!-- MCP Setup slots -->
    <span slot="mcp-setup-title">${getStarted.mcp_setup_title || ''}</span>

    <!-- MCP Config slots -->
    ${mcpConfigs
          .map(
            (mcpConfig, idx) => `
    <div slot="mcp-config-${idx}"
         data-ide="${mcpConfig.ide || ''}"
         data-ide-name="${mcpConfig.ide_name || ''}"
         data-logo-path="${mcpConfig.logo_path || ''}"
         data-logo-width="${mcpConfig.logo_width || ''}"
         data-prerequisites='${JSON.stringify(mcpConfig.prerequisites || [])}'
         data-setup-instructions="${(mcpConfig.setup_instructions || '').replace(/"/g, '&quot;')}">
      <pre><code>${mcpConfig.code || ''}</code></pre>
    </div>`
          )
          .join('\n')}

    <!-- Product Hunt slot -->
    ${(() => {
          const productHunt = (config.landing as any).product_hunt;
          if (productHunt?.enabled) {
            return `
    <div slot="product-hunt"
         data-enabled="true"
         data-post-id="${productHunt.post_id || ''}"
         data-theme="${productHunt.theme || 'light'}">
      <a href="https://www.producthunt.com/products/preloop?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-preloop" target="_blank" rel="noopener noreferrer">
        <img alt="Preloop - The MCP Governance Layer | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=${productHunt.post_id}&amp;theme=${productHunt.theme}" />
      </a>
    </div>`;
          }
          return '';
        })()}

    <!-- Featured Video slot -->
    ${(() => {
          const featuredVideo = (config.landing as any).featured_video;
          if (featuredVideo?.enabled) {
            return `
    <div slot="featured-video"
         data-enabled="true"
         data-title="${featuredVideo.title || ''}"
         data-youtube-url="${featuredVideo.youtube_url || ''}"
         data-youtube-embed="${featuredVideo.youtube_embed || ''}">
      ${featuredVideo.title ? `<h2>${featuredVideo.title}</h2>` : ''}
      <iframe width="560" height="315" src="${featuredVideo.youtube_embed}" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
    </div>`;
          }
          return '';
        })()}
  `;

    case '/privacy':
      // Privacy page - will load markdown content
      return await loadMarkdownContent(contentBasePath, brandKey, 'privacy');

    case '/pricing':
      // Pricing page - will load markdown content
      return generatePricingContent(config);

    case '/ai-act-readiness':
      return await loadMarkdownContent(contentBasePath, brandKey, 'ai-act-readiness');

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
  const meta = get_meta_for_route(route, config);
  const canonicalUrl = get_canonical_url(route, config);
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
    `<meta property="og:title" content="${meta.og_title}">`
  );

  // Replace Open Graph description
  html = html.replace(
    /<meta property="og:description" content=".*?">/,
    `<meta property="og:description" content="${meta.og_description}">`
  );

  // Replace Open Graph image
  html = html.replace(
    /<meta property="og:image" content=".*?">/,
    `<meta property="og:image" content="${meta.og_image}">`
  );

  // Replace Open Graph URL
  html = html.replace(
    /<meta property="og:url" content=".*?">/,
    `<meta property="og:url" content="${canonicalUrl}">`
  );

  html = upsertHeadTag(
    html,
    /<link rel="canonical" href=".*?">/,
    `<link rel="canonical" href="${canonicalUrl}">`
  );

  html = upsertHeadTag(
    html,
    /<meta name="robots" content=".*?">/,
    '<meta name="robots" content="index, follow">'
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

  html = upsertStructuredDataTag(html, route, config);

  // Replace <lit-app> with content-wrapped version
  // Handle both empty <lit-app></lit-app> and <lit-app>...</lit-app> with existing content
  html = html.replace(
    /<lit-app[^>]*>[\s\S]*?<\/lit-app>/,
    `<lit-app data-ssr-route="${route}"><static-view-wrapper>${content}</static-view-wrapper></lit-app>`
  );

  return html;
}

function upsertHeadTag(html: string, pattern: RegExp, tag: string): string {
  if (pattern.test(html)) {
    return html.replace(pattern, tag);
  }

  return html.replace('</head>', `  ${tag}\n</head>`);
}

function upsertStructuredDataTag(
  html: string,
  route: string,
  config: BrandConfig
): string {
  const structuredData = JSON.stringify(
    get_structured_data_for_route(route, config)
  )
    .replaceAll('<', '\\u003c')
    .replaceAll('</script', '<\\/script');

  return upsertHeadTag(
    html,
    /<script id="preloop-structured-data" type="application\/ld\+json">[\s\S]*?<\/script>/,
    `<script id="preloop-structured-data" type="application/ld+json">${structuredData}</script>`
  );
}

function generateSitemapXml(
  config: BrandConfig,
  includeAiActReadiness: boolean
): string {
  const routes = get_static_routes_with_options(
    config,
    includeAiActReadiness
  );
  const urls = routes
    .map(
      (route) => `  <url>\n    <loc>https://${config.domain}${route}</loc>\n  </url>`
    )
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}

function generateRobotsTxt(config: BrandConfig): string {
  return `User-agent: *\nAllow: /\n\nSitemap: https://${config.domain}/sitemap.xml\n`;
}

function generateLlmsTxt(
  config: BrandConfig,
  includeAiActReadiness: boolean
): string {
  const meta = config.landing?.meta || {};
  const hero = config.landing?.hero || {};
  const routes = get_static_routes_with_options(
    config,
    includeAiActReadiness
  );

  return [
    `# ${config.name}`,
    '',
    meta.description || '',
    '',
    'Primary pages:',
    ...routes.map((route) => `- https://${config.domain}${route}`),
    '',
    'Primary calls to action:',
    `- ${hero.cta_primary || 'Sign up'} -> https://${config.domain}/register`,
    `- ${hero.cta_secondary || 'Request demo'} -> ${(hero as any).cta_secondary_url || `https://${config.domain}/request-demo`}`,
    '',
  ].join('\n');
}

/**
 * Load and convert markdown file to HTML using marked
 */
async function loadMarkdownContent(contentBasePath: string, brandName: string, filename: string): Promise<string> {
  const contentPath = path.resolve(contentBasePath, `${brandName}/${filename}.md`);

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
      /* Team section styles */
      .team-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 2rem;
        margin: 2rem 0;
      }
      .team-member {
        text-align: center;
        padding: 1.5rem;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
      }
      .team-photo {
        width: 150px;
        height: 150px;
        border-radius: 50%;
        object-fit: cover;
        margin-bottom: 1rem;
        border: 3px solid var(--sl-color-primary-500);
      }
      .team-member h4 {
        font-size: 1.3rem;
        font-weight: 500;
        margin: 0.5rem 0 0.25rem;
        color: var(--sl-color-neutral-0);
      }
      .team-member p {
        font-size: 0.95rem;
        line-height: 1.5;
        text-align: left;
      }
      .team-member p strong {
        color: var(--sl-color-primary-400);
      }
    </style>
    ${html}
  </article>`;

  return styledArticle;
}

// generatePrivacyContent removed - use loadMarkdownContent(brandKey, 'privacy') directly

/**
 * Generate pricing content for SEO
 * This content is rendered in the main DOM for search engine indexing.
 * The actual interactive pricing UI is handled by the public-pricing-view component.
 */
function generatePricingContent(config: BrandConfig): string {
  return `
    <article class="pricing-content">
      <h1>Pricing - ${config.name}</h1>
      <p class="lead">Choose the plan that fits your team</p>

      <section class="pricing-plans">
        <div class="plan">
          <h2>Open Source</h2>
          <p class="price">Free</p>
          <ul>
            <li>Self-hosted deployment</li>
            <li>MCP proxy &amp; tool management</li>
            <li>Single-user approvals</li>
            <li>Email &amp; mobile notifications</li>
            <li>Issue tracker integration</li>
            <li>Vector search &amp; duplicates</li>
            <li>Agentic flows</li>
            <li>Community support</li>
          </ul>
          <a href="https://github.com/preloop/preloop" target="_blank" rel="noopener noreferrer">View on GitHub</a>
        </div>

        <div class="plan">
          <h2>Teams</h2>
          <p class="price">$29/month or $290/year</p>
          <ul>
            <li>Everything in Open Source</li>
            <li>Cloud-hosted (managed)</li>
            <li>RBAC &amp; team management</li>
            <li>CEL conditional approvals</li>
            <li>Team-based approvals (quorum)</li>
            <li>Approval escalation</li>
            <li>Slack &amp; Mattermost notifications</li>
            <li>Audit logging</li>
            <li>14-day free trial</li>
            <li>Email support</li>
          </ul>
          <a href="/register">Start Free Trial</a>
        </div>

        <div class="plan">
          <h2>Enterprise</h2>
          <p class="price">Custom pricing</p>
          <ul>
            <li>Everything in Teams</li>
            <li>Self-hosted deployment option</li>
            <li>SSO, OIDC, SCIM support</li>
            <li>SLA commitments</li>
            <li>Dedicated support channels</li>
            <li>Priority feature requests</li>
          </ul>
          <a href="/request-demo">Contact Sales</a>
        </div>
      </section>

      <section class="pricing-faq">
        <h2>Frequently Asked Questions</h2>

        <h3>Can I change plans later?</h3>
        <p>Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately.</p>

        <h3>What payment methods do you accept?</h3>
        <p>We accept all major credit cards and can invoice for annual plans.</p>

        <h3>Is there a free trial?</h3>
        <p>Yes, the Teams plan comes with a 14-day free trial.</p>

        <h3>Is the Open Source edition really free?</h3>
        <p>Yes! ${config.name} is open source under the Apache 2.0 license. You can self-host it for free with no limitations on usage.</p>

        <h3>What's the difference between Teams and Enterprise?</h3>
        <p>Teams is cloud-hosted with all advanced approval features. Enterprise adds self-hosted deployment options, SSO/SCIM, admin dashboard, and dedicated support with SLA commitments.</p>
      </section>
    </article>
  `;
}
