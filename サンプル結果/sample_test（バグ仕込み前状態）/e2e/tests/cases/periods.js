// TD-006(テストデータ/期間.json): LTC-020〜LTC-032
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { requireAges, requireMonth, requireNoDrawdownPremise, ages, previousBalance, near } = require('../lib/checks');
const { runWith, expectOnlyIncome } = require('../lib/steps');

const FILE = '期間.json';

/** 収入の種類の並びを、続いた月のかたまりごとにまとめる(各月の収入の行は1つでなければならない) */
function incomeRuns(result) {
  const runs = [];
  const unclear = [];
  for (const m of result.months) {
    if (m.incomeType === null) {
      unclear.push(`${m.label}: 収入の行が1つに決まらない(${m.incomes.map((i) => i.type).join('・') || 'なし'})`);
      continue;
    }
    if (runs[runs.length - 1] !== m.incomeType) runs.push(m.incomeType);
  }
  return { runs, unclear };
}

/** 期間ごとの (収入の種類, 生活費) の組(項目を別々の額に。入れた値から) */
function periodPairs(c) {
  return { 給与: c.expenseCurrent, 退職後収入: c.expenseGap, 年金: c.expenseRetired };
}

/** すべての月で収入が type だけ、生活費が expense(LTC-022・LTC-024) */
function expectAllMonthsOnly(result, type, expense) {
  const violations = [];
  for (const m of result.months) {
    const kinds = m.incomes.map((i) => i.type);
    if (kinds.length === 0 || kinds.some((k) => k !== type)) violations.push(`${m.label}: 収入の行が ${kinds.join('・') || 'なし'}`);
    if (m.expense !== expense) violations.push(`${m.label}: 生活費 ${m.expense}`);
  }
  expect(result.months.length, '結果に月がある').toBeGreaterThan(0);
  expect(violations, `すべての月で、収入の行が${type}、生活費が ${expense}(ほかの収入の行が一度も出ない)`).toEqual([]);
}

function monthsWithIncome(result, type) {
  return result.months.filter((m) => m.incomes.some((i) => i.type === type)).map((m) => m.label);
}

