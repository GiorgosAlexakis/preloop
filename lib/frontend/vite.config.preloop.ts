import { defineConfig } from 'vite';
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';
import { brandPlugin } from './vite-plugin-brand';

/**
 * Vite configuration for Preloop brand
 */
export default defineConfig({
  base: '/',
  build: {
    outDir: 'dist-preloop',
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
        // Only inject CSS into the main chunk, not the HTML files
        return /main/.test(chunk.fileName);
      },
    }),
    brandPlugin('preloop'),
  ],
  resolve: {
    alias: {
      events: 'events',
    },
  },
  server: {
    port: 5174,
    hmr: {
      clientPort: 5174,
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
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
