// TD-008(テストデータ/投資と利回り.json): LTC-038〜LTC-047
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { requireAges, requireMonth, requireNoDrawdownPremise, ages, monthsOfAges, previousBalance, near } = require('../lib/checks');
const { runWith, runComparison } = require('../lib/steps');

const FILE = '投資と利回り.json';

/** 30歳12月の投資が、30歳1月〜12月の給与の額の合計 × 投資率 と12円以内で合う */
function expectYearInvest(result, rate, what) {
  requireAges(result, [30]);
  const months = result.ofAge(30);
  const missing = months.filter((m) => m.salary === null).map((m) => m.label);
  expect(missing, '30歳の各月に給与の行がある').toEqual([]);
  const sum = months.reduce((s, m) => s + m.salary, 0);
  const dec = result.at(30, 12);
  expect(Math.abs(dec.invest - sum * rate), `${what}: 30歳12月の投資 ${dec.invest}、給与の合計 ${sum} × ${rate} = ${sum * rate}`).toBeLessThanOrEqual(12);
}

/** 比べる月の投資の、年齢 from→from+1 … (to-1)→to の比 */
function yearRatios(result, month, from, to, valueOf = (age) => requireMonth(result, age, month).invest) {
  const ratios = [];
  for (let a = from; a < to; a++) ratios.push({ from: a, to: a + 1, ratio: valueOf(a + 1) / valueOf(a) });
  return ratios;
}

function expectRatiosConstant(ratios, tol, what) {
  const violations = [];
  for (const r of ratios) if (!(r.ratio > 1)) violations.push(`${r.from}歳→${r.to}歳 の比 ${r.ratio} が1より大きくない`);
  for (let i = 0; i < ratios.length; i++) {
    for (let j = i + 1; j < ratios.length; j++) {
      if (!near(ratios[i].ratio, ratios[j].ratio, tol)) violations.push(`${ratios[i].from}歳→${ratios[i].to}歳 ${ratios[i].ratio} と ${ratios[j].from}歳→${ratios[j].to}歳 ${ratios[j].ratio}`);
    }
  }
  expect(violations, what).toEqual([]);
}

