import { playwrightLauncher } from '@web/test-runner-playwright';
import { esbuildPlugin } from '@web/dev-server-esbuild';

export default {
  plugins: [esbuildPlugin({ ts: true, tsconfig: './tsconfig.json', target: 'es2020' })],
  browsers: [playwrightLauncher({ product: 'chromium' })],
  testFramework: {
    config: {
      timeout: '240000',
    },
  },
};