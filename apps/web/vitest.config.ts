import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['e2e/**', 'node_modules/**', '.next/**'],
    pool: 'threads',
    minWorkers: 1,
    maxWorkers: 1,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/app/health/route.ts'],
      thresholds: { lines: 90, functions: 90, statements: 90, branches: 85 },
    },
  },
});
