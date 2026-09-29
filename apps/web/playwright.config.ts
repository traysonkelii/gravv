import { defineConfig, devices } from '@playwright/test'

/* Runs against the local stack. Supabase must already be running (make dev starts it); the api and web
   servers are started here unless they are already up. */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: 'bash ../../scripts/e2e-api.sh',
      url: 'http://127.0.0.1:8000/readyz',
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: 'pnpm dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
