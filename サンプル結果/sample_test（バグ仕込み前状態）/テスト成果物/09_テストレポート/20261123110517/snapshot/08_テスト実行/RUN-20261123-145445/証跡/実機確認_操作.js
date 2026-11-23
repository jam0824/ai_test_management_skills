// 実機確認(RUN-20261123-145445)。質問表で未回答の Q-001〜Q-022 について、テスト対象を動かして今の動きを記録する。
// テスト対象: http://localhost:8000/retirement_simulator.html(テスト対象のファイルは変えない)
// Playwright は D:/codes/sample_test/e2e の node_modules から読み込むだけ(そのフォルダには書き込まない)。
// 前提はテスト環境.md・テストデータ.md と同じ: 乱数は TD-002 の「支出なし」(読み込む前に Math.random を差し替え)、
// 突発的な支出そのものを見る質問(Q-014、Q-015、Q-020 の(2))だけ「差し替えない」。書いていない入力欄は初期値のまま。
// 証跡は、このスクリプトのあるフォルダに書く。
// 使い方: node 実機確認_操作.js [Q-001 Q-002 ...](引数なしなら全部)
const path = require('path');
const fs = require('fs');
const { chromium } = require('D:/codes/sample_test/e2e/node_modules/playwright');

const URL = 'http://localhost:8000/retirement_simulator.html';
const OUT = __dirname;
const NO_EVENT = 0.9999999999999999; // TD-002「支出なし」
// TD-001 の略記
const 別々 = { gapIncome: 70000, salary: 5000000, monthlyPension: 130000, initialCash: 1000000000, expenseCurrent: 150000, expenseGap: 210000, expenseRetired: 270000 };

let browser;
async function openPage({ stub = '支出なし', viewport } = {}) {
  const ctx = await browser.newContext({ viewport: viewport || { width: 1280, height: 900 }, locale: 'ja-JP' });
  const page = await ctx.newPage();
  page.dialogs = [];
  page.on('dialog', async d => { page.dialogs.push(`${d.type()}: ${d.message()}`); await d.dismiss(); });
  page.consoleMsgs = [];
  page.on('console', m => page.consoleMsgs.push(`${m.type()}: ${m.text()}`));
  if (stub === '支出なし') await page.addInitScript(v => { Math.random = () => v; }, NO_EVENT);
  await page.goto(URL);
  return page;
}
async function setFields(page, cond) {
  for (const [id, v] of Object.entries(cond)) await page.fill('#' + id, v === null ? '' : String(v));
}
async function addChanges(page, changes) {
  if (changes.length && !(await page.isVisible('#salaryChanges'))) await page.click('#toggleSalaryChanges');
  for (const [age, sal] of changes) {
    await page.click('#addSalaryChange');
    const item = page.locator('.salary-change-item').last();
    if (age !== null) await item.locator('.salary-change-age').fill(String(age));
    if (sal !== null) await item.locator('.salary-change-salary').fill(String(sal));
  }
}
async function run(page) { await page.click('#runBtn'); return (await page.textContent('#output')) || ''; }
async function inputs(page) {
  return page.evaluate(() => [...document.querySelectorAll('#controls input[type=number]')].filter(e => e.id)
    .map(e => `${e.id}=${JSON.stringify(e.value)}`).join(' '));
}
// 結果の欄を、月の見出しごとのかたまりにする
function parse(text) {
  const months = []; const map = {}; let cur = null; const interest = [];
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    const m = l.match(/^-- (.+?) --$/);
    if (m) { cur = { h: m[1], lines: [] }; months.push(cur); map[m[1]] = cur; continue; }
    if (l.startsWith('== ')) { interest.push(l + ' / ' + (lines[i + 1] || '').trim()); cur = null; i++; continue; }
    if (cur) cur.lines.push(l.trim());
  }
  return { months, map, interest, lines };
}
function num(s) { return Number(s.replace(/,/g, '')); }
function balance(block) {
  const l = block.lines.find(x => x.startsWith('現金:'));
  const m = l.match(/現金: ¥(-?[\d,]+) 投資: ¥(-?[\d,]+) 総資産: ¥(-?[\d,]+)/);
  return { cash: num(m[1]), inv: num(m[2]), total: num(m[3]) };
}
function excerpt(p, heads) {
  return heads.map(h => p.map[h] ? `-- ${h} --\n  ` + p.map[h].lines.join('\n  ') : `-- ${h} -- (結果に無い)`).join('\n');
}
function save(name, content) { fs.writeFileSync(path.join(OUT, name), content, 'utf8'); console.log('saved', name); }
// 結果の欄を、見出しの行が上に来るようにスクロールしてから、ページ全体を撮る
async function shot(page, name, heading) {
  if (heading) {
    await page.evaluate(h => {
      const out = document.getElementById('output'); const tn = out.firstChild; if (!tn) return;
      const idx = tn.textContent.indexOf(h); if (idx < 0) return;
      const r = document.createRange(); r.setStart(tn, idx); r.setEnd(tn, idx + h.length);
      out.scrollTop = r.getBoundingClientRect().top - out.getBoundingClientRect().top + out.scrollTop - 4;
    }, heading.startsWith('==') ? heading : `-- ${heading} --`);
  }
  await page.screenshot({ path: path.join(OUT, name), fullPage: true });
  console.log('saved', name);
}
function header(title, cond, extra = '') {
  return `# ${title}\n# URL: ${URL}\n# 乱数: ${cond.stub || '支出なし(TD-002)'}\n# 入力: ${cond.text}\n${extra}`;
}

