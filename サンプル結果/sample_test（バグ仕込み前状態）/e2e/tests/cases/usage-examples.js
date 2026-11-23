// TD-005(テストデータ/使用例.json): LTC-015〜LTC-019
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { settings } = require('../lib/data');
const { requireAges, ages, previousBalance, near } = require('../lib/checks');
const { runWith, runComparison, expectOnlyIncome } = require('../lib/steps');

const FILE = '使用例.json';
const ORDER = ['給与', '退職後収入', '年金'];

/** LTC-015 の (1)〜(5): 結果が計算の性質を満たす */
function checkProperties(result) {
  expect(result.months.length, '(1) 結果の欄に月ごとの結果が出る').toBeGreaterThan(0);

  const order = [];
  let last = -1;
  for (const m of result.months) {
    const index = ORDER.indexOf(m.incomeType);
    if (index < 0) order.push(`${m.label}: 収入の行が1つに決まらない(${m.incomes.map((i) => i.type).join('・') || 'なし'})`);
    else if (index < last) order.push(`${m.label}: ${ORDER[last]} の後に ${m.incomeType} に戻った`);
    else last = index;
  }
  expect(order, '(2) 収入の種類が 給与 → 退職後収入 → 年金 の順に進み、前の種類に戻らない').toEqual([]);

  const total = result.months.filter((m) => !near(m.total, m.cash + m.invest, 1))
    .map((m) => `${m.label}: 総資産 ${m.total}、現金 + 投資 = ${m.cash + m.invest}`);
  expect(total, '(3) どの月も、総資産が 現金 + 投資 と1円以内で合う').toEqual([]);

  const negative = result.months.filter((m) => !(m.invest >= 0)).map((m) => `${m.label}: 投資 ${m.invest}`);
  expect(negative, '(4) どの月も投資が0円以上').toEqual([]);

  const cash = [];
  for (const m of result.months) {
    const prev = previousBalance(result, m);
    if (m.invest < prev.invest && m.invest > 0 && !(m.cash >= 0)) cash.push(`${m.label}: 投資 ${prev.invest} → ${m.invest}、現金 ${m.cash}`);
  }
  expect(cash, '(5) 投資が前の月より減り、まだ0円より大きい月は、現金が0円以上').toEqual([]);
}

module.exports = [
  defineCase(FILE, 'LTC-015', async (env, data) => {
    checkProperties(await runWith(env, data));
  }),

  defineCase(FILE, 'LTC-016', async (env, data) => {
    // 操作: 条件を入れ、給与変更設定を表示して2つ追加し、年齢と年収を入れて「開始」
    checkProperties(await runWith(env, data));
  }),

  defineCase(FILE, 'LTC-017', async (env, data) => {
    checkProperties(await runWith(env, data));
  }),

  defineCase(FILE, 'LTC-018', async (env, data) => {
    const main = await runWith(env, data, { label: 'LTC-016 と同じ条件' });
    const [cmpA, cmpB] = data.比較用の実行;
    const a = await runComparison(env, data, cmpA, '比較用の実行A');
    const b = await runComparison(env, data, cmpB, '比較用の実行B');
    const [from, to] = data.判定に使う値.見る年齢;
    for (const r of [main, a, b]) requireAges(r, ages(from, to));
    const violations = [];
    for (const m of main.months.filter((x) => x.age >= from && x.age <= to)) {
      const ma = a.at(m.age, m.month);
      const mb = b.at(m.age, m.month);
      if (m.salary === null || m.salary !== ma.salary) violations.push(`${m.label}: 給与 ${m.salary}、比較用の実行A ${ma.salary}`);
      if (m.salary === mb.salary) violations.push(`${m.label}: 給与 ${m.salary} が比較用の実行B ${mb.salary} と同じ`);
      if (ma.salary === mb.salary) violations.push(`${m.label}: 比較用の実行AとBの給与がどちらも ${ma.salary}`);
    }
    expect(violations, `${from}歳1月〜${to}歳12月の給与の額が、比較用の実行Aと同じで、比較用の実行Bと違う(AとBも違う)`).toEqual([]);
  }),

  defineCase(FILE, 'LTC-019', async (env, data) => {
    const result = await runWith(env, data);
    const { 現役だけの年齢: working, 年金だけの年齢: pension } = data.判定に使う値;
    requireAges(result, [...working, ...pension]);
    expect(result.months.length, '(1) 結果の欄に月ごとの結果が出る').toBeGreaterThan(0);
    // 現役時生活費は入れていない(初期値のまま)。期待値どおり、「開始」のときに画面の欄にあった値と比べる
    const expenseCurrent = Number(result.inputs.expenseCurrent);
    expectOnlyIncome(result, working, '給与', expenseCurrent,
      `(2) ${working.join('歳・')}歳のすべての月で、収入の行が給与だけで、生活費が現役時生活費の欄の値(${expenseCurrent})`);
    const expenseRetired = settings().READMEの初期値.expenseRetired; // 老後生活費の初期値(TD-001)
    expectOnlyIncome(result, pension, '年金', expenseRetired,
      `(3) ${pension.join('歳・')}歳のすべての月で、収入の行が年金だけで、生活費が ${expenseRetired}`);
  }),
];
