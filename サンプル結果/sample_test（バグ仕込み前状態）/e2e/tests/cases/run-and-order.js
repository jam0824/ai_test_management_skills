// TD-003(テストデータ/実行と結果の並び.json): LTC-001〜LTC-008
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');

const FILE = '実行と結果の並び.json';

/** 同じ年齢・月の見出しが2回出ていれば、その見出しを返す */
function duplicatedHeaders(result) {
  const seen = new Set();
  const dup = [];
  for (const m of result.months) {
    if (seen.has(m.label)) dup.push(m.label);
    seen.add(m.label);
  }
  return dup;
}

/** 比較用の実行: 画面を開き直し(乱数の差し替えも最初からやり直す)、書いた条件だけを入れて1回「開始」 */
async function comparisonRun(env, data, comparison, label) {
  const screen = await env.open({ random: data.乱数, label });
  await screen.setConditions(comparison.条件);
  return screen.start();
}

/** 「開始」し直した結果と、比較用の実行の結果を比べる(LTC-002〜LTC-004) */
async function restartCase(env, data, firstConditions) {
  const screen = await env.open({ random: data.乱数, label: '開始し直す画面' });
  await screen.setConditions(firstConditions);
  await screen.start();
  await screen.setConditions(data.条件);
  const restarted = await screen.start();
  const comparison = await comparisonRun(env, data, data.比較用の実行[0], '比較用の実行');
  expect(restarted.text, '開始し直した後の結果の欄の内容が、比較用の実行と一致する').toBe(comparison.text);
  return { restarted, comparison };
}

/** LTC-007・LTC-008 の (1)〜(3) */
function checkOrder(result, firstAge) {
  expect(result.months.length, '結果に月の見出しがある').toBeGreaterThan(0);
  expect(result.months[0].age, `(1) 最初の月の見出しの年齢が ${firstAge}歳`).toBe(firstAge);
  const violations = [];
  for (let i = 1; i < result.months.length; i++) {
    const a = result.months[i - 1];
    const b = result.months[i];
    const nextMonth = a.month === 12 ? 1 : a.month + 1;
    if (b.month !== nextMonth) violations.push(`${a.label} の次が ${b.label}(月の番号が1つ進んでいない)`);
    if (b.age < a.age) violations.push(`${a.label} の次が ${b.label}(年齢が下がった)`);
    if (b.age > a.age + 1) violations.push(`${a.label} の次が ${b.label}(年齢が1つより多く上がった)`);
  }
  expect(violations, '(2) 隣り合う月の見出しで、月の番号が1つ進み、年齢が下がらず1つより多く上がらない').toEqual([]);
  expect(duplicatedHeaders(result), '(3) 同じ年齢・月の見出しが2回出ない').toEqual([]);
}

module.exports = [
  defineCase(FILE, 'LTC-001', async (env, data) => {
    const screen = await env.open({ random: data.乱数 });
    const result = await screen.start();
    expect(result.months.length, '結果の欄に月の見出しが1つ以上ある').toBeGreaterThan(0);
    const violations = [];
    for (const m of result.months) {
      const kinds = m.incomes.map((i) => i.type);
      if (kinds.length === 0) violations.push(`${m.label}: 収入の行(給与・退職後収入・年金)が無い`);
      if (m.expense === null) violations.push(`${m.label}: 生活費の行が無い`);
      if (m.cash === null || m.invest === null || m.total === null) violations.push(`${m.label}: 現金・投資・総資産の行が無い`);
    }
    expect(violations, 'どの月にも 収入の行・生活費・現金・投資・総資産 が出ている').toEqual([]);
  }),

  defineCase(FILE, 'LTC-002', async (env, data) => {
    // 事前条件: 初期値のまま一度「開始」し、結果が出ている
    await restartCase(env, data, {});
  }),

  defineCase(FILE, 'LTC-003', async (env, data) => {
    await restartCase(env, data, {});
  }),

  defineCase(FILE, 'LTC-004', async (env, data) => {
    // 事前条件: 開始年齢 40歳 で一度「開始」し、結果が出ている(ローレベルテストケースの事前条件・操作。テストデータの「条件」は戻した後の値)
    await restartCase(env, data, { startAge: 40 });
  }),

  defineCase(FILE, 'LTC-005', async (env, data) => {
    const screen = await env.open({ random: data.乱数, label: '2回クリックする画面' });
    const result = await screen.start({ times: 2 }); // 操作: 「開始」を続けて2回クリック
    const comparison = await comparisonRun(env, data, data.比較用の実行[0], '比較用の実行');
    expect(result.text, '結果の欄の内容が、比較用の実行(1回だけクリック)と一致する').toBe(comparison.text);
    expect(duplicatedHeaders(result), '同じ年齢・月の見出しが2回出ない').toEqual([]);
  }),

  defineCase(FILE, 'LTC-006', async (env, data) => {
    const screen = await env.open({ random: data.乱数, label: '10回クリックする画面' });
    const result = await screen.start({ times: 10 }); // 操作: 「開始」を続けて10回クリック
    const comparison = await comparisonRun(env, data, data.比較用の実行[0], '比較用の実行');
    expect(result.text, '結果の欄の内容が、比較用の実行(1回だけクリック)と一致する').toBe(comparison.text);
    expect(duplicatedHeaders(result), '同じ年齢・月の見出しが2回出ない').toEqual([]);
  }),

  defineCase(FILE, 'LTC-007', async (env, data) => {
    const screen = await env.open({ random: data.乱数 });
    const result = await screen.start();
    checkOrder(result, data.判定に使う値.最初の月の年齢);
  }),

  defineCase(FILE, 'LTC-008', async (env, data) => {
    const screen = await env.open({ random: data.乱数 });
    await screen.setConditions(data.条件);
    const result = await screen.start();
    checkOrder(result, data.判定に使う値.最初の月の年齢);
  }),
];
