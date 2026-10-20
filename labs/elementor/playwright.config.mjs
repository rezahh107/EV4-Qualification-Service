import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.mjs',
  workers: 1,
  retries: 0,
  timeout: 90000,
  expect: { timeout: 15000 },
  use: { baseURL: process.env.LAB_BASE_URL || 'http://localhost:8888',
    browserName: 'chromium', headless: true,
    screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  reporter: [['list'], ['json', {outputFile: './artifacts/playwright.json'}],
    ['html', {outputFolder: './artifacts/html', open: 'never'}]],
  outputDir: './artifacts/test-results',
});
