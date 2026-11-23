// 画面の開き方と、利用者と同じ画面からの操作。
// テストケースは「画面を開き直す」(比較用の実行など)ことが多いので、開くたびに新しいブラウザのコンテキストを作る。
// browser.newContext() を自分で開くと設定ファイルの video が効かないので、録画は recordVideo で指定し、
// 合格したら消す(retain-on-failure と同じ扱い)。失敗したときはスクリーンショットとコンソールの記録も添付する。
const fs = require('fs');
const crypto = require('crypto');
const { expect } = require('@playwright/test');
const { HTTP_URL, settings } = require('./data');
const { randomConfig, initScript } = require('./random');
const { parseOutput } = require('./output');
const { block } = require('./checks');

const INPUT_IDS = Object.keys(settings().項目); // 14項目の入力欄の id(TD-001)

class Env {
  /**
   * @param {import('@playwright/test').Browser} browser
   * @param {import('@playwright/test').TestInfo} testInfo
   * @param {string} prefix 証跡のファイル名の頭(ブラウザ互換のテストで、どのテストケースのものかを分ける)
   * @param {{ screenshots?: boolean }} [options] screenshots: 失敗したときに自分でスクリーンショットを撮る。
   *   テストの browser の fixture から開いた画面は設定ファイルの screenshot が撮るので、自分で起動したブラウザ(LTC-097・LTC-098)と
   *   1つのテストで多くのテストケースを流すとき(LTC-096〜LTC-098)だけ true にする
   */
  constructor(browser, testInfo, prefix = '', options = {}) {
    this.browser = browser;
    this.testInfo = testInfo;
    this.prefix = prefix;
    this.screenshots = Boolean(options.screenshots);
    this.contexts = [];
    this.logs = [];
    /** 読んだ結果の欄の内容の記録(LTC-096〜LTC-098 で、ブラウザどうしを比べるために使う)。text は keepText のときだけ持つ */
    this.outputs = [];
    this.keepText = false;
    this.videoDir = testInfo.outputPath(`videos${prefix ? '-' + prefix : ''}`);
  }

  /**
   * 画面を開く。
   * @param {object} o
   * @param {string} [o.url] 開くURL(既定は http)
   * @param {*} [o.random] ローレベルテストケースの「乱数」('支出なし' など。省くと差し替えない)
   * @param {boolean} [o.offline] 開く前からオフラインにする
   * @param {string} [o.label] 証跡と出力の記録に付ける名前
   * @param {(ctx: import('@playwright/test').BrowserContext, page: import('@playwright/test').Page) => Promise<void>} [o.beforeGoto]
   */
  async open(o = {}) {
    const label = o.label || `画面${this.contexts.length + 1}`;
    const context = await this.browser.newContext({ recordVideo: { dir: this.videoDir } });
    this.contexts.push(context);
    // 自分で起動したブラウザ(LTC-097・LTC-098)にも同じ待ち時間の上限を効かせる
    context.setDefaultTimeout(15 * 1000);
    context.setDefaultNavigationTimeout(30 * 1000);
    if (o.offline) await context.setOffline(true);
    const page = await context.newPage();
    page.on('console', (msg) => this.logs.push(`[${label}] console.${msg.type()}: ${msg.text()}`));
    page.on('pageerror', (err) => this.logs.push(`[${label}] pageerror: ${err.message}`));
    const cfg = randomConfig(o.random);
    if (cfg) await page.addInitScript({ content: initScript(cfg) });
    if (o.beforeGoto) await o.beforeGoto(context, page);
    await page.goto(o.url || HTTP_URL);
    await expect(page.locator('#runBtn')).toBeVisible();
    if (cfg) {
      // 差し替えが効いていなければ判定できない(TD-002 の差し替えの決まり)
      const name = await page.evaluate(() => (window.__e2eRandom ? window.__e2eRandom.name : null));
      if (name !== cfg.name) block(`乱数の差し替え(${cfg.name})が効いていない`);
    }
    return new Screen(this, context, page, cfg, label);
  }

  /** 開いたコンテキストを閉じる。failed なら証跡を添付し、合格なら録画を消す */
  async dispose(failed) {
    const tag = this.prefix ? `${this.prefix}-` : '';
    for (const [i, context] of this.contexts.entries()) {
      const pages = context.pages();
      if (failed && this.screenshots) {
        for (const [j, page] of pages.entries()) {
          try {
            const body = await page.screenshot({ fullPage: true });
            await this.testInfo.attach(`${tag}screenshot-${i + 1}-${j + 1}.png`, { body, contentType: 'image/png' });
          } catch (e) {
            this.logs.push(`スクリーンショットを撮れなかった: ${e.message}`);
          }
        }
      }
      const videos = pages.map((p) => p.video()).filter(Boolean);
      await context.close().catch(() => {});
      if (failed) {
        for (const [j, video] of videos.entries()) {
          try {
            await this.testInfo.attach(`${tag}video-${i + 1}-${j + 1}.webm`, { path: await video.path(), contentType: 'video/webm' });
          } catch (e) {
            this.logs.push(`録画を添付できなかった: ${e.message}`);
          }
        }
      }
    }
    if (failed && this.logs.length) {
      await this.testInfo.attach(`${tag}console.log`, { body: this.logs.join('\n'), contentType: 'text/plain' });
    }
    if (!failed) fs.rmSync(this.videoDir, { recursive: true, force: true });
    this.contexts = [];
  }
}

