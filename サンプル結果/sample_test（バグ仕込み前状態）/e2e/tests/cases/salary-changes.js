// TD-010(テストデータ/給与変更.json): LTC-060〜LTC-079
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { requireAges, requireNoDrawdownPremise, ages, monthsOfAges, yen } = require('../lib/checks');
const { runWith, runComparison, salaryMismatches, expectComparisonsDiffer, firstSalaryChange } = require('../lib/steps');

const FILE = '給与変更.json';

/** 比較用の実行をすべて行う(画面を開き直して1回ずつ「開始」) */
async function runComparisons(env, data) {
  const results = [];
  for (const [i, c] of data.比較用の実行.entries()) results.push(await runComparison(env, data, c, c.名前 ? `比較用の実行${c.名前}` : `比較用の実行${i + 1}`));
  return results;
}

/** 区間ごとに、その年齢のすべての月の給与の額が、比較用の実行の同じ月と同じ */
function expectSalaryLikeComparisons(result, sections, what) {
  const violations = [];
  for (const { comparison, from, to } of sections) {
    requireAges(result, ages(from, to));
    requireAges(comparison, ages(from, to));
    violations.push(...salaryMismatches(result, comparison, ages(from, to)));
  }
  expect(violations, what).toEqual([]);
}

/** 給与変更を入れて「開始」し、結果の欄の内容が比較用の実行と一致する(LTC-068、LTC-074、LTC-075、LTC-077、LTC-078) */
async function sameAsComparison(env, data) {
  const result = await runWith(env, data);
  const [comparison] = await runComparisons(env, data);
  expect(result.text, `結果の欄の内容が、比較用の実行(${data.比較用の実行[0].説明})と一致する`).toBe(comparison.text);
}