// 手取りの候補の式(観察した値と比べるためのもの。どれが正しいかを決めるものではない)
const NAT = [[1950000, .05], [3300000, .10], [6950000, .20], [9000000, .23], [18000000, .33], [40000000, .40], [Infinity, .45]];
function progressive(t) { let tax = 0, prev = 0; for (const [up, r] of NAT) { if (t <= prev) break; tax += (Math.min(up, t) - prev) * r; prev = up; } return tax; }
function kyuyo(S) { if (S <= 1625000) return Math.min(S, 550000); if (S <= 1800000) return S * .4 - 100000; if (S <= 3600000) return S * .3 + 80000; if (S <= 6600000) return S * .2 + 440000; if (S <= 8500000) return S * .1 + 1100000; return 1950000; }
const CAND = {
  A_控除後の額に所得税と住民税: S => { const so = S * .14, t = Math.max(0, S - so - 480000); return (S - so - progressive(t) - t * .10) / 12; },
  B_住民税は年収の10: S => { const so = S * .14, t = Math.max(0, S - so - 480000); return (S - so - progressive(t) - S * .10) / 12; },
  C_住民税に基礎控除を使わない: S => { const so = S * .14, t = Math.max(0, S - so - 480000), tr = Math.max(0, S - so); return (S - so - progressive(t) - tr * .10) / 12; },
  D_給与所得控除も引く: S => { const so = S * .14, t = Math.max(0, S - kyuyo(S) - so - 480000); return (S - so - progressive(t) - t * .10) / 12; },
};

const Q = {};

Q['Q-001'] = async () => {
  let out = '';
  const condA = { startAge: 30, retirementAge: 50, pensionStartAge: 55, ...別々 };
  let page = await openPage(); await setFields(page, condA);
  let p = parse(await run(page));
  out += header('Q-001 (A) 退職年齢50・年金開始年齢55、期間ごとに収入と生活費を別々の額に(LTC-026 と同じ条件)', { text: JSON.stringify(condA) }) +
    excerpt(p, ['30歳12月', '31歳1月', '49歳11月', '49歳12月', '50歳1月', '50歳2月', '50歳12月', '51歳1月', '54歳12月', '55歳1月', '55歳2月']) + '\n\n';
  const kinds = {}; for (const b of p.months) { const age = b.h.match(/^(\d+)歳/)[1]; const k = b.lines[0].split(':')[0] + '/' + b.lines[1]; (kinds[age] = kinds[age] || new Set()).add(k); }
  out += '# 年齢ごとの「収入の種類/生活費」の組(48〜56歳)\n' + Object.entries(kinds).filter(([a]) => a >= 48 && a <= 56).map(([a, s]) => `${a}歳: ${[...s].join(' , ')}`).join('\n') + '\n\n';
  await shot(page, 'Q-001_1_49歳12月から50歳1月.png', '49歳12月');
  await shot(page, 'Q-001_2_54歳12月から55歳1月.png', '54歳12月');
  const condB = {};
  page = await openPage(); p = parse(await run(page));
  out += header('Q-001 (B) 初期値(退職年齢65・年金開始年齢65)', { text: '初期値のまま' }) + excerpt(p, ['64歳11月', '64歳12月', '65歳1月', '65歳2月']) + '\n\n';
  await shot(page, 'Q-001_3_初期値_64歳12月から65歳1月.png', '64歳12月');
  page = await openPage(); await addChanges(page, [[45, 6000000]]); p = parse(await run(page));
  out += header('Q-001 (C) 給与変更 (45歳, 6,000,000円) を1つ(LTC-069 と同じ条件)', { text: '給与変更 (45, 6000000)。ほかは初期値' }) + excerpt(p, ['44歳11月', '44歳12月', '45歳1月', '45歳2月']) + '\n';
  await shot(page, 'Q-001_4_給与変更45歳_44歳12月から45歳1月.png', '44歳12月');
  save('Q-001_結果の抜き出し.txt', out);
};

Q['Q-002'] = async () => {
  let out = '';
  const cond4 = { retirementAge: 70, salary: 10000000, monthlyPension: 200000, investRate: 40, interest: 3 };
  let page = await openPage(); await setFields(page, cond4);
  let p = parse(await run(page));
  const kinds = (p, a1, a2) => { const r = {}; for (const b of p.months) { const age = +b.h.match(/^(\d+)歳/)[1]; if (age < a1 || age > a2) continue; const k = b.lines[0].replace(/¥[-\d,]+/g, '¥…').replace(/\[年収.*\]/, '') + ' / ' + b.lines[1]; (r[age] = r[age] || new Set()).add(k); } return Object.entries(r).map(([a, s]) => `${a}歳: ${[...s].join(' , ')}`).join('\n'); };
  out += header('Q-002 (A) 使用例ケース4(退職年齢70、年金開始年齢は初期値の65)(LTC-019 と同じ条件)', { text: JSON.stringify(cond4) }) +
    excerpt(p, ['64歳12月', '65歳1月', '67歳6月', '69歳12月', '70歳1月']) + '\n# 年齢ごとの「収入の種類 / 生活費」(63〜72歳)\n' + kinds(p, 63, 72) +
    `\n# 結果全体で「退職後収入」の行の数: ${p.months.filter(b => b.lines[0].startsWith('退職後収入')).length}\n\n`;
  await shot(page, 'Q-002_1_ケース4_64歳12月から65歳1月.png', '64歳12月');
  await shot(page, 'Q-002_2_ケース4_69歳12月から70歳1月.png', '69歳12月');
  const condB = { startAge: 30, retirementAge: 60, pensionStartAge: 55, ...別々 };
  page = await openPage(); await setFields(page, condB); p = parse(await run(page));
  out += header('Q-002 (B) 退職年齢60・年金開始年齢55、期間ごとに別々の額(LTC-030 と同じ条件)', { text: JSON.stringify(condB) }) +
    excerpt(p, ['54歳12月', '55歳1月', '59歳12月', '60歳1月']) + '\n# 年齢ごとの「収入の種類 / 生活費」(53〜62歳)\n' + kinds(p, 53, 62) +
    `\n# 結果全体で「退職後収入」の行の数: ${p.months.filter(b => b.lines[0].startsWith('退職後収入')).length}\n`;
  await shot(page, 'Q-002_3_退職60年金55_59歳12月から60歳1月.png', '59歳12月');
  save('Q-002_結果の抜き出し.txt', out);
};

