import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
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
      include: [
        'src/components/auth-form.tsx',
        'src/components/ai-builder-project.tsx',
        'src/components/turnstile-widget.tsx',
        'src/components/portal-shell.tsx',
        'src/components/portal-pages.tsx',
        'src/components/route-states.tsx',
        '../../packages/ui/src/index.tsx',
        'src/lib/api.ts',
        'src/proxy.ts',
      ],
      exclude: ['src/app/health/route.ts'],
      thresholds: { lines: 90, functions: 90, statements: 90, branches: 85 },
    },
  },
});
