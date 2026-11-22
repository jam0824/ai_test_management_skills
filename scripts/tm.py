#!/usr/bin/env python3
"""テスト成果物を扱うコマンド。標準ライブラリだけで動く(Python 3.9 以上)。

  python tm.py check        トレーサビリティと決まりを確かめる
  python tm.py impact ID…   変えたIDの下流(影響範囲)を出す
  python tm.py html         視認性アップ: 成果物をHTMLにする
  python tm.py new-run      新しいテストランのフォルダを作る
  python tm.py e2e-results  PlaywrightのJSONレポートを、idごとのテスト結果にする
  python tm.py metrics      テストレポートに載せる数字を数え直す
  python tm.py report       テストレポート(HTML)を作る

成果物のフォルダは --root で指定する。省くと、今いるフォルダの「テスト成果物」を使う。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tm_core  # noqa: E402
import tm_html  # noqa: E402


def _load(args) -> tm_core.Project:
    return tm_core.load_project(Path(args.root))


def cmd_check(args) -> int:
    project = _load(args)
    stage = args.stage or tm_core.detect_stage(project)
    if args.stage:
        errors, downstream, warnings = tm_core.check_scoped(project, stage)
    else:
        (errors, warnings), downstream = tm_core.check(project, stage), []
    print(f"確認した範囲: 「{tm_core.STAGE_NAMES[stage]}」まで / 成果物 {len(project.records)} 件(全工程の合計)")
    print(f"エラー: {len(errors)} 件 (紐づけの抜け・切れ、決まりに合わない値。必ず直す)")
    for error in errors:
        print(f"  [エラー] {error}")
    if downstream:
        print(f"下流の工程に残っているエラー: {len(downstream)} 件"
              " (この工程では直さない。前の工程を変えたために残ったものなので、テストマネージャーに報告する)")
        for error in downstream:
            print(f"  [下流] {error}")
    print(f"警告: {len(warnings)} 件 (下流がまだ無いもの、文章の中の定義されていないID。理由を確かめる)")
    for warning in warnings:
        print(f"  [警告] {warning}")
    return 1 if errors else 0


def cmd_impact(args) -> int:
    project = _load(args)
    unknown = [i for i in args.ids if i not in project.records]
    if unknown:
        print(f"定義されていないID: {', '.join(unknown)}")
        return 1
    grouped = tm_core.impact(project, args.ids)
    print(f"{', '.join(args.ids)} を変えたときに影響を受ける下流:")
    if not grouped:
        print("  なし")
    for type_key, ids in grouped.items():
        print(f"  {tm_core.TYPES[type_key]} ({len(ids)} 件): {', '.join(ids)}")
    return 0


def cmd_html(args) -> int:
    project = _load(args)
    stages = [args.stage] if args.stage else None
    written = tm_html.build_html(project, project.root / "html", stages)
    print(f"HTMLを作った: {project.root / 'html'} ({len(written)} ページ)")
    target = f"{args.stage}.html" if args.stage else "index.html"
    print(f"開くページ: {(project.root / 'html' / target).resolve()}")
    return 0


def cmd_new_run(args) -> int:
    run_id = "RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.root) / tm_core.EXECUTION_DIR / run_id
    (run_dir / "証跡").mkdir(parents=True, exist_ok=False)
    (run_dir / "セッションシート").mkdir()
    print(run_id)
    return 0


def cmd_e2e_results(args) -> int:
    project = _load(args)
    data = json.loads(Path(args.json).read_text(encoding="utf-8-sig"))
    parsed = tm_core.parse_playwright_report(data)
    expected = [s_link for s in project.of_type("SCR") for s_link in s.links if tm_core.type_of(s_link) == "LTC"]
    path = tm_core.write_e2e_results(project.root, args.run, parsed, expected)
    counts = {status: 0 for status in tm_core.RESULTS}
    missing = [ltc for ltc in expected if ltc not in parsed]
    for ltc in set(expected) | set(parsed):
        counts[parsed[ltc]["result"] if ltc in parsed else "未実行"] += 1
    print(f"書いたファイル: {path}")
    print(" / ".join(f"{status} {count} 件" for status, count in counts.items()))
    if missing:
        print(f"実行結果にidが無かったテストケース(未実行にした。テストマネージャーに報告する): {', '.join(sorted(missing))}")
    unknown = [ltc for ltc in parsed if ltc not in project.records]
    if unknown:
        print(f"成果物に定義が無いid(スクリプトのidを確かめる): {', '.join(sorted(unknown))}")
    return 0


def cmd_metrics(args) -> int:
    data = tm_core.metrics(_load(args))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    t = data["testcases"]
    print(f"テストケース {t['total']} 件 / 実行率 {t['execution_rate']}% (実行 {t['executed']} ÷ ローレベルテストケース {t['total']})")
    print(f"Pass {t['Pass']} / Fail {t['Fail']} / ブロック {t['ブロック']} / 未実行 {t['未実行']} / 未実装 {t['未実装']}")
    print(f"テストラン: {', '.join(data['runs']) or 'なし'}")
    print(f"修正されていない不具合 {len(data['open_bugs'])} 件: " + ", ".join(f"{b['id']}({b['severity']})" for b in data["open_bugs"]))
    print(f"未回答の質問 {len(data['open_questions'])} 件: " + ", ".join(q["id"] for q in data["open_questions"]))
    for label, rows in (("要求", data["requirements"]), ("リスク", data["risks"])):
        print(f"{label}ごとの状態:")
        for row in rows:
            level = f" レベル{row['level']}({row['class']})" if "level" in row else ""
            print(f"  {row['id']}{level}: {row['state']} (Pass {row['Pass']} / Fail {row['Fail']} / ブロック {row['ブロック']}"
                  f" / 未実行 {row['未実行']} / 未実装 {row['未実装']} / セッション {row['sessions']})")
    print("終了条件:")
    for criterion in data["exit_criteria"]:
        print(f"  {criterion['id']}: {criterion['text']} (測り方: {criterion['measure']})")
    return 0


def cmd_report(args) -> int:
    project = _load(args)
    try:
        out = tm_html.build_report(project, args.timestamp)
    except tm_html.ReportError as error:
        print(f"テストレポートを作れない: {error}")
        return 1
    print(f"テストレポートを作った: {(out / 'index.html').resolve()}")
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="テスト成果物を扱うコマンド")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, func, help_text: str):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--root", default=tm_core.DEFAULT_ROOT, help="成果物のフォルダ(省くと ./テスト成果物)")
        command.set_defaults(func=func)
        return command

    stage_help = "工程: " + ", ".join(f"{k}({tm_core.STAGE_NAMES[k]})" for k in tm_core.STAGE_KEYS)
    check = add("check", cmd_check, "トレーサビリティと決まりを確かめる")
    check.add_argument("--stage", choices=tm_core.STAGE_KEYS, help=stage_help + "。省くと成果物がある最後の工程まで")
    impact = add("impact", cmd_impact, "変えたIDの下流を出す")
    impact.add_argument("ids", nargs="+", metavar="ID")
    html = add("html", cmd_html, "成果物をHTMLにする")
    html.add_argument("--stage", choices=tm_html.VIEW_STAGES, help="この工程のページだけ作り直す(省くと全部)")
    add("new-run", cmd_new_run, "新しいテストランのフォルダを作り、そのIDを出す")
    e2e = add("e2e-results", cmd_e2e_results, "PlaywrightのJSONレポートをidごとの結果にする")
    e2e.add_argument("--run", required=True, help="テストランのID(new-run で作ったもの)")
    e2e.add_argument("--json", required=True, help="PlaywrightのJSONレポートのファイル")
    metrics = add("metrics", cmd_metrics, "テストレポートに載せる数字を数え直す")
    metrics.add_argument("--json", action="store_true", help="JSONで出す")
    report = add("report", cmd_report, "テストレポートを作る")
    report.add_argument("--timestamp", help="レポートのフォルダ名(yyyyMMddHHmmss)。省くと今の時刻")

    args = parser.parse_args(argv)
    if not Path(args.root).is_dir():
        print(f"成果物のフォルダが無い: {Path(args.root).resolve()}")
        print("テストするプロジェクトのフォルダで実行するか、--root <フォルダ> で場所を指定する。")
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
