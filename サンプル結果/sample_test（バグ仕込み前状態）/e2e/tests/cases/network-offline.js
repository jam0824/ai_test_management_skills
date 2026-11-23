// TD-012(テストデータ/通信とオフライン.json): LTC-090、LTC-091、LTC-093〜LTC-095
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { HTTP_URL, FAVICON_URL, FILE_URL } = require('../lib/data');
const { block, previousBalance } = require('../lib/checks');
const { INPUT_IDS } = require('../lib/env');

const FILE = '通信とオフライン.json';

/**
 * 全部の操作: 14項目に値を入れる → 表示 → 「➕ 給与変更を追加」を2回クリックして入れる → 2つ目の「削除」
 * → 非表示 → 「開始」(ローレベルテストケースの操作)
 */
async function allOperations(screen, data) {
  await screen.setConditions(data.条件);
  await screen.toggleSalaryChanges();
  await expect(screen.salaryPanel()).toBeVisible();
  for (let i = 0; i < data.給与変更.length; i++) await screen.clickAddSalaryChange();
  for (const [i, change] of data.給与変更.entries()) await screen.fillSalaryChange(i, change);
  await screen.deleteSalaryChange(1); // 2つ目の「削除」
  await screen.toggleSalaryChanges();
  await expect(screen.salaryPanel()).toBeHidden();
  return screen.start({ label: '全部の操作の「開始」' });
}

/** 1回目の「開始」の結果に、突発的な支出・取り崩し・利息がすべて出ていることを確かめる(LTC-090・LTC-091 の備考) */
function requireAllFeaturesShown(result) {
  const hasEvent = result.months.some((m) => m.events.length > 0);
  const hasDraw = result.months.some((m) => m.invest < previousBalance(result, m).invest);
  const hasInterest = result.months.some((m) => m.age >= 61 && result.prev(m) && m.invest > result.prev(m).invest);
  if (!hasEvent || !hasDraw || !hasInterest) {
    block(`1回目の「開始」の結果に、突発的な支出(${hasEvent})・取り崩し(${hasDraw})・利息(${hasInterest})のすべてが出ていない`);
  }
}

/** ネットワークの要求(WebSocket を含む)を、画面を開く前からすべて記録する */
function recordRequests(list) {
  return async (context, page) => {
    context.on('request', (r) => list.push({ kind: 'request', url: r.url() }));
    page.on('websocket', (ws) => list.push({ kind: 'websocket', url: ws.url() }));
  };
}

/** 全部の操作をして、最後に開始年齢を変えてもう一度「開始」する(LTC-090・LTC-091) */
async function operateAndRestart(screen, data) {
  const first = await allOperations(screen, data);
  requireAllFeaturesShown(first);
  await screen.setConditions({ startAge: 35 }); // 操作: 開始年齢を 35 にして「開始」(ローレベルテストケースの操作)
  await screen.start({ label: '開始年齢を変えた「開始」' });
}

/** 14項目の入力欄と「開始」が表示される */
async function expectInputsShown(screen) {
  for (const id of INPUT_IDS) await expect(screen.input(id), `入力欄 #${id} が表示される`).toBeVisible();
  await expect(screen.page.locator('#runBtn'), '「開始」が表示される').toBeVisible();
}

module.exports = [
  defineCase(FILE, 'LTC-090', async (env, data) => {
    const recorded = [];
    const screen = await env.open({ url: HTTP_URL, random: data.乱数, beforeGoto: recordRequests(recorded) });
    await operateAndRestart(screen, data);
    const urls = recorded.map((r) => `${r.kind} ${r.url}`);
    // favicon はテスト対象が出す要求ではないので除く(ローレベルテストケースの備考)
    const others = recorded.filter((r) => !(r.kind === 'request' && r.url === FAVICON_URL));
    expect(others.map((r) => `${r.kind} ${r.url}`), `記録した要求が ${HTTP_URL} の1件と favicon だけ(記録: ${urls.join(', ')})`).toEqual([`request ${HTTP_URL}`]);
    const outside = recorded.filter((r) => new URL(r.url).host !== 'localhost:8000');
    expect(outside.map((r) => r.url), 'localhost:8000 以外への要求が0件').toEqual([]);
  }),

  defineCase(FILE, 'LTC-091', async (env, data) => {
    const recorded = [];
    const screen = await env.open({ url: FILE_URL, random: data.乱数, beforeGoto: recordRequests(recorded) });
    await operateAndRestart(screen, data);
    const network = recorded.filter((r) => /^(https?|wss?):/i.test(r.url));
    expect(network.map((r) => `${r.kind} ${r.url}`), `記録した要求のうち、http・https・ws・wss の要求が0件(記録: ${recorded.map((r) => r.url).join(', ')})`).toEqual([]);
  }),

  defineCase(FILE, 'LTC-093', async (env, data) => {
    const screen = await env.open({ url: FILE_URL, random: data.乱数, offline: true, label: 'オフラインの file://' });
    await expectInputsShown(screen);
    const offline = await allOperations(screen, data);
    const online = await allOperations(await env.open({ url: FILE_URL, random: data.乱数, label: 'オンラインの file://' }), data);
    expect(offline.text, '(2) 結果の欄の内容が、比較用の実行(オンラインのまま file:// で同じ操作)と一致する').toBe(online.text);
  }),

  defineCase(FILE, 'LTC-094', async (env, data) => {
    const screen = await env.open({ url: HTTP_URL, random: data.乱数, label: '開いた後にオフライン' });
    await screen.context.setOffline(true); // 事前条件: 開いた後、オフラインの設定にする
    const offline = await allOperations(screen, data);
    const online = await allOperations(await env.open({ url: HTTP_URL, random: data.乱数, label: 'オンラインの http' }), data);
    expect(offline.text, '結果の欄の内容が、比較用の実行(オンラインのまま http で同じ操作)と一致する').toBe(online.text);
  }),

  defineCase(FILE, 'LTC-095', async (env, data) => {
    const screen = await env.open({ url: FILE_URL, random: data.乱数, label: 'file://' });
    await expectInputsShown(screen);
    const result = await screen.start();
    const comparison = await (await env.open({ url: HTTP_URL, random: data.乱数, label: 'http' })).start();
    expect(result.text, '(2) 結果の欄の内容が、比較用の実行(http で開いて初期値のまま「開始」)と一致する').toBe(comparison.text);
  }),
];
