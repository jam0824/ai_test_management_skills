// 参考: Playwright の WebKit で、ローレベルテストケース1件ずつのテストを流す(テスト計画の TA-018 の備考)。
// WebKit は Safari そのものではないので、SPEC-061(Safari)を確かめたことにはしない。テスト結果(e2e-results)には取り込まない。
// 証跡とJSONは、ふだんの実行(playwright.config.js)と別のフォルダに出す。
const base = require('./playwright.config');
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  ...base,
  outputDir: './test-results-webkit',
  reporter: [['list'], ['json', { outputFile: 'test-results-webkit/playwright-report.json' }]],
  projects: [
    {
      name: 'webkit-reference',
      testIgnore: 'browsers/**',
      use: { browserName: 'webkit' },
    },
  ],
});
