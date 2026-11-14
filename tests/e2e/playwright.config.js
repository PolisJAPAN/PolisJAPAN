// 本番定期テストの設定。テストケースの定義は docs/本番定期テストケース.md。
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './specs',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  // 失敗したケースだけを最大 2 回やり直す（docs/本番定期テストケース.md §7）
  retries: process.env.E2E_RETRIES ? Number(process.env.E2E_RETRIES) : 2,
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  reporter: [['list'], ['json', { outputFile: 'results/results.json' }]],
  outputDir: 'results/artifacts',
  use: {
    browserName: 'chromium',
    channel: process.env.PW_CHANNEL || undefined,
    viewport: { width: 390, height: 844 },
    locale: 'ja-JP',
    timezoneId: 'Asia/Tokyo',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