module.exports = [
  defineCase(FILE, 'LTC-060', async (env, data) => {
    const screen = await env.open({ random: data.乱数, label: '非表示で開始する画面' });
    const [change] = data.給与変更;
    await expect(screen.salaryPanel(), '(1) 画面を開いた直後は給与変更設定の欄が見えない').toBeHidden();
    await screen.toggleSalaryChanges();
    await expect(screen.salaryPanel(), '(2) 切り替えると見える').toBeVisible();
    await screen.clickAddSalaryChange();
    await expect(screen.salaryItems()).toHaveCount(1);
    await screen.fillSalaryChange(0, change);
    await screen.toggleSalaryChanges();
    await expect(screen.salaryPanel(), '(4) もう一度切り替えると見えない').toBeHidden();
    const hiddenRun = await screen.start({ label: '(5) 非表示のまま開始' });
    await screen.toggleSalaryChanges();
    await expect(screen.salaryPanel(), '(6) もう一度切り替えると見える').toBeVisible();
    expect(await screen.readSalaryChanges(), '(6) 年齢と年収がそのまま入っている').toEqual([change.map(String)]);

    const [cmpA, cmpB] = data.比較用の実行;
    // 比較用の実行A: 設定を表示したまま「開始」
    const a = await runComparison(env, data, cmpA, '比較用の実行A');
    expect(await a.screen.salaryPanel().isVisible(), '比較用の実行Aは設定を表示したまま').toBe(true);
    const b = await runComparison(env, data, cmpB, '比較用の実行B');
    expect(hiddenRun.text, '(5) 結果の欄の内容が、比較用の実行A(同じ設定を表示したまま「開始」)と一致する').toBe(a.text);
    expect(hiddenRun.text, '(5) 結果の欄の内容が、比較用の実行B(給与変更なしで「開始」)と違う').not.toBe(b.text);
    // 事後条件: 入れた設定が欄に残っている
    expect(await screen.readSalaryChanges(), '事後条件: 入れた設定が欄に残っている').toEqual([change.map(String)]);
  }),

  defineCase(FILE, 'LTC-061', async (env, data) => {
    const screen = await env.open({ random: data.乱数 });
    await screen.toggleSalaryChanges(); // 事前条件: 給与変更設定を表示している
    await expect(screen.salaryPanel()).toBeVisible();
    await expect(screen.salaryItems(), '事前条件: 設定が1つも無い').toHaveCount(0);
    await screen.clickAddSalaryChange();
    await screen.fillSalaryChange(0, data.給与変更[0]);
    await expect(screen.salaryItems(), '設定が1つになる').toHaveCount(1);
    expect(await screen.readSalaryChanges(), '年齢の欄と年収の欄に入れた値が入っている').toEqual(data.給与変更.map((c) => c.map(String)));
  }),

  defineCase(FILE, 'LTC-062', async (env, data) => {
    const screen = await env.open({ random: data.乱数 });
    await screen.toggleSalaryChanges();
    await expect(screen.salaryPanel()).toBeVisible();
    await expect(screen.salaryItems(), '事前条件: 設定が1つも無い').toHaveCount(0);
    for (let i = 0; i < data.給与変更.length; i++) await screen.clickAddSalaryChange(); // 続けて3回クリック
    for (const [i, change] of data.給与変更.entries()) await screen.fillSalaryChange(i, change); // 上から順に入れる
    await expect(screen.salaryItems(), `設定が${data.給与変更.length}つになる`).toHaveCount(data.給与変更.length);
    expect(await screen.readSalaryChanges(), '上から入れた順に、それぞれの欄に値が入っている').toEqual(data.給与変更.map((c) => c.map(String)));
  }),

  defineCase(FILE, 'LTC-063', async (env, data) => {
    const screen = await env.open({ random: data.乱数, label: '削除する画面' });
    await screen.addSalaryChanges(data.給与変更);
    await screen.deleteSalaryChange(0);
    await expect(screen.salaryItems(), '設定の数が0になる').toHaveCount(0);
    const result = await screen.start();
    const [comparison] = await runComparisons(env, data);
    expect(result.text, '結果の欄の内容が、比較用の実行(給与変更なしで「開始」)と一致する').toBe(comparison.text);
  }),

  defineCase(FILE, 'LTC-064', async (env, data) => {
    const screen = await env.open({ random: data.乱数, label: '削除する画面' });
    await screen.addSalaryChanges(data.給与変更);
    await screen.deleteSalaryChange(1); // 2番目の「削除」
    const remaining = data.比較用の実行[0].給与変更;
    await expect(screen.salaryItems(), `設定の数が${remaining.length}になる`).toHaveCount(remaining.length);
    expect(await screen.readSalaryChanges(), '残った設定が元のまま入っている').toEqual(remaining.map((c) => c.map(String)));
    const result = await screen.start();
    const [comparison] = await runComparisons(env, data);
    expect(result.text, '結果の欄の内容が、比較用の実行(その2つだけを入れて「開始」)と一致する').toBe(comparison.text);
  }),

  defineCase(FILE, 'LTC-065', async (env, data) => {
    const result = await runWith(env, data);
    expect(result.months.length, '(1) 結果の欄に月ごとの結果が出る').toBeGreaterThan(0);
    const [from, to] = [30, 64]; // ローレベルテストケースの期待値の範囲(退職年齢は初期値の65歳)
    requireAges(result, ages(from, to));
    const months = monthsOfAges(result, from, to);
    const values = [...new Set(months.map((m) => m.salary))];
    expect(values.length === 1 && values[0] !== null, `(2) ${from}歳1月〜${to}歳12月のすべての月の給与の額が同じ(出た額: ${values.join('、')})`).toBe(true);
    expect(result.text.includes('[年収:'), '(3) 結果の欄のどこにも `[年収:` が無い').toBe(false);
  }),

  defineCase(FILE, 'LTC-066', async (env, data) => {
    const screen = await env.open({ random: data.乱数, label: '転職と昇進を入れる画面' });
    const [first, second] = data.給与変更;
    await screen.toggleSalaryChanges();
    await screen.clickAddSalaryChange();
    await screen.fillSalaryChange(0, first); // 1つ目(転職)
    await screen.clickAddSalaryChange();
    await screen.fillSalaryChange(1, second); // 2つ目(昇進)
    const result = await screen.start();
    const [c3, c4, c6] = await runComparisons(env, data);
    // (1) 見る年齢はローレベルテストケースの期待値(34歳 / 36歳と44歳 / 46歳)
    expectSalaryLikeComparisons(result, [
      { comparison: c3, from: 34, to: 34 },
      { comparison: c4, from: 36, to: 36 },
      { comparison: c4, from: 44, to: 44 },
      { comparison: c6, from: 46, to: 46 },
    ], '(1) 34歳は基本年収、36歳と44歳は転職後、46歳は昇進後の年収の比較用の実行と、各月の給与の額が同じ');
    expectComparisonsDiffer([c3, c4, c6], [34, 36, 44, 46], '3つの比較用の実行の給与の額がどれも違う');
    // (2) 給与の額が前の月と変わった月のうち、35歳〜36歳 / 45歳〜46歳 の間の最初の月
    for (const [[age, salary], from, to] of [[first, 35, 36], [second, 45, 46]]) {
      const changed = firstSalaryChange(result, from, to);
      expect(changed, `(2) ${from}歳〜${to}歳の間に、給与の額が前の月と変わった月がある`).toBeTruthy();
      expect(changed.incomes[0].line, `(2) ${from}歳〜${to}歳の間の最初の変わった月(${changed.label})に \`[年収: ${yen(salary)}]\` が出る(${age}歳からの設定)`).toContain(`[年収: ${yen(salary)}]`);
    }
  }),

  defineCase(FILE, 'LTC-067', async (env, data) => {
    const screen = await env.open({ random: data.乱数, label: '削除して入れ直す画面' });
    await screen.addSalaryChanges(data.給与変更); // 表示して2つ追加し、入れる
    await screen.deleteSalaryChange(0); // 1つ目の「削除」
    await screen.clickAddSalaryChange();
    await screen.fillSalaryChange(data.給与変更.length - 1, data.給与変更[0]); // 消した (35, 4000000) を入れ直す
    await screen.toggleSalaryChanges();
    await expect(screen.salaryPanel(), '非表示にしてから「開始」する').toBeHidden();
    const result = await screen.start();
    const [comparison] = await runComparisons(env, data);
    expect(result.text, '結果の欄の内容が、比較用の実行(削除も非表示もせずに「開始」)と一致する').toBe(comparison.text);
  }),

  defineCase(FILE, 'LTC-068', sameAsComparison),

  defineCase(FILE, 'LTC-069', async (env, data) => {
    const result = await runWith(env, data);
    const [c3, c6] = await runComparisons(env, data);
    // 見る年齢はローレベルテストケースの期待値(44歳 / 46歳)
    expectSalaryLikeComparisons(result, [
      { comparison: c3, from: 44, to: 44 },
      { comparison: c6, from: 46, to: 46 },
    ], '44歳は基本年収、46歳は給与変更の年収の比較用の実行と、各月の給与の額が同じ');
    expectComparisonsDiffer([c3, c6], [44, 46], '2つの比較用の実行の給与の額が違う');
  }),

  defineCase(FILE, 'LTC-070', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    const [c3] = await runComparisons(env, data);
    expectSalaryLikeComparisons(result, [{ comparison: c3, from: 44, to: 44 }], '44歳のすべての月の給与の額が、比較用の実行(基本年収)と同じ');
    const [from, to] = [46, 64]; // ローレベルテストケースの期待値の範囲
    requireAges(result, ages(from, to));
    const violations = [];
    for (const m of monthsOfAges(result, from, to)) {
      if (m.salary !== 0) violations.push(`${m.label}: 給与 ${m.salary}`);
      const p = result.prev(m);
      if (m.invest > p.invest) violations.push(`${m.label}: 投資が ${p.invest} → ${m.invest} に増えた`);
    }
    expect(violations, `${from}歳1月〜${to}歳12月のすべての月で、給与の額が ¥0 で、投資が前の月から増えない`).toEqual([]);
  }),

  defineCase(FILE, 'LTC-071', async (env, data) => {
    const result = await runWith(env, data);
    requireNoDrawdownPremise(result);
    const [c1] = await runComparisons(env, data);
    expectSalaryLikeComparisons(result, [{ comparison: c1, from: 46, to: 46 }], '46歳のすべての月の給与の額が、比較用の実行(基本年収 1円)と同じ');
  }),

  defineCase(FILE, 'LTC-072', async (env, data) => {
    const result = await runWith(env, data);
    const [c3, c4, c6] = await runComparisons(env, data);
    // 区間はローレベルテストケースの期待値(34歳 / 36〜44歳 / 46〜64歳)
    expectSalaryLikeComparisons(result, [
      { comparison: c3, from: 34, to: 34 },
      { comparison: c4, from: 36, to: 44 },
      { comparison: c6, from: 46, to: 64 },
    ], '34歳・36〜44歳・46〜64歳の各月の給与の額が、それぞれの年収の比較用の実行と同じ');
  }),

  defineCase(FILE, 'LTC-073', async (env, data) => {
    const result = await runWith(env, data);
    const [c3, c4, c5, c6] = await runComparisons(env, data);
    // 区間はローレベルテストケースの期待値(34歳 / 36〜41歳 / 43〜49歳 / 51〜64歳)
    expectSalaryLikeComparisons(result, [
      { comparison: c3, from: 34, to: 34 },
      { comparison: c4, from: 36, to: 41 },
      { comparison: c5, from: 43, to: 49 },
      { comparison: c6, from: 51, to: 64 },
    ], '34歳・36〜41歳・43〜49歳・51〜64歳の各月の給与の額が、それぞれの年収の比較用の実行と同じ');
  }),

  defineCase(FILE, 'LTC-074', sameAsComparison),
  defineCase(FILE, 'LTC-075', sameAsComparison),

  defineCase(FILE, 'LTC-076', async (env, data) => {
    const result = await runWith(env, data);
    const [c6] = await runComparisons(env, data);
    expectSalaryLikeComparisons(result, [{ comparison: c6, from: 30, to: 64 }], '30歳1月〜64歳12月のすべての月の給与の額が、比較用の実行と同じ');
  }),

  defineCase(FILE, 'LTC-077', sameAsComparison),
  defineCase(FILE, 'LTC-078', sameAsComparison),

  defineCase(FILE, 'LTC-079', async (env, data) => {
    const result = await runWith(env, data);
    const [[age, salary]] = data.給与変更;
    const [from, to] = [age, age + 1]; // ローレベルテストケースの期待値(45歳〜46歳の間)
    requireAges(result, ages(from, to));
    const changed = firstSalaryChange(result, from, to);
    expect(changed, `${from}歳〜${to}歳の間に、給与の額が前の月と変わった月がある`).toBeTruthy();
    expect(changed.incomes[0].line, `給与の額が前の月と変わった最初の月(${changed.label})の収入の行に \`[年収: ${yen(salary)}]\` がある`).toContain(`[年収: ${yen(salary)}]`);
  }),
];
