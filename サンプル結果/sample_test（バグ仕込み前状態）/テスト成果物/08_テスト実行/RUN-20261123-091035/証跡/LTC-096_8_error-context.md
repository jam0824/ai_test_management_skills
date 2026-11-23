# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: browsers\browser-compat.spec.js >> LTC-096 Chrome で、数値の入力欄・桁区切りの表示・計算結果が動く
- Location: tests\browsers\browser-compat.spec.js:116:1

# Error details

```
Error: Chrome 157.0.8103.79 (1) 流したローレベルテストケースが、それぞれの期待値を満たす

expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 7

- Array []
+ Array [
+   "LTC-055: すべての月で、投資が0円以上",
+   "LTC-056: すべての月で、投資が0円以上",
+   "LTC-057: すべての月で、投資が0円以上",
+   "LTC-058: すべての月で、投資が0円以上",
+   "LTC-070: 46歳1月〜64歳12月のすべての月で、給与の額が ¥0 で、投資が前の月から増えない",
+ ]
```

# Test source

```ts
  1   | // TD-015(テストデータ/ブラウザ.json): LTC-096(Chrome)、LTC-097(Edge)、LTC-098(Playwright の Firefox)
  2   | // TD-015 のローレベルテストケースを、それぞれのブラウザで、ほかのテストと同じ定義(cases/)のまま流す。
  3   | // LTC-097・LTC-098 は LTC-096 が保存した結果の欄の内容と比べるので、このファイルは書いた順に流す(設定ファイルの browser-compat)。
  4   | const fs = require('fs');
  5   | const path = require('path');
  6   | const zlib = require('zlib');
  7   | const { test, expect } = require('@playwright/test');
  8   | const { byId } = require('../cases');
  9   | const { Env } = require('../lib/env');
  10  | const { isBlock, block } = require('../lib/checks');
  11  | const { loadTestData, caseData, targetSha256 } = require('../lib/data');
  12  | const { parseOutput } = require('../lib/output');
  13  | 
  14  | const td = loadTestData('ブラウザ.json');
  15  | // LTC-096 の結果の欄の内容を保存する場所(outputDir の外。Playwright の実行のたびに消されないように)
  16  | const SAVED_FILE = path.resolve(__dirname, '..', '..', 'saved', 'LTC-096_chrome_結果の欄.json.gz');
  17  | // (3) の金額の書き方(LTC-096 の期待値の正規表現)
  18  | const YEN_FORMAT = /^¥-?\d{1,3}(,\d{3})*(\.\d+)?$/;
  19  | 
  20  | // 書いた順に流す(1件が失敗しても、続きのテストは流れる)。1件で TD-015 のテストケースをすべて流すので、時間の上限を長くする
  21  | test.describe.configure({ mode: 'default', timeout: 90 * 60 * 1000 });
  22  | 
  23  | /** JST の日時(yyyy-MM-dd HH:mm:ss) */
  24  | function nowJst() {
  25  |   const d = new Date();
  26  |   const p = (n) => String(n).padStart(2, '0');
  27  |   return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  28  | }
  29  | 
  30  | /** TD-015 のローレベルテストケースを、そのブラウザで1件ずつ流す */
  31  | async function runAll(browser, testInfo) {
  32  |   const results = {};
  33  |   for (const id of td.流すローレベルテストケース) {
  34  |     const c = byId.get(id);
  35  |     if (!c) throw new Error(`${id} の定義が無い`);
  36  |     const env = new Env(browser, testInfo, id, { screenshots: true });
  37  |     env.keepText = true;
  38  |     let status = 'passed';
  39  |     let message = '';
  40  |     try {
  41  |       await test.step(c.title, async () => c.run(env));
  42  |     } catch (err) {
  43  |       status = isBlock(err) ? 'blocked' : 'failed';
  44  |       message = String(err.message).split('\n').find((l) => l.trim()) || '';
  45  |     }
  46  |     await env.dispose(status !== 'passed');
  47  |     results[id] = { status, message, outputs: env.outputs };
  48  |   }
  49  |   return results;
  50  | }
  51  | 
  52  | /** (1)〜(3) の確認。(1) 流したテストケースがそれぞれの期待値を満たす (2) LTC-020 の入れた値 (3) 金額の桁区切り */
  53  | function checkCommon(results, prefix) {
  54  |   const failed = Object.entries(results).filter(([, r]) => r.status === 'failed').map(([id, r]) => `${id}: ${r.message}`);
> 55  |   expect.soft(failed, `${prefix} (1) 流したローレベルテストケースが、それぞれの期待値を満たす`).toEqual([]);
      |                                                                     ^ Error: Chrome 157.0.8103.79 (1) 流したローレベルテストケースが、それぞれの期待値を満たす
  56  | 
  57  |   const c020 = caseData('期間.json', 'LTC-020').条件;
  58  |   const out020 = (results['LTC-020'] || { outputs: [] }).outputs[0];
  59  |   const first = out020 ? parseOutput(out020.text).at(30, 1) : undefined;
  60  |   expect.soft(first && [first.cash, first.invest], `${prefix} (2) LTC-020 で入れた開始時貯金・開始時投資残高が、30歳1月の現金・投資にそのまま出る`)
  61  |     .toEqual([c020.initialCash, c020.initialInv]);
  62  | 
  63  |   const badFormat = [];
  64  |   for (const [id, r] of Object.entries(results)) {
  65  |     for (const o of r.outputs) {
  66  |       for (const token of o.text.match(/¥[^\s()[\]]*/g) || []) {
  67  |         if (!YEN_FORMAT.test(token)) badFormat.push(`${id} ${o.label}: ${token}`);
  68  |       }
  69  |     }
  70  |   }
  71  |   expect.soft([...new Set(badFormat)].slice(0, 50), `${prefix} (3) 結果の欄の金額が、どれも ¥ の後に3桁ごとに , で区切った数字`).toEqual([]);
  72  | }
  73  | 
  74  | /** ブロックだけが残ったときは判定せず、ブロックにする */
  75  | function finish(results, testInfo, extraBlocked = []) {
  76  |   if (testInfo.errors.length) return; // 期待値を満たさないものがあった(上の expect.soft で失敗にしている)
  77  |   const blocked = Object.entries(results).filter(([, r]) => r.status === 'blocked').map(([id, r]) => `${id}: ${r.message}`);
  78  |   if (blocked.length || extraBlocked.length) block(`判定できないものがある: ${[...extraBlocked, ...blocked].join(' / ')}`);
  79  | }
  80  | 
  81  | async function attachSummary(testInfo, results) {
  82  |   const summary = Object.fromEntries(Object.entries(results).map(([id, r]) => [id, { status: r.status, message: r.message, 結果の欄: r.outputs.length }]));
  83  |   await testInfo.attach('cases.json', { body: JSON.stringify(summary, null, 2), contentType: 'application/json' });
  84  | }
  85  | 
  86  | /** LTC-097・LTC-098: LTC-096 と同じ確認と、(4) Chrome で保存した内容との一致 */
  87  | async function compareWithChrome(browser, testInfo, label) {
  88  |   const results = await runAll(browser, testInfo);
  89  |   await attachSummary(testInfo, results);
  90  |   checkCommon(results, label);
  91  |   const extraBlocked = [];
  92  |   if (!fs.existsSync(SAVED_FILE)) {
  93  |     extraBlocked.push(`(4) LTC-096 の結果の欄の内容が保存されていない(${SAVED_FILE})`);
  94  |   } else {
  95  |     const saved = JSON.parse(zlib.gunzipSync(fs.readFileSync(SAVED_FILE)).toString('utf-8'));
  96  |     if (saved.targetSha256 !== targetSha256()) {
  97  |       extraBlocked.push('(4) LTC-096 で保存したときとテスト対象のファイルが違う(SHA-256 が違う)');
  98  |     } else {
  99  |       const notCompared = new Set(td.結果を比べないローレベルテストケース);
  100 |       const diff = [];
  101 |       for (const id of td.流すローレベルテストケース.filter((x) => !notCompared.has(x))) {
  102 |         const chrome = (saved.cases[id] || { outputs: [] }).outputs;
  103 |         const mine = results[id].outputs;
  104 |         if (chrome.length !== mine.length) diff.push(`${id}: 結果の欄を読んだ数が違う(Chrome ${chrome.length}、${label} ${mine.length})`);
  105 |         chrome.forEach((o, i) => {
  106 |           if (mine[i] && mine[i].sha256 !== o.sha256) diff.push(`${id}: ${o.label} の内容が Chrome と違う`);
  107 |         });
  108 |       }
  109 |       expect.soft(diff, `${label} (4) 乱数を差し替えたテストケースのそれぞれで、結果の欄の内容が LTC-096(Chrome、${saved.createdAt} に保存)と一致する`).toEqual([]);
  110 |     }
  111 |   }
  112 |   finish(results, testInfo, extraBlocked);
  113 | }
  114 | 
  115 | const t096 = caseData('ブラウザ.json', 'LTC-096');
  116 | test(`LTC-096 ${t096.テストケース}`, async ({ playwright }, testInfo) => {
  117 |   // 3つのテストで同じ扱いにするため、どのブラウザもテストの中で起動する(インストール済みの Chrome)
  118 |   const chrome = await playwright.chromium.launch({ channel: 'chrome' });
  119 |   try {
  120 |     const results = await runAll(chrome, testInfo);
  121 |     // 期待値を確かめる前に、LTC-097・LTC-098 で比べるための結果の欄の内容を保存する(LTC-096 の備考)
  122 |     const saved = {
  123 |       browser: `Chrome ${chrome.version()}`, createdAt: nowJst(), targetSha256: targetSha256(),
  124 |       cases: Object.fromEntries(Object.entries(results).map(([id, r]) => [id, { status: r.status, outputs: r.outputs }])),
  125 |     };
  126 |     fs.mkdirSync(path.dirname(SAVED_FILE), { recursive: true });
  127 |     fs.writeFileSync(SAVED_FILE, zlib.gzipSync(JSON.stringify(saved)));
  128 |     await testInfo.attach('LTC-096_chrome_結果の欄.json.gz', { path: SAVED_FILE, contentType: 'application/gzip' });
  129 |     await attachSummary(testInfo, results);
  130 |     checkCommon(results, `Chrome ${chrome.version()}`);
  131 |     finish(results, testInfo);
  132 |   } finally {
  133 |     await chrome.close();
  134 |   }
  135 | });
  136 | 
  137 | const t097 = caseData('ブラウザ.json', 'LTC-097');
  138 | test(`LTC-097 ${t097.テストケース}`, async ({ playwright }, testInfo) => {
  139 |   const edge = await playwright.chromium.launch({ channel: 'msedge' });
  140 |   try {
  141 |     await compareWithChrome(edge, testInfo, `Edge ${edge.version()}`);
  142 |   } finally {
  143 |     await edge.close();
  144 |   }
  145 | });
  146 | 
  147 | const t098 = caseData('ブラウザ.json', 'LTC-098');
  148 | test(`LTC-098 ${t098.テストケース}`, async ({ playwright }, testInfo) => {
  149 |   const firefox = await playwright.firefox.launch();
  150 |   try {
  151 |     await compareWithChrome(firefox, testInfo, `Firefox ${firefox.version()}`);
  152 |   } finally {
  153 |     await firefox.close();
  154 |   }
  155 | });
```