// E2E自動テストの設定。テスト対象は http://localhost:8000/retirement_simulator.html(すでに配信中のものを使う。webServer では立てない)と
// file:///D:/codes/sample_test/retirement_simulator.html。Chrome・Edge はインストール済みのものを channel で使う。
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.js',
  // 証跡の出力先は、この設定ファイルのあるフォルダの中に決める。Playwright は実行のたびにこの中を消す
  outputDir: './test-results',
  reporter: [['list'], ['json', { outputFile: 'test-results/playwright-report.json' }]],
  timeout: 5 * 60 * 1000,
  expect: { timeout: 5 * 1000 },
  retries: 0,
  fullyParallel: true,
  // 配信は Python の http.server 1つ(接続の待ち行列が小さい)。同時に開きすぎると接続を断られるので、worker の数をしぼる
  workers: 4,
  use: {
    headless: true,
    actionTimeout: 15 * 1000,
    navigationTimeout: 30 * 1000,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      // ローレベルテストケース1件ずつ(LTC-001〜LTC-091、LTC-093〜LTC-095)。インストール済みの Chrome
      name: 'chrome',
      testIgnore: 'browsers/**',
      use: { browserName: 'chromium', channel: 'chrome' },
    },
    {
      // ブラウザの互換性(LTC-096 Chrome → LTC-097 Edge → LTC-098 Playwright の Firefox)。書いた順に1つの worker で流す。
      // ブラウザはテストの中で起動する(Chrome・Edge は channel、Firefox は Playwright の Firefox)
      name: 'browser-compat',
      testMatch: 'browsers/**/*.spec.js',
      fullyParallel: false,
      // 1つのテストで多くの画面を開くので、設定の screenshot は使わず、失敗したテストケースの画面だけを自分で撮る(lib/env.js)
      use: { screenshot: 'off' },
    },
  ],
});
