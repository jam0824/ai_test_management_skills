// テストケースの定義は cases/net-salary.js。ローレベルテストケース1件をテスト1件として登録する(テスト名の先頭がid)
const { test } = require('./lib/fixtures');

for (const c of require('./cases/net-salary')) {
  test(c.title, async ({ env }) => {
    if (c.timeout) test.setTimeout(c.timeout);
    await c.run(env);
  });
}
