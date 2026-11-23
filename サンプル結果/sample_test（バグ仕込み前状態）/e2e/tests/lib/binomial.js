// 二項分布の範囲(LTC-080〜LTC-084 の期待値)。テスト設計のテストオラクルのとおり、数えた合計の月数 N から Node.js で計算する。
// 「下側・上側それぞれ確率 alpha 以下になる値を除いた範囲」:
//   下限 = P(X ≤ k) > alpha となる最小の k、上限 = P(X ≥ k) > alpha となる最大の k

function binomialRange(n, p, alpha) {
  // 対数で確率を出し、最大値でそろえてから足す(n = 100,000 でもあふれないように)
  const logs = new Float64Array(n + 1);
  logs[0] = n * Math.log1p(-p);
  const logRatio = Math.log(p) - Math.log1p(-p);
  for (let k = 0; k < n; k++) logs[k + 1] = logs[k] + Math.log(n - k) - Math.log(k + 1) + logRatio;
  let max = -Infinity;
  for (const v of logs) if (v > max) max = v;
  const pmf = new Float64Array(n + 1);
  let sum = 0;
  for (let k = 0; k <= n; k++) {
    pmf[k] = Math.exp(logs[k] - max);
    sum += pmf[k];
  }
  let low = 0;
  let cdf = 0;
  for (let k = 0; k <= n; k++) {
    cdf += pmf[k] / sum;
    if (cdf > alpha) { low = k; break; }
  }
  let high = n;
  let upper = 0;
  for (let k = n; k >= 0; k--) {
    upper += pmf[k] / sum;
    if (upper > alpha) { high = k; break; }
  }
  return { low, high };
}

module.exports = { binomialRange };
