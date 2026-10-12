import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e', timeout: 60000, expect: { timeout: 20000 },
  fullyParallel: false, workers: 1, retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:5174', viewport: { width: 1360, height: 1000 }, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: [
    { command: 'cd ../backend && uv run python ../frontend/e2e/serve_backend.py', url: 'http://127.0.0.1:8011/api/v1/health/db', timeout: 60000, reuseExistingServer: false, gracefulShutdown: { signal: 'SIGTERM', timeout: 15000 } },
    { command: 'npm run dev -- --mode e2e --port 5174', url: 'http://127.0.0.1:5174', timeout: 30000, reuseExistingServer: false },
  ],
})
