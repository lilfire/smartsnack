import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    root: 'static/js',
    globals: true,
    coverage: {
      provider: 'istanbul',
      exclude: ['coverage/**', '__tests__/**', '**/static/js/static/**'],
    },
  },
});
