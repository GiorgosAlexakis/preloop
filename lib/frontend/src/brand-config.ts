/**
 * Brand configuration interfaces
 *
 * These interfaces define the structure of brand-specific configuration
 * loaded from brands.yaml at build time.
 */

export interface BrandCompany {
  legal_name: string;
  address: string;
  city: string;
}

export interface BrandBranding {
  logo_light: string;
  logo_dark: string;
  favicon: string;
  primary_color: string;
  gradient_product: string;
  gradient_ai: string;
}

export interface BrandSocial {
  twitter: string;
  linkedin: string;
  instagram: string;
}

export interface BrandMeta {
  title: string;
  description: string;
  extended_description?: string;
  keywords: string;
  og_image: string;
}

export interface BrandHero {
  title: string;
  lead: string;
  cta_primary: string;
  cta_secondary: string;
  cta_secondary_url: string;
}

export interface BrandFeature {
  title: string;
  text: string;
  videoUrl: string;
  placeholderImg: string;
}

export interface BrandFAQ {
  q: string;
  a: string;
}

export interface BrandGetStartedFeature {
  icon: string;
  title: string;
  text: string;
}

export interface BrandMCPConfig {
  ide: string;
  ide_name: string;
  logo_path: string;
  logo_width: string;
  prerequisites: string[];
  setup_instructions: string;
  code: string;
}

export interface BrandGetStarted {
  title: string;
  link_text: string;
  link_url: string;
  features: BrandGetStartedFeature[];
  mcp_setup_title: string;
  mcp_configs: BrandMCPConfig[];
}

export interface BrandLanding {
  meta: BrandMeta;
  hero: BrandHero;
  features: BrandFeature[];
  faqs: BrandFAQ[];
  get_started: BrandGetStarted;
}

// Runtime config - minimal metadata injected into window.BRAND_CONFIG
export interface BrandRuntimeConfig {
  name: string;
  domain: string;
  company: BrandCompany;
  branding: BrandBranding;
  social: BrandSocial;
}

// Full config - used at build time only (includes landing content)
export interface BrandConfig extends BrandRuntimeConfig {
  landing: BrandLanding;
}

export interface BrandsConfig {
  brands: {
    [key: string]: BrandConfig;
  };
}

/**
 * Get the current brand configuration
 *
 * This function retrieves the brand config that was injected into
 * window.BRAND_CONFIG by the Vite plugin at build time.
 *
 * @returns The current brand configuration
 * @throws Error if BRAND_CONFIG is not defined
 */
export function getBrandConfig(): BrandRuntimeConfig {
  if (typeof window === 'undefined') {
    throw new Error('getBrandConfig() can only be called in the browser');
  }

  const config = (window as any).BRAND_CONFIG as BrandRuntimeConfig | undefined;

  if (!config) {
    throw new Error(
      'BRAND_CONFIG not found on window. Make sure the Vite brand plugin is configured correctly.'
    );
  }

  return config;
}

/**
 * Check if BRAND_CONFIG is available
 *
 * Useful for defensive programming when the config might not be loaded yet.
 *
 * @returns true if BRAND_CONFIG is available
 */
export function hasBrandConfig(): boolean {
  return typeof window !== 'undefined' && !!(window as any).BRAND_CONFIG;
}
