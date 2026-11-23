// 乱数(Math.random)の差し替え。TD-002(テストデータ/乱数.json)の決まりのとおりに作る。
// - ページを読み込む前に addInitScript で差し替える(テスト対象のファイルは変えない)
// - 「1か月だけ」「両端」は、「開始」をクリックする直前に数と位置を0に戻す(Screen.start が reset を呼ぶ)
// - 「シード」は、画面を開き直すまで続けて使う(「開始」を繰り返しても初期化し直さない)
const { loadTestData } = require('./data');

/**
 * ローレベルテストケースの「乱数」の書き方を、差し替えの設定にする。
 * '支出なし' | '両端' | '差し替えない' | { 種類: '1か月だけ', n } | { 種類: 'シード', シード }
 */
function randomConfig(spec) {
  const td = loadTestData('乱数.json').並び;
  if (spec === undefined || spec === '差し替えない') return null;
  if (spec === '支出なし') return { name: '支出なし', kind: 'const', value: td.支出なし.値, resetBeforeStart: false };
  if (spec === '両端') return { name: '両端', kind: 'cycle', seq: td.両端.並び, resetBeforeStart: true };
  if (spec && spec.種類 === '1か月だけ') {
    return {
      name: `1か月だけ(${spec.n}回目)`, kind: 'nth', n: spec.n,
      hit: td['1か月だけ'].n回目の値, other: td['1か月だけ'].ほかの値, resetBeforeStart: true,
    };
  }
  if (spec && spec.種類 === 'シード') {
    return { name: `シード${spec.シード}`, kind: 'seed', seed: spec.シード, code: td.シードつき疑似乱数.コード, resetBeforeStart: false };
  }
  throw new Error(`乱数の書き方がわからない: ${JSON.stringify(spec)}`);
}

/** addInitScript に渡すスクリプト。差し替えたことを window.__e2eRandom.name で確かめられるようにする */
function initScript(cfg) {
  const { code, ...plain } = cfg;
  const maker = cfg.kind === 'seed' ? `(${code})` : 'null';
  return `(() => {
  const cfg = ${JSON.stringify(plain)};
  const makeSeeded = ${maker};
  let random;
  let reset = () => {};
  if (cfg.kind === 'const') {
    random = () => cfg.value;
  } else if (cfg.kind === 'nth') {
    let count = 0;
    random = () => { count += 1; return count === cfg.n ? cfg.hit : cfg.other; };
    reset = () => { count = 0; };
  } else if (cfg.kind === 'cycle') {
    let index = 0;
    random = () => { const v = cfg.seq[index % cfg.seq.length]; index += 1; return v; };
    reset = () => { index = 0; };
  } else if (cfg.kind === 'seed') {
    random = makeSeeded(cfg.seed);
  }
  Math.random = random;
  window.__e2eRandom = { name: cfg.name, reset };
})();`;
}

module.exports = { randomConfig, initScript };
