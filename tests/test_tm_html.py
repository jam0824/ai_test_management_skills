"""tm_html(視認性アップのHTMLとテストレポート)のテスト。"""
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
    def test_工程ごとのページとID索引を作る(self, root):
        project = tm_core.load_project(root)
        out = root / "html"
        tm_html.build_html(project, out)
        for name in ["index.html", "ids.html", "requirements.html", "risk.html", "plan.html", "analysis.html",
                     "design.html", "implementation.html", "e2e.html", "execution.html"]:
            assert (out / name).exists(), name

    def test_リスクのページで要求から仕様とリスクまでたどれる(self, root):
        html = tm_html.render_stage(tm_core.load_project(root), "risk")
        row = next(line for line in html.split("</tr>") if 'id="row-RISK-001"' in line)
        assert "REQ-001" in row and "SPEC-001" in row

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
    def _build(self, root, judgment=JUDGMENT):
        (root / "09_テストレポート").mkdir(exist_ok=True)
        (root / "09_テストレポート/判定.md").write_text(judgment, encoding="utf-8")
        project = tm_core.load_project(root)
        return tm_html.build_report(project, "20261101120000")

    def test_ファーストビューに終了条件の判定と問題点を出す(self, root):
        out = self._build(root)
        html = (out / "index.html").read_text(encoding="utf-8")
        first = html.split('id="first-view"')[1].split('id="details"')[0]
        assert "満たしていない終了条件が 1 件" in first
        assert "EXIT-002" in first and "が未修正" in first
        assert "BUG-001" in first and "17歳で登録できてしまう" in first
        assert "未回答の質問" in first

    def test_満たしていない終了条件を先に並べてバナーにIDを書く(self, root):
        out = self._build(root)
        html = (out / "index.html").read_text(encoding="utf-8")
        first = html.split('id="first-view"')[1].split('id="details"')[0]
        banner = first.split("</div>")[0]
        assert "EXIT-002" in banner and "EXIT-001" not in banner
        assert first.index('EXIT-002') < first.index('EXIT-001')

    def test_判定が書かれていない終了条件は未判定として出す(self, root):
        out = self._build(root, JUDGMENT.replace("| EXIT-002 | 満たしていない | 重要度が高の BUG-001 が未修正 |\n", ""))
        html = (out / "index.html").read_text(encoding="utf-8")
        first = html.split('id="first-view"')[1].split('id="details"')[0]
        assert "未判定" in first
        assert "すべての終了条件を満たした" not in first

    def test_すべて満たしたときはそう書く(self, root):
        out = self._build(root, JUDGMENT.replace("満たしていない | 重要度が高の BUG-001 が未修正", "満たした | 未修正は0件"))
        html = (out / "index.html").read_text(encoding="utf-8")
        assert "すべての終了条件を満たした" in html.split('id="first-view"')[1].split('id="details"')[0]

    def test_要求とリスクのカバレッジを数えて出す(self, root):
        out = self._build(root)
        html = (out / "index.html").read_text(encoding="utf-8")
        row = next(line for line in html.split("</tr>") if 'id="cov-REQ-001"' in line)
        assert "実行したがFailあり" in row
        risk_part = html.split('id="risk-coverage"')[1]
        assert risk_part.index("RISK-001") < risk_part.index("RISK-002")

    def test_仕様のカバレッジとテストチャーターの時間を出す(self, root):
        out = self._build(root)
        html = (out / "index.html").read_text(encoding="utf-8")
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
        html = (out / "index.html").read_text(encoding="utf-8")
        assert "境界値のテスト条件を最初から厚くする" in html
        assert "RB-001" in html

    def test_作った時点の成果物を一緒に保存する(self, root):
        out = self._build(root)
        assert (out / "snapshot/01_要求仕様/要求.md").exists()
        assert (out / "snapshot/08_テスト実行/RUN-20261101-100000/証跡/LTC-002.png").exists()
        assert not (out / "snapshot/09_テストレポート").exists()
        assert (out / "ids.html").exists()

    def test_判定のファイルが無いと作らずに理由を伝える(self, root):
        project = tm_core.load_project(root)
        with pytest.raises(tm_html.ReportError) as error:
            tm_html.build_report(project, "20261101120000")
        assert "判定.md" in str(error.value)
