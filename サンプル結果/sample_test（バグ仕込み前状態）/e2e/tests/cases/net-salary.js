// TD-007(テストデータ/手取り.json): LTC-033〜LTC-037
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { requireAges, ages, monthsOfAges } = require('../lib/checks');
const { runWith } = require('../lib/steps');

const FILE = '手取り.json';

/** 30歳1月〜12月の給与の額の合計(給与の行が無い月があれば、判定できないので止める) */
function salarySumAt30(result) {
  requireAges(result, [30]);
  const months = result.ofAge(30);
  const missing = months.filter((m) => m.salary === null).map((m) => m.label);
  expect(missing, `${result.label}: 30歳の各月に給与の行がある`).toEqual([]);
  return months.reduce((s, m) => s + m.salary, 0);
}

module.exports = [
  defineCase(FILE, 'LTC-033', async (env, data) => {
    const result = await runWith(env, data);
    // 期待値の範囲: 30歳1月〜64歳12月(退職年齢は初期値の65歳。ローレベルテストケースの期待値)
    const [from, to] = [30, 64];
    requireAges(result, ages(from, to));
    const violations = monthsOfAges(result, from, to).filter((m) => m.salary !== 0).map((m) => `${m.label}: 給与 ${m.salary}`);
    expect(violations, `${from}歳1月〜${to}歳12月のすべての月で、給与の額が ¥0`).toEqual([]);
  }),

  ...['LTC-034', 'LTC-035', 'LTC-036'].map((id) => defineCase(FILE, id, async (env, data) => {
    const result = await runWith(env, data);
    const limit = data.判定に使う値['上限(円)'];
    expect(salarySumAt30(result), `30歳1月〜12月の給与の額の合計が ${limit}円(年収 + 12円)以下`).toBeLessThanOrEqual(limit);
  })),

  defineCase(FILE, 'LTC-037', async (env, data) => {
    const { 年収の並び: salaries } = data.判定に使う値;
    const tol = data.判定に使う値['許す差(円)'];
    const sums = [];
    for (const salary of salaries) {
      // 年収ごとに画面を開き直して「開始」
      const result = await runWith(env, data, { conditions: { salary }, label: `年収${salary}` });
      sums.push(salarySumAt30(result));
      await result.screen.close();
    }
    const violations = [];
    for (let i = 1; i < salaries.length; i++) {
      if (!(sums[i] >= sums[i - 1] - tol)) violations.push(`年収 ${salaries[i - 1]} → ${salaries[i]}: 30歳の給与の合計 ${sums[i - 1]} → ${sums[i]}`);
    }
    expect(violations, `隣り合う年収の組(${salaries.length - 1}組)すべてで、大きい方の合計が小さい方の合計 − ${tol}円 以上`).toEqual([]);
  }, { timeout: 10 * 60 * 1000 }),
];
