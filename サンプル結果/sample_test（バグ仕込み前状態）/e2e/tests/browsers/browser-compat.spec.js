// TD-015(テストデータ/ブラウザ.json): LTC-096(Chrome)、LTC-097(Edge)、LTC-098(Playwright の Firefox)
// TD-015 のローレベルテストケースを、それぞれのブラウザで、ほかのテストと同じ定義(cases/)のまま流す。
// LTC-097・LTC-098 は LTC-096 が保存した結果の欄の内容と比べるので、このファイルは書いた順に流す(設定ファイルの browser-compat)。
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const { test, expect } = require('@playwright/test');
const { byId } = require('../cases');
const { Env } = require('../lib/env');
const { isBlock, block } = require('../lib/checks');
const { loadTestData, caseData, targetSha256 } = require('../lib/data');
const { parseOutput } = require('../lib/output');

const td = loadTestData('ブラウザ.json');
// LTC-096 の結果の欄の内容を保存する場所(outputDir の外。Playwright の実行のたびに消されないように)
const SAVED_FILE = path.resolve(__dirname, '..', '..', 'saved', 'LTC-096_chrome_結果の欄.json.gz');
// (3) の金額の書き方(LTC-096 の期待値の正規表現)
const YEN_FORMAT = /^¥-?\d{1,3}(,\d{3})*(\.\d+)?$/;

// 書いた順に流す(1件が失敗しても、続きのテストは流れる)。1件で TD-015 のテストケースをすべて流すので、時間の上限を長くする
test.describe.configure({ mode: 'default', timeout: 90 * 60 * 1000 });

/** JST の日時(yyyy-MM-dd HH:mm:ss) */
function nowJst() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** TD-015 のローレベルテストケースを、そのブラウザで1件ずつ流す */
async function runAll(browser, testInfo) {
  const results = {};
  for (const id of td.流すローレベルテストケース) {
    const c = byId.get(id);
    if (!c) throw new Error(`${id} の定義が無い`);
    const env = new Env(browser, testInfo, id, { screenshots: true });
    env.keepText = true;
    let status = 'passed';
    let message = '';
    try {
      await test.step(c.title, async () => c.run(env));
    } catch (err) {
      status = isBlock(err) ? 'blocked' : 'failed';
      message = String(err.message).split('\n').find((l) => l.trim()) || '';
    }
    await env.dispose(status !== 'passed');
    results[id] = { status, message, outputs: env.outputs };
  }
  return results;
}

/** (1)〜(3) の確認。(1) 流したテストケースがそれぞれの期待値を満たす (2) LTC-020 の入れた値 (3) 金額の桁区切り */
function checkCommon(results, prefix) {
  const failed = Object.entries(results).filter(([, r]) => r.status === 'failed').map(([id, r]) => `${id}: ${r.message}`);
  expect.soft(failed, `${prefix} (1) 流したローレベルテストケースが、それぞれの期待値を満たす`).toEqual([]);

  const c020 = caseData('期間.json', 'LTC-020').条件;
  const out020 = (results['LTC-020'] || { outputs: [] }).outputs[0];
  const first = out020 ? parseOutput(out020.text).at(30, 1) : undefined;
  expect.soft(first && [first.cash, first.invest], `${prefix} (2) LTC-020 で入れた開始時貯金・開始時投資残高が、30歳1月の現金・投資にそのまま出る`)
    .toEqual([c020.initialCash, c020.initialInv]);

  const badFormat = [];
  for (const [id, r] of Object.entries(results)) {
    for (const o of r.outputs) {
      for (const token of o.text.match(/¥[^\s()[\]]*/g) || []) {
        if (!YEN_FORMAT.test(token)) badFormat.push(`${id} ${o.label}: ${token}`);
      }
    }
  }
  expect.soft([...new Set(badFormat)].slice(0, 50), `${prefix} (3) 結果の欄の金額が、どれも ¥ の後に3桁ごとに , で区切った数字`).toEqual([]);
}

/** ブロックだけが残ったときは判定せず、ブロックにする */
function finish(results, testInfo, extraBlocked = []) {
  if (testInfo.errors.length) return; // 期待値を満たさないものがあった(上の expect.soft で失敗にしている)
  const blocked = Object.entries(results).filter(([, r]) => r.status === 'blocked').map(([id, r]) => `${id}: ${r.message}`);
  if (blocked.length || extraBlocked.length) block(`判定できないものがある: ${[...extraBlocked, ...blocked].join(' / ')}`);
}

