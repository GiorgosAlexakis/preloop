import { playwrightLauncher } from '@web/test-runner-playwright';
import { esbuildPlugin } from '@web/dev-server-esbuild';

// Run headless in CI, headed for local development
const isCI = process.env.CI === 'true';

export default {
  plugins: [esbuildPlugin({ ts: true, tsconfig: './tsconfig.json', target: 'es2020' })],
  browsers: [playwrightLauncher({
    product: 'chromium',
    launchOptions: { headless: isCI }
  })],
  testFramework: {
    config: {
      timeout: '240000',
    },
  },
  nodeResolve: true,
};
