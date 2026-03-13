import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    root: 'static/js',
    globals: true,
    pool: 'forks',
    poolOptions: {
      forks: {
        execArgv: ['--max-old-space-size=4096'],
      },
    },
    coverage: {
      provider: 'istanbul',
      exclude: ['coverage/**', '__tests__/**', '**/static/js/static/**'],
    },
  },
});
