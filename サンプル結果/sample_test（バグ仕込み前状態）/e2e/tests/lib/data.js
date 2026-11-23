// テストデータ(テスト実装で作った JSON)を読み込む。値はスクリプトに埋め込まず、ここから取る。
// 置き場所: テスト成果物/06_テスト実装/テストデータ/(テストデータ.md の TD-001〜TD-015)
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..');
const TEST_DATA_DIR = path.join(PROJECT_ROOT, 'テスト成果物', '06_テスト実装', 'テストデータ');

// テスト対象と開くURL(テスト環境.md の「起動のしかた」)
const TARGET_FILE = path.join(PROJECT_ROOT, 'retirement_simulator.html');
const HTTP_URL = 'http://localhost:8000/retirement_simulator.html';
const FAVICON_URL = 'http://localhost:8000/favicon.ico';
const FILE_URL = 'file:///D:/codes/sample_test/retirement_simulator.html';

const cache = new Map();

function loadTestData(fileName) {
  if (!cache.has(fileName)) {
    const text = fs.readFileSync(path.join(TEST_DATA_DIR, fileName), 'utf-8');
    cache.set(fileName, JSON.parse(text));
  }
  return cache.get(fileName);
}

/** ローレベルテストケース1件分のテストデータ(条件・給与変更・乱数・比較用の実行・判定に使う値) */
function caseData(fileName, ltcId) {
  const data = loadTestData(fileName).ローレベルテストケース[ltcId];
  if (!data) throw new Error(`テストデータ ${fileName} に ${ltcId} が無い`);
  return data;
}

/** TD-001: 入力欄の id と名前、README の初期値 */
function settings() {
  return loadTestData('設定項目.json');
}

function targetSha256() {
  return crypto.createHash('sha256').update(fs.readFileSync(TARGET_FILE)).digest('hex');
}

module.exports = {
  PROJECT_ROOT, TEST_DATA_DIR, TARGET_FILE, HTTP_URL, FAVICON_URL, FILE_URL,
  loadTestData, caseData, settings, targetSha256,
};
