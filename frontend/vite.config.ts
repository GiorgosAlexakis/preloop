import { defineConfig, Plugin } from 'vite';
import { resolve } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';
import cssInjectedByJsPlugin from 'vite-plugin-css-injected-by-js';
import { brandPlugin } from './vite-plugin-brand';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

/**
 * Plugin to handle optional EE plugin imports.
 * In OSS builds where the plugins directory doesn't exist,
 * this resolves EE plugin imports to an empty module.
 */
function optionalEePlugins(): Plugin {
  const eePluginsPath = resolve(__dirname, '../../plugins/frontend/ee-plugins.ts');
  const eePluginsExist = existsSync(eePluginsPath);

  return {
    name: 'optional-ee-plugins',
    enforce: 'pre', // Run before other plugins and default resolution
    resolveId(source) {
      // Check if this is the EE plugins import (handles both relative and absolute paths)
      if (source.includes('ee-plugins') && source.includes('plugins')) {
        if (eePluginsExist) {
          // EE build - resolve to actual file
          return eePluginsPath;
        } else {
          // OSS build - resolve to virtual empty module
          return '\0virtual:ee-plugins-stub';
        }
      }
      return null;
    },
    load(id) {
      if (id === '\0virtual:ee-plugins-stub') {
        // Return empty module for OSS builds
        return '// EE plugins not available in open source build\nexport {};';
      }
      return null;
    },
  };
}

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
    optionalEePlugins(),
    cssInjectedByJsPlugin({
      jsAssetsFilterFunction: (chunk) => {
        return /main/.test(chunk.fileName);
      },
    }),
    brandPlugin(brand),
  ],
  resolve: {
    alias: [
      { find: 'events', replacement: 'events' },
      // Ensure packages resolve from frontend's node_modules for plugins outside this package
      { find: /^lit($|\/)/, replacement: resolve(__dirname, 'node_modules/lit$1') },
      {
        find: /^@shoelace-style\/shoelace(\/.*)?$/,
        replacement: resolve(__dirname, 'node_modules/@shoelace-style/shoelace$1'),
      },
      {
        find: /^@lit\/reactive-element(\/.*)?$/,
        replacement: resolve(__dirname, 'node_modules/@lit/reactive-element$1'),
      },
    ],
    // Dedupe ensures only one copy of these packages is used
    dedupe: ['lit', '@lit/reactive-element', 'lit-element', 'lit-html', '@shoelace-style/shoelace'],
  },
  optimizeDeps: {
    include: ['lit', 'lit/decorators.js'],
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
      '/mcp': {
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