Q['Q-003'] = async () => {
  const rows = ['開始年齢\t最初の月\t最後の月\t月の数\t結果の欄の文字数'];
  let page;
  for (const s of [30, 50, 99, 100, 101]) {
    page = await openPage(); await setFields(page, { startAge: s });
    const text = await run(page); const p = parse(text);
    rows.push([s, p.months[0] ? p.months[0].h : '(なし)', p.months.length ? p.months[p.months.length - 1].h : '(なし)', p.months.length, text.length].join('\t'));
    if (s === 30) { await shot(page, 'Q-003_1_初期値_結果の最後.png', '100歳12月'); save('Q-003_初期値の結果全体.txt', header('Q-003 初期値の結果の欄の全体', { text: '初期値のまま' }) + text); }
    if (s === 101) await shot(page, 'Q-003_2_開始年齢101.png');
  }
  save('Q-003_開始年齢と最後の月.tsv', rows.join('\n') + '\n');
};

Q['Q-004'] = async () => {
  const page = await openPage();
  const v = await page.inputValue('#expenseCurrent');
  const label = await page.evaluate(() => document.getElementById('expenseCurrent').parentElement.textContent.trim());
  save('Q-004_初期値.txt', `# Q-004 画面を開いた直後(何も操作しない)の入力欄の値\n現役時生活費の欄のラベル: ${label}\n#expenseCurrent の value: ${v}\nすべての欄: ${await inputs(page)}\n`);
  await page.locator('#expenseCurrent').scrollIntoViewIfNeeded();
  await shot(page, 'Q-004_1_開いた直後の初期値.png');
};

Q['Q-005'] = Q['Q-006'] = async () => {
  if (Q.__taxDone) return; Q.__taxDone = true;
  const page = await openPage();
  const read = async S => {
    await page.fill('#salary', String(S)); await page.click('#runBtn');
    return page.evaluate(() => document.getElementById('output').textContent.split('\n').find(l => l.includes('給与:')).trim());
  };
  const salaries = new Set([0, 479999, 480000, 480001, 500000]);
  for (let s = 0; s <= 50000000; s += 50000) salaries.add(s);
  for (let s = 0; s <= 12000000; s += 250000) salaries.add(s);
  const list = [...salaries].sort((a, b) => a - b);
  const data = [];
  for (const S of list) {
    const l = await read(S);
    const m = l.match(/給与: ¥(-?[\d,]+) \(投資: ¥(-?[\d,]+)\)/);
    data.push({ S, net: num(m[1]), inv: num(m[2]), line: l });
  }
  // 候補の式との差
  const names = Object.keys(CAND);
  const rows = ['年収(入力)\t30歳1月の給与(画面)\t投資(画面)\t' + names.map(n => '候補' + n + '(月・四捨五入)').join('\t') + '\t' + names.map(n => '差_' + n).join('\t')];
  const maxDiff = Object.fromEntries(names.map(n => [n, 0]));
  for (const d of data) {
    const pred = names.map(n => Math.round(CAND[n](d.S)));
    const diff = pred.map(p => d.net - p);
    names.forEach((n, i) => { maxDiff[n] = Math.max(maxDiff[n], Math.abs(diff[i])); });
    rows.push([d.S, d.net, d.inv, ...pred, ...diff].join('\t'));
  }
  save('Q-005_Q-006_年収と手取り.tsv', rows.join('\n') + '\n');
  // 傾き(年収 50,000円 増えたときの、1年の給与(月×12)の増え方)と、傾きが変わる位置
  const grid = data.filter(d => d.S % 50000 === 0);
  const slopes = []; for (let i = 1; i < grid.length; i++) slopes.push({ a: grid[i - 1].S, b: grid[i].S, k: (grid[i].net - grid[i - 1].net) * 12 / (grid[i].S - grid[i - 1].S) });
  const kinks = [];
  for (let i = 1; i < slopes.length; i++) {
    if (Math.abs(slopes[i].k - slopes[i - 1].k) > 0.01) {
      // 左右の直線(前後それぞれ 4 区間)の交点で、傾きが変わる年収を見積もる
      const L = grid.filter(d => d.S <= slopes[i - 1].a && d.S >= slopes[i - 1].a - 200000);
      const R = grid.filter(d => d.S >= slopes[i].b && d.S <= slopes[i].b + 200000);
      const fit = pts => { const n = pts.length, sx = pts.reduce((s, p) => s + p.S, 0), sy = pts.reduce((s, p) => s + p.net * 12, 0), sxx = pts.reduce((s, p) => s + p.S * p.S, 0), sxy = pts.reduce((s, p) => s + p.S * p.net * 12, 0); const k = (n * sxy - sx * sy) / (n * sxx - sx * sx); return { k, c: (sy - k * sx) / n }; };
      if (L.length < 2 || R.length < 2) continue;
      const fl = fit(L), fr = fit(R); const x = (fr.c - fl.c) / (fl.k - fr.k);
      kinks.push({ 区間: `${slopes[i - 1].a}〜${slopes[i].b}`, 前の傾き: fl.k.toFixed(4), 後の傾き: fr.k.toFixed(4), 交点の年収: Math.round(x), 交点の年収x086引く48万: Math.round(x * 0.86 - 480000) });
    }
  }
  // 隣り合う区間で同じ境目を2回数えないように、交点の年収が近いものをまとめる
  const merged = []; for (const k of kinks) { if (merged.length && Math.abs(merged[merged.length - 1].交点の年収 - k.交点の年収) < 60000) continue; merged.push(k); }
  let txt = '# Q-005・Q-006 年収(#salary)だけを変えて「開始」し、30歳1月の「給与」の額を読んだ(ほかは初期値、乱数は支出なし)\n';
  txt += `# 試した年収: ${list.length} 通り(0〜50,000,000円を50,000円ずつ、0〜12,000,000円を250,000円ずつ(TD-007)、479,999・480,000・480,001・500,000円)\n`;
  txt += '# 候補の式と画面の値の差の最大(円・月): ' + JSON.stringify(maxDiff) + '\n';
  txt += '# 候補の式の中身: A=社会保険料14%を年収にかけ、課税される額=年収−社会保険料−48万円(0未満は0)、所得税=課税される額に国の税率表(5/10/20/23/33/40/45%)、住民税=課税される額の10%、手取り=(年収−社会保険料−所得税−住民税)÷12。B=Aの住民税を年収の10%に。C=Aの住民税の元を年収−社会保険料(48万円を引かない)に。D=Aの課税される額から、さらに給与所得控除(令和2年分以降の表)を引く\n';
  txt += '# 傾き(年収が1円増えたときの、1年の給与(月の額×12)の増え方)が変わった位置:\n';
  txt += '区間\t前の傾き\t後の傾き\t交点の年収(見積もり)\t交点の年収×0.86−480,000\n' + merged.map(k => Object.values(k).join('\t')).join('\n') + '\n';
  txt += '# 代表の行(画面の文字そのまま):\n' + data.filter(d => [0, 479999, 480000, 480001, 500000, 3000000, 5000000, 10000000].includes(d.S)).map(d => `年収 ${d.S}: ${d.line}`).join('\n') + '\n';
  save('Q-005_Q-006_手取りのまとめ.txt', txt);
  await page.fill('#salary', '3000000'); await page.click('#runBtn');
  await shot(page, 'Q-005_1_年収300万_30歳1月.png', '30歳1月');
};

