import { defineConfig } from 'vite';
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';
import { brandPlugin } from './vite-plugin-brand';

// Get brand from environment variable, default to 'preloop'
const brand = process.env.VITE_BRAND || 'preloop';

/**
 * Default Vite configuration for Preloop Open Source / Self-Hosted edition
 *
 * This build:
 * - Redirects landing page to login (no marketing content)
 * - Removes pricing page
 * - Uses minimal branding configuration
 *
 * For SaaS builds, set VITE_BRAND environment variable
 */
export default defineConfig({
  base: '/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: 'index.html',
      },
    },
  },
  plugins: [
    cssInjectedByJsPlugin({
      jsAssetsFilterFunction: (chunk) => {
        return /main/.test(chunk.fileName);
      },
    }),
    brandPlugin(brand),
  ],
  resolve: {
    alias: {
      events: 'events',
    },
  },
  server: {
    hmr: {
      clientPort: 5173,
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
      '/admin': {
        target: 'http://127.0.0.1:5175',
        changeOrigin: true,
        ws: true,
      },
      '/docs': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
