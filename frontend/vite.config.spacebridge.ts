import { defineConfig } from 'vite';
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';
import { brandPlugin } from './vite-plugin-brand';

/**
 * Vite configuration for SpaceBridge brand
 */
export default defineConfig({
  base: '/',
  build: {
    outDir: 'dist-spacebridge',
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
    brandPlugin('spacebridge'),
  ],
  resolve: {
    alias: {
      events: 'events',
    },
  },
  server: {
    port: 5173,
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
        target: 'http://localhost:5175',
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
