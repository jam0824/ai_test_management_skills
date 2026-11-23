"""統合テスト: tm.py のコマンドを通して、成果物の読み取りからHTML・レポートまでがつながっていることを確かめる。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sample_project import make_project, replace_in  # noqa: E402
from test_tm_html import JUDGMENT  # noqa: E402

TM = Path(__file__).resolve().parent.parent / "scripts" / "tm.py"


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(TM), *args], capture_output=True, text=True, encoding="utf-8", cwd=cwd)


@pytest.fixture
def root(tmp_path):
    return make_project(tmp_path / "テスト成果物")


class Test統合テスト:
    def test_checkは問題が無ければ成功で終わる(self, root):
        result = run("check", "--root", str(root))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "エラー: 0 件" in result.stdout

    def test_checkは紐づけが切れていると失敗で終わりIDを示す(self, root):
        replace_in(root, "06_テスト実装/ローレベルテストケース.md", "| LTC-002 | HTC-002 |", "| LTC-002 | HTC-099 |")
        result = run("check", "--root", str(root))
        assert result.returncode == 1
        assert "LTC-002" in result.stdout and "HTC-099" in result.stdout

    def test_checkは工程を指定すると下流に残ったエラーを分けて出し失敗にしない(self, root):
        replace_in(root, "01_要求仕様/仕様.md", "| SPEC-003 | 登録後に確認画面を表示する | REQ-002 | 仕様書 2.2 |\n", "")
        scoped = run("check", "--root", str(root), "--stage", "requirements")
        assert scoped.returncode == 0, scoped.stdout
        assert "エラー: 0 件" in scoped.stdout
        assert "下流の工程に残っているエラー" in scoped.stdout and "RISK-002" in scoped.stdout
        whole = run("check", "--root", str(root))
        assert whole.returncode == 1  # 工程を指定しなければ、全体のエラーとして失敗にする

    def test_rootを省くと今いるフォルダのテスト成果物を使う(self, root):
        result = run("check", cwd=root.parent)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_impactは影響を受ける下流のIDを出す(self, root):
        result = run("impact", "SPEC-003", "--root", str(root))
        assert result.returncode == 0
        assert "COND-002" in result.stdout and "LTC-003" in result.stdout
        assert "LTC-001" not in result.stdout

    def test_htmlは指定した工程のページを作る(self, root):
        result = run("html", "--root", str(root), "--stage", "analysis")
        assert result.returncode == 0, result.stdout + result.stderr
        assert (root / "結果まとめ/テスト分析.html").exists()
        assert (root / "結果まとめ/ID索引.html").exists()
        assert (root / "04_テスト分析/テスト分析.html").exists()
        assert "結果まとめ" in result.stdout and "テスト分析.html" in result.stdout

    def test_E2Eの実行結果からテストランとレポートまでつながる(self, root, tmp_path):
        new_run = run("new-run", "--root", str(root))
        run_id = new_run.stdout.strip().splitlines()[-1]
        assert run_id.startswith("RUN-") and (root / "08_テスト実行" / run_id).is_dir()

        report = {"suites": [{"title": "register.spec.js", "specs": [
            {"title": "LTC-001 18歳で登録する", "tests": [{"status": "expected", "results": [{"status": "passed"}]}]},
            {"title": "LTC-002 17歳で登録する", "tests": [{"status": "expected", "results": [{"status": "passed"}]}]},
        ]}]}
        json_path = tmp_path / "playwright.json"
        json_path.write_text(json.dumps(report), encoding="utf-8")
        e2e = run("e2e-results", "--root", str(root), "--run", run_id, "--json", str(json_path))
        assert e2e.returncode == 0, e2e.stdout + e2e.stderr

        metrics = run("metrics", "--root", str(root), "--json")
        data = json.loads(metrics.stdout)
        assert data["testcases"]["Pass"] == 3  # 新しいテストランの結果が最終結果になる

        (root / "09_テストレポート").mkdir()
        (root / "09_テストレポート/判定.md").write_text(JUDGMENT, encoding="utf-8")
        built = run("report", "--root", str(root), "--timestamp", "20261103130000")
        assert built.returncode == 0, built.stdout + built.stderr
        index = root / "09_テストレポート/20261103130000/テストレポート.html"
        assert index.exists()
        assert run_id in index.read_text(encoding="utf-8")

    def test_reportは判定が無いと失敗で終わり何が要るかを示す(self, root):
        result = run("report", "--root", str(root))
        assert result.returncode == 1
        assert "判定.md" in result.stdout + result.stderr

    def test_成果物のフォルダが無いと何も作らずに失敗で終わる(self, tmp_path):
        missing = tmp_path / "どこにもない"
        for command in (["check"], ["html"], ["metrics"], ["report"]):
            result = run(*command, "--root", str(missing))
            assert result.returncode == 1, command
            assert "成果物のフォルダが無い" in result.stdout, command
        assert not missing.exists()
