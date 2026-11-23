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
        assert "<td>2 / 2</td><td>100%</td>" in self._coverage_row(html, "要求")
        assert "<td>3 / 3</td><td>100%</td>" in self._coverage_row(html, "仕様")
        assert "<td>2 / 2</td><td>100%</td>" in self._coverage_row(html, "リスク")

    def test_テストアプローチが無い仕様があれば割合とIDと理由を出す(self, root):
        append_to(root, "01_要求仕様/仕様.md", "| SPEC-004 | 確認画面に戻るボタンがある | REQ-002 | 仕様書 2.3 |\n")
        row = self._coverage_row(tm_html.render_stage(tm_core.load_project(root), "plan"), "仕様")
        assert "<td>3 / 4</td><td>75%</td>" in row and "SPEC-004" in row and "テストアプローチが無い" in row

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
        assert "<td>2 / 2</td><td>100%</td>" in rows["要求"]
        assert "<td>2 / 3</td><td>66%</td>" in rows["仕様"] and "SPEC-002" in rows["仕様"]
        assert "テスト条件が無い" in rows["仕様"]
        assert "<td>2 / 2</td><td>100%</td>" in rows["リスク"]
        assert "<td>3 / 3</td><td>100%</td>" in rows["テストアプローチ"]

    def test_要求からたどると仕様の下にテスト条件が出て無い仕様は赤くなる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "analysis")
        pane = self._pane(html, "an-req")
        req1 = pane.split('id="an-req-REQ-001"')[1]
        assert "COND-003" in req1.split('id="an-req-SPEC-001"')[0]  # 要求に直接紐づくテスト条件(利用の流れ)
        assert "COND-001" not in req1.split('id="an-req-SPEC-001"')[0]  # 仕様のテスト条件は要求の直下に重ねて出さない
        assert "テスト条件 2件" in req1.split("</summary>")[0]
        assert "COND-001" in req1.split('id="an-req-SPEC-001"')[1].split("</details>")[0]
        spec2 = pane.split('id="an-req-SPEC-002"')[1].split("</summary>")[0]
        assert 'class="ng"' in spec2 and "テスト条件 0件" in spec2
        assert 'class="ok"' in pane.split('id="an-req-SPEC-001"')[1].split("</summary>")[0]

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
        spec2 = self._pane(html, "an-req").split('id="an-req-SPEC-002"')[1].split("</summary>")[0]
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

    def test_テスト実装のページでカバレッジアイテムをどこまで通せているかがわかる(self, root):
        text = (root / "05_テスト設計/テスト設計.md").read_text(encoding="utf-8")
        text = text.replace("| CI-003 | 確認画面が表示される | COND-002 |", "| CI-003 | 確認画面が表示される | COND-002 |\n| CI-004 | 上限の境界値 65 | COND-001 |")
        text = text.replace("| 手動テスト | 低 | 設計済み |\n", "| 手動テスト | 低 | 設計済み |\n| HTC-004 | 上限の境界値のとき登録できる | COND-001 | CI-004 | 登録できる | E2E自動テスト | 高 | 設計済み |\n")
        (root / "05_テスト設計/テスト設計.md").write_text(text, encoding="utf-8")
        html = tm_html.render_stage(tm_core.load_project(root), "implementation")
        row = next(line for line in html.split("</tr>") if 'id="impl-cov-COND-001"' in line)
        assert "<td>2 / 3</td>" in row      # ローレベルテストケースで通せている数 / 出した数
        assert "CI-004" in row              # 通せていないカバレッジアイテム

    def test_テスト実行のページで結果と証跡と欠陥レポートをたどれる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "execution")
        row = next(line for line in html.split("</tr>") if 'id="result-LTC-002"' in line)
        assert "Fail" in row and "BUG-001" in row
        assert "../08_テスト実行/RUN-20261101-100000/証跡/LTC-002.png" in row

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
        row = next(line for line in html.split("</tr>") if "BUG-001" in line and "<td" in line and "高" in line)
        assert "スコープ外" in row and "REQ-001" not in row

    def test_判定に書いた文章と戻し記録を載せる(self, root):
        out = self._build(root)
        html = (out / "テストレポート.html").read_text(encoding="utf-8")
        assert "境界値のテスト条件を最初から厚くする" in html
        assert "RB-001" in html

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