Q['Q-007'] = async () => {
  const page = await openPage(); const p = parse(await run(page));
  const heads = []; for (let m = 1; m <= 12; m++) heads.push(`30歳${m}月`);
  const work = p.months.filter(b => b.lines[0].startsWith('給与'));
  const byAge = {}; for (const b of work) { const a = b.h.match(/^(\d+)歳/)[1]; (byAge[a] = byAge[a] || new Set()).add(b.lines[0]); }
  const invDelta = []; for (let i = 1; i < 12; i++) { const a = balance(p.months[i - 1]), b = balance(p.months[i]); invDelta.push(`${p.months[i].h}: 投資 ${a.inv}→${b.inv} (差 ${b.inv - a.inv}) 現金 ${a.cash}→${b.cash} (差 ${b.cash - a.cash})`); }
  save('Q-007_結果の抜き出し.txt', header('Q-007 初期値(年収3,000,000円、投資率20%)', { text: '初期値のまま' }) + excerpt(p, heads) +
    '\n\n# 30歳の月ごとの、前の月からの投資と現金の増減\n' + invDelta.join('\n') +
    '\n\n# 給与の月(現役期間)の、年齢ごとの「収入の行」の種類の数\n' + Object.entries(byAge).map(([a, s]) => `${a}歳: ${s.size} 種類 (${[...s][0]})`).join('\n') + '\n');
  await shot(page, 'Q-007_1_初期値_30歳1月から.png', '30歳1月');
};

Q['Q-008'] = async () => {
  const cond = { startAge: 30, retirementAge: 40, pensionStartAge: 45, ...別々, interest: 0 };
  const page = await openPage(); await setFields(page, cond); const p = parse(await run(page));
  const d = h => { const i = p.months.findIndex(b => b.h === h); const a = balance(p.months[i - 1]), b = balance(p.months[i]); return `${h}: 現金 ${a.cash}→${b.cash} (差 ${b.cash - a.cash})、投資 ${a.inv}→${b.inv}`; };
  save('Q-008_結果の抜き出し.txt', header('Q-008 退職年齢40・年金開始年齢45、退職後収入70,000円・年金130,000円、生活費は期間ごとに別々、利息なし(LTC-025 と同じ条件)', { text: JSON.stringify(cond) }) +
    excerpt(p, ['42歳5月', '42歳6月', '46歳5月', '46歳6月']) + '\n\n# 前の月からの現金の増減\n' + d('42歳6月') + '\n' + d('46歳6月') + '\n');
  await shot(page, 'Q-008_1_42歳5月から.png', '42歳5月');
  await shot(page, 'Q-008_2_46歳5月から.png', '46歳5月');
};

