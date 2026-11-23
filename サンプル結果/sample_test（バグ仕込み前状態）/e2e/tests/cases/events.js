// TD-011(テストデータ/突発的な支出.json): LTC-080〜LTC-088
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { block, requireNoDrawdownPremise, near } = require('../lib/checks');
const { runWith } = require('../lib/steps');
const { binomialRange } = require('../lib/binomial');

const FILE = '突発的な支出.json';

/** 発生率の割合: 画面を開き直さずに「開始」を繰り返し、合計の月数が下限以上になるまで数える */
async function eventRate(env, data) {
  const v = data.判定に使う値;
  const screen = await env.open({ random: data.乱数, label: `シード${data.乱数.シード}` });
  await screen.setConditions(data.条件);
  let months = 0;
  let eventMonths = 0;
  let runs = 0;
  while (months < v.合計の月数の下限) {
    const result = await screen.start({ label: `開始${runs + 1}` });
    runs += 1;
    if (result.months.length === 0) throw new Error('結果に月が無い(合計の月数が増えない)');
    months += result.months.length;
    eventMonths += result.months.filter((m) => m.events.length > 0).length;
  }
  // 期待値の範囲は、数えた N から二項分布で計算する(ローレベルテストケースの備考)
  const p = v['発生率(%)'] / 100;
  const { low, high } = binomialRange(months, p, v['外れる確率の上限(片側)']);
  const msg = `突発的な支出が出た月の数 ${eventMonths} が、N = ${months}(「開始」${runs}回)、p = ${p} の二項分布の範囲 ${low}〜${high} に入る`;
  expect(eventMonths, msg).toBeGreaterThanOrEqual(low);
  expect(eventMonths, msg).toBeLessThanOrEqual(high);
}

module.exports = [
  ...['LTC-080', 'LTC-081', 'LTC-082', 'LTC-083', 'LTC-084'].map((id) => defineCase(FILE, id, eventRate, { timeout: 10 * 60 * 1000 })),

  defineCase(FILE, 'LTC-085', async (env, data) => {
    const result = await runWith(env, data);
    expect(result.months.length, '結果に月がある').toBeGreaterThan(0);
    const withEvent = result.months.filter((m) => m.events.length > 0).map((m) => m.label);
    expect(withEvent, 'どの月にも突発的な支出(▶ の行)が無い').toEqual([]);
  }),

  defineCase(FILE, 'LTC-086', async (env, data) => {
    const result = await runWith(env, data);
    expect(result.months.length, '結果に月がある').toBeGreaterThan(0);
    const withoutEvent = result.months.filter((m) => m.events.length === 0).map((m) => m.label);
    expect(withoutEvent, 'すべての月に突発的な支出(▶ の行)がある').toEqual([]);
  }),

  defineCase(FILE, 'LTC-087', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    const eventMonths = result.months.filter((m) => m.events.length > 0);
    if (eventMonths.length === 0) block('▶ の行がある月が無い(1か月だけ起こす差し替えが効いていない)');
    expect(eventMonths.map((m) => m.label), '(1) ▶ の行がある月が1つだけ').toHaveLength(1);
    const E = eventMonths[0];
    const D = result.prev(E);
    const C = D && result.prev(D);
    if (!C) block(`起きた月 ${E.label} の前の2か月が結果に無い`);
    // C・D・E が同じ期間で、境目の年(退職年齢・年金開始年齢の年)でないことを確かめてから判定する
    const boundary = [Number(result.inputs.retirementAge), Number(result.inputs.pensionStartAge)];
    const types = [C, D, E].map((m) => m.incomeType);
    if (types.some((t) => t === null) || new Set(types).size !== 1) block(`C・D・E(${C.label}・${D.label}・${E.label})が同じ期間でない(${types.join('・')})`);
    if ([C, D, E].some((m) => boundary.includes(m.age))) block(`C・D・E(${C.label}・${D.label}・${E.label})が境目の年にかかる`);
    const spent = E.events.reduce((s, e) => s + e.amount, 0);
    expect(near(D.cash - E.cash, (C.cash - D.cash) + spent, 1),
      `(2) (D の現金 − E の現金) ${D.cash - E.cash} が、(C の現金 − D の現金) ${C.cash - D.cash} + 支出の額 ${spent} と1円以内で合う`).toBe(true);
    const expected = E.incomeAmount - E.expense - (E.invest - D.invest) - spent;
    expect(near(E.cash - D.cash, expected, 1),
      `(3) (E の現金 − D の現金) ${E.cash - D.cash} が、収入 ${E.incomeAmount} − 生活費 ${E.expense} − 投資の増えた分 ${E.invest - D.invest} − 支出の額 ${spent} = ${expected} と1円以内で合う`).toBe(true);
  }),

  defineCase(FILE, 'LTC-088', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    const names = result.months.flatMap((m) => m.events.map((e) => e.name));
    // 名前の組はローレベルテストケースの期待値(「入院」か「医療費」、「家電故障」か「車検」、「冠婚葬祭」、「引越し」)
    const groups = [['入院', '医療費'], ['家電故障', '車検'], ['冠婚葬祭'], ['引越し']];
    const missing = groups.filter((g) => !names.some((n) => g.some((word) => n.includes(word)))).map((g) => g.join('か'));
    expect(missing, `▶ の行の支出の名前に、4つの種類を含むものがそれぞれ1つ以上ある(出た名前: ${[...new Set(names)].join('、')})`).toEqual([]);
  }),
];
