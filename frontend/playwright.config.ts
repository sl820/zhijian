import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/playwright',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    viewport: { width: 1280, height: 720 },
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
    trace: 'off',
    video: 'off',
  },
  webServer: {
    command: 'npx vite --port 5173 --host 127.0.0.1',
    url: 'http://127.0.0.1:5173/zhijian-v2/',
    timeout: 60_000,
    reuseExistingServer: true,
    stdout: 'pipe',
    stderr: 'pipe',
  },
})
