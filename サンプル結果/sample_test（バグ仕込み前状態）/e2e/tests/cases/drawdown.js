// TD-009(テストデータ/取り崩しと総資産.json): LTC-048〜LTC-059、LTC-089
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { block, requireMonth, previousBalance, near } = require('../lib/checks');
const { runWith } = require('../lib/steps');

const FILE = '取り崩しと総資産.json';

/** 「30歳3月」→ [30, 3] */
function parseMonthLabel(label) {
  const r = label.match(/^(\d+)歳(\d+)月$/);
  if (!r) throw new Error(`月の書き方がわからない: ${label}`);
  return [Number(r[1]), Number(r[2])];
}

/** (3) 指定した月より後で、投資が前の月より減り、なお0円より大きい月は、どの月も現金が0円以上 */
function expectCashAfterDraw(result, after) {
  const start = result.months.indexOf(after) + 1;
  const violations = [];
  for (const m of result.months.slice(start)) {
    const p = result.prev(m);
    if (m.invest < p.invest && m.invest > 0 && !(m.cash >= 0)) violations.push(`${m.label}: 投資 ${p.invest} → ${m.invest}、現金 ${m.cash}`);
  }
  expect(violations, `(3) ${after.label}より後で、投資が前の月より減り、なお0円より大きい月は、どの月も現金が0円以上`).toEqual([]);
}

/** 投資の残高が0未満にならない(LTC-055〜LTC-059) */
async function investNeverNegative(env, data) {
  const result = await runWith(env, data);
  expect(result.months.length, '結果に月がある').toBeGreaterThan(0);
  const violations = result.months.filter((m) => !(m.invest >= 0)).map((m) => `${m.label}: 投資 ${m.invest}`);
  expect(violations, 'すべての月で、投資が0円以上').toEqual([]);
}

module.exports = [
  ...['LTC-048', 'LTC-049', 'LTC-050', 'LTC-051', 'LTC-052'].map((id) => defineCase(FILE, id, async (env, data) => {
    const result = await runWith(env, data);
    // 給与の額が0円であることを確かめてから判定する(ローレベルテストケースの備考)
    const salaried = result.months.filter((m) => m.salary !== null && m.salary !== 0);
    if (salaried.length) block(`給与の額が0円でない月がある(${salaried[0].label}: ${salaried[0].salary})`);
    const v = data.判定に使う値;
    const [age, month] = parseMonthLabel(v.見る月);
    const target = requireMonth(result, age, month);
    const before = result.prev(target);
    if (!before) block(`${v.見る月} の前の月が結果に無い`);
    if (v.不足) {
      expect(target.cash, `(2) ${target.label}の現金が0円以上`).toBeGreaterThanOrEqual(0);
      expect(target.invest, `(2) ${target.label}の投資(${target.invest})が、${before.label}の投資(${before.invest})より少ない`).toBeLessThan(before.invest);
    } else {
      expect(target.invest, `(1) ${target.label}の投資が、${before.label}の投資と同じ額`).toBe(before.invest);
      expect(target.cash, `(1) ${target.label}の現金が0円以上`).toBeGreaterThanOrEqual(0);
    }
    expectCashAfterDraw(result, target);
  })),

  defineCase(FILE, 'LTC-053', async (env, data) => {
    const result = await runWith(env, data);
    // 突発的な支出が表示された月が1つだけで、それが現役期間(退職年齢より前)であることを確かめてから判定する
    const eventMonths = result.months.filter((m) => m.events.length > 0);
    const retirementAge = Number(result.inputs.retirementAge);
    if (eventMonths.length !== 1) block(`突発的な支出が表示された月が1つでない(${eventMonths.length}か月)`);
    const e = eventMonths[0];
    if (!(e.age < retirementAge)) block(`突発的な支出が表示された月(${e.label})が現役期間でない`);
    const p = previousBalance(result, e);
    expect(e.cash, `突発的な支出が表示された月(${e.label})の現金が0円以上`).toBeGreaterThanOrEqual(0);
    expect(e.invest, `${e.label}の投資(${e.invest})が、前の月の投資(${p.invest})より少ない`).toBeLessThan(p.invest);
  }),

  defineCase(FILE, 'LTC-054', async (env, data) => {
    const result = await runWith(env, data);
    const m = requireMonth(result, 30, 1);
    expect(m.cash, '30歳1月の現金が0円以上').toBeGreaterThanOrEqual(0);
    expect(m.invest, `30歳1月の投資が ¥${data.条件.initialInv.toLocaleString('en-US')} より少ない`).toBeLessThan(data.条件.initialInv);
  }),

  ...['LTC-055', 'LTC-056', 'LTC-057', 'LTC-058', 'LTC-059'].map((id) => defineCase(FILE, id, investNeverNegative)),

  defineCase(FILE, 'LTC-089', async (env, data) => {
    const result = await runWith(env, data);
    // 投資が前の月より減った月と減らない月の両方があり、どの月も投資が0円より大きいことを確かめてから判定する
    let decreased = 0;
    let notDecreased = 0;
    for (const m of result.months) {
      const p = previousBalance(result, m);
      if (m.invest < p.invest) decreased += 1;
      else notDecreased += 1;
    }
    const nonPositive = result.months.find((m) => !(m.invest > 0));
    if (!decreased || !notDecreased) block(`投資が減った月(${decreased})と減らない月(${notDecreased})の両方が無い`);
    if (nonPositive) block(`投資が0円より大きくない月がある(${nonPositive.label}: ${nonPositive.invest})`);
    const violations = result.months.filter((m) => !near(m.total, m.cash + m.invest, 1))
      .map((m) => `${m.label}: 総資産 ${m.total}、現金 + 投資 = ${m.cash + m.invest}`);
    expect(violations, 'すべての月で、総資産が 現金 + 投資 と1円以内で合う').toEqual([]);
  }),
];