module.exports = [
  defineCase(FILE, 'LTC-020', async (env, data) => {
    const result = await runWith(env, data);
    const first = requireMonth(result, 30, 1);
    expect(result.months[0].label, '最初の月が 30歳1月').toBe('30歳1月');
    expect(first.cash, `最初の月(30歳1月)の現金が ¥${data.条件.initialCash.toLocaleString('en-US')}`).toBe(data.条件.initialCash);
    expect(first.invest, `最初の月(30歳1月)の投資が ¥${data.条件.initialInv.toLocaleString('en-US')}`).toBe(data.条件.initialInv);
  }),

  defineCase(FILE, 'LTC-021', async (env, data) => {
    const result = await runWith(env, data);
    const [from, to] = data.判定に使う値.退職後の年齢;
    requireAges(result, ages(from, to));
    expectOnlyIncome(result, ages(from, to), '退職後収入', data.条件.expenseGap,
      `${from}歳1月〜${to}歳12月のすべての月で、収入の行が退職後収入、生活費が ${data.条件.expenseGap}`);
    expect(monthsWithIncome(result, '給与'), '結果のどの月にも給与の行が無い').toEqual([]);
  }),

  defineCase(FILE, 'LTC-022', async (env, data) => {
    const result = await runWith(env, data);
    expectAllMonthsOnly(result, '年金', data.条件.expenseRetired);
  }),

  defineCase(FILE, 'LTC-023', async (env, data) => {
    const result = await runWith(env, data);
    const [from, to] = data.判定に使う値.退職後の年齢;
    requireAges(result, ages(from, to));
    expectOnlyIncome(result, ages(from, to), '退職後収入', data.条件.expenseGap,
      `${from}歳1月〜${to}歳12月のすべての月で、収入の行が退職後収入、生活費が ${data.条件.expenseGap}`);
    expect(monthsWithIncome(result, '給与'), '結果のどの月にも給与の行が無い').toEqual([]);
  }),

  defineCase(FILE, 'LTC-024', async (env, data) => {
    const result = await runWith(env, data);
    expectAllMonthsOnly(result, '年金', data.条件.expenseRetired);
  }),

  defineCase(FILE, 'LTC-025', async (env, data) => {
    const result = await runWith(env, data);
    const c = data.条件;
    const v = data.判定に使う値;
    requireNoDrawdownPremise(result);
    requireAges(result, [v.現役の年齢, v.退職後の年齢, v.年金の年齢]);
    // (1)
    expectOnlyIncome(result, [v.現役の年齢], '給与', c.expenseCurrent, `(1) ${v.現役の年齢}歳のすべての月は 給与・${c.expenseCurrent}`);
    expectOnlyIncome(result, [v.退職後の年齢], '退職後収入', c.expenseGap, `(1) ${v.退職後の年齢}歳のすべての月は 退職後収入・${c.expenseGap}`);
    expectOnlyIncome(result, [v.年金の年齢], '年金', c.expenseRetired, `(1) ${v.年金の年齢}歳のすべての月は 年金・${c.expenseRetired}`);
    // (2)
    const pairs = periodPairs(c);
    const pairViolations = result.months
      .filter((m) => !v.除く年齢.includes(m.age))
      .filter((m) => !(m.incomeType && pairs[m.incomeType] === m.expense))
      .map((m) => `${m.label}: (${m.incomes.map((i) => i.type).join('・') || 'なし'}, ${m.expense})`);
    expect(pairViolations, `(2) ${v.除く年齢.join('歳と')}歳を除くすべての月で、(収入の種類, 生活費) が (給与, ${c.expenseCurrent})・(退職後収入, ${c.expenseGap})・(年金, ${c.expenseRetired}) のどれか`).toEqual([]);
    // (3)
    const tol = v['許す差(円)'];
    const flow = [];
    for (const m of result.months) {
      const p = previousBalance(result, m);
      const income = m.incomeAmount;
      const expected = income - m.expense - (m.invest - p.invest);
      if (income === null || !near(m.cash - p.cash, expected, tol)) {
        flow.push(`${m.label}: 現金の増えた分 ${m.cash - p.cash}、収入 ${income} − 生活費 ${m.expense} − 投資の増えた分 ${m.invest - p.invest} = ${expected}`);
      }
    }
    expect(flow, `(3) すべての月で、現金の増えた分が 収入 − 生活費 − 投資の増えた分 と${tol}円以内で合う`).toEqual([]);
  }),

  defineCase(FILE, 'LTC-026', async (env, data) => {
    const result = await runWith(env, data);
    const c = data.条件;
    const v = data.判定に使う値;
    requireAges(result, [...v.現役, ...v.退職後, ...v.年金]);
    expectOnlyIncome(result, v.現役, '給与', c.expenseCurrent, `${v.現役.join('歳・')}歳のすべての月は 給与・${c.expenseCurrent}`);
    expectOnlyIncome(result, v.退職後, '退職後収入', c.expenseGap, `${v.退職後.join('歳・')}歳のすべての月は 退職後収入・${c.expenseGap}`);
    expectOnlyIncome(result, v.年金, '年金', c.expenseRetired, `${v.年金.join('歳・')}歳のすべての月は 年金・${c.expenseRetired}`);
  }),

  ...['LTC-027', 'LTC-028'].map((id) => defineCase(FILE, id, async (env, data) => {
    const result = await runWith(env, data);
    const { runs, unclear } = incomeRuns(result);
    expect(unclear, 'どの月も収入の行が1つ').toEqual([]);
    expect(runs, '最初の月から最後の月まで、収入の種類が 給与 → 退職後収入 → 年金 の順に、それぞれ1つのかたまりとして出る').toEqual(['給与', '退職後収入', '年金']);
  })),

  defineCase(FILE, 'LTC-029', async (env, data) => {
    const result = await runWith(env, data);
    const { runs, unclear } = incomeRuns(result);
    expect(unclear, 'どの月も収入の行が1つ').toEqual([]);
    expect(runs, '(1) 収入の種類が 給与 → 年金 の順に進み、前の種類に戻らない').toEqual(['給与', '年金']);
    expect(monthsWithIncome(result, '退職後収入'), '(2) どの月にも退職後収入の行が無い').toEqual([]);
    const gapExpense = result.months.filter((m) => m.expense === data.条件.expenseGap).map((m) => m.label);
    expect(gapExpense, `(2) 生活費が ${data.条件.expenseGap} の月が無い`).toEqual([]);
  }),

  ...['LTC-030', 'LTC-031'].map((id) => defineCase(FILE, id, async (env, data) => {
    const result = await runWith(env, data);
    const c = data.条件;
    const v = data.判定に使う値;
    requireAges(result, [...v.現役だけ, ...v.年金だけ]);
    expectOnlyIncome(result, v.現役だけ, '給与', c.expenseCurrent, `${v.現役だけ.join('歳・')}歳のすべての月で、収入の行が給与だけで生活費が ${c.expenseCurrent}`);
    expectOnlyIncome(result, v.年金だけ, '年金', c.expenseRetired, `${v.年金だけ.join('歳・')}歳のすべての月で、収入の行が年金だけで生活費が ${c.expenseRetired}`);
  })),

  defineCase(FILE, 'LTC-032', async (env, data) => {
    const result = await runWith(env, data);
    const v = data.判定に使う値;
    const violations = [];
    for (const [a, b] of v.組) {
      const ma = requireMonth(result, a, v.比べる月);
      const mb = requireMonth(result, b, v.比べる月);
      if (ma.incomeAmount === null || ma.incomeAmount !== mb.incomeAmount) violations.push(`${ma.label} と ${mb.label}: 収入の額 ${ma.incomeAmount} と ${mb.incomeAmount}`);
      if (ma.expense !== mb.expense) violations.push(`${ma.label} と ${mb.label}: 生活費 ${ma.expense} と ${mb.expense}`);
    }
    expect(violations, `${v.比べる月}月どうしで比べて、組 ${JSON.stringify(v.組)} の収入の額と生活費の額が一致する`).toEqual([]);
  }),
];
