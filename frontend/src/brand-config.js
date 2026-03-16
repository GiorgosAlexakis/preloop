/**
 * Brand configuration interfaces
 *
 * These interfaces define the structure of brand-specific configuration
 * loaded from brands.yaml at build time.
 */
/**
 * Get the current brand configuration
 *
 * This function retrieves the brand config that was injected into
 * window.BRAND_CONFIG by the Vite plugin at build time.
 *
 * @returns The current brand configuration
 * @throws Error if BRAND_CONFIG is not defined
 */
export function getBrandConfig() {
    if (typeof window === 'undefined') {
        throw new Error('getBrandConfig() can only be called in the browser');
    }
    const config = window.BRAND_CONFIG;
    if (!config) {
        throw new Error('BRAND_CONFIG not found on window. Make sure the Vite brand plugin is configured correctly.');
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
export function hasBrandConfig() {
    return typeof window !== 'undefined' && !!window.BRAND_CONFIG;
}
/**
 * Check if the current brand is self-hosted edition
 * Self-hosted editions have minimal landing pages and no pricing
 */
export function isSelfHosted() {
    try {
        return getBrandConfig().edition === 'selfhosted';
    }
    catch {
        return false;
    }
}
/**
 * Check if the current brand is SaaS edition
 * SaaS editions have full marketing landing pages and pricing
 */
export function isSaaS() {
    try {
        return getBrandConfig().edition === 'saas';
    }
    catch {
        return true; // Default to SaaS behavior
    }
}