Q['Q-009'] = async () => {
  let out = '';
  const condA = { initialInv: 1000000, investRate: 0, interest: 4, initialCash: 1000000000 };
  let page = await openPage(); await setFields(page, condA); let p = parse(await run(page));
  out += header('Q-009 (A) 開始時投資残高1,000,000円、投資率0%、利回り4%、開始時貯金10億円(取り崩しなし)', { text: JSON.stringify(condA) }) +
    excerpt(p, ['30歳1月', '30歳6月', '30歳12月', '31歳1月', '31歳2月', '31歳12月', '32歳1月']) + '\n# 投資利息の行(最初の3つ)\n' + p.interest.slice(0, 3).join('\n') + `\n# 投資利息の行の数: ${p.interest.length}(最初: ${p.interest[0]})\n\n`;
  await shot(page, 'Q-009_1_投資率0_30歳12月から31歳1月.png', '30歳12月');
  const condB = { initialInv: 0, investRate: 20, interest: 4, initialCash: 1000000000 };
  page = await openPage(); await setFields(page, condB); p = parse(await run(page));
  out += header('Q-009 (B) 開始時投資残高0円、投資率20%(初期値)、利回り4%、開始時貯金10億円(取り崩しなし)', { text: JSON.stringify(condB) }) +
    excerpt(p, ['30歳1月', '30歳12月', '31歳1月']) + '\n# 投資利息の行(最初の2つ)\n' + p.interest.slice(0, 2).join('\n') + '\n';
  await shot(page, 'Q-009_2_投資率20_30歳12月から31歳1月.png', '30歳12月');
  save('Q-009_結果の抜き出し.txt', out);
};

Q['Q-010'] = async () => {
  const cond = { initialCash: 0, initialInv: 1000000, salary: 0, investRate: 0, interest: 0 };
  const page = await openPage(); await setFields(page, cond); const p = parse(await run(page));
  save('Q-010_結果の抜き出し.txt', header('Q-010 開始時貯金0円、開始時投資残高1,000,000円、年収0円、投資率0%、利回り0%(毎月、生活費155,600円の分だけ現金が足りなくなる)', { text: JSON.stringify(cond) }) +
    excerpt(p, ['30歳1月', '30歳2月', '30歳3月', '30歳5月', '30歳6月']) + '\n');
  await shot(page, 'Q-010_1_取り崩し_30歳1月から.png', '30歳1月');
};

Q['Q-011'] = async () => {
  const cond = { initialCash: 0, initialInv: 100000, salary: 0, investRate: 0 };
  const page = await openPage(); const pre = page.consoleMsgs.length; await setFields(page, cond); const text = await run(page); const p = parse(text);
  const known = /^(-- .+ --|== .+ ==|\s+(給与|退職後収入|年金|生活費|現金|投資|▶|🔄).*)$/;
  const other = p.lines.filter(l => !known.test(l));
  const neg = p.months.filter(b => balance(b).total < 0);
  save('Q-011_結果の抜き出し.txt', header('Q-011 開始時貯金0円、開始時投資残高100,000円、年収0円、投資率0%(利回り4%は初期値)。1か月目で資金が尽きる', { text: JSON.stringify(cond) }) +
    excerpt(p, ['30歳1月', '30歳2月', '30歳12月', '31歳1月', '100歳12月']) +
    '\n# 31歳1月の投資利息の行: ' + (p.interest[0] || '(なし)') +
    `\n# 総資産がマイナスの月の数: ${neg.length} / ${p.months.length}(最初: ${neg[0] && neg[0].h}、最後: ${neg.length && neg[neg.length - 1].h})` +
    `\n# 月の行・利息の行のどれにも当てはまらない行(知らせの文など)の数: ${other.length}${other.length ? '\n' + other.slice(0, 10).join('\n') : ''}` +
    `\n# ダイアログ: ${page.dialogs.length ? page.dialogs.join(' / ') : 'なし'}` +
    `\n# 「開始」の後のコンソール: ${page.consoleMsgs.slice(pre).join(' / ') || 'なし'}\n`);
  await shot(page, 'Q-011_1_資金が尽きる_30歳1月から.png', '30歳1月');
  await shot(page, 'Q-011_2_資金が尽きた後_100歳12月.png', '100歳12月');
};

Q['Q-012'] = async () => {
  let out = '';
  const cases = [
    ['(a) 同じ45歳で 6,000,000円 → 4,000,000円 の順に追加', [[45, 6000000], [45, 4000000]], ['44歳12月', '45歳1月', '46歳1月']],
    ['(b) 同じ45歳で 4,000,000円 → 6,000,000円 の順に追加', [[45, 4000000], [45, 6000000]], ['44歳12月', '45歳1月', '46歳1月']],
    ['(c) 年齢の順でなく (55歳, 6,000,000円) → (35歳, 4,000,000円) の順に追加', [[55, 6000000], [35, 4000000]], ['34歳12月', '35歳1月', '54歳12月', '55歳1月']],
    ['(d) 退職年齢(65)以降の (70歳, 6,000,000円)', [[70, 6000000]], ['64歳12月', '65歳1月', '70歳1月']],
    ['(e) 開始年齢(30)より前の (20歳, 6,000,000円)', [[20, 6000000]], ['30歳1月', '64歳12月']],
  ];
  let i = 0;
  for (const [title, ch, heads] of cases) {
    i++;
    const page = await openPage(); await addChanges(page, ch); const p = parse(await run(page));
    const tag = p.months.filter(b => b.lines[0].includes('[年収'));
    out += header('Q-012 ' + title, { text: '給与変更 ' + JSON.stringify(ch) + '。ほかは初期値(年収3,000,000円、退職年齢65)' }) + excerpt(p, heads) +
      `\n# [年収: …] が付いた月の数: ${tag.length}${tag.length ? `(最初 ${tag[0].h}、最後 ${tag[tag.length - 1].h})` : ''}\n\n`;
    await shot(page, `Q-012_${i}_${title.slice(1, 2)}.png`, heads[0]);
  }
  // 比べるための、給与変更なしの実行
  for (const S of [4000000, 6000000]) { const page = await openPage(); await setFields(page, { salary: S }); const p = parse(await run(page)); out += `# 比較用の実行: 年収 ${S}、給与変更なし → 30歳1月 ${p.map['30歳1月'].lines[0]}\n`; }
  save('Q-012_結果の抜き出し.txt', out);
};

