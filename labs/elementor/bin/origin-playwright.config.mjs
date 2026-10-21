import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: '.',
  testMatch: '**/origin-contract.spec.mjs',
  workers: 1,
  retries: 0,
  timeout: 15000,
  reporter: [['list']],
  outputDir: '../artifacts/origin-contract-test-results'
});
