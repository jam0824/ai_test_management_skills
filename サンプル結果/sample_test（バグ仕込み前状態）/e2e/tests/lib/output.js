// 結果の欄(#output)の文字を、月ごとの値にする。読み方は テスト環境.md の「結果の欄の読み方」のとおり。
// - 月のかたまり: `-- <年齢>歳<月>月 --` の行から、次の `-- ` か `== ` で始まる行の前まで
// - 年の初めの `== … 投資利息 ==` と、その次の `投資: ¥… → ¥…` の行は、月のかたまりに含めない
// - 額は `¥` の後の数字。`,` を除いて数にする。`-` が付けば負の数

const AMOUNT = '(-?[\\d,]+(?:\\.\\d+)?)';
const HEADER = /^-- (-?\d+(?:\.\d+)?)歳(\d+)月 --$/;
const INCOME = new RegExp(`^\\s*(給与|退職後収入|年金): ¥${AMOUNT}`);
const INVEST_PART = new RegExp(`\\(投資: ¥${AMOUNT}\\)`);
const ANNUAL_PART = new RegExp(`\\[年収: ¥${AMOUNT}\\]`);
const EXPENSE = new RegExp(`^\\s*生活費: ¥${AMOUNT}`);
const EVENT = new RegExp(`^\\s*▶ (.+): ¥${AMOUNT}\\s*$`);
const DRAW = /^\s*🔄 投資から補填:/;
const BALANCE = new RegExp(`^\\s*現金: ¥${AMOUNT} 投資: ¥${AMOUNT} 総資産: ¥${AMOUNT}`);

function amount(text) {
  return Number(text.replace(/,/g, ''));
}

function analyzeMonth(block) {
  const m = {
    age: block.age, month: block.month, label: `${block.age}歳${block.month}月`, lines: block.lines,
    incomes: [], expense: null, events: [], draws: 0, cash: null, invest: null, total: null,
  };
  for (const line of block.lines) {
    let r;
    if ((r = line.match(INCOME))) {
      const income = { type: r[1], amount: amount(r[2]), line: line.trim() };
      const inv = line.match(INVEST_PART);
      if (inv) income.investAmount = amount(inv[1]);
      const annual = line.match(ANNUAL_PART);
      if (annual) income.annual = amount(annual[1]);
      m.incomes.push(income);
    } else if ((r = line.match(EXPENSE))) {
      m.expense = amount(r[1]);
    } else if ((r = line.match(EVENT))) {
      m.events.push({ name: r[1], amount: amount(r[2]) });
    } else if (DRAW.test(line)) {
      m.draws += 1;
    } else if ((r = line.match(BALANCE))) {
      m.cash = amount(r[1]);
      m.invest = amount(r[2]);
      m.total = amount(r[3]);
    }
  }
  // 収入の種類: 収入の行がちょうど1つのときだけ決まる(0行・2行以上のときは null)
  m.incomeType = m.incomes.length === 1 ? m.incomes[0].type : null;
  m.incomeAmount = m.incomes.length === 1 ? m.incomes[0].amount : null;
  // 給与の額: 収入の行の `給与: ¥` の後の額
  const salaryLine = m.incomes.find((i) => i.type === '給与');
  m.salary = salaryLine ? salaryLine.amount : null;
  return m;
}

/** 結果の欄の文字全体を読む。months は結果に出た順 */
function parseOutput(text) {
  const blocks = [];
  let cur = null;
  for (const line of text.split('\n')) {
    const h = line.match(HEADER);
    if (h) {
      cur = { age: Number(h[1]), month: Number(h[2]), lines: [] };
      blocks.push(cur);
      continue;
    }
    if (line.startsWith('-- ') || line.startsWith('== ')) {
      cur = null;
      continue;
    }
    if (cur) cur.lines.push(line);
  }
  const months = blocks.map(analyzeMonth);
  const byLabel = new Map(months.map((m) => [m.label, m]));
  return {
    text,
    months,
    /** その年齢の月(結果に出た順) */
    ofAge: (age) => months.filter((m) => m.age === age),
    /** その年齢・月(無ければ undefined) */
    at: (age, month) => byLabel.get(`${age}歳${month}月`),
    /** 結果に出た順で1つ前の月(最初の月なら undefined) */
    prev: (m) => months[months.indexOf(m) - 1],
  };
}

module.exports = { parseOutput, amount };
