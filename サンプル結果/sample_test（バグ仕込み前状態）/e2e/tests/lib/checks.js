// 判定の前に確かめること(事前条件)と、判定でよく使う形。
// 事前条件が成り立たないときは判定せず、【ブロック】で始まるエラーで止める(ローレベルテストケースの共通の決まり)。
// Playwright の結果は失敗になるが、メッセージの先頭が【ブロック】のものは、テスト実行でブロックとして扱う(スクリプト一覧.md)。

class BlockError extends Error {
  constructor(message) {
    super(`【ブロック】${message}`);
    this.name = 'BlockError';
  }
}

function block(message) {
  throw new BlockError(message);
}

function isBlock(err) {
  return err instanceof BlockError || String(err && err.message).includes('【ブロック】');
}

/** 範囲内: 判定に使う年齢の12か月が結果に出ていることを確かめる(結果の最後の月は Q-003 の回答待ち) */
function requireAges(result, ages, what = '') {
  for (const age of ages) {
    for (let m = 1; m <= 12; m++) {
      if (!result.at(age, m)) block(`範囲内でない: ${what}${result.label} に ${age}歳${m}月 が無い`);
    }
  }
}

/** 判定に使う月が結果に出ていることを確かめて、その月を返す */
function requireMonth(result, age, month, what = '') {
  const m = result.at(age, month);
  if (!m) block(`範囲内でない: ${what}${result.label} に ${age}歳${month}月 が無い`);
  return m;
}

/** 取り崩しなし: 結果が1,200か月より長いときは前提が成り立たない */
function requireNoDrawdownPremise(result) {
  if (result.months.length > 1200) block(`取り崩しなしの前提が成り立たない(${result.label} が ${result.months.length} か月)`);
}

/** from 歳〜to 歳(両端を含む)の年齢の並び */
function ages(from, to) {
  const list = [];
  for (let a = from; a <= to; a++) list.push(a);
  return list;
}

/** 範囲 [from, to] の年齢のすべての月 */
function monthsOfAges(result, from, to) {
  return result.months.filter((m) => m.age >= from && m.age <= to);
}

/** 前の月(最初の月は、開始時貯金・開始時投資残高を「前の月」とする) */
function previousBalance(result, m) {
  const p = result.prev(m);
  if (p) return { cash: p.cash, invest: p.invest };
  return { cash: Number(result.inputs.initialCash), invest: Number(result.inputs.initialInv) };
}

function near(a, b, tolerance) {
  return Math.abs(a - b) <= tolerance;
}

/** 年収の表示の書き方(`[年収: ¥6,000,000]` のように、3桁ごとに `,`) */
function yen(n) {
  return `¥${Number(n).toLocaleString('en-US')}`;
}

module.exports = {
  BlockError, block, isBlock, requireAges, requireMonth, requireNoDrawdownPremise,
  ages, monthsOfAges, previousBalance, near, yen,
};