Q['Q-013'] = async () => {
  let out = '';
  const cases = [
    ['(a) (45歳, 6,000,000円)', [[45, 6000000]]],
    ['(b) 基本年収と同じ額 (45歳, 3,000,000円)', [[45, 3000000]]],
    ['(c) (45歳, 6,000,000円) と (50歳, 3,000,000円)(基本年収と同じ額に戻す)', [[45, 6000000], [50, 3000000]]],
  ];
  let i = 0;
  for (const [title, ch] of cases) {
    i++;
    const page = await openPage(); await addChanges(page, ch); const p = parse(await run(page));
    const tag = p.months.filter(b => b.lines[0].includes('[年収'));
    const ages = [...new Set(tag.map(b => b.h.match(/^(\d+)歳/)[1]))];
    out += header('Q-013 ' + title, { text: '給与変更 ' + JSON.stringify(ch) + '。ほかは初期値(年収3,000,000円、退職年齢65)' }) +
      excerpt(p, ['44歳12月', '45歳1月', '45歳2月', '49歳12月', '50歳1月', '64歳12月']) +
      `\n# [年収: …] が付いた月の数: ${tag.length}${tag.length ? `(最初 ${tag[0].h}、最後 ${tag[tag.length - 1].h}、年齢 ${ages[0]}〜${ages[ages.length - 1]}歳)` : ''}\n\n`;
    await shot(page, `Q-013_${i}_${title.slice(1, 2)}_44歳12月から.png`, '44歳12月');
  }
  save('Q-013_結果の抜き出し.txt', out);
};

Q['Q-014'] = Q['Q-015'] = async () => {
  if (Q.__evtDone) return; Q.__evtDone = true;
  let out = '# Q-014・Q-015 乱数は差し替えない。イベント発生率だけを変えて「開始」(ほかは初期値)\n';
  out += '発生率(%)\t実行\t月の数\t▶の行の数\t▶が2行以上の月の数\t▶が1行の月の数\n';
  const kinds = {};
  for (const prob of [0, 50, 100]) {
    const page = await openPage({ stub: '差し替えない' }); await setFields(page, { eventProb: prob });
    for (let r = 1; r <= 3; r++) {
      const p = parse(await run(page));
      let total = 0, multi = 0, one = 0;
      for (const b of p.months) { const e = b.lines.filter(l => l.startsWith('▶')); total += e.length; if (e.length >= 2) multi++; if (e.length === 1) one++; for (const l of e) { const m = l.match(/^▶ (.+): ¥([\d,]+)$/); const k = `${m[1]}\t${m[2]}`; kinds[k] = (kinds[k] || 0) + 1; } }
      out += `${prob}\t${r}\t${p.months.length}\t${total}\t${multi}\t${one}\n`;
      if (r === 1 && prob === 100) { await shot(page, 'Q-014_1_発生率100_30歳1月から.png', '30歳1月'); save('Q-014_発生率100の結果全体.txt', header('Q-014 発生率100%の1回目の結果の欄', { stub: '差し替えない', text: '{"eventProb":100}' }) + p.lines.join('\n')); }
      if (r === 1 && prob === 0) await shot(page, 'Q-015_1_発生率0_30歳1月から.png', '30歳1月');
    }
  }
  out += '\n# 出た突発的な支出の種類と額(9回の実行の合計)\n名前\t額\t出た回数\n' + Object.entries(kinds).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${k}\t${n}`).join('\n') + '\n';
  save('Q-014_Q-015_突発的な支出.tsv', out);
};

Q['Q-016'] = async () => {
  let out = '# Q-016 ありえない値を1つずつ入れて「開始」(乱数は支出なし、ほかは初期値)。画面に出た知らせ・欄の状態・結果を記録した\n';
  const rec = async (title, fn, heads, shotName) => {
    const page = await openPage(); const pre = page.consoleMsgs.length;
    await fn(page);
    const before = await inputs(page);
    const validity = await page.evaluate(() => [...document.querySelectorAll('input[type=number]')].filter(e => !e.validity.valid).map(e => (e.id || e.className) + ':' + JSON.stringify(e.value) + (e.validity.badInput ? '(badInput)' : '') + (e.validity.rangeUnderflow ? '(min未満)' : '') + (e.validity.rangeOverflow ? '(max超え)' : '')).join(', '));
    const text = await run(page); const p = parse(text);
    const bodyText = await page.evaluate(() => document.body.innerText.replace(document.getElementById('output').innerText, ''));
    out += `\n## ${title}\n# 「開始」の前の欄の値: ${before}\n# 不正な値の状態の欄: ${validity || 'なし'}\n# ダイアログ: ${page.dialogs.join(' / ') || 'なし'}\n# 「開始」の後のコンソール: ${page.consoleMsgs.slice(pre).join(' / ') || 'なし'}\n# 結果の欄の外の文字に「エラー」「不正」「入力」を含む行: ${bodyText.split('\n').filter(l => /エラー|不正|入力/.test(l)).join(' / ') || 'なし'}\n# 月の数: ${p.months.length}(最初 ${p.months[0] && p.months[0].h}、最後 ${p.months.length && p.months[p.months.length - 1].h})\n` + excerpt(p, heads) + '\n';
    if (shotName) await shot(page, shotName, heads[0]);
  };
  await rec('(1) 負の金額: 開始時貯金 −500,000', pg => setFields(pg, { initialCash: -500000 }), ['30歳1月'], 'Q-016_1_開始時貯金マイナス.png');
  await rec('(2) 100%を超える投資率: 150', pg => setFields(pg, { investRate: 150 }), ['30歳1月', '30歳2月'], 'Q-016_2_投資率150.png');
  await rec('(3) 小数の年齢: 退職年齢 60.5', pg => setFields(pg, { retirementAge: 60.5 }), ['60歳12月', '61歳1月'], 'Q-016_3_退職年齢60.5.png');
  await rec('(4) 小数の年齢: 開始年齢 30.5', pg => setFields(pg, { startAge: 30.5 }), ['30.5歳1月'], null);
  await rec('(5) 空欄: 開始時貯金', pg => setFields(pg, { initialCash: null }), ['30歳1月'], 'Q-016_4_開始時貯金空欄.png');
  await rec('(6) 空欄: 開始年齢', pg => setFields(pg, { startAge: null }), ['0歳1月'], null);
  await rec('(7) 開始年齢が退職年齢より後: 開始年齢 70(退職年齢65・年金開始年齢65)', pg => setFields(pg, { startAge: 70 }), ['70歳1月'], 'Q-016_5_開始年齢70.png');
  await rec('(8) 数字でない文字: 年金月額に abc をキーで打つ', async pg => { await pg.fill('#monthlyPension', ''); await pg.locator('#monthlyPension').pressSequentially('abc'); }, ['65歳1月'], 'Q-016_6_年金月額abc.png');
  await rec('(9) 給与変更を追加しただけ(年齢も年収も空)', pg => addChanges(pg, [[null, null]]), ['30歳1月', '45歳1月'], null);
  await rec('(10) 給与変更の年齢だけ空(年収 6,000,000)', pg => addChanges(pg, [[null, 6000000]]), ['30歳1月', '45歳1月'], null);
  await rec('(11) 給与変更の年収だけ空(年齢 45)', pg => addChanges(pg, [[45, null]]), ['30歳1月', '45歳1月'], 'Q-016_7_給与変更の年収が空.png');
  save('Q-016_ありえない値.txt', out);
};

