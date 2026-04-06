import type { BrandConfig } from './brand-config';

export type RouteMeta = {
  title: string;
  description: string;
  keywords: string;
  og_image: string;
  og_title: string;
  og_description: string;
};

export function get_route_from_filename(filename: string): string {
  if (filename.includes('ai-act-readiness.html')) {
    return '/ai-act-readiness';
  }

  if (filename.includes('about.html')) {
    return '/about';
  }

  if (filename.includes('whatis-mcp.html')) {
    return '/whatis-mcp';
  }

  if (filename.includes('terms.html')) {
    return '/terms';
  }

  if (filename.includes('privacy.html')) {
    return '/privacy';
  }

  if (filename.includes('pricing.html')) {
    return '/pricing';
  }

  return '/';
}

export function get_canonical_url(route: string, config: BrandConfig): string {
  return `https://${config.domain}${route}`;
}

export function get_meta_for_route(
  route: string,
  config: BrandConfig
): RouteMeta {
  const meta = config.landing?.meta || {};
  const default_title = meta.title || config.name || 'Preloop';
  const default_description = meta.description || '';
  const default_keywords = meta.keywords || '';
  const default_og_image = meta.og_image || '';
  const default_og_title = meta.og_title || default_title;
  const default_og_description = meta.og_description || default_description;

  switch (route) {
    case '/':
      return {
        title: default_title,
        description: default_description,
        keywords: default_keywords,
        og_image: default_og_image,
        og_title: default_og_title,
        og_description: default_og_description,
      };
    case '/privacy':
      return {
        title: `Privacy Policy - ${config.name}`,
        description: `${config.name} Privacy Policy - Learn how we protect your data.`,
        keywords: `${config.name}, Privacy Policy, Data Protection`,
        og_image: default_og_image,
        og_title: `Privacy Policy - ${config.name}`,
        og_description: `${config.name} Privacy Policy - Learn how we protect your data.`,
      };
    case '/pricing':
      return {
        title: `Pricing - ${config.name}`,
        description: `${config.name} Pricing - Choose the plan that fits your team.`,
        keywords: `${config.name}, Pricing, Plans, Subscription`,
        og_image: default_og_image,
        og_title: `Pricing - ${config.name}`,
        og_description: `${config.name} Pricing - Choose the plan that fits your team.`,
      };
    case '/terms':
      return {
        title: `Terms of Service - ${config.name}`,
        description: `${config.name} Terms of Service - Read our terms and conditions.`,
        keywords: `${config.name}, Terms of Service, Legal`,
        og_image: default_og_image,
        og_title: `Terms of Service - ${config.name}`,
        og_description: `${config.name} Terms of Service - Read our terms and conditions.`,
      };
    case '/whatis-mcp':
      return {
        title: `What is MCP? - ${config.name}`,
        description: `Learn what the Model Context Protocol (MCP) is and how ${config.name} uses it to govern AI agents and tool access.`,
        keywords: `${config.name}, MCP, Model Context Protocol, AI agents, AI governance`,
        og_image: default_og_image,
        og_title: `What is MCP? - ${config.name}`,
        og_description: `Learn what the Model Context Protocol (MCP) is and how ${config.name} uses it to govern AI agents and tool access.`,
      };
    case '/about':
      return {
        title: `About - ${config.name}`,
        description: `Learn about ${config.name} and our mission to make AI automation governable, observable, and human-centered.`,
        keywords: `${config.name}, About, Company, Team, Mission, AI governance`,
        og_image: default_og_image,
        og_title: `About - ${config.name}`,
        og_description: `Learn about ${config.name} and our mission to make AI automation governable, observable, and human-centered.`,
      };
    case '/ai-act-readiness':
      return {
        title: `EU AI Act readiness with ${config.name}`,
        description: `${config.name} helps teams implement approvals, runtime visibility, policy enforcement, and audit trails that can support AI governance programs and EU AI Act readiness work.`,
        keywords: `${config.name}, EU AI Act, AI Act readiness, AI governance, AI approvals, AI audit trail, operational AI governance`,
        og_image: default_og_image,
        og_title: `EU AI Act readiness with ${config.name}`,
        og_description: `${config.name} supports AI governance programs with approvals, policy enforcement, runtime visibility, and audit trails for AI Act readiness work.`,
      };
    default:
      return {
        title: default_title,
        description: default_description,
        keywords: default_keywords,
        og_image: default_og_image,
        og_title: default_og_title,
        og_description: default_og_description,
      };
  }
}

export function get_static_routes(config: BrandConfig): string[] {
  return get_static_routes_with_options(config, true);
}

export function get_static_routes_with_options(
  config: BrandConfig,
  include_ai_act_readiness: boolean
): string[] {
  const routes = ['/', '/privacy', '/terms', '/whatis-mcp'];

  if ((config.edition || 'saas') === 'saas') {
    routes.push('/pricing', '/about');
    if (include_ai_act_readiness) {
      routes.push('/ai-act-readiness');
    }
  }

  return routes;
}

export function get_structured_data_for_route(
  route: string,
  config: BrandConfig
): Array<Record<string, unknown>> {
  const meta = get_meta_for_route(route, config);
  const canonical_url = get_canonical_url(route, config);
  const organization = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: config.name,
    url: `https://${config.domain}/`,
    logo: `https://${config.domain}${meta.og_image}`,
    sameAs: Object.values(config.social || {}).filter(Boolean),
  };

  if (route === '/') {
    const faq_page =
      config.landing?.faqs && config.landing.faqs.length > 0
        ? {
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            mainEntity: config.landing.faqs.map((faq) => ({
              '@type': 'Question',
              name: faq.q,
              acceptedAnswer: {
                '@type': 'Answer',
                text: faq.a.replace(/<[^>]+>/g, ''),
              },
            })),
          }
        : null;

    return [
      organization,
      {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        name: meta.title,
        url: canonical_url,
        description: meta.description,
      },
      {
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        name: config.name,
        applicationCategory: 'BusinessApplication',
        operatingSystem: 'Web',
        description: meta.description,
        url: canonical_url,
        featureList: (config.landing?.features || []).map(
          (feature) => feature.title
        ),
      },
      ...(faq_page ? [faq_page] : []),
    ];
  }

  if (route === '/about') {
    return [
      organization,
      {
        '@context': 'https://schema.org',
        '@type': 'AboutPage',
        name: meta.title,
        url: canonical_url,
        description: meta.description,
      },
    ];
  }

  if (route === '/whatis-mcp') {
    return [
      organization,
      {
        '@context': 'https://schema.org',
        '@type': 'TechArticle',
        headline: meta.title,
        url: canonical_url,
        description: meta.description,
        author: {
          '@type': 'Organization',
          name: config.name,
        },
        publisher: {
          '@type': 'Organization',
          name: config.name,
        },
      },
    ];
  }

  if (route === '/ai-act-readiness') {
    return [
      organization,
      {
        '@context': 'https://schema.org',
        '@type': 'Article',
        headline: meta.title,
        url: canonical_url,
        description: meta.description,
        about: ['EU AI Act', 'AI governance', 'AI agent approvals'],
        author: {
          '@type': 'Organization',
          name: config.name,
        },
        publisher: {
          '@type': 'Organization',
          name: config.name,
        },
        isAccessibleForFree: true,
      },
    ];
  }

  return [
    organization,
    {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: meta.title,
      url: canonical_url,
      description: meta.description,
    },
  ];
}
