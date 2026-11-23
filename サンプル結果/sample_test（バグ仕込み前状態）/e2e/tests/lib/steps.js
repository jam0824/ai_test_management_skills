// 複数のテストケースで使う操作と判定の形
const { expect } = require('@playwright/test');

/**
 * 画面を開き、条件を入れ、給与変更を追加して「開始」する(「条件を入れて「開始」」の操作)。
 * 比較用の実行もこれで行う(画面を開き直し、乱数の差し替えも最初からやり直す)。
 */
async function runWith(env, data, { conditions = data.条件 || {}, changes = data.給与変更 || [], random = data.乱数, label } = {}) {
  const screen = await env.open({ random, label });
  await screen.setConditions(conditions);
  if (changes.length) await screen.addSalaryChanges(changes);
  return screen.start();
}

/** 比較用の実行(テストデータの「比較用の実行」の1つ) */
function runComparison(env, data, comparison, label) {
  return runWith(env, data, { conditions: comparison.条件 || {}, changes: comparison.給与変更 || [], label: label || comparison.説明 });
}

/** 指定した年齢のすべての月で、収入の行がその種類だけで、生活費がその額 */
function expectOnlyIncome(result, ageList, type, expense, what) {
  const violations = [];
  for (const age of ageList) {
    const months = result.ofAge(age);
    if (months.length === 0) violations.push(`${age}歳の月が無い`);
    for (const m of months) {
      const kinds = m.incomes.map((i) => i.type);
      if (kinds.length === 0 || kinds.some((k) => k !== type)) violations.push(`${m.label}: 収入の行が ${kinds.join('・') || 'なし'}`);
      if (m.expense !== expense) violations.push(`${m.label}: 生活費 ${m.expense}`);
    }
  }
  expect(violations, what).toEqual([]);
}

/**
 * 指定した年齢のすべての月で、給与の額が、比較用の実行の同じ月の給与の額と同じ。
 * @returns {string[]} 合わなかった月
 */
function salaryMismatches(result, comparison, ageList) {
  const violations = [];
  for (const age of ageList) {
    const months = result.ofAge(age);
    if (months.length === 0) violations.push(`${age}歳の月が無い`);
    for (const m of months) {
      const c = comparison.at(m.age, m.month);
      if (!c) violations.push(`${m.label}: 比較用の実行(${comparison.label})に同じ月が無い`);
      else if (m.salary === null || m.salary !== c.salary) violations.push(`${m.label}: 給与 ${m.salary}、比較用の実行(${comparison.label}) ${c.salary}`);
    }
  }
  return violations;
}

/** 比較用の実行どうしで、指定した年齢の各月の給与の額がどれも違うこと */
function expectComparisonsDiffer(comparisons, ageList, what) {
  const violations = [];
  for (const age of ageList) {
    for (const m of comparisons[0].ofAge(age)) {
      const values = comparisons.map((c) => (c.at(m.age, m.month) || {}).salary);
      if (values.some((v) => v === null || v === undefined) || new Set(values).size !== values.length) {
        violations.push(`${m.label}: ${comparisons.map((c, i) => `${c.label}=${values[i]}`).join('、')}`);
      }
    }
  }
  expect(violations, what).toEqual([]);
}

/** 給与の額が前の月と変わった、範囲 [from, to] 歳の中の最初の月(前の月は範囲の外でもよい) */
function firstSalaryChange(result, from, to) {
  for (const m of result.months) {
    if (m.age < from || m.age > to) continue;
    const p = result.prev(m);
    if (p && m.salary !== null && p.salary !== null && m.salary !== p.salary) return m;
  }
  return undefined;
}

module.exports = { runWith, runComparison, expectOnlyIncome, salaryMismatches, expectComparisonsDiffer, firstSalaryChange };