Q['Q-017'] = async () => {
  let out = '# Q-017 結果の各月の「現金」「投資」「総資産」の関係\n';
  for (const [title, cond] of [['初期値', {}], ['資金が尽きる条件(Q-011 と同じ)', { initialCash: 0, initialInv: 100000, salary: 0, investRate: 0 }], ['取り崩しが続く条件(Q-010 と同じ)', { initialCash: 0, initialInv: 1000000, salary: 0, investRate: 0, interest: 0 }]]) {
    const page = await openPage(); await setFields(page, cond); const p = parse(await run(page));
    let ok = 0, maxd = 0; const bad = [];
    for (const b of p.months) { const v = balance(b); const d = Math.abs(v.total - (v.cash + v.inv)); maxd = Math.max(maxd, d); if (d <= 1) ok++; else bad.push(b.h); }
    out += `\n## ${title} ${JSON.stringify(cond)}\n# 月の数 ${p.months.length}、「総資産」と「現金+投資」の差が1円以内の月 ${ok}、差の最大 ${maxd} 円${bad.length ? '、合わない月 ' + bad.slice(0, 5).join(',') : ''}\n` +
      excerpt(p, ['30歳1月', '64歳12月', '100歳12月']) + '\n';
    if (title === '初期値') await shot(page, 'Q-017_1_初期値_30歳1月から.png', '30歳1月');
  }
  save('Q-017_総資産.txt', out);
};

Q['Q-018'] = async () => {
  const page = await openPage();
  const res = await page.goto('http://localhost:8000/test_retirement_simulator.html');
  save('Q-018_付属のテストファイル.txt', `# Q-018 配信中の場所に README の付属ファイルを要求した\nGET http://localhost:8000/test_retirement_simulator.html → HTTP ${res.status()}\n`);
};