module.exports = [
  defineCase(FILE, 'LTC-038', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    expectYearInvest(result, data.条件.investRate / 100, '(1)');
    // (2) 30歳1月〜64歳12月(退職年齢は初期値の65歳。ローレベルテストケースの期待値)
    const [from, to] = [30, 64];
    requireAges(result, ages(from, to));
    const violations = [];
    for (const m of monthsOfAges(result, from, to)) {
      const p = previousBalance(result, m);
      const left = (m.cash - p.cash) + (m.invest - p.invest);
      if (m.salary === null || !near(left, m.salary - m.expense, 1)) violations.push(`${m.label}: 現金と投資の増えた分 ${left}、給与 ${m.salary} − 生活費 ${m.expense}`);
    }
    expect(violations, `(2) ${from}歳1月〜${to}歳12月の各月で、(現金の増えた分 + 投資の増えた分) が (給与の額 − 生活費の額) と1円以内で合う`).toEqual([]);
  }),

  defineCase(FILE, 'LTC-039', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    requireAges(result, [38, 39, 41, 46]);
    // 見る年齢はローレベルテストケースの期待値(38歳・39歳の12月、41歳・46歳)
    const m38 = result.at(38, 12);
    const m39 = result.at(39, 12);
    expect(m39.invest, `(1) 39歳12月の投資(${m39.invest})が、38歳12月の投資(${m38.invest})より多い`).toBeGreaterThan(m38.invest);
    const violations = [];
    for (const age of [41, 46]) {
      for (const m of result.ofAge(age)) {
        const p = result.prev(m);
        if (!p || m.invest !== p.invest) violations.push(`${m.label}: 投資 ${p && p.invest} → ${m.invest}`);
      }
    }
    expect(violations, '(2) 41歳と46歳のすべての月で、投資が前の月と同じ額').toEqual([]);
  }),

  defineCase(FILE, 'LTC-040', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    const [from, to] = [30, 64]; // ローレベルテストケースの期待値の範囲
    requireAges(result, ages(from, to));
    const violations = monthsOfAges(result, from, to).filter((m) => m.invest !== 0).map((m) => `${m.label}: 投資 ${m.invest}`);
    expect(violations, `${from}歳1月〜${to}歳12月のすべての月で、投資が ¥0`).toEqual([]);
  }),

  ...['LTC-041', 'LTC-042'].map((id) => defineCase(FILE, id, async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    expectYearInvest(result, data.判定に使う値.投資率 / 100, '30歳12月の投資が、30歳の給与の額の合計 × 投資率 と12円以内');
  })),

  defineCase(FILE, 'LTC-043', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    expectYearInvest(result, data.判定に使う値.投資率 / 100, '(1) 30歳12月の投資が、30歳の給与の額の合計と12円以内');
    const violations = [];
    for (const m of result.ofAge(30)) {
      const p = previousBalance(result, m);
      if (!near(p.cash - m.cash, m.expense, 1)) violations.push(`${m.label}: 現金の減り ${p.cash - m.cash}、生活費 ${m.expense}`);
    }
    expect(violations, '(2) 30歳の各月で、前の月からの現金の減りが、表示された生活費の額と1円以内で合う').toEqual([]);
  }),

  defineCase(FILE, 'LTC-044', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    const v = data.判定に使う値;
    const [from, to] = v.年齢;
    const ratios = yearRatios(result, v.比べる月, from, to);
    expectRatiosConstant(ratios, v.許す差, `${v.比べる月}月の投資で、${from}歳→${from + 1}歳 … ${to - 1}歳→${to}歳 の${ratios.length}つの比が、どの2つも差が ${v.許す差} 以内で、どれも1より大きい`);
  }),

  defineCase(FILE, 'LTC-045', async (env, data) => {
    const v = data.判定に使う値;
    const [from, to] = v.年齢;
    const mine = await runWith(env, data, { label: 'この条件' });
    const base = await runComparison(env, data, data.比較用の実行[0], 'LTC-044 の条件');
    requireNoDrawdownPremise(mine);
    requireNoDrawdownPremise(base);
    const diff = (age) => requireMonth(base, age, v.比べる月).invest - requireMonth(mine, age, v.比べる月).invest;
    const diffRatios = yearRatios(mine, v.比べる月, from, to, diff);
    const baseRatios = yearRatios(base, v.比べる月, from, to);
    const violations = [];
    diffRatios.forEach((r, i) => {
      if (!near(r.ratio, baseRatios[i].ratio, v.許す差)) violations.push(`${r.from}歳→${r.to}歳: 差の比 ${r.ratio}、LTC-044 の条件の比 ${baseRatios[i].ratio}`);
    });
    expect(violations, `${v.比べる月}月の投資の差(LTC-044 の条件 − この実行)の比 ${diffRatios.length}つが、LTC-044 の条件の同じ年の比と、差が ${v.許す差} 以内`).toEqual([]);
  }),

  defineCase(FILE, 'LTC-046', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    expect(result.months.length, '結果に月がある').toBeGreaterThan(0);
    const expected = data.条件.initialInv;
    const violations = result.months.filter((m) => m.invest !== expected).map((m) => `${m.label}: 投資 ${m.invest}`);
    expect(violations, `すべての月で、投資が ¥${expected.toLocaleString('en-US')}`).toEqual([]);
  }),

  defineCase(FILE, 'LTC-047', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    const v = data.判定に使う値;
    const [from, to] = v.年齢;
    // 比は テストデータの年齢の範囲(41歳→42歳 … 49歳→50歳)ですべて取る
    const ratios = yearRatios(result, v.比べる月, from, to);
    expectRatiosConstant(ratios, v.許す差, `${v.比べる月}月の投資で、${from}歳→${from + 1}歳 … ${to - 1}歳→${to}歳 の${ratios.length}つの比が、どの2つも差が ${v.許す差} 以内で、どれも1より大きい`);
  }),
];
