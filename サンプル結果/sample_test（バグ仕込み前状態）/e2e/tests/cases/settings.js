// TD-001(テストデータ/設定項目.json): LTC-014
const { expect } = require('@playwright/test');
const { defineCase } = require('../lib/fixtures');
const { settings } = require('../lib/data');

module.exports = [
  defineCase('設定項目.json', 'LTC-014', async (env, data) => {
    const screen = await env.open({ random: data.乱数 }); // 乱数: 差し替えない。何も操作しない
    const expected = settings().READMEの初期値;
    for (const [id, value] of Object.entries(expected)) {
      await expect(screen.input(id), `${settings().項目[id]} の初期値が ${value}`).toHaveValue(String(value));
    }
  }),
];
