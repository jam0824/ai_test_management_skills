// TD-004(テストデータ/ありえない値.json): LTC-009〜LTC-013
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { settings } = require('../lib/data');

const FILE = 'ありえない値.json';

/**
 * ありえない値を入れて「開始」→ その項目を初期値(TD-001 の README の初期値)に戻して「開始」。
 * 2回目の結果を、比較用の実行(画面を開き直し、初期値のまま1回「開始」)と比べる。1回目の結果は判定しない。
 */
async function invalidThenRestore(env, data) {
  const defaults = settings().READMEの初期値;
  const screen = await env.open({ random: data.乱数, label: 'ありえない値を入れる画面' });
  await screen.setConditions(data.条件);
  await screen.start({ label: '1回目(判定しない)' });
  const restore = {};
  for (const id of Object.keys(data.条件)) {
    if (!(id in defaults)) throw new Error(`TD-001 に ${id} の初期値が無い`);
    restore[id] = defaults[id];
  }
  await screen.setConditions(restore);
  const second = await screen.start({ label: '2回目' });
  const comparisonScreen = await env.open({ random: data.乱数, label: '比較用の実行' });
  await comparisonScreen.setConditions(data.比較用の実行[0].条件);
  const comparison = await comparisonScreen.start();
  expect(second.text, '2回目の結果の欄の内容が、比較用の実行(画面を開き直し、初期値のまま1回「開始」)と一致する').toBe(comparison.text);
}

module.exports = [
  defineCase(FILE, 'LTC-009', invalidThenRestore),
  defineCase(FILE, 'LTC-010', invalidThenRestore),
  defineCase(FILE, 'LTC-011', invalidThenRestore),
  defineCase(FILE, 'LTC-012', invalidThenRestore),
  defineCase(FILE, 'LTC-013', invalidThenRestore),
];
