"""tm_html(視認性アップのHTMLとテストレポート)のテスト。"""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tm_core  # noqa: E402
import tm_html  # noqa: E402
from sample_project import append_to, make_project  # noqa: E402

JUDGMENT = """# テストレポートの判定

## 終了条件の判定

| 終了条件ID | 判定 | 根拠 |
|---|---|---|
| EXIT-001 | 満たした | 3件中3件を実行した |
| EXIT-002 | 満たしていない | 重要度が高の BUG-001 が未修正 |

## 足りないこと

BUG-001 の修正と確認テストが必要。

## テスト計画からの変更

変更なし。

## テストの妨げになったことと対処

なし。

## 未解決のリスク

RISK-001 は不具合が残っている。

## 次のテストに向けた教訓

境界値のテスト条件を最初から厚くする。
"""


@pytest.fixture
def root(tmp_path):
    return make_project(tmp_path / "テスト成果物")


class TestMarkdownからHTML:
    def test_見出しと表とリストを変換する(self):
        html = tm_html.md_to_html("# 題\n\n本文\n\n* 一\n* 二\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
        assert "<h1>題</h1>" in html
        assert "<li>一</li>" in html
        assert "<th>a</th>" in html and "<td>2</td>" in html

    def test_HTMLの記号をエスケープする(self):
        html = tm_html.md_to_html("<script>alert(1)</script> & 本文")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_セルの中の改行タグは残す(self):
        html = tm_html.md_to_html("| a |\n|---|\n| 1<br>2 |\n")
        assert "1<br>2" in html

    def test_定義されているIDをリンクにする(self):
        html = tm_html.md_to_html("REQ-001 と REQ-999", known_ids={"REQ-001"}, id_href="ids.html")
        assert '<a href="ids.html#REQ-001"' in html
        assert "#REQ-999" not in html


    def test_字下げした箇条書きは入れ子のまま出す(self):
        html = tm_html.md_to_html("- a\n  - b\n- c\n")
        assert html == "<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>"

    def test_箇条書きの下の番号付きリストも入れ子にする(self):
        html = tm_html.md_to_html("- 手順:\n  1. 開く\n  2. 押す\n- 期待値: 出る\n")
        assert html == "<ul><li>手順:<ol><li>開く</li><li>押す</li></ol></li><li>期待値: 出る</li></ul>"

    def test_危ないリンクはリンクにしない(self):
        html = tm_html.md_to_html('[a](javascript:alert(1)) と [b](x"onmouseover="alert(1)) と [c](https://example.com/a) と [d](証跡/a.png)')
        assert "javascript:" not in html.replace("[a](javascript:alert(1))", "")
        assert "onmouseover=" not in html.replace('[b](x"onmouseover="alert(1))', "")
        assert '<a href="https://example.com/a">c</a>' in html
        assert '<a href="証跡/a.png">d</a>' in html


class Test視認性アップ:
    def test_結果まとめに目次とID索引と工程ごとのページを日本語の名前で作る(self, root):
        tm_html.build_html(tm_core.load_project(root))
        out = root / "結果まとめ"
        for name in ["目次.html", "ID索引.html", "要求仕様整理.html", "リスク分析.html", "テスト計画.html", "テスト分析.html",
                     "テスト設計.html", "テスト実装.html", "E2E自動テストスクリプト作成.html", "テスト実行.html"]:
            assert (out / name).exists(), name
        assert not (root / "html").exists()

    def test_工程のフォルダにもその工程のページを作る(self, root):
        tm_html.build_html(tm_core.load_project(root))
        assert (root / "02_リスク分析/リスク分析.html").exists()
        assert (root / "08_テスト実行/テスト実行.html").exists()

    def test_まだ無い工程のフォルダは作らない(self, root):
        shutil.rmtree(root / "07_E2E自動テストスクリプト")
        tm_html.build_html(tm_core.load_project(root))
        assert not (root / "07_E2E自動テストスクリプト").exists()
        assert (root / "結果まとめ/E2E自動テストスクリプト作成.html").exists()

    def test_工程のフォルダのページから結果まとめとID索引へリンクする(self, root):
        tm_html.build_html(tm_core.load_project(root))
        html = (root / "02_リスク分析/リスク分析.html").read_text(encoding="utf-8")
        assert 'href="../結果まとめ/ID索引.html#RISK-001"' in html
        assert 'href="../結果まとめ/目次.html"' in html and 'href="../結果まとめ/テスト計画.html"' in html
        execution = (root / "08_テスト実行/テスト実行.html").read_text(encoding="utf-8")
        assert 'href="../08_テスト実行/RUN-20261101-100000/証跡/LTC-002.png"' in execution

    def test_結果まとめのページは同じフォルダのページへリンクする(self, root):
        tm_html.build_html(tm_core.load_project(root))
        html = (root / "結果まとめ/リスク分析.html").read_text(encoding="utf-8")
        assert 'href="ID索引.html#RISK-001"' in html and 'href="テスト計画.html"' in html
        index = (root / "結果まとめ/目次.html").read_text(encoding="utf-8")
        assert 'href="リスク分析.html"' in index

    @staticmethod
    def _risk_block(html: str, risk_id: str) -> tuple[str, str]:
        """開く一覧から、その行の見出し(summary)と、開くと出る中身を取り出す。"""
        block = html.split(f'<details class="card" id="row-{risk_id}"')[1].split("</details>")[0]
        summary, kids = block.split("</summary>")
        return summary, kids

    def test_要求仕様整理のページは要求を並べて開くと紐づく仕様が出る(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "requirements")
        summary, kids = self._risk_block(html, "REQ-001")
        assert "REQ-001" in summary and "年齢を入力して登録できる" in summary and "紐づく仕様 2件" in summary
        assert "SPEC-001" not in summary
        assert "SPEC-001" in kids and "SPEC-002" in kids and "SPEC-003" not in kids
        assert "サービスを使うため" in kids  # 要求のほかの欄(誰が・何のために など)も出る

    def test_テスト計画のページはテストアイテムとテストスコープを上に出す(self, root):
        path = root / "03_テスト計画/テスト計画.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "## テスト終了条件",
            "## テストアイテム\n\n会員登録アプリ v1.2\n\n## テストスコープ\n\n- 年齢の入力(SPEC-001)\n\n## テスト終了条件"),
            encoding="utf-8")
        html = tm_html.render_stage(tm_core.load_project(root), "plan")
        main = html.split("<main>")[1]
        assert main.index("<h2>テストアイテム</h2>") < main.index("<h2>テストスコープ</h2>") < main.index("<h2>テスト終了条件</h2>")
        items = main.split("<h2>テストアイテム</h2>")[1].split("<h2>")[0]
        scope = main.split("<h2>テストスコープ</h2>")[1].split("<h2>")[0]
        assert "会員登録アプリ v1.2" in items
        assert "年齢の入力" in scope and 'href="ID索引.html#SPEC-001"' in scope

    def test_テストアプローチはテストタイプ_内容_実施方法_要求_仕様_リスクの順に並べる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "plan")
        section = html.split("テストアプローチ</h2>")[1]
        headers = section.split("<thead><tr>")[1].split("</tr></thead>")[0]
        assert headers == "".join(f"<th>{h}</th>" for h in ["テストタイプ", "テストアプローチ", "実施方法", "要求", "仕様", "リスク"])
        row = next(line for line in section.split("</tr>") if 'id="row-TA-001"' in line)
        cells = row.split("<td>")[1:]
        assert "機能テスト" in cells[0]
        assert "TA-001" in cells[1] and "年齢の入力チェックを確かめる" in cells[1]
        assert "E2E自動テスト" in cells[2]
        assert "REQ-001" in cells[3] and "SPEC-001" in cells[4] and "RISK-001" in cells[5]

    @staticmethod
    def _coverage_row(html: str, kind: str) -> str:
        coverage = html.split("満たしている割合</h2>")[1].split("<h2>")[0]
        return next(r for r in coverage.split("</tr>") if f">{kind}</span></td>" in r)

    def test_テストアプローチの上に要求と仕様とリスクを満たしている割合を出す(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "plan")
        main = html.split("<main>")[1]
        assert main.index("<h2>テスト終了条件</h2>") < main.index("満たしている割合</h2>") < main.index("<h2>テストアプローチ</h2>")
        assert "<td>2 / 2</td><td><span class=\"pct ok\">100%</span></td>" in self._coverage_row(html, "要求")
        assert "<td>3 / 3</td><td><span class=\"pct ok\">100%</span></td>" in self._coverage_row(html, "仕様")
        assert "<td>2 / 2</td><td><span class=\"pct ok\">100%</span></td>" in self._coverage_row(html, "リスク")

    def test_テストアプローチが無い仕様があれば割合とIDと理由を出す(self, root):
        append_to(root, "01_要求仕様/仕様.md", "| SPEC-004 | 確認画面に戻るボタンがある | REQ-002 | 仕様書 2.3 |\n")
        row = self._coverage_row(tm_html.render_stage(tm_core.load_project(root), "plan"), "仕様")
        assert "<td>3 / 4</td><td><span class=\"pct warn\">75%</span></td>" in row and "SPEC-004" in row and "テストアプローチが無い" in row

    def test_押さえていないものと理由は件数だけ見せてたたんでおく(self, root):
        append_to(root, "01_要求仕様/仕様.md", "| SPEC-004 | 確認画面に戻るボタンがある | REQ-002 | 仕様書 2.3 |\n")
        html = tm_html.render_stage(tm_core.load_project(root), "plan")
        row = self._coverage_row(html, "仕様")
        reasons = row.split('<details class="reasons"><summary>')[1]
        assert reasons.startswith("1件")
        assert "SPEC-004" in reasons.split("</summary>")[1] and "テストアプローチが無い" in reasons.split("</summary>")[1]
        assert "<details" not in self._coverage_row(html, "要求")  # 無いときは「なし」だけ

    def test_どれも押さえていない種類の割合は赤くする(self, root):
        path = root / "03_テスト計画/テスト計画.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.split("| TA-001 |")[0], encoding="utf-8")  # テストアプローチの行を消す
        row = self._coverage_row(tm_html.render_stage(tm_core.load_project(root), "plan"), "要求")
        assert '<td>0 / 2</td><td><span class="pct ng">0%</span></td>' in row

    def test_テスト計画で対象外にしたものは対象外の理由を出す(self, root):
        append_to(root, "01_要求仕様/仕様.md", "| SPEC-004 | 確認画面に戻るボタンがある | REQ-002 | 仕様書 2.3 |\n")
        path = root / "03_テスト計画/テスト計画.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "## テスト終了条件",
            "## 対象外/制約\n\n### 対象外\n\n| 対象外にするもの | 理由 |\n|---|---|\n| 戻るボタン(SPEC-004) | 次の版で作る |\n\n"
            "### 制約\n\n- 時間は1日\n\n## テスト終了条件"), encoding="utf-8")
        row = self._coverage_row(tm_html.render_stage(tm_core.load_project(root), "plan"), "仕様")
        assert "SPEC-004" in row and "対象外" in row and "次の版で作る" in row
        assert "テストアプローチが無い" not in row

    def test_仕様が無い要求は仕様が無いことと扱っているリスクとテストアプローチを出す(self, root):
        append_to(root, "01_要求仕様/要求.md", "| REQ-003 | ありえない値で誤った結果を信じない | 利用者 | 判断を誤らないため |\n")
        append_to(root, "02_リスク分析/リスク分析.md", "| RISK-003 | ありえない値を入れても知らされない |  | 4 | 4 | 16 | 高 | REQ-003 に仕様が無い |\n")
        append_to(root, "03_テスト計画/テスト計画.md", "| TA-004 | 機能テスト | 探索的テスト | ありえない値を探索する |  | RISK-003 |\n")
        row = self._coverage_row(tm_html.render_stage(tm_core.load_project(root), "plan"), "要求")
        assert "REQ-003" in row and "仕様が無い" in row and "RISK-003" in row and "TA-004" in row

    # ---- テスト分析: テスト条件のカバレッジ ----

    @staticmethod
    def _pane(html: str, pane_id: str) -> str:
        return html.split(f'id="{pane_id}"')[1].split('<div class="pane')[0].split("<h2>")[0]

    def test_テスト分析のページはいちばん上にテスト条件のカバレッジを出す(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "analysis")
        main = html.split("<main>")[1]
        assert main.index("<h2>テスト条件のカバレッジ</h2>") < main.index("<h2>フィーチャーごとのテスト条件</h2>") \
            < main.index("<h2>この工程で出た質問</h2>")
        assert main.split("<h2>")[1].startswith("テスト条件のカバレッジ")

    def test_テスト条件が要求と仕様とリスクとテストアプローチを押さえている割合を出す(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "analysis")
        table = html.split("<h2>テスト条件のカバレッジ</h2>")[1].split("</table>")[0]
        rows = {kind: next(r for r in table.split("</tr>") if f">{kind}</span></td>" in r)
                for kind in ("要求", "仕様", "リスク", "テストアプローチ")}
        assert "<td>2 / 2</td><td><span class=\"pct ok\">100%</span></td>" in rows["要求"]
        assert "<td>2 / 3</td><td><span class=\"pct warn\">66%</span></td>" in rows["仕様"] and "SPEC-002" in rows["仕様"]
        assert "テスト条件が無い" in rows["仕様"]
        assert "<td>2 / 2</td><td><span class=\"pct ok\">100%</span></td>" in rows["リスク"]
        assert "<td>3 / 3</td><td><span class=\"pct ok\">100%</span></td>" in rows["テストアプローチ"]

    def test_要求からたどると仕様の下にテスト条件が出て無い仕様は赤くなる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "analysis")
        pane = self._pane(html, "an-req")
        req1 = pane.split('id="an-req-REQ-001"')[1]
        assert "COND-003" in req1.split('id="an-req-REQ-001-SPEC-001"')[0]  # 要求に直接紐づくテスト条件(利用の流れ)
        assert "COND-001" not in req1.split('id="an-req-REQ-001-SPEC-001"')[0]  # 仕様のテスト条件は要求の直下に重ねて出さない
        assert "テスト条件 2件" in req1.split("</summary>")[0]
        assert "COND-001" in req1.split('id="an-req-REQ-001-SPEC-001"')[1].split("</details>")[0]
        spec2 = pane.split('id="an-req-REQ-001-SPEC-002"')[1].split("</summary>")[0]
        assert 'class="ng"' in spec2 and "テスト条件 0件" in spec2
        assert 'class="ok"' in pane.split('id="an-req-REQ-001-SPEC-001"')[1].split("</summary>")[0]

    def test_リスクとテストアプローチからもテスト条件をたどれる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "analysis")
        risk1 = self._pane(html, "an-risk").split('id="an-risk-RISK-001"')[1].split("</details>")[0]
        assert "COND-001" in risk1 and "COND-003" in risk1 and "COND-002" not in risk1
        ta3 = self._pane(html, "an-ta").split('id="an-ta-TA-003"')[1].split("</details>")[0]
        assert "COND-003" in ta3 and "COND-001" not in ta3

    def test_テスト計画で対象外にした仕様は灰色で理由を出す(self, root):
        path = root / "03_テスト計画/テスト計画.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "## テスト終了条件",
            "## 対象外/制約\n\n### 対象外\n\n| 対象外にするもの | 理由 |\n|---|---|\n| エラー表示(SPEC-002) | 次の版で作る |\n\n## テスト終了条件"),
            encoding="utf-8")
        html = tm_html.render_stage(tm_core.load_project(root), "analysis")
        spec2 = self._pane(html, "an-req").split('id="an-req-REQ-001-SPEC-002"')[1].split("</summary>")[0]
        assert 'class="ex"' in spec2
        table = html.split("<h2>テスト条件のカバレッジ</h2>")[1].split("</table>")[0]
        assert "次の版で作る" in table

    def test_工程のページの質問は並べて開くと理由と関連が出る(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "analysis")
        summary, kids = self._risk_block(html, "Q-001")
        assert "Q-001" in summary and "小数の年齢はどう扱うか" in summary and "未回答" in summary
        assert "SPEC-001" not in summary
        assert "曖昧" in kids and "期待結果が決まらない" in kids and "SPEC-001" in kids

    def test_回答があれば質問を開くと回答が出る(self, root):
        path = root / "質問表.md"
        path.write_text(path.read_text(encoding="utf-8").replace("| 未回答 | |", "| 回答済み | 整数だけ扱う |"),
                        encoding="utf-8")
        html = tm_html.render_stage(tm_core.load_project(root), "analysis")
        summary, kids = self._risk_block(html, "Q-001")
        assert "回答済み" in summary and "整数だけ扱う" in kids

    OBSERVED = "17.5 を入れると 17 として登録される。証跡: RUN-20261101-100000/証跡/LTC-002.png"

    def _add_observed(self, root):
        """質問表に実機の動きの列を足し、Q-001 に実機確認の結果を書く。"""
        path = root / "質問表.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("| 回答が必要な理由 | 状態 | 回答 |\n|---|---|---|---|---|---|---|---|",
                            "| 回答が必要な理由 | 実機の動き | 状態 | 回答 |\n|---|---|---|---|---|---|---|---|---|")
        text = text.replace("| 期待結果が決まらない | 未回答 |", f"| 期待結果が決まらない | {self.OBSERVED} | 未回答 |")
        path.write_text(text, encoding="utf-8")

    def test_質問を開くと実機の動きと証跡へのリンクが出る(self, root):
        self._add_observed(root)
        html = tm_html.render_stage(tm_core.load_project(root), "analysis")
        _, kids = self._risk_block(html, "Q-001")
        assert "実機の動き" in kids and "17 として登録される" in kids
        assert 'href="../08_テスト実行/RUN-20261101-100000/証跡/LTC-002.png"' in kids
        note = kids.split("<dt>実機の動き</dt><dd>")[1].split("</dd>")[0]
        assert "証跡:" not in note  # 証跡はリンクの行に出すので、文の中のパスは省く

    def test_リスクのページはリスクを並べて開くと紐づく仕様と要求が出る(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "risk")
        summary, kids = self._risk_block(html, "RISK-001")
        assert "RISK-001" in summary and "年齢の境界を誤って登録を通す" in summary and "紐づく仕様 1件" in summary
        assert "SPEC-001" not in summary
        assert "SPEC-001" in kids and "REQ-001" in kids
        assert "SPEC-003" not in kids

    def test_リスクのページはリスクレベルの高い順に並ぶ(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "risk")
        assert html.index('id="row-RISK-001"') < html.index('id="row-RISK-002"')

    def test_リスクのページで開くと根拠と備考も出る(self, root):
        path = root / "02_リスク分析/リスク分析.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("| 区分 | 根拠 |", "| 区分 | 根拠 | 備考 |").replace("|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|---|---|")
        text = text.replace("起きやすい |", "起きやすい | Q-001 の回答待ち |").replace("単純な画面遷移 |", "単純な画面遷移 | |")
        path.write_text(text, encoding="utf-8")
        html = tm_html.render_stage(tm_core.load_project(root), "risk")
        summary, kids = self._risk_block(html, "RISK-001")
        assert "境界の実装ミスは起きやすい" in kids
        assert 'href="ID索引.html#Q-001"' in kids and "の回答待ち" in kids
        assert kids.index("境界の実装ミス") < kids.index("SPEC-001")
        assert "境界の実装ミスは起きやすい" not in summary
        _, kids2 = self._risk_block(html, "RISK-002")
        assert "単純な画面遷移" in kids2 and "備考" not in kids2

    def test_リスクのページで仕様が紐づかないリスクは開いても仕様が出ない(self, root):
        append_to(root, "02_リスク分析/リスク分析.md", "| RISK-003 | 仕様に無いところで落ちる |  | 3 | 1 | 3 | 低 | 不明 |\n")
        html = tm_html.render_stage(tm_core.load_project(root), "risk")
        summary, kids = self._risk_block(html, "RISK-003")
        assert "RISK-003" in summary
        assert "不明" in kids
        assert "SPEC-" not in kids

    def test_要求仕様のページで仕様が無い要求がわかる(self, root):
        append_to(root, "01_要求仕様/要求.md", "| REQ-003 | 退会できる | 利用者 | やめたいとき |\n")
        html = tm_html.render_stage(tm_core.load_project(root), "requirements")
        section = html.split("仕様が無い要求")[1]
        assert "REQ-003" in section

    # ---- テスト設計: テストケースのカバレッジ ----

    def test_テスト設計のページはいちばん上にテストケースのカバレッジを出し古い追跡表は出さない(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "design")
        main = html.split("<main>")[1]
        assert main.split("<h2>")[1].startswith("テストケースのカバレッジ")
        assert main.index("<h2>テスト条件ごとの技法とカバレッジ</h2>") < main.index("<h2>テストチャーター</h2>")
        assert "要求 → ハイレベルテストケース" not in main and "要求 → テストチャーター" not in main

    def test_テストケースとチャーターが押さえている割合を種類ごとに出す(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "design")
        table = html.split("<h2>テストケースのカバレッジ</h2>")[1].split("</table>")[0]
        rows = {kind: next(r for r in table.split("</tr>") if f">{kind}</span></td>" in r)
                for kind in ("要求", "仕様", "リスク", "テスト条件", "カバレッジアイテム")}
        assert "<td>2 / 2</td><td><span class=\"pct ok\">100%</span></td>" in rows["要求"]
        assert "<td>2 / 3</td><td><span class=\"pct warn\">66%</span></td>" in rows["仕様"] and "SPEC-002" in rows["仕様"]
        assert "テストケース・テストチャーターが無い" in rows["仕様"]
        assert "<td>2 / 2</td><td><span class=\"pct ok\">100%</span></td>" in rows["リスク"]
        assert "<td>3 / 3</td><td><span class=\"pct ok\">100%</span></td>" in rows["テスト条件"]
        assert "<td>3 / 3</td><td><span class=\"pct ok\">100%</span></td>" in rows["カバレッジアイテム"]

    def test_通さない理由があるカバレッジアイテムは理由を出し灰色にする(self, root):
        path = root / "05_テスト設計/テスト設計.md"
        text = path.read_text(encoding="utf-8").replace(
            "| ID | カバレッジアイテム | テスト条件ID |\n|---|---|---|",
            "| ID | カバレッジアイテム | テスト条件ID | 通さない理由 |\n|---|---|---|---|").replace(
            "| CI-003 | 確認画面が表示される | COND-002 |",
            "| CI-003 | 確認画面が表示される | COND-002 |\n| CI-004 | 上限の外 66 | COND-001 | 同値の代表で足りる |")
        path.write_text(text, encoding="utf-8")
        html = tm_html.render_stage(tm_core.load_project(root), "design")
        table = html.split("<h2>テストケースのカバレッジ</h2>")[1].split("</table>")[0]
        row = next(r for r in table.split("</tr>") if ">カバレッジアイテム</span></td>" in r)
        assert "<td>3 / 4</td><td><span class=\"pct warn\">75%</span></td>" in row and "CI-004" in row and "同値の代表で足りる" in row
        ci4 = self._pane(html, "ds-cond").split('id="ds-cond-CI-004"')[1].split("</summary>")[0]
        assert 'class="ex"' in ci4

    def test_テスト条件からカバレッジアイテムとテストケースとチャーターをたどれる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "design")
        pane = self._pane(html, "ds-cond")
        cond1 = pane.split('id="ds-cond-COND-001"')[1]
        assert 'class="ok"' in cond1.split("</summary>")[0] and "カバレッジアイテム 2 / 2" in cond1.split("</summary>")[0]
        assert "HTC-001" in cond1.split('id="ds-cond-CI-001"')[1].split("</details>")[0]
        cond3 = pane.split('id="ds-cond-COND-003"')[1].split("</details>")[0]
        assert "CH-001" in cond3

    def test_回答待ちのテストケースでしか通らないものは黄色にする(self, root):
        path = root / "05_テスト設計/テスト設計.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "| エラーを表示 | E2E自動テスト | 高 | 設計済み |", "| エラーを表示 | E2E自動テスト | 高 | 回答待ち(Q-001) |"),
            encoding="utf-8")
        pane = self._pane(tm_html.render_stage(tm_core.load_project(root), "design"), "ds-cond")
        assert 'class="warn"' in pane.split('id="ds-cond-CI-002"')[1].split("</summary>")[0]
        assert 'class="warn"' in pane.split('id="ds-cond-COND-001"')[1].split("</summary>")[0]

    def test_要求から仕様とテスト条件をたどれてテストケースの無い仕様は赤くなる(self, root):
        pane = self._pane(tm_html.render_stage(tm_core.load_project(root), "design"), "ds-req")
        req1 = pane.split('id="ds-req-REQ-001"')[1]
        assert "COND-003" in req1.split('id="ds-req-REQ-001-SPEC-001"')[0]
        assert "COND-001" in req1.split('id="ds-req-REQ-001-SPEC-001"')[1].split("</details>")[0]
        assert 'class="ng"' in pane.split('id="ds-req-REQ-001-SPEC-002"')[1].split("</summary>")[0]

    def test_要求からたどるとテスト条件の下にテストケースとチャーターが出る(self, root):
        pane = self._pane(tm_html.render_stage(tm_core.load_project(root), "design"), "ds-req")
        cond1 = pane.split('id="ds-req-REQ-001-SPEC-001-COND-001"')[1].split("</details>")[0]
        assert "HTC-001" in cond1 and "HTC-002" in cond1 and "テストケース 2件" in cond1.split("</summary>")[0]
        cond3 = pane.split('id="ds-req-REQ-001-COND-003"')[1].split("</details>")[0]
        assert "CH-001" in cond3

    def test_開いた中の行は長い文を途中で切らない(self, root):
        long_goal = "登録画面を不正な値で探索し入力チェックの漏れを見つける。" * 4  # 100文字を超える
        path = root / "05_テスト設計/テスト設計.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "| CH-001 | 登録画面を不正な値で探索し入力チェックの漏れを見つける |", f"| CH-001 | {long_goal} |"), encoding="utf-8")
        pane = self._pane(tm_html.render_stage(tm_core.load_project(root), "design"), "ds-cond")
        cond3 = pane.split('id="ds-cond-COND-003"')[1].split("</details>")[0]
        assert long_goal in cond3

    def test_テストチャーターは開くと対象の領域と時間枠とテスト条件が出る(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "design")
        section = html.split("<h2>テストチャーター</h2>")[1]
        summary, kids = section.split('id="ch-CH-001"')[1].split("</details>")[0].split("</summary>")
        assert "登録画面を不正な値で探索し入力チェックの漏れを見つける" in summary
        assert "登録画面" in kids and "15" in kids and "COND-003" in kids

    def test_テスト設計のページでテスト条件ごとのカバレッジがわかる(self, root):
        append_to(root, "05_テスト設計/テスト設計.md", "")
        text = (root / "05_テスト設計/テスト設計.md").read_text(encoding="utf-8")
        text = text.replace("| CI-003 | 確認画面が表示される | COND-002 |", "| CI-003 | 確認画面が表示される | COND-002 |\n| CI-004 | 上限の境界値 65 | COND-001 |")
        (root / "05_テスト設計/テスト設計.md").write_text(text, encoding="utf-8")
        html = tm_html.render_stage(tm_core.load_project(root), "design")
        row = next(line for line in html.split("</tr>") if 'id="cov-COND-001"' in line)
        assert "2 / 3" in row

    def test_テスト設計のページで回答待ちのテストケースでしか通らないものがわかる(self, root):
        text = (root / "05_テスト設計/テスト設計.md").read_text(encoding="utf-8")
        text = text.replace("| エラーを表示 | E2E自動テスト | 高 | 設計済み |", "| エラーを表示 | E2E自動テスト | 高 | 回答待ち(Q-001) |")
        (root / "05_テスト設計/テスト設計.md").write_text(text, encoding="utf-8")
        html = tm_html.render_stage(tm_core.load_project(root), "design")
        row = next(line for line in html.split("</tr>") if 'id="cov-COND-001"' in line)
        assert "<td>2 / 2</td>" in row      # テストケースで通る数 / 出した数
        assert "<td>1</td>" in row          # そのうち、回答待ちのテストケースでしか通らない数

    # ---- テスト実装: ローレベルテストケースのカバレッジ ----

    @staticmethod
    def _add_htc4(root, unimplemented_reason: str = ""):
        """ローレベルテストケースの無い HTC-004(CI-004)を足す。理由を渡すと未実装.md に書く。"""
        path = root / "05_テスト設計/テスト設計.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("| CI-003 | 確認画面が表示される | COND-002 |", "| CI-003 | 確認画面が表示される | COND-002 |\n| CI-004 | 上限の境界値 65 | COND-001 |")
        text = text.replace("| 手動テスト | 低 | 設計済み |\n", "| 手動テスト | 低 | 設計済み |\n| HTC-004 | 上限の境界値のとき登録できる | COND-001 | CI-004 | 登録できる | E2E自動テスト | 高 | 設計済み |\n")
        path.write_text(text, encoding="utf-8")
        if unimplemented_reason:
            (root / "06_テスト実装/未実装.md").write_text(
                f"# 未実装\n\n| ハイレベルテストケースID | 理由 |\n|---|---|\n| HTC-004 | {unimplemented_reason} |\n", encoding="utf-8")

    @staticmethod
    def _impl_rows(html: str) -> dict[str, str]:
        table = html.split("<h2>ローレベルテストケースのカバレッジ</h2>")[1].split("</table>")[0]
        return {kind: next(r for r in table.split("</tr>") if f">{kind}</span></td>" in r)
                for kind in ("要求", "仕様", "リスク", "テスト条件", "カバレッジアイテム", "ハイレベルテストケース")}

    def test_テスト実装のページはいちばん上にローレベルテストケースのカバレッジを出し古い表は出さない(self, root):
        main = tm_html.render_stage(tm_core.load_project(root), "implementation").split("<main>")[1]
        assert main.split("<h2>")[1].startswith("ローレベルテストケースのカバレッジ")
        assert main.index("<h2>ローレベルテストケース</h2>") < main.index("<h2>未実装のテストケースと理由</h2>")
        assert "要求 → ローレベルテストケース → テスト手順" not in main
        assert "ローレベルテストケースでどこまで通せているか" not in main

    def test_ローレベルテストケースが押さえている割合を種類ごとに出す(self, root):
        rows = self._impl_rows(tm_html.render_stage(tm_core.load_project(root), "implementation"))
        assert "<td>2 / 2</td><td><span class=\"pct ok\">100%</span></td>" in rows["要求"]
        assert "<td>2 / 3</td><td><span class=\"pct warn\">66%</span></td>" in rows["仕様"] and "SPEC-002" in rows["仕様"]
        assert "<td>2 / 2</td><td><span class=\"pct ok\">100%</span></td>" in rows["リスク"]
        assert "<td>3 / 3</td><td><span class=\"pct ok\">100%</span></td>" in rows["テスト条件"]  # 探索的テストの COND-003 はチャーターで押さえる
        assert "<td>3 / 3</td><td><span class=\"pct ok\">100%</span></td>" in rows["カバレッジアイテム"]
        assert "<td>3 / 3</td><td><span class=\"pct ok\">100%</span></td>" in rows["ハイレベルテストケース"]

    def test_未実装のハイレベルテストケースは未実装の理由を出し赤くする(self, root):
        self._add_htc4(root, "上限の入力欄がまだ無い")
        html = tm_html.render_stage(tm_core.load_project(root), "implementation")
        rows = self._impl_rows(html)
        assert "<td>3 / 4</td><td><span class=\"pct warn\">75%</span></td>" in rows["ハイレベルテストケース"]
        assert "HTC-004" in rows["ハイレベルテストケース"] and "上限の入力欄がまだ無い" in rows["ハイレベルテストケース"]
        assert "<td>3 / 4</td><td><span class=\"pct warn\">75%</span></td>" in rows["カバレッジアイテム"] and "上限の入力欄がまだ無い" in rows["カバレッジアイテム"]
        htc4 = self._pane(html, "im-cond").split('id="im-cond-COND-001-HTC-004"')[1].split("</details>")[0]
        assert 'class="ng"' in htc4.split("</summary>")[0] and "上限の入力欄がまだ無い" in htc4
        assert 'class="warn"' in self._pane(html, "im-cond").split('id="im-cond-COND-001"')[1].split("</summary>")[0]

    def test_テスト実装のカバレッジは種類ごとの割合を開く一覧より上に出す(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "implementation")
        section = html.split("<h2>ローレベルテストケースのカバレッジ</h2>")[1].split("<h2>")[0]
        assert section.index("<table>") < section.index('<div class="tabs">')

    def test_一覧の件数の横に実装したハイレベルテストケースの割合を出す(self, root):
        self._add_htc4(root, "上限の入力欄がまだ無い")
        html = tm_html.render_stage(tm_core.load_project(root), "implementation")
        cond1 = self._pane(html, "im-cond").split('id="im-cond-COND-001"')[1].split("</summary>")[0]
        assert "実装したハイレベル 2 / 3 (66%)" in cond1
        req = self._pane(html, "im-req")
        assert "実装したハイレベル 2 / 3 (66%)" in req.split('id="im-req-REQ-001-SPEC-001"')[1].split("</summary>")[0]
        assert "実装したハイレベル 1 / 1 (100%)" in req.split('id="im-req-REQ-002"')[1].split("</summary>")[0]
        cond3 = req.split('id="im-req-REQ-001-COND-003"')[1].split("</summary>")[0]
        assert "実装したハイレベル" not in cond3  # チャーターしかないテスト条件には割合を出さない

    def test_未実装で止まっているテスト条件と仕様は止まっている理由をたどって出す(self, root):
        path = root / "06_テスト実装/ローレベルテストケース.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "| LTC-003 | HTC-003 | 登録後の画面を確かめる | 30 | 確認画面を表示 | 手動テスト | 低 |\n", ""), encoding="utf-8")
        (root / "06_テスト実装/未実装.md").write_text(
            "# 未実装\n\n| ハイレベルテストケースID | 理由 |\n|---|---|\n| HTC-003 | 確認画面の文言が回答待ち |\n", encoding="utf-8")
        rows = self._impl_rows(tm_html.render_stage(tm_core.load_project(root), "implementation"))
        assert "COND-002" in rows["テスト条件"] and "確認画面の文言が回答待ち" in rows["テスト条件"]
        assert "SPEC-003" in rows["仕様"] and "COND-002" in rows["仕様"]

    def test_未実装に書いていないハイレベルテストケースはローレベルテストケースが無いと出す(self, root):
        self._add_htc4(root)
        rows = self._impl_rows(tm_html.render_stage(tm_core.load_project(root), "implementation"))
        assert "ローレベルテストケースが無い" in rows["ハイレベルテストケース"]

    def test_テスト条件からハイレベルとローレベルのテストケースをたどれる(self, root):
        pane = self._pane(tm_html.render_stage(tm_core.load_project(root), "implementation"), "im-cond")
        cond1 = pane.split('id="im-cond-COND-001"')[1]
        assert 'class="ok"' in cond1.split("</summary>")[0]
        assert "LTC-001" in cond1.split('id="im-cond-COND-001-HTC-001"')[1].split("</details>")[0]
        assert "CH-001" in pane.split('id="im-cond-COND-003"')[1].split("</details>")[0]

    def test_要求からテスト条件の下のローレベルテストケースまでたどれる(self, root):
        pane = self._pane(tm_html.render_stage(tm_core.load_project(root), "implementation"), "im-req")
        cond1 = pane.split('id="im-req-REQ-001-SPEC-001-COND-001"')[1].split("</details>")[0]
        assert "LTC-001" in cond1 and "LTC-002" in cond1 and "HTC-001" in cond1

    def test_ローレベルテストケースは開くと入力と期待値ともとのテストケースと手順が出る(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "implementation")
        section = html.split("<h2>ローレベルテストケース</h2>")[1]
        summary, kids = section.split('id="ltc-LTC-003"')[1].split("</details>")[0].split("</summary>")
        assert "登録後の画面を確かめる" in summary
        assert "確認画面を表示" in kids and "30" in kids and "HTC-003" in kids and "PROC-001" in kids

    # ---- E2E自動テストスクリプト作成: スクリプトのカバレッジ ----

    @staticmethod
    def _drop_scr2(root, unautomated_reason: str = ""):
        """SCR-002 を消して、LTC-002 をスクリプトの無い状態にする。理由を渡すと 07 の未実装.md に書く。"""
        path = root / "07_E2E自動テストスクリプト/スクリプト一覧.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "| SCR-002 | LTC-002 | tests/e2e/register.spec.js | LTC-002 17歳で登録する |\n", ""), encoding="utf-8")
        if unautomated_reason:
            (root / "07_E2E自動テストスクリプト/未実装.md").write_text(
                f"# 未実装\n\n| ローレベルテストケースID | 理由 |\n|---|---|\n| LTC-002 | {unautomated_reason} |\n", encoding="utf-8")

    @staticmethod
    def _e2e_rows(html: str) -> dict[str, str]:
        table = html.split("<h2>E2E自動テストスクリプトのカバレッジ</h2>")[1].split("</table>")[0]
        return {kind: next(r for r in table.split("</tr>") if f">{kind}</span></td>" in r)
                for kind in ("要求", "仕様", "テスト条件", "ローレベルテストケース")}

    def test_E2Eのページはいちばん上にスクリプトのカバレッジを出し古い追跡表は出さない(self, root):
        main = tm_html.render_stage(tm_core.load_project(root), "e2e").split("<main>")[1]
        assert main.split("<h2>")[1].startswith("E2E自動テストスクリプトのカバレッジ")
        assert "<h2>自動化できなかったテストケースと理由</h2>" in main
        assert "要求 → E2E自動テストスクリプト" not in main

    def test_E2E自動テストのローレベルテストケースのうちスクリプトがある割合を出す(self, root):
        rows = self._e2e_rows(tm_html.render_stage(tm_core.load_project(root), "e2e"))
        ok = '<td><span class=\"pct ok\">100%</span></td>'
        assert "<td>2 / 2</td>" + ok in rows["ローレベルテストケース"]  # 手動テストの LTC-003 は数えない
        assert "<td>1 / 1</td>" + ok in rows["テスト条件"]
        assert "<td>1 / 1</td>" + ok in rows["仕様"]
        assert "<td>1 / 1</td>" + ok in rows["要求"]

    def test_スクリプトが無いものは理由とともに出す(self, root):
        self._drop_scr2(root)
        rows = self._e2e_rows(tm_html.render_stage(tm_core.load_project(root), "e2e"))
        assert "<td>1 / 2</td>" in rows["ローレベルテストケース"] and "LTC-002" in rows["ローレベルテストケース"]
        assert "スクリプトが無い" in rows["ローレベルテストケース"]
        assert "<td>0 / 1</td>" in rows["テスト条件"] and "LTC-002" in rows["テスト条件"]

    def test_自動化できなかったものは理由を出す(self, root):
        self._drop_scr2(root, "画面の外の操作が要る")
        html = tm_html.render_stage(tm_core.load_project(root), "e2e")
        assert "画面の外の操作が要る" in self._e2e_rows(html)["ローレベルテストケース"]
        ltc2 = self._pane(html, "e2e-req").split('id="e2e-req-REQ-001-SPEC-001-COND-001"')[1].split("</details>")[0]
        assert "LTC-002" in ltc2 and "画面の外の操作が要る" in ltc2
        assert 'class="warn"' in self._pane(html, "e2e-req").split('id="e2e-req-REQ-001-SPEC-001-COND-001"')[1].split("</summary>")[0]

    def test_テスト名から出どころの成果物を上にたどれる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "e2e")
        assert "ファイルからたどる" not in html
        summary, kids = self._pane(html, "e2e-test").split('id="e2e-test-SCR-001"')[1].split("</details>")[0].split("</summary>")
        assert "LTC-001 18歳で登録する" in summary
        assert "tests/e2e/register.spec.js" in kids
        for upstream in ("LTC-001", "HTC-001", "COND-001", "SPEC-001", "REQ-001"):
            assert f'href="ID索引.html#{upstream}"' in kids, upstream
        assert kids.index("LTC-001") < kids.index("HTC-001") < kids.index("COND-001") < kids.index("SPEC-001") < kids.index("REQ-001")

    def test_要求からE2Eのローレベルテストケースとスクリプトまでたどれる(self, root):
        pane = self._pane(tm_html.render_stage(tm_core.load_project(root), "e2e"), "e2e-req")
        cond1 = pane.split('id="e2e-req-REQ-001-SPEC-001-COND-001"')[1].split("</details>")[0]
        assert "LTC-001" in cond1 and "SCR-001" in cond1 and "register.spec.js" in cond1
        assert "LTC-003" not in pane  # 手動テストは出さない
        assert 'id="e2e-req-REQ-002"' not in pane  # E2E自動テストが無い要求は出さない

    # ---- テスト実行: タブで切り替えるページ ----

    @staticmethod
    def _ex_card(html: str, pane: str, card_id: str) -> tuple[str, str]:
        block = html.split(f'id="{pane}"')[1].split(f'id="{card_id}"')[1]
        summary, rest = block.split("</summary>", 1)
        return summary, rest.split('<details class="card"')[0]  # 中にたたみが入れ子になるので、次のカードの手前まで

    def test_テスト実行のページは7つのタブで切り替える(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        main = html.split("<main>")[1]
        labels = [l.split("</label>")[0] for l in main.split('<label for="tab-ex-')[1:8]]
        names = [l.split('">')[1] for l in labels]
        assert [n.split("(")[0] for n in names] == ["まとめ", "Fail", "E2E自動テスト", "手動テスト", "探索的テスト", "欠陥レポート", "質問・ドキュメント"]
        assert "Fail(1)" in names and "E2E自動テスト(2)" in names and "手動テスト(1)" in names and "欠陥レポート(1)" in names
        # 質問とドキュメントは最後のタブの中に入れ、ページの下には重ねて出さない
        last = main.split('id="ex-docs"')[1]
        assert "この工程のドキュメント" in last and main.count("この工程のドキュメント</h2>") == 1

    def test_まとめのタブに件数と要求からたどれる一覧を出す(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        pane = html.split('id="ex-sum"')[1].split('id="ex-e2e"')[0]
        assert "実施方法" in pane and "Pass" in pane and 'id="tree-REQ-001"' in pane

    def test_まとめのタブに探索的テストの結果も出す(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        pane = html.split('id="ex-sum"')[1].split('id="ex-e2e"')[0]
        assert "探索的テストのセッション <b>1</b>" in pane
        table = pane.split("<h3>探索的テスト</h3>")[1].split("</table>")[0]
        row = table.split("<tbody>")[1]
        # テストチャーター / 探索した / セッション / 時間(合計 / 時間枠) / 時間枠に達した / 見つけた不具合
        assert "<td>1</td><td>1</td><td>1</td><td>15 / 15</td><td>1 / 1</td><td>0件</td>" in row

    def test_FailのタブにはFailのテストケースだけを出す(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        pane = html.split('id="ex-fail"')[1].split('id="ex-e2e"')[0]
        assert 'id="ex-fail-ltc-LTC-002"' in pane and "BUG-001" in pane
        assert "LTC-001" not in pane and "LTC-003" not in pane

    def test_E2Eと手動のタブでテストケースごとの結果と証跡と欠陥レポートをたどれる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        summary, kids = self._ex_card(html, "ex-e2e", "ex-ltc-LTC-002")
        assert 'class="ng"' in summary and "Fail" in summary and "17歳で登録する" in summary
        assert "../08_テスト実行/RUN-20261101-100000/証跡/LTC-002.png" in kids and "BUG-001" in kids
        assert "LTC-003" not in html.split('id="ex-e2e"')[1].split('id="ex-manual"')[0]
        summary3, _ = self._ex_card(html, "ex-manual", "ex-ltc-LTC-003")
        assert 'class="ok"' in summary3 and "Pass" in summary3

    def test_探索的テストのタブでセッションからチャーターとセッションシートをたどれる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        summary, kids = self._ex_card(html, "ex-ses", "ex-ses-SES-001")
        assert "15分" in summary
        assert "CH-001" in kids and "セッションシート" in kids

    def test_欠陥レポートのタブで詳しい節と見つけたテストと影響する要求が出る(self, root):
        append_to(root, "08_テスト実行/欠陥レポート.md", "\n## BUG-001\n\n- 再現できる手順: 年齢に17を入れて登録する\n")
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        summary, kids = self._ex_card(html, "ex-bug", "ex-bug-BUG-001")
        assert "17歳で登録できてしまう" in summary and "高" in summary and "未修正" in summary
        assert "年齢に17を入れて登録する" in kids and "LTC-002" in kids and "REQ-001" in kids

    BUG_DETAIL = (
        "\n## BUG-001\n\n"
        "- 再現できる手順:\n  1. 登録画面を開く\n  2. 年齢に17を入れて登録する\n"
        "- 期待値: エラーを表示する\n"
        "- 実際の結果: 登録が完了する\n  - 17歳: 登録完了\n  - 16歳: 登録完了\n"
        "- 原因の見立て(推測): 下限の比較が逆\n"
        "- 証跡: RUN-20261101-100000/証跡/LTC-002.png、LTC-003.png(どれも同じフォルダ)\n"
        "- 重要度: 年齢の確認は法令に関わるので高\n"
        "- メモ: 18歳は正しく通る\n"
    )

    def _bug_kids(self, root) -> str:
        append_to(root, "08_テスト実行/欠陥レポート.md", self.BUG_DETAIL)
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        return self._ex_card(html, "ex-bug", "ex-bug-BUG-001")[1]

    def test_欠陥レポートは期待値と実際の結果を並べ再現手順をその下に出す(self, root):
        kids = self._bug_kids(root)
        compare = kids.split('<div class="bug-compare">')[1].split('<div class="bug-steps">')[0]
        assert "期待値" in compare and "エラーを表示する" in compare
        assert "実際の結果" in compare and "登録が完了する" in compare and "16歳" not in compare
        steps = kids.split('<div class="bug-steps">')[1].split("</div>")[0]
        assert "<ol><li>登録画面を開く</li><li>年齢に17を入れて登録する</li></ol>" in steps

    def test_欠陥レポートのほかの項目はたたんでおく(self, root):
        kids = self._bug_kids(root)
        folds = [f.split("</summary>")[0] for f in kids.split('<details class="fold"><summary>')[1:]]
        assert folds[0] == "実際の結果の詳しい内容(2件)"
        for name in ("原因の見立て(推測)", "重要度", "証跡(2件)", "見つけたテスト(LTC 1件・セッション 0件)",
                     "影響する要求・リスク・テスト対象と環境", "メモ"):
            assert name in folds, name
        assert "16歳: 登録完了" in kids.split("実際の結果の詳しい内容(2件)</summary>")[1].split("</details>")[0]

    def test_欠陥レポートの証跡はテストランのフォルダのファイルへのリンクにする(self, root):
        evidence = self._bug_kids(root).split("証跡(2件)</summary>")[1].split("</details>")[0]
        assert 'href="../08_テスト実行/RUN-20261101-100000/証跡/LTC-002.png"' in evidence
        assert 'href="../08_テスト実行/RUN-20261101-100000/証跡/LTC-003.png"' in evidence  # 同じフォルダのファイル

    def test_証跡の欄に文や注記が続いてもファイルごとにリンクにする(self):
        v = tm_html.View(tm_core.Project(Path(".")))
        text = ("RUN-1/証跡/a.png。探索的テストの証跡: RUN-1/証跡/b.txt(画面が無いので、文字で残した)、c.jpg、"
                "RUN-2/証跡/d.png(どれも同じフォルダ)")
        hrefs = [l.split('href="')[1].split('"')[0] for l in tm_html._evidence_links(v, text) if 'href="' in l]
        assert hrefs == ["../08_テスト実行/RUN-1/証跡/a.png", "../08_テスト実行/RUN-1/証跡/b.txt",
                         "../08_テスト実行/RUN-1/証跡/c.jpg", "../08_テスト実行/RUN-2/証跡/d.png"]

    def test_証跡はフォルダにある実際のファイル名を探してリンクにする(self, root):
        evidence = root / "08_テスト実行/RUN-20261101-100000/証跡"
        (evidence / "SES-001_退職60,5と65。5.jpg").write_bytes(b"x")
        v = tm_html.View(tm_core.load_project(root))
        text = "RUN-20261101-100000/証跡/LTC-002.png、SES-001_退職60,5と65。5.jpg(区切りの記号を含む名前)"
        hrefs = [l.split('href="')[1].split('"')[0] for l in tm_html._evidence_links(v, text) if 'href="' in l]
        assert hrefs == ["../08_テスト実行/RUN-20261101-100000/証跡/LTC-002.png",
                         "../08_テスト実行/RUN-20261101-100000/証跡/SES-001_退職60,5と65。5.jpg"]

    def test_ID索引で上流と下流の両方にたどれる(self, root):
        html = tm_html.render_ids(tm_core.load_project(root))
        block = html.split('id="COND-001"')[1].split('class="record"')[0]
        assert "REQ-001" in block  # 上流
        assert "LTC-001" in block  # 下流


class Testテストレポート:
    def _build(self, root, judgment=JUDGMENT, timestamp="20261101120000"):
        (root / "09_テストレポート").mkdir(exist_ok=True)
        (root / "09_テストレポート/判定.md").write_text(judgment, encoding="utf-8")
        project = tm_core.load_project(root)
        return tm_html.build_report(project, timestamp)

    @staticmethod
    def _target(entry: Path) -> str:
        """入口のページが飛ぶ先(meta refresh の url)。"""
        from urllib.parse import unquote
        html = entry.read_text(encoding="utf-8")
        return unquote(html.split('http-equiv="refresh" content="0; url=')[1].split('"')[0])

    def test_成果物のフォルダの直下とレポートのフォルダに最新のレポートへ飛ぶ入口を置く(self, root):
        self._build(root)
        assert self._target(root / "テストレポート.html") == "09_テストレポート/20261101120000/テストレポート.html"
        assert self._target(root / "09_テストレポート/テストレポート.html") == "20261101120000/テストレポート.html"

    def test_入口は日時のいちばん新しいレポートへ飛ぶ(self, root):
        self._build(root, timestamp="20261102120000")
        self._build(root, timestamp="20261101120000")  # 古い日時で作り直しても、新しい方を指したまま
        assert "20261102120000" in self._target(root / "テストレポート.html")

    def test_入口は成果物の写しに入れない(self, root):
        self._build(root, timestamp="20261101120000")
        out = self._build(root, timestamp="20261102120000")
        assert not (out / "snapshot/テストレポート.html").exists()

    def test_レポートを作ると目次にも最新のレポートへのリンクが出る(self, root):
        tm_html.build_html(tm_core.load_project(root))  # テスト実行までの工程で目次ができている
        self._build(root)
        index = (root / "結果まとめ/目次.html").read_text(encoding="utf-8")
        assert 'href="../09_テストレポート/20261101120000/テストレポート.html"' in index

    def test_目次のいちばん上に最新のレポートへのリンクを出す(self, root):
        self._build(root)
        (root / "テストレポート.html").unlink()
        tm_html.build_html(tm_core.load_project(root))
        index = (root / "結果まとめ/目次.html").read_text(encoding="utf-8")
        main = index.split("<main>")[1]
        assert main.index('class="latest-report"') < main.index("<h2>")
        assert 'href="../09_テストレポート/20261101120000/テストレポート.html"' in main
        assert (root / "テストレポート.html").exists()  # 視認性アップでも入口を作り直す

    def test_ファーストビューに終了条件の判定と問題点を出す(self, root):
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        first = html.split('id="first-view"')[1].split('id="details"')[0]
        assert "満たしていない終了条件が 1 件" in first
        assert "EXIT-002" in first and "が未修正" in first
        assert "BUG-001" in first and "17歳で登録できてしまう" in first
        assert "未回答の質問" in first

    def test_満たしていない終了条件を先に並べてバナーにIDを書く(self, root):
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        first = html.split('id="first-view"')[1].split('id="details"')[0]
        banner = first.split("</div>")[0]
        assert "EXIT-002" in banner and "EXIT-001" not in banner
        assert first.index('EXIT-002') < first.index('EXIT-001')

    def test_判定が書かれていない終了条件は未判定として出す(self, root):
        out = self._build(root, JUDGMENT.replace("| EXIT-002 | 満たしていない | 重要度が高の BUG-001 が未修正 |\n", ""))
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        first = html.split('id="first-view"')[1].split('id="details"')[0]
        assert "未判定" in first
        assert "すべての終了条件を満たした" not in first

    def test_すべて満たしたときはそう書く(self, root):
        out = self._build(root, JUDGMENT.replace("満たしていない | 重要度が高の BUG-001 が未修正", "満たした | 未修正は0件"))
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        assert "すべての終了条件を満たした" in html.split('id="first-view"')[1].split('id="details"')[0]

    def _tree_block(self, html, top_id, next_id=None):
        block = html.split(f'id="tree-{top_id}"')[1]
        return block.split(f'id="tree-{next_id}"')[0] if next_id else block

    def test_要求からテスト結果まで開いてたどれる(self, root):
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        block = self._tree_block(html, "REQ-001", "REQ-002")
        order = [block.index(i) for i in ["SPEC-001", "COND-001", "HTC-001", "LTC-001"]]
        assert order == sorted(order)
        ltc = block.split('data-id="LTC-002"')[1].split("</div>")[0]
        assert "Fail" in ltc and "BUG-001" in ltc and "証跡" in ltc
        assert "COND-003" in block and "CH-001" in block and "SES-001" in block  # 利用の流れと探索的テスト

    def test_仕様の下に出るテスト条件は要求の直下にもう一度出さない(self, root):
        text = (root / "04_テスト分析/テスト分析.md").read_text(encoding="utf-8")
        text = text.replace("| COND-001 | 年齢の有効範囲 | FT-001 | TA-001 | SPEC-001 |", "| COND-001 | 年齢の有効範囲 | FT-001 | TA-001 | SPEC-001, REQ-001 |")
        (root / "04_テスト分析/テスト分析.md").write_text(text, encoding="utf-8")
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        block = self._tree_block(html, "REQ-001", "REQ-002")
        assert block.count('data-id="COND-001"') == 1

    def test_行に実行の割合と問題の件数を出す(self, root):
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        summary = self._tree_block(html, "REQ-001").split("</summary>")[0]
        assert "実行 3/3(100%)" in summary  # LTC-001・LTC-002 と、探索したテストチャーター CH-001
        assert "Fail 1" in summary and "不具合 1" in summary
        assert 'class="ng"' in summary
        summary = self._tree_block(html, "REQ-002").split("</summary>")[0]
        assert "実行 1/1(100%)" in summary and 'class="ok"' in summary

    def test_テスト条件の行にカバレッジアイテムの通る数を出す(self, root):
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        cond = self._tree_block(html, "REQ-001", "REQ-002").split('data-id="COND-001"')[1].split("</summary>")[0]
        assert "カバレッジアイテム 2/2" in cond

    def test_未実装のハイレベルテストケースは理由を出す(self, root):
        text = (root / "05_テスト設計/テスト設計.md").read_text(encoding="utf-8")
        text = text.replace("| CI-003 | 確認画面が表示される | COND-002 |", "| CI-003 | 確認画面が表示される | COND-002 |\n| CI-004 | 上限の境界値 65 | COND-001 |")
        text = text.replace("| 手動テスト | 低 | 設計済み |\n", "| 手動テスト | 低 | 設計済み |\n| HTC-004 | 上限の境界値のとき登録できる | COND-001 | CI-004 | 登録できる | E2E自動テスト | 高 | 回答待ち(Q-001) |\n")
        (root / "05_テスト設計/テスト設計.md").write_text(text, encoding="utf-8")
        append_to(root, "06_テスト実装/未実装.md", "# 未実装\n\n| ハイレベルテストケースID | 理由 |\n|---|---|\n| HTC-004 | 回答待ち(Q-001) |\n")
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        htc = self._tree_block(html, "REQ-001", "REQ-002").split('data-id="HTC-004"')[1].split("</details>")[0]
        assert "未実装" in htc and "Q-001" in htc
        cond = self._tree_block(html, "REQ-001", "REQ-002").split('data-id="COND-001"')[1].split("</summary>")[0]
        assert "カバレッジアイテム 2/3" in cond

    def test_リスクからたどる版をリスクレベルの高い順に出す(self, root):
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        risk_part = html.split('id="risk-coverage"')[1]
        assert risk_part.index('id="tree-RISK-001"') < risk_part.index('id="tree-RISK-002"')

    def test_仕様のカバレッジとテストチャーターの時間を出す(self, root):
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        row = next(line for line in html.split("</tr>") if 'id="cov-SPEC-002"' in line)
        assert "まったくテストしていない" in row
        row = next(line for line in html.split("</tr>") if 'id="time-CH-001"' in line)
        assert "15" in row and "達した" in row

    def test_スコープ外の不具合は影響する要求を出さずスコープ外と書く(self, root):
        text = (root / "08_テスト実行/欠陥レポート.md").read_text(encoding="utf-8")
        text = text.replace("| 関連ID |\n|---|---|---|---|---|---|\n", "| 関連ID | 要求・仕様ID |\n|---|---|---|---|---|---|---|\n")
        text = text.replace("| LTC-002 |\n", "| LTC-002 | スコープ外 |\n")
        (root / "08_テスト実行/欠陥レポート.md").write_text(text, encoding="utf-8")
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        _, kids = Test視認性アップ._ex_card(html, "ex-bug", "ex-bug-BUG-001")
        affected = kids.split("<dt>影響する要求</dt>")[1].split("</dd>")[0]
        assert "スコープ外" in affected and "REQ-001" not in affected

    def test_判定に書いた文章と戻し記録を載せる(self, root):
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        assert "境界値のテスト条件を最初から厚くする" in html
        assert "RB-001" in html

    # ---- テストレポートのタブ ----

    @staticmethod
    def _report_pane(html: str, pane_id: str, next_id: str | None) -> str:
        part = html.split(f'<div class="pane tree" id="{pane_id}">')[1]
        return part.split(f'<div class="pane tree" id="{next_id}">')[0] if next_id else part

    def test_レポートは判定と実行のタブと判定の記録のタブで切り替える(self, root):
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        main = html.split("<main>")[1]
        labels = [l.split("</label>")[0].split('">')[1] for l in main.split('<label for="tab-rp-')[1:]]
        labels += [l.split("</label>")[0].split('">')[1] for l in main.split('<label for="tab-ex-')[1:]]
        order = sorted(labels, key=lambda name: main.index(f'">{name}</label>'))
        assert [n.split("(")[0] for n in order] == [
            "判定", "まとめ", "Fail", "E2E自動テスト", "手動テスト", "探索的テスト", "欠陥レポート", "判定の記録"]
        assert '<input type="radio" name="rp-tab" id="tab-rp-judge" checked>' in main  # 最初は判定を開く
        assert "質問・ドキュメント" not in main

    def test_判定のタブは帯のあとに問題点とやるべきことを1列で並べる(self, root):
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        first = html.split('id="first-view"')[1].split('id="details"')[0]
        assert 'class="cols"' not in first
        assert first.index("満たしていない終了条件が 1 件") < first.index("問題点は何か") < first.index("やるべきことをやったか")

    def test_判定のタブにファーストビューを出す(self, root):
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        judge = self._report_pane(html, "rp-judge", "ex-sum")
        assert 'id="first-view"' in judge and "満たしていない終了条件が 1 件" in judge

    @staticmethod
    def _rerun_on_new_version(root):
        """v1 で全部実行したあと、v2 で LTC-002 だけ実行し直す。"""
        append_to(root, "08_テスト実行/RUN-20261101-100000/実行情報.md", "- テスト対象の版: v1\n")
        append_to(root, "08_テスト実行/RUN-20261102-090000/実行情報.md", "- テスト対象の版: v2\n")
        append_to(root, "08_テスト実行/RUN-20261102-090000/テスト結果_E2E自動.md",
                  "| ローレベルテストケースID | 実施方法 | 結果 | 証跡 | 欠陥レポートID | メモ |\n|---|---|---|---|---|---|\n"
                  "| LTC-002 | E2E自動テスト | Pass | | | 確認テスト |\n")

    def test_判定のタブの問題点に前の版の結果を使っているテストケースを出す(self, root):
        self._rerun_on_new_version(root)
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        problems = self._report_pane(html, "rp-judge", "ex-sum").split("問題点は何か")[1].split("やるべきことをやったか")[0]
        assert "今の版(v2)で確かめていない結果: 2 件" in problems
        assert "LTC-001" in problems and "LTC-003" in problems

    def test_判定の記録のタブに今の版で確かめていない結果を全件出す(self, root):
        self._rerun_on_new_version(root)
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        stale = self._report_pane(html, "rp-record", None).split('id="stale-results"')[1].split("</table>")[0]
        assert "RUN-20261102-090000" in stale  # 今の版を決めたテストラン
        assert stale.count("<tr>") == 3 and "LTC-001" in stale and "LTC-003" in stale and "LTC-002" not in stale

    def test_どのテストランにも版が無ければ前の版の結果を出さない(self, root):
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        assert "で確かめていない結果" not in html

    def test_テスト結果を開くとテスト対象の版が出る(self, root):
        self._rerun_on_new_version(root)
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        card = html.split('id="ex-ltc-LTC-001"')[1].split("</details>")[0]
        assert "テスト対象の版" in card and "v1" in card

    def test_まとめのタブに仕様のカバレッジとテストチャーターの時間も出す(self, root):
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        summary = self._report_pane(html, "ex-sum", "ex-fail")
        assert 'id="cov-SPEC-002"' in summary and 'id="time-CH-001"' in summary and 'id="tree-REQ-001"' in summary

    def test_判定の記録のタブに書いた文章と実行していないものと質問と戻し記録を出す(self, root):
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        record = self._report_pane(html, "rp-record", None)
        assert "境界値のテスト条件を最初から厚くする" in record and "RB-001" in record
        assert 'id="not-run"' in record and 'id="questions"' in record

    def test_レポートの未回答の質問に実機の動きを出す(self, root):
        Test視認性アップ._add_observed(Test視認性アップ(), root)
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        questions = self._report_pane(html, "rp-record", None).split('id="questions"')[1].split("</table>")[0]
        assert "<th>実機の動き</th>" in questions and "17 として登録される" in questions
        assert "証跡: RUN-" not in questions
        assert 'href="snapshot/08_テスト実行/RUN-20261101-100000/証跡/LTC-002.png"' in questions
        first = html.split('id="first-view"')[1].split('id="details"')[0]
        assert "うち実機の動きあり <b>1</b> 件" in first

    def test_ページの中のリンクで別のタブの中へ飛ぶとそのタブを開く(self, root):
        html = (self._build(root) / "テストレポート.html").read_text(encoding="utf-8")
        assert "function tmShowHash" in html and "hashchange" in html

    def test_作った時点の成果物を一緒に保存する(self, root):
        out = self._build(root)
        assert (out / "snapshot/01_要求仕様/要求.md").exists()
        assert (out / "snapshot/08_テスト実行/RUN-20261101-100000/証跡/LTC-002.png").exists()
        assert not (out / "snapshot/09_テストレポート").exists()
        assert (out / "ID索引.html").exists() and (out / "リスク分析.html").exists()

    def test_成果物の写しに結果まとめと工程のページは入れない(self, root):
        tm_html.build_html(tm_core.load_project(root))
        out = self._build(root)
        assert not (out / "snapshot/結果まとめ").exists()
        assert not (out / "snapshot/02_リスク分析/リスク分析.html").exists()
        assert (out / "snapshot/02_リスク分析/リスク分析.md").exists()

    def test_レポートのページはレポートの中のページへリンクする(self, root):
        out = self._build(root)
        html = (out / "リスク分析.html").read_text(encoding="utf-8")
        assert '<a href="テストレポート.html">テストレポート</a>' in html
        assert 'href="ID索引.html#RISK-001"' in html and 'href="テスト計画.html"' in html
        ids = (out / "ID索引.html").read_text(encoding="utf-8")
        assert 'href="snapshot/02_リスク分析/リスク分析.md"' in ids

    def test_判定のファイルが無いと作らずに理由を伝える(self, root):
        project = tm_core.load_project(root)
        with pytest.raises(tm_html.ReportError) as error:
            tm_html.build_report(project, "20261101120000")
        assert "判定.md" in str(error.value)