class Screen {
  constructor(env, context, page, randomCfg, label) {
    this.env = env;
    this.context = context;
    this.page = page;
    this.randomCfg = randomCfg;
    this.label = label;
    this.starts = 0;
  }

  input(id) {
    return this.page.locator(`#${id}`);
  }

  /**
   * 入力欄に値を入れる(キーは入力欄の id)。
   * 数 → その値を入れる / null → 空欄にする / 数字でない文字 → 欄の値を選んでキーボードで打つ(LTC-013。テスト環境.md)
   */
  async setConditions(conditions = {}) {
    for (const [id, value] of Object.entries(conditions)) {
      const field = this.input(id);
      if (value === null) {
        await field.fill('');
      } else if (typeof value === 'string' && Number.isNaN(Number(value))) {
        await field.click();
        await field.press('ControlOrMeta+a');
        await this.page.keyboard.type(value);
      } else {
        await field.fill(String(value));
      }
    }
  }

  /** 14項目の入力欄の値(「開始」の直前に画面に入っていた値) */
  async readInputs() {
    const values = {};
    for (const id of INPUT_IDS) values[id] = await this.input(id).inputValue();
    return values;
  }

  toggleSalaryChanges() {
    return this.page.locator('#toggleSalaryChanges').click();
  }

  salaryPanel() {
    return this.page.locator('#salaryChanges');
  }

  salaryItems() {
    return this.page.locator('#salaryChangesList .salary-change-item');
  }

  clickAddSalaryChange() {
    return this.page.locator('#addSalaryChange').click();
  }

  /** 結果を読み終えた画面を閉じる(多くの画面を開き直すテストで、開いたままにしないため) */
  async close() {
    this.env.contexts = this.env.contexts.filter((c) => c !== this.context);
    await this.context.close();
  }

  /** 上から index 番目(0から)の給与変更の設定に、年齢と年収を入れる */
  async fillSalaryChange(index, [age, salary]) {
    const item = this.salaryItems().nth(index);
    await item.locator('.salary-change-age').fill(String(age));
    await item.locator('.salary-change-salary').fill(String(salary));
  }

  /** 上から index 番目(0から)の給与変更の「削除」をクリックする */
  deleteSalaryChange(index) {
    return this.salaryItems().nth(index).locator('button', { hasText: '削除' }).click();
  }

  /** 上から順に、給与変更の設定の (年齢, 年収) を読む */
  async readSalaryChanges() {
    const items = this.salaryItems();
    const n = await items.count();
    const list = [];
    for (let i = 0; i < n; i++) {
      list.push([
        await items.nth(i).locator('.salary-change-age').inputValue(),
        await items.nth(i).locator('.salary-change-salary').inputValue(),
      ]);
    }
    return list;
  }

  /**
   * 給与変更を、書いた順に1つずつ追加して年齢と年収を入れる。
   * 設定の欄が非表示なら、先に「📈 給与変更設定を表示/非表示」で表示する(「➕ 給与変更を追加」は表示しないと押せない)。
   */
  async addSalaryChanges(changes) {
    if (!(await this.salaryPanel().isVisible())) await this.toggleSalaryChanges();
    for (const change of changes) {
      const n = await this.salaryItems().count();
      await this.clickAddSalaryChange();
      await expect(this.salaryItems()).toHaveCount(n + 1);
      await this.fillSalaryChange(n, change);
    }
  }

  /** 「開始」を times 回続けてクリックし、結果の欄を読む */
  async start({ times = 1, label } = {}) {
    const inputs = await this.readInputs();
    if (this.randomCfg && this.randomCfg.resetBeforeStart) {
      await this.page.evaluate(() => window.__e2eRandom.reset());
    }
    for (let i = 0; i < times; i++) await this.page.locator('#runBtn').click();
    const output = this.page.locator('#output');
    await expect(output).not.toBeEmpty();
    const text = await output.textContent();
    this.starts += 1;
    const name = label || `${this.label}-開始${this.starts}`;
    this.env.outputs.push({ label: name, sha256: sha256(text), length: text.length, text: this.env.keepText ? text : undefined });
    const result = parseOutput(text);
    result.inputs = inputs;
    result.label = name;
    result.screen = this;
    if (this.randomCfg && this.randomCfg.name === '支出なし') {
      // 支出なし: `▶` の行が1つでも出たら、差し替えが効いていないので判定しない(ローレベルテストケースの共通の決まり)
      const withEvent = result.months.find((m) => m.events.length > 0);
      if (withEvent) block(`支出なしの差し替えが効いていない(${name} の ${withEvent.label} に ▶ の行がある)`);
    }
    return result;
  }
}

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf-8').digest('hex');
}

module.exports = { Env, Screen, INPUT_IDS, sha256 };
