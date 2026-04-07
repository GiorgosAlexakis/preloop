import { expect } from '@open-wc/testing';

import type { BrandConfig } from './brand-config';
import {
  get_meta_for_route,
  get_route_from_filename,
  get_static_routes_with_options,
  get_structured_data_for_route,
} from './brand-seo';

const test_config: BrandConfig = {
  name: 'Preloop',
  domain: 'preloop.ai',
  edition: 'saas',
  company: {
    legal_name: 'Spacecode.AI, Inc.',
    address: '28 Geary St STE 650 Suite #235',
    city: 'San Francisco, CA 94108',
  },
  branding: {
    logo_light: '/images/logos/preloop_logo_light.svg',
    logo_dark: '/images/logos/preloop_logo_dark.svg',
    favicon: '/assets/preloop-badge.png',
    primary_color: '#7c3aed',
    gradient_product:
      'linear-gradient(90deg, hsl(270, 70%, 55%), hsl(290, 75%, 50%))',
    gradient_ai:
      'linear-gradient(90deg, hsl(200, 80%, 55%), hsl(180, 85%, 50%))',
  },
  social: {
    twitter: '@preloopai',
    linkedin: 'https://www.linkedin.com/company/preloop-ai/',
    instagram: 'https://www.instagram.com/preloop.ai',
  },
  landing: {
    meta: {
      title:
        'Preloop: AI agent governance, approvals, and AI Act readiness support',
      description:
        'Preloop helps engineering, platform, security, and operations teams govern AI agents in real workflows.',
      extended_description:
        'Preloop is an AI safety and control platform for teams deploying AI agents into real workflows.',
      keywords: 'Preloop, AI agent governance, AI Act readiness',
      og_image: '/assets/mcp-firewall.svg',
      og_title:
        'Preloop: Govern AI agents without slowing engineering teams down',
      og_description:
        'Onboard existing agents, govern tool access, and keep runtime activity visible.',
    },
    features_layout: 'grid',
    hero: {
      title: 'Onboard and Control AI Agents',
      lead: 'Govern AI agents in real workflows.',
      cta_primary: 'Start Free Trial',
      cta_secondary: 'Plan Your Rollout',
      cta_secondary_url: 'https://calendar.app.google/FV95tXZtfGpPk7398',
    },
    features: [
      {
        title: 'Govern tool access with policies and approvals',
        text: 'Define allow, deny, justification, and approval rules.',
        videoUrl: '',
        placeholderImg: '',
      },
    ],
    faqs: [
      {
        q: 'Can Preloop help with EU AI Act readiness?',
        a: 'Yes. See <a href="/ai-act-readiness">AI Act readiness with Preloop</a>.',
      },
    ],
    get_started: {
      title: 'Onboard or connect your AI agent in minutes',
      link_text: 'See AI Act readiness guidance',
      link_url: '/ai-act-readiness',
      features: [],
      mcp_setup_title: 'Start with preloop agents discover',
      mcp_configs: [],
    },
  },
};

describe('brand-seo', () => {
  it('maps ai-act-readiness html files to the correct route', () => {
    expect(get_route_from_filename('/tmp/dist/ai-act-readiness.html')).to.equal(
      '/ai-act-readiness'
    );
  });

  it('returns route-specific AI Act metadata', () => {
    const meta = get_meta_for_route('/ai-act-readiness', test_config);

    expect(meta.title).to.equal('EU AI Act readiness with Preloop');
    expect(meta.description).to.include('AI governance programs');
    expect(meta.keywords).to.include('EU AI Act');
  });

  it('can exclude AI Act readiness from static routes when content is absent', () => {
    const routes = get_static_routes_with_options(test_config, false);

    expect(routes).to.include('/pricing');
    expect(routes).to.include('/about');
    expect(routes).to.not.include('/ai-act-readiness');
  });

  it('includes article structured data for the AI Act readiness page', () => {
    const structured_data = get_structured_data_for_route(
      '/ai-act-readiness',
      test_config
    );

    const article = structured_data.find(
      (entry) => entry['@type'] === 'Article'
    );

    expect(article).to.exist;
    expect(article?.headline).to.equal('EU AI Act readiness with Preloop');
    expect(article?.about).to.deep.equal([
      'EU AI Act',
      'AI governance',
      'AI agent approvals',
    ]);
  });

  it('includes FAQ structured data on the homepage', () => {
    const structured_data = get_structured_data_for_route('/', test_config);

    const faq_page = structured_data.find(
      (entry) => entry['@type'] === 'FAQPage'
    );

    expect(faq_page).to.exist;
    expect(faq_page?.mainEntity).to.have.length(1);
  });
});