async function attachSummary(testInfo, results) {
  const summary = Object.fromEntries(Object.entries(results).map(([id, r]) => [id, { status: r.status, message: r.message, 結果の欄: r.outputs.length }]));
  await testInfo.attach('cases.json', { body: JSON.stringify(summary, null, 2), contentType: 'application/json' });
}

/** LTC-097・LTC-098: LTC-096 と同じ確認と、(4) Chrome で保存した内容との一致 */
async function compareWithChrome(browser, testInfo, label) {
  const results = await runAll(browser, testInfo);
  await attachSummary(testInfo, results);
  checkCommon(results, label);
  const extraBlocked = [];
  if (!fs.existsSync(SAVED_FILE)) {
    extraBlocked.push(`(4) LTC-096 の結果の欄の内容が保存されていない(${SAVED_FILE})`);
  } else {
    const saved = JSON.parse(zlib.gunzipSync(fs.readFileSync(SAVED_FILE)).toString('utf-8'));
    if (saved.targetSha256 !== targetSha256()) {
      extraBlocked.push('(4) LTC-096 で保存したときとテスト対象のファイルが違う(SHA-256 が違う)');
    } else {
      const notCompared = new Set(td.結果を比べないローレベルテストケース);
      const diff = [];
      for (const id of td.流すローレベルテストケース.filter((x) => !notCompared.has(x))) {
        const chrome = (saved.cases[id] || { outputs: [] }).outputs;
        const mine = results[id].outputs;
        if (chrome.length !== mine.length) diff.push(`${id}: 結果の欄を読んだ数が違う(Chrome ${chrome.length}、${label} ${mine.length})`);
        chrome.forEach((o, i) => {
          if (mine[i] && mine[i].sha256 !== o.sha256) diff.push(`${id}: ${o.label} の内容が Chrome と違う`);
        });
      }
      expect.soft(diff, `${label} (4) 乱数を差し替えたテストケースのそれぞれで、結果の欄の内容が LTC-096(Chrome、${saved.createdAt} に保存)と一致する`).toEqual([]);
    }
  }
  finish(results, testInfo, extraBlocked);
}

const t096 = caseData('ブラウザ.json', 'LTC-096');
test(`LTC-096 ${t096.テストケース}`, async ({ playwright }, testInfo) => {
  // 3つのテストで同じ扱いにするため、どのブラウザもテストの中で起動する(インストール済みの Chrome)
  const chrome = await playwright.chromium.launch({ channel: 'chrome' });
  try {
    const results = await runAll(chrome, testInfo);
    // 期待値を確かめる前に、LTC-097・LTC-098 で比べるための結果の欄の内容を保存する(LTC-096 の備考)
    const saved = {
      browser: `Chrome ${chrome.version()}`, createdAt: nowJst(), targetSha256: targetSha256(),
      cases: Object.fromEntries(Object.entries(results).map(([id, r]) => [id, { status: r.status, outputs: r.outputs }])),
    };
    fs.mkdirSync(path.dirname(SAVED_FILE), { recursive: true });
    fs.writeFileSync(SAVED_FILE, zlib.gzipSync(JSON.stringify(saved)));
    await testInfo.attach('LTC-096_chrome_結果の欄.json.gz', { path: SAVED_FILE, contentType: 'application/gzip' });
    await attachSummary(testInfo, results);
    checkCommon(results, `Chrome ${chrome.version()}`);
    finish(results, testInfo);
  } finally {
    await chrome.close();
  }
});

const t097 = caseData('ブラウザ.json', 'LTC-097');
test(`LTC-097 ${t097.テストケース}`, async ({ playwright }, testInfo) => {
  const edge = await playwright.chromium.launch({ channel: 'msedge' });
  try {
    await compareWithChrome(edge, testInfo, `Edge ${edge.version()}`);
  } finally {
    await edge.close();
  }
});

const t098 = caseData('ブラウザ.json', 'LTC-098');
test(`LTC-098 ${t098.テストケース}`, async ({ playwright }, testInfo) => {
  const firefox = await playwright.firefox.launch();
  try {
    await compareWithChrome(firefox, testInfo, `Firefox ${firefox.version()}`);
  } finally {
    await firefox.close();
  }
});