Q['Q-020'] = async () => {
  let out = '';
  // (1) 入力欄のラベル(単位が画面に出ているか)
  let page = await openPage();
  await page.click('#toggleSalaryChanges'); await page.click('#addSalaryChange');
  const labels = await page.evaluate(() => [...document.querySelectorAll('#controls input[type=number]')].map(e => (e.id || e.className) + '\t' + e.closest('label').textContent.replace(/\s+/g, ' ').trim()));
  out += '# (1) 入力欄とラベルの文字(給与変更の欄は1つ追加して読んだ)\n' + labels.join('\n') + '\n';
  await shot(page, 'Q-020_1_入力欄のラベル.png');
  // (2) 同じ条件で2回「開始」(乱数は差し替えない)
  page = await openPage({ stub: '差し替えない' });
  const t1 = await run(page); const t2 = await run(page);
  const pageText = await page.evaluate(() => document.body.innerText.replace(document.getElementById('output').innerText, ''));
  const ev = t => t.split('\n').filter(l => l.trim().startsWith('▶')).length;
  out += `\n# (2) 初期値のまま、同じ画面で「開始」を2回(乱数は差し替えない)\n1回目と2回目の結果の欄が同じか: ${t1 === t2 ? '同じ' : '違う'}\n▶の行の数: 1回目 ${ev(t1)}、2回目 ${ev(t2)}\n100歳12月の残高の行: 1回目 ${parse(t1).map['100歳12月'].lines.slice(-1)[0]} / 2回目 ${parse(t2).map['100歳12月'].lines.slice(-1)[0]}\n結果の欄の外の文字に「乱数」「ランダム」「確率」「毎回」「変わ」を含む行: ${pageText.split('\n').filter(l => /乱数|ランダム|確率|毎回|変わ/.test(l)).join(' / ') || 'なし'}\n`;
  // (3) 給与変更を入れてから非表示にして「開始」
  page = await openPage();
  await addChanges(page, [[45, 6000000]]); await page.click('#toggleSalaryChanges');
  const vis = await page.isVisible('#salaryChanges');
  const p = parse(await run(page)); const tag = p.months.filter(b => b.lines[0].includes('[年収'));
  out += `\n# (3) 給与変更 (45歳, 6,000,000円) を入れてから「給与変更設定を表示/非表示」で隠し、「開始」\n給与変更設定の欄が見えているか: ${vis ? '見えている' : '見えていない'}\n[年収: …] が付いた月の数: ${tag.length}(最初 ${tag[0] && tag[0].h})\n` + excerpt(p, ['44歳12月', '45歳1月']) + '\n';
  await shot(page, 'Q-020_2_非表示で開始_44歳12月から.png', '44歳12月');
  save('Q-020_画面からわかるか.txt', out);
};

Q['Q-021'] = async () => {
  let out = '';
  const cond = { initialCash: 0, investRate: 50 };
  let page = await openPage(); await setFields(page, cond); let p = parse(await run(page));
  out += header('Q-021 (A) 開始時貯金0円、投資率50%(年収3,000,000円・生活費155,600円は初期値)', { text: JSON.stringify(cond) }) + excerpt(p, ['30歳1月', '30歳2月']) + '\n\n';
  await shot(page, 'Q-021_1_投資率50_30歳1月から.png', '30歳1月');
  out += '# (B) 投資率だけを変えた(ほかは初期値、乱数は支出なし)\n投資率(%)\t取り崩しの行(🔄)がある月の数\t最初に🔄が出た月\t64歳12月の残高の行\t総資産が最初にマイナスになった月\n';
  for (const r of [0, 10, 20, 30, 40, 50, 60, 70]) {
    page = await openPage(); await setFields(page, { investRate: r }); p = parse(await run(page));
    const dr = p.months.filter(b => b.lines.some(l => l.startsWith('🔄')));
    const neg = p.months.find(b => balance(b).total < 0);
    out += `${r}\t${dr.length}\t${dr[0] ? dr[0].h : 'なし'}\t${p.map['64歳12月'].lines.slice(-1)[0]}\t${neg ? neg.h : 'なし'}\n`;
  }
  save('Q-021_投資と取り崩し.txt', out);
};

Q['Q-022'] = async () => {
  let out = '';
  // 狭い画面
  let page = await openPage({ viewport: { width: 375, height: 812 } });
  await run(page);
  const w = await page.evaluate(() => ({ innerWidth: innerWidth, scrollWidth: document.documentElement.scrollWidth, outputWidth: Math.round(document.getElementById('output').getBoundingClientRect().width), outputRight: Math.round(document.getElementById('output').getBoundingClientRect().right) }));
  out += `# (1) 幅375×高さ812で開き、初期値で「開始」\n${JSON.stringify(w)}\n`;
  await shot(page, 'Q-022_1_幅375.png');
  // キーボードだけ
  page = await openPage();
  const seq = [];
  for (let i = 0; i < 20; i++) { await page.keyboard.press('Tab'); seq.push(await page.evaluate(() => { const e = document.activeElement; return e.id || e.className || e.tagName; })); }
  out += `\n# (2) 開いた直後から Tab を20回押したときに、フォーカスが移った順\n${seq.join(' → ')}\n`;
  await page.focus('#runBtn'); await page.keyboard.press('Enter');
  const afterEnter = ((await page.textContent('#output')) || '').length;
  await page.focus('#toggleSalaryChanges'); await page.keyboard.press('Space');
  const visSpace = await page.isVisible('#salaryChanges');
  out += `「開始」にフォーカスして Enter → 結果の欄の文字数 ${afterEnter}\n「給与変更設定を表示/非表示」にフォーカスして Space → 給与変更設定の欄が ${visSpace ? '見えた' : '見えない'}\n`;
  // 支援技術に伝わる情報(アクセシビリティツリー)
  page = await openPage(); await run(page);
  const outAttrs = await page.evaluate(() => { const o = document.getElementById('output'); return [...o.attributes].map(a => `${a.name}=${a.value}`).join(' ') + ` / role=${o.getAttribute('role')} aria-live=${o.getAttribute('aria-live')}`; });
  const snap = await page.locator('#controls').ariaSnapshot();
  out += `\n# (3) 結果の欄(#output)の属性: ${outAttrs}\n# 入力欄と「開始」のアクセシビリティツリー(Playwright の ariaSnapshot)\n${snap}\n`;
  save('Q-022_狭い画面とキーボードと支援技術.txt', out);
};

(async () => {
  const want = process.argv.slice(2);
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    for (const id of Object.keys(Q)) { if (id.startsWith('__')) continue; if (want.length && !want.includes(id)) continue; console.log('==', id); await Q[id](); }
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
