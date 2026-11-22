"""tm_core(成果物の読み取り・トレーサビリティの確認・集計)のテスト。"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tm_core  # noqa: E402
from sample_project import append_to, make_project, replace_in  # noqa: E402


@pytest.fixture
def root(tmp_path):
    return make_project(tmp_path / "テスト成果物")


class Test表の読み取り:
    def test_ID表の行をレコードとして読み取る(self, root):
        project = tm_core.load_project(root)
        spec = project.records["SPEC-001"]
        assert spec.type == "SPEC"
        assert spec.fields["仕様"] == "年齢は18〜65の整数だけ登録できる"
        assert spec.links == {"REQ-001"}
        assert spec.file == "01_要求仕様/仕様.md"

    def test_エスケープした縦棒を含むセルを読める(self):
        text = "| ID | 要求 |\n|---|---|\n| REQ-001 | A \\| B |\n"
        table = tm_core.parse_tables(text)[0]
        assert table.rows[0] == ["REQ-001", "A | B"]

    def test_コードブロックの中の表は読まない(self):
        text = "```\n| ID | 要求 |\n|---|---|\n| REQ-001 | 例 |\n```\n"
        assert tm_core.parse_tables(text) == []

    def test_日本語に続けて書かれたIDも拾う(self):
        assert tm_core.find_ids("要求REQ-001と仕様SPEC-002、FAQ-001は別") == ["REQ-001", "SPEC-002"]

    def test_先頭の列がIDでない表はレコードにしない(self, root):
        project = tm_core.load_project(root)
        # テスト結果の表は「ローレベルテストケースID」で始まるので、LTC を二重に定義しない
        assert not [e for e in project.load_errors if "LTC-001" in e]


class Testトレーサビリティの確認:
    def test_正しい成果物ではエラーが出ない(self, root):
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert errors == []

    def test_重複したIDをエラーにする(self, root):
        append_to(root, "01_要求仕様/要求.md", "| REQ-001 | 重複 | 利用者 | - |\n")
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert any("REQ-001" in e and "重複" in e for e in errors)

    def test_定義されていないIDへの紐づけをエラーにする(self, root):
        replace_in(root, "04_テスト分析/テスト分析.md", "| COND-002 | 確認画面の表示 | FT-002 |", "| COND-002 | 確認画面の表示 | FT-099 |")
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert any("COND-002" in e and "FT-099" in e for e in errors)

    def test_必須の紐づけが無いとエラーにする(self, root):
        replace_in(root, "01_要求仕様/仕様.md", "| REQ-002 | 仕様書 2.2 |", "| | 仕様書 2.2 |")
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert any("SPEC-003" in e and "要求" in e for e in errors)

    def test_どちらか一方でよい紐づけは片方あればエラーにしない(self, root):
        # テストアプローチは 仕様 か リスク のどちらかに紐づけばよい
        replace_in(root, "03_テスト計画/テスト計画.md", "| SPEC-003 | RISK-002 |", "| | RISK-002 |")
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert errors == []

    def test_リスクレベルの計算が合わないとエラーにする(self, root):
        replace_in(root, "02_リスク分析/リスク分析.md", "| 5 | 4 | 20 | 高 |", "| 5 | 4 | 12 | 中 |")
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert any("RISK-001" in e and "20" in e for e in errors)

    def test_リスクレベルと区分が合わないとエラーにする(self, root):
        replace_in(root, "02_リスク分析/リスク分析.md", "| 5 | 4 | 20 | 高 |", "| 5 | 4 | 20 | 中 |")
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert any("RISK-001" in e and "区分" in e for e in errors)

    def test_決められた値以外のテスト結果をエラーにする(self, root):
        replace_in(root, "08_テスト実行/RUN-20261101-100000/テスト結果_手動.md", "| Pass |", "| OK |")
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert any("LTC-003" in e and "OK" in e for e in errors)

    def test_戻し記録に書いた消したIDはエラーにしない(self, root):
        replace_in(root, "戻し記録.md", "COND-002 を追加", "COND-099 を削除")
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert errors == []


    def test_備考に書いたIDは紐づけにしない(self, root):
        # 「〜ID」の列だけが紐づけ。備考などの文章に出てくるIDまで紐づけにすると、
        # 関係のない要求やリスクをカバーしたことになってしまう。
        replace_in(root, "06_テスト実装/ローレベルテストケース.md",
                   "| ID | ハイレベルテストケースID | テストケース | 入力データ | 期待値 | 実施方法 | 優先順位 |\n|---|---|---|---|---|---|---|",
                   "| ID | ハイレベルテストケースID | テストケース | 入力データ | 期待値 | 実施方法 | 優先順位 | 備考 |\n|---|---|---|---|---|---|---|---|")
        replace_in(root, "06_テスト実装/ローレベルテストケース.md", "| LTC-001 | HTC-001 | 18歳で登録する | 18 | 登録完了と表示 | E2E自動テスト | 高 |",
                   "| LTC-001 | HTC-001 | 18歳で登録する | 18 | 登録完了と表示 | E2E自動テスト | 高 | HTC-003 と同じ画面を使う |")
        project = tm_core.load_project(root)
        assert project.records["LTC-001"].links == {"HTC-001"}
        assert project.records["LTC-001"].mentions == {"HTC-003"}
        assert "REQ-002" not in project.ancestors("LTC-001")

    def test_文章の中の定義されていないIDは警告にする(self, root):
        replace_in(root, "01_要求仕様/仕様.md", "| REQ-002 | 仕様書 2.2 |", "| REQ-002 | 仕様書 2.2、SPEC-090 も参照 |")
        errors, warnings = tm_core.check(tm_core.load_project(root))
        assert errors == []
        assert any("SPEC-003" in w and "SPEC-090" in w for w in warnings)


class Test下流が無いものの警告:
    def test_テストケースが無いテスト条件をテスト設計の工程で警告する(self, root):
        append_to(root, "04_テスト分析/テスト分析.md", "| COND-004 | 上限の扱い | FT-001 | TA-001 | SPEC-001 | RISK-001 | 高 | 仕様の記述 | 仕様 |\n")
        _, warnings = tm_core.check(tm_core.load_project(root), stage="design")
        assert any("COND-004" in w for w in warnings)

    def test_まだ来ていない工程の分は警告しない(self, root):
        append_to(root, "04_テスト分析/テスト分析.md", "| COND-004 | 上限の扱い | FT-001 | TA-001 | SPEC-001 | RISK-001 | 高 | 仕様の記述 | 仕様 |\n")
        _, warnings = tm_core.check(tm_core.load_project(root), stage="analysis")
        assert not any("COND-004" in w for w in warnings)

    def test_未実装に記録したハイレベルテストケースは警告しない(self, root):
        replace_in(root, "06_テスト実装/ローレベルテストケース.md", "| LTC-003 | HTC-003 | 登録後の画面を確かめる | 30 | 確認画面を表示 | 手動テスト | 低 |\n", "")
        replace_in(root, "06_テスト実装/テスト手順.md", "| PROC-001 | LTC-003 | 登録して確認画面を見る |\n", "")
        replace_in(root, "08_テスト実行/RUN-20261101-100000/テスト結果_手動.md", "| LTC-003 | 手動テスト | Pass | 証跡/LTC-003.png | | |\n", "")
        _, before = tm_core.check(tm_core.load_project(root), stage="implementation")
        assert any("HTC-003" in w for w in before)
        append_to(root, "06_テスト実装/未実装.md", "# 未実装\n\n| ハイレベルテストケースID | 理由 |\n|---|---|\n| HTC-003 | テスト環境が用意できない |\n")
        _, after = tm_core.check(tm_core.load_project(root), stage="implementation")
        assert not any("HTC-003" in w for w in after)

    def test_結果が無いローレベルテストケースをテスト実行の工程で警告する(self, root):
        replace_in(root, "08_テスト実行/RUN-20261101-100000/テスト結果_手動.md", "| LTC-003 | 手動テスト | Pass | 証跡/LTC-003.png | | |\n", "")
        _, warnings = tm_core.check(tm_core.load_project(root), stage="execution")
        assert any("LTC-003" in w for w in warnings)

    def test_テストアプローチが無い高いリスクをテスト計画の工程で警告する(self, root):
        replace_in(root, "03_テスト計画/テスト計画.md", "| SPEC-001, SPEC-002 | RISK-001 |", "| SPEC-001, SPEC-002 | |")
        replace_in(root, "03_テスト計画/テスト計画.md", "| 登録まわりを探索する | SPEC-001 | RISK-001 |", "| 登録まわりを探索する | SPEC-001 | |")
        _, warnings = tm_core.check(tm_core.load_project(root), stage="plan")
        assert any("RISK-001" in w and "テストアプローチ" in w for w in warnings)
        assert not any("RISK-002" in w for w in warnings)  # 低いリスクは警告しない

    def test_テストアプローチが無い仕様をテスト計画の工程で警告する(self, root):
        replace_in(root, "03_テスト計画/テスト計画.md", "| SPEC-001, SPEC-002 | RISK-001 |", "| SPEC-001 | RISK-001 |")
        _, warnings = tm_core.check(tm_core.load_project(root), stage="plan")
        assert any("SPEC-002" in w and "テストアプローチ" in w for w in warnings)
        assert not any("SPEC-001" in w for w in warnings)

    def test_リスクを通してテストアプローチがある仕様は警告しない(self, root):
        # SPEC-003 は TA-002 の仕様IDからは外しても、RISK-002 を通して TA-002 がある
        replace_in(root, "03_テスト計画/テスト計画.md", "| SPEC-003 | RISK-002 |", "| | RISK-002 |")
        _, warnings = tm_core.check(tm_core.load_project(root), stage="plan")
        assert not any("SPEC-003" in w for w in warnings)

    def test_通さない理由を書いたカバレッジアイテムは警告しない(self, root):
        table = "\n## 通さないカバレッジアイテム\n\n| ID | カバレッジアイテム | テスト条件ID | 通さない理由 |\n|---|---|---|---|\n| CI-004 | 上限の外 66 | COND-001 | {} |\n"
        append_to(root, "05_テスト設計/テスト設計.md", table.format(""))
        _, warnings = tm_core.check(tm_core.load_project(root), stage="design")
        assert any("CI-004" in w for w in warnings)
        replace_in(root, "05_テスト設計/テスト設計.md", "| COND-001 |  |", "| COND-001 | 範囲外の機能で期待値が決まるため |")
        _, warnings = tm_core.check(tm_core.load_project(root), stage="design")
        assert not any("CI-004" in w for w in warnings)

    def test_工程を指定しないと成果物がある最後の工程まで確認する(self, root):
        assert tm_core.detect_stage(tm_core.load_project(root)) == "execution"


class Testたどる:
    def test_ローレベルテストケースから要求までたどれる(self, root):
        project = tm_core.load_project(root)
        ancestors = project.ancestors("LTC-001")
        assert {"HTC-001", "COND-001", "CI-001", "FT-001", "SPEC-001", "REQ-001", "RISK-001", "TA-001"} <= ancestors

    def test_リスクやテストアプローチを経由しては上にたどらない(self, root):
        # COND-002 は FT-002 → SPEC-003 → REQ-002 にだけつながる。
        # TA や RISK を経由して別の仕様・要求につながったことにすると、カバレッジを数えすぎる。
        replace_in(root, "03_テスト計画/テスト計画.md", "| SPEC-003 | RISK-002 |", "| SPEC-001, SPEC-003 | RISK-002 |")
        project = tm_core.load_project(root)
        assert "REQ-001" not in project.ancestors("COND-002")

    def test_フィーチャーを経由して上流の要求に数えない(self, root):
        # フィーチャーは複数の仕様をまとめるので、フィーチャー経由でたどると、
        # テスト条件が確かめていない仕様の要求までカバーしたことになる。
        replace_in(root, "04_テスト分析/テスト分析.md", "| FT-002 | 確認画面 | 機能 | SPEC-003 |", "| FT-002 | 確認画面 | 機能 | SPEC-001, SPEC-003 |")
        project = tm_core.load_project(root)
        assert "REQ-001" not in project.ancestors("COND-002")

    def test_質問の影響はフィーチャーやリスクやテストアプローチを経由して広げない(self, root):
        # SPEC-002 を直接確かめるテスト条件は無い。FT-001 や TA-001 を経由した
        # COND-001・COND-003 は、Q-001 の回答を待っていない。
        replace_in(root, "質問表.md", "| SPEC-001 | 曖昧 |", "| SPEC-002 | 曖昧 |")
        impact = tm_core.impact(tm_core.load_project(root), ["Q-001"])
        assert impact["SPEC"] == ["SPEC-002"]
        assert "FT-001" in impact["FT"] and "TA-001" in impact["TA"]
        assert "COND" not in impact and "LTC" not in impact

    def test_要求から欠陥レポートまで下にたどれる(self, root):
        project = tm_core.load_project(root)
        descendants = project.descendants("REQ-001")
        assert {"SPEC-001", "FT-001", "COND-001", "HTC-002", "LTC-002", "BUG-001", "CH-001", "SES-001"} <= descendants

    def test_変更の影響範囲を種類ごとに出す(self, root):
        project = tm_core.load_project(root)
        impact = tm_core.impact(project, ["RISK-002"])
        assert impact["TA"] == ["TA-002"]
        assert impact["COND"] == ["COND-002"]
        assert impact["LTC"] == ["LTC-003"]


class Test集計:
    def test_結果の件数と実行率を数える(self, root):
        m = tm_core.metrics(tm_core.load_project(root))
        assert m["testcases"]["total"] == 3
        assert m["testcases"]["Pass"] == 2
        assert m["testcases"]["Fail"] == 1
        assert m["testcases"]["execution_rate"] == 100.0

    def test_新しいテストランの結果を最終結果にする(self, root):
        append_to(root, "08_テスト実行/RUN-20261102-090000/テスト結果_E2E自動.md",
                  "| ローレベルテストケースID | 実施方法 | 結果 | 証跡 | 欠陥レポートID | メモ |\n|---|---|---|---|---|---|\n| LTC-002 | E2E自動テスト | Pass | | | 確認テスト |\n")
        project = tm_core.load_project(root)
        assert project.final_results()["LTC-002"].result == "Pass"
        assert project.final_results()["LTC-001"].run == "RUN-20261101-100000"

    def test_結果が無いテストケースは未実行として数え実行率に入れない(self, root):
        replace_in(root, "08_テスト実行/RUN-20261101-100000/テスト結果_手動.md", "| LTC-003 | 手動テスト | Pass | 証跡/LTC-003.png | | |\n", "")
        m = tm_core.metrics(tm_core.load_project(root))
        assert m["testcases"]["未実行"] == 1
        assert m["testcases"]["execution_rate"] == pytest.approx(66.7, abs=0.1)

    def test_要求ごとの状態を出す(self, root):
        m = tm_core.metrics(tm_core.load_project(root))
        by_id = {r["id"]: r for r in m["requirements"]}
        assert by_id["REQ-001"]["state"] == "実行したがFailあり"
        assert by_id["REQ-001"]["Fail"] == 1
        assert by_id["REQ-001"]["sessions"] == 1
        assert by_id["REQ-002"]["state"] == "すべて実行してすべてPass"

    def test_一部しか実行していない要求とまったくテストしていない要求を分ける(self, root):
        replace_in(root, "08_テスト実行/RUN-20261101-100000/テスト結果_E2E自動.md", "| LTC-002 | E2E自動テスト | Fail | 証跡/LTC-002.png | BUG-001 | 登録できた |", "| LTC-002 | E2E自動テスト | ブロック | | | 環境の不具合 |")
        replace_in(root, "08_テスト実行/欠陥レポート.md", "| BUG-001 | 17歳で登録できてしまう | 高 | 未修正 | 2026-11-01 10:05 | LTC-002 |\n", "")
        replace_in(root, "08_テスト実行/RUN-20261101-100000/テスト結果_手動.md", "| LTC-003 | 手動テスト | Pass | 証跡/LTC-003.png | | |\n", "")
        m = tm_core.metrics(tm_core.load_project(root))
        by_id = {r["id"]: r for r in m["requirements"]}
        assert by_id["REQ-001"]["state"] == "一部しか実行していない"
        assert by_id["REQ-002"]["state"] == "まったくテストしていない"

    def test_リスクはリスクレベルの高い順に並べる(self, root):
        m = tm_core.metrics(tm_core.load_project(root))
        assert [r["id"] for r in m["risks"]] == ["RISK-001", "RISK-002"]
        assert m["risks"][0]["level"] == 20
        assert m["risks"][0]["class"] == "高"

    def test_修正されていない不具合を重要度の高い順に出す(self, root):
        append_to(root, "08_テスト実行/欠陥レポート.md", "| BUG-002 | 文言の誤り | 低 | 未修正 | 2026-11-01 11:00 | SES-001 |\n| BUG-003 | 直った不具合 | 高 | クローズ | 2026-11-01 11:10 | LTC-001 |\n")
        m = tm_core.metrics(tm_core.load_project(root))
        assert [b["id"] for b in m["open_bugs"]] == ["BUG-001", "BUG-002"]

    def test_未回答の質問を数える(self, root):
        m = tm_core.metrics(tm_core.load_project(root))
        assert [q["id"] for q in m["open_questions"]] == ["Q-001"]

    def test_仕様ごとの状態を出す(self, root):
        m = tm_core.metrics(tm_core.load_project(root))
        by_id = {r["id"]: r for r in m["specs"]}
        assert by_id["SPEC-001"]["state"] == "実行したがFailあり"
        assert by_id["SPEC-002"]["state"] == "まったくテストしていない"  # 直接確かめるテスト条件が無い
        assert by_id["SPEC-003"]["state"] == "すべて実行してすべてPass"

    def test_テストチャーターごとにセッションの時間が時間枠に達したかを出す(self, root):
        m = tm_core.metrics(tm_core.load_project(root))
        assert m["charters"] == [{"id": "CH-001", "timebox": 15, "minutes": 15.0, "sessions": ["SES-001"], "reached": True}]
        replace_in(root, "08_テスト実行/RUN-20261101-100000/セッションシート/SES-001.md", "| 2026-11-01 10:30 | 15 |", "| 2026-11-01 10:30 | 12.5 |")
        m = tm_core.metrics(tm_core.load_project(root))
        assert m["charters"][0]["minutes"] == 12.5 and m["charters"][0]["reached"] is False

    def test_未実装のハイレベルテストケースを数える(self, root):
        replace_in(root, "05_テスト設計/テスト設計.md", "| 手動テスト | 低 | 設計済み |\n",
                   "| 手動テスト | 低 | 設計済み |\n| HTC-004 | 上限の境界値のとき登録できる | COND-001 | CI-001 | 登録できる | E2E自動テスト | 高 | 回答待ち(Q-001) |\n")
        m = tm_core.metrics(tm_core.load_project(root))
        assert m["testcases"]["未実装"] == 1
        by_id = {r["id"]: r for r in m["requirements"]}
        assert by_id["REQ-001"]["未実装"] == 1


class Test欠陥レポートの範囲:
    HEADER = "| ID | タイトル | 重要度 | 状態 | 見つけた日時 | 関連ID |\n|---|---|---|---|---|---|\n| BUG-001 | 17歳で登録できてしまう | 高 | 未修正 | 2026-11-01 10:05 | LTC-002 |\n"
    NEW = ("| ID | タイトル | 重要度 | 状態 | 見つけた日時 | 関連ID | 要求・仕様ID |\n|---|---|---|---|---|---|---|\n"
           "| BUG-001 | 17歳で登録できてしまう | 高 | 未修正 | 2026-11-01 10:05 | LTC-002 | |\n"
           "| BUG-002 | {title} | 中 | 未修正 | 2026-11-01 10:40 | SES-001 | {scope} |\n")

    def _bugs(self, root, title, scope):
        replace_in(root, "08_テスト実行/欠陥レポート.md", self.HEADER, self.NEW.format(title=title, scope=scope))
        m = tm_core.metrics(tm_core.load_project(root))
        return {r["id"]: r for r in m["requirements"]}

    def test_スコープ外と書いた不具合は要求の不具合に数えない(self, root):
        by_id = self._bugs(root, "範囲外の画面の表示崩れ", "スコープ外")
        assert by_id["REQ-001"]["bugs"] == 1  # BUG-001 だけ
        assert tm_core.metrics(tm_core.load_project(root))["open_bugs"][1]["id"] == "BUG-002"  # 不具合の一覧には残す

    def test_要求仕様IDを書いた不具合はその要求に数える(self, root):
        by_id = self._bugs(root, "確認画面の文言の誤り", "SPEC-003")
        assert by_id["REQ-001"]["bugs"] == 1
        assert by_id["REQ-002"]["bugs"] == 1
        assert by_id["REQ-002"]["state"] == "実行したがFailあり"

    def test_要求仕様IDが空の不具合は見つけたテストからたどる(self, root):
        by_id = self._bugs(root, "入力チェックの漏れ", "")
        assert by_id["REQ-001"]["bugs"] == 2


class TestE2Eの結果の取り込み:
    def _report(self):
        return {
            "suites": [{
                "title": "register.spec.js",
                "specs": [
                    {"title": "LTC-001 18歳で登録する", "tests": [{"projectName": "chromium", "status": "expected", "results": [{"status": "passed", "attachments": []}]}]},
                ],
                "suites": [{
                    "title": "異常系",
                    "specs": [
                        {"title": "LTC-002 17歳で登録する", "tests": [{"projectName": "chromium", "status": "unexpected", "results": [{"status": "failed", "attachments": [{"name": "screenshot", "path": "test-results/a/shot.png"}]}]}]},
                        {"title": "LTC-005 あとで作る", "tests": [{"projectName": "chromium", "status": "skipped", "results": []}]},
                        {"title": "LTC-006 不安定", "tests": [{"projectName": "chromium", "status": "flaky", "results": [{"status": "failed"}, {"status": "passed"}]}]},
                    ],
                }],
            }]
        }

    def test_idごとにPassとFailを付ける(self):
        parsed = tm_core.parse_playwright_report(self._report())
        assert parsed["LTC-001"]["result"] == "Pass"
        assert parsed["LTC-002"]["result"] == "Fail"
        assert parsed["LTC-002"]["evidence"] == ["test-results/a/shot.png"]

    def test_複数のブラウザのうち一部だけ失敗したときはFailにして失敗したブラウザを書く(self):
        report = {"suites": [{"title": "a.spec.js", "specs": [
            {"title": "LTC-001 登録する", "tests": [{"projectName": "chromium", "status": "expected", "results": [{"status": "passed"}]}]},
            {"title": "LTC-001 登録する", "tests": [{"projectName": "firefox", "status": "unexpected", "results": [{"status": "failed"}]}]},
        ]}]}
        parsed = tm_core.parse_playwright_report(report)
        assert parsed["LTC-001"]["result"] == "Fail"
        assert "firefox" in parsed["LTC-001"]["memo"] and "chromium" not in parsed["LTC-001"]["memo"]

    def test_スキップは未実行にし不安定なテストはPassにしない(self):
        parsed = tm_core.parse_playwright_report(self._report())
        assert parsed["LTC-005"]["result"] == "未実行"
        assert parsed["LTC-006"]["result"] == "Fail"
        assert "不安定" in parsed["LTC-006"]["memo"]

    def test_PassにもJSONレポートを証跡として書く(self, root):
        run_dir = root / "08_テスト実行/RUN-20261103-120000"
        run_dir.mkdir(parents=True)
        report = run_dir / "playwright-report.json"
        report.write_text("{}", encoding="utf-8")
        parsed = tm_core.parse_playwright_report(self._report())
        tm_core.write_e2e_results(root, "RUN-20261103-120000", parsed, expected=["LTC-001"], report=report)
        final = tm_core.load_project(root).final_results()
        assert final["LTC-001"].result == "Pass"
        assert final["LTC-001"].evidence == ["playwright-report.json"]

    def test_JSONレポートがテストランの外にあればコピーして証跡にする(self, root, tmp_path):
        report = tmp_path / "report.json"
        report.write_text("{}", encoding="utf-8")
        parsed = tm_core.parse_playwright_report(self._report())
        tm_core.write_e2e_results(root, "RUN-20261103-120000", parsed, expected=["LTC-001"], report=report)
        final = tm_core.load_project(root).final_results()
        assert final["LTC-001"].evidence == ["証跡/report.json"]
        assert (root / "08_テスト実行/RUN-20261103-120000/証跡/report.json").is_file()

    def test_結果にidが無いケースはPassにせず理由を書く(self, root):
        parsed = tm_core.parse_playwright_report(self._report())
        del parsed["LTC-002"]
        path = tm_core.write_e2e_results(root, "RUN-20261103-120000", parsed, expected=["LTC-001", "LTC-002"])
        project = tm_core.load_project(root)
        final = project.final_results()
        assert path.name == "テスト結果_E2E自動.md"
        assert final["LTC-001"].result == "Pass"
        assert final["LTC-002"].result == "未実行"
        assert "id" in final["LTC-002"].memo


class Test戻してやり直すとき:
    def test_上流を変えて下流に残ったエラーは自分の工程のエラーと分ける(self, root):
        # 要求仕様整理に戻って仕様を消すと、下流はまだ消した仕様に紐づいている。
        # これは要求仕様整理のエージェントが直すものではないので、分けて出す。
        replace_in(root, "01_要求仕様/仕様.md", "| SPEC-003 | 登録後に確認画面を表示する | REQ-002 | 仕様書 2.2 |\n", "")
        own, downstream, _ = tm_core.check_scoped(tm_core.load_project(root), "requirements")
        assert own == []
        assert any("RISK-002" in e and "SPEC-003" in e for e in downstream)
        assert any("FT-002" in e for e in downstream)

    def test_自分の工程までのエラーは自分のエラーにする(self, root):
        replace_in(root, "04_テスト分析/テスト分析.md", "| COND-002 | 確認画面の表示 | FT-002 |", "| COND-002 | 確認画面の表示 | FT-099 |")
        own, downstream, _ = tm_core.check_scoped(tm_core.load_project(root), "analysis")
        assert any("COND-002" in e for e in own)
        assert downstream == []

    def test_質問表のエラーはどの工程でも自分のエラーにする(self, root):
        replace_in(root, "質問表.md", "| SPEC-001 | 曖昧 |", "| SPEC-077 | 曖昧 |")
        own, _, _ = tm_core.check_scoped(tm_core.load_project(root), "requirements")
        assert any("Q-001" in e and "SPEC-077" in e for e in own)

    def test_質問を待っている成果物と質問の関連先を影響範囲に出す(self, root):
        replace_in(root, "05_テスト設計/テスト設計.md", "| 手動テスト | 低 | 設計済み |", "| 手動テスト | 低 | 回答待ち(Q-001) |")
        grouped = tm_core.impact(tm_core.load_project(root), ["Q-001"])
        assert "HTC-003" in grouped["HTC"]   # 状態の列に質問のidを書いて待っている成果物
        assert "LTC-003" in grouped["LTC"]   # その下流
        assert "SPEC-001" in grouped["SPEC"]  # 質問の関連IDに書かれた成果物

    def test_回答待ちのテストケースも未実装に記録していなければ警告する(self, root):
        replace_in(root, "05_テスト設計/テスト設計.md", "| 手動テスト | 低 | 設計済み |", "| 手動テスト | 低 | 回答待ち(Q-001) |")
        replace_in(root, "06_テスト実装/ローレベルテストケース.md", "| LTC-003 | HTC-003 | 登録後の画面を確かめる | 30 | 確認画面を表示 | 手動テスト | 低 |\n", "")
        replace_in(root, "06_テスト実装/テスト手順.md", "| PROC-001 | LTC-003 | 登録して確認画面を見る |\n", "")
        replace_in(root, "08_テスト実行/RUN-20261101-100000/テスト結果_手動.md", "| LTC-003 | 手動テスト | Pass | 証跡/LTC-003.png | | |\n", "")
        _, warnings = tm_core.check(tm_core.load_project(root), stage="implementation")
        assert any("HTC-003" in w for w in warnings)

    def test_定義ではない表でもIDの列に書いた定義されていないIDをエラーにする(self, root):
        append_to(root, "06_テスト実装/テストスイート.md",
                  "# テストスイート\n\n| 順番 | ローレベルテストケースID | 実施方法 |\n|---|---|---|\n| 1 | LTC-001 | E2E自動テスト |\n| 2 | LTC-099 | 手動テスト |\n")
        errors, _ = tm_core.check(tm_core.load_project(root))
        assert any("LTC-099" in e and "テストスイート.md" in e for e in errors)
        assert not any("LTC-001" in e for e in errors)
