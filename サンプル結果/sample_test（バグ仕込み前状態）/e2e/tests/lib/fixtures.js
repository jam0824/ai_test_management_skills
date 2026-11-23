// テストの登録のしかた。ローレベルテストケース1件をテスト1件にし、テスト名の先頭にidを付ける。
const base = require('@playwright/test');
const { Env } = require('./env');
const { caseData } = require('./data');

const test = base.test.extend({
  /** 画面を開くための道具。テストが終わったらコンテキストを閉じ、失敗していれば証跡を添付する */
  env: async ({ browser }, use, testInfo) => {
    const env = new Env(browser, testInfo);
    await use(env);
    await env.dispose(testInfo.status !== testInfo.expectedStatus);
  },
});

/**
 * テストケースを1件定義する。テスト名は `<id> <テストデータのテストケース名>`。
 * @param {string} file テストデータのファイル名(テストデータIDの列のもの)
 * @param {string} id ローレベルテストケースID
 * @param {(env: Env, data: object) => Promise<void>} run
 * @param {{ timeout?: number }} [options]
 */
function defineCase(file, id, run, options = {}) {
  const data = caseData(file, id);
  return { id, file, title: `${id} ${data.テストケース}`, timeout: options.timeout, run: (env) => run(env, data) };
}

module.exports = { test, expect: base.expect, defineCase };
