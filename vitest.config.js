import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    root: 'static/js',
    globals: true,
    pool: 'forks',
    poolOptions: {
      forks: {
        maxForks: 2,
        execArgv: ['--max-old-space-size=4096', '--max-semi-space-size=64'],
      },
    },
    coverage: {
      provider: 'istanbul',
      exclude: ['coverage/**', '__tests__/**', '**/static/js/static/**'],
    },
  },
});
