// すべてのテストケースの定義(id → 定義)。spec ファイルと、ブラウザの互換性のテスト(LTC-096〜LTC-098)が使う。
const groups = {
  'run-and-order': require('./run-and-order'),
  'invalid-values': require('./invalid-values'),
  settings: require('./settings'),
  'usage-examples': require('./usage-examples'),
  periods: require('./periods'),
  'net-salary': require('./net-salary'),
  invest: require('./invest'),
  drawdown: require('./drawdown'),
  'salary-changes': require('./salary-changes'),
  events: require('./events'),
  'network-offline': require('./network-offline'),
};

const byId = new Map();
for (const cases of Object.values(groups)) {
  for (const c of cases) {
    if (byId.has(c.id)) throw new Error(`${c.id} が2つ定義されている`);
    byId.set(c.id, c);
  }
}

module.exports = { groups, byId };
