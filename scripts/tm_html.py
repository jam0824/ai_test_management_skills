"""成果物を人が読みやすいHTMLにする(視認性アップ)。テストレポートも作る。標準ライブラリだけで動く。"""
from __future__ import annotations

import html as html_lib
import re
import shutil
from datetime import datetime
from pathlib import Path

import tm_core
from tm_core import TYPES, Project, type_of

VIEW_STAGES = [s for s in tm_core.STAGE_KEYS if s != "report"]


class ReportError(Exception):
    """テストレポートを作れないとき。メッセージに、何が要るかを書く。"""


# ---- Markdown → HTML ----

def _escape(text: str) -> str:
    escaped = html_lib.escape(text, quote=False)
    return re.sub(r"&lt;br\s*/?&gt;", "<br>", escaped)


def link_ids(html: str, known_ids, id_href: str) -> str:
    """文章の中の、定義されているIDをID索引へのリンクにする。タグの中と、リンクの中は変えない。"""
    if not known_ids:
        return html
    parts = re.split(r"(<[^>]+>)", html)
    in_anchor = False
    for i, part in enumerate(parts):
        if part.startswith("<"):
            if part.startswith("<a "):
                in_anchor = True
            elif part.startswith("</a"):
                in_anchor = False
        elif not in_anchor:
            parts[i] = tm_core.ID_RE.sub(
                lambda m: f'<a href="{id_href}#{m.group(0)}" class="id">{m.group(0)}</a>'
                if m.group(0) in known_ids else m.group(0),
                part,
            )
    return "".join(parts)


def _inline(text: str) -> str:
    out = _escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, out)


_SAFE_URL = re.compile(r"""^(https?://[^\s"'<>]+|[^\s"'<>:]+)$""")


def _link(match: re.Match) -> str:
    """http(s) か相対パスだけをリンクにする。成果物には外から来た文章が入るので、それ以外はそのまま出す。"""
    if not _SAFE_URL.match(match.group(2)):
        return match.group(0)
    return f'<a href="{match.group(2)}">{match.group(1)}</a>'


def md_to_html(text: str, known_ids=None, id_href: str = "ids.html") -> str:
    """成果物で使う範囲のMarkdown(見出し・段落・リスト・表・コード)をHTMLにする。"""
    lines = text.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    i = 0

    def flush() -> None:
        if paragraph:
            out.append("<p>" + "<br>".join(_inline(p) for p in paragraph) + "</p>")
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append("<pre><code>" + html_lib.escape("\n".join(code), quote=False) + "</code></pre>")
            i += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and tm_core._is_separator(lines[i + 1]):
            flush()
            headers = tm_core._split_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = tm_core._split_row(lines[i])
                rows.append(row + [""] * (len(headers) - len(row)))
                i += 1
            out.append(_table([_inline(h) for h in headers], [[_inline(c) for c in r] for r in rows]))
            continue
        item = re.match(r"^(\s*)([*\-]|\d+\.)\s+(.*)$", line)
        if item:
            flush()
            ordered = item.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines):
                m = re.match(r"^(\s*)([*\-]|\d+\.)\s+(.*)$", lines[i])
                if not m or m.group(2)[0].isdigit() != ordered:
                    break
                items.append(f"<li>{_inline(m.group(3))}</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        if not stripped:
            flush()
        else:
            paragraph.append(stripped)
        i += 1
    flush()
    return link_ids("\n".join(out), known_ids, id_href)


# ---- 部品 ----

def _table(headers: list[str], rows: list[list[str]], row_ids: list[str] | None = None, cls: str = "") -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = []
    for n, row in enumerate(rows):
        attr = f' id="{row_ids[n]}"' if row_ids else ""
        body.append(f"<tr{attr}>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    cls_attr = f' class="{cls}"' if cls else ""
    return f"<div class=\"scroll\"><table{cls_attr}><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def _badge(text: str) -> str:
    kinds = {
        "Pass": "ok", "満たした": "ok", "すべて実行してすべてPass": "ok", "クローズ": "ok", "低": "low",
        "Fail": "ng", "満たしていない": "ng", "未判定": "ng", "実行したがFailあり": "ng", "未修正": "ng", "高": "high",
        "ブロック": "warn", "一部しか実行していない": "warn", "修正済み": "warn", "中": "mid",
        "未実行": "none", "まったくテストしていない": "none", "未実装": "none",
    }
    return f'<span class="badge {kinds.get(text.strip(), "plain")}">{_escape(text)}</span>'


class View:
    """1ページ分の描画の設定(ID索引とファイルへの相対パス)を持つ。"""

    def __init__(self, project: Project, id_href: str = "ids.html", file_base: str = "../"):
        self.project = project
        self.id_href = id_href
        self.file_base = file_base
        self.known = set(project.records)

    def ref(self, record_id: str, with_title: bool = True) -> str:
        record = self.project.records.get(record_id)
        link = f'<a href="{self.id_href}#{record_id}" class="id">{record_id}</a>'
        if record is None:
            return f'<span class="missing">{record_id}(定義なし)</span>'
        return f"{link} {_escape(record.title[:60])}" if with_title else link

    def refs(self, ids, with_title: bool = True) -> str:
        ids = sorted(ids, key=tm_core._id_key)
        return "<br>".join(self.ref(i, with_title) for i in ids) if ids else '<span class="none-text">なし</span>'

    def text(self, value: str) -> str:
        return link_ids(_inline(value or ""), self.known, self.id_href)

    def related(self, record_id: str, type_key: str) -> list[str]:
        if type_of(record_id) == type_key:
            return [record_id]
        up = [a for a in self.project.ancestors(record_id) if type_of(a) == type_key]
        return up or [d for d in self.project.descendants(record_id) if type_of(d) == type_key]

    def chain(self, focus_ids: list[str], columns: list[str], extra: list[str] = (), row_prefix: str = "row-") -> str:
        """1行に1件、上流から順に並べた追跡表。extra は、その成果物自身の項目。"""
        headers = [TYPES[c] for c in columns] + list(extra)
        rows = []
        for record_id in focus_ids:
            record = self.project.records[record_id]
            cells = [self.refs(self.related(record_id, c)) for c in columns]
            for name in extra:
                value = record.fields.get(name, "")
                cells.append(_badge(value) if name in ("区分", "結果") else self.text(value))
            rows.append(cells)
        return _table(headers, rows, [row_prefix + i for i in focus_ids])

    def file_link(self, relative: str, label: str | None = None) -> str:
        return f'<a href="{self.file_base}{html_lib.escape(relative)}">{_escape(label or relative)}</a>'

    def documents(self, folder: str) -> str:
        """その工程のフォルダにあるMarkdownを、たたんだ状態で載せる。"""
        base = self.project.root / folder
        blocks = []
        for path in sorted(base.rglob("*.md")) if base.is_dir() else []:
            rel = path.relative_to(self.project.root).as_posix()
            body = md_to_html(path.read_text(encoding="utf-8-sig"), self.known, self.id_href)
            blocks.append(f"<details><summary>{_escape(rel)}</summary><div class=\"doc\">{body}</div></details>")
        return "<h2>この工程のドキュメント</h2>" + ("".join(blocks) or "<p>まだありません。</p>")

    def counts(self, record_id: str) -> list[str]:
        row = tm_core.coverage(self.project, record_id)
        return [str(row["testcases"]), str(row["Pass"]), str(row["Fail"]), str(row["ブロック"]),
                str(row["未実行"]), str(row["未実装"]), str(row["sessions"]), str(row["bugs"]), _badge(row["state"])]


COUNT_HEADERS = ["テストケース", "Pass", "Fail", "ブロック", "未実行", "未実装", "探索的テストのセッション", "見つけた不具合", "状態"]

CSS = """
:root{--fg:#1f2328;--muted:#59636e;--line:#d1d9e0;--bg:#fff;--soft:#f6f8fa;--ok:#1a7f37;--ng:#cf222e;--warn:#9a6700;--link:#0969da}
@media (prefers-color-scheme: dark){:root{--fg:#e6edf3;--muted:#9198a1;--line:#3d444d;--bg:#0d1117;--soft:#151b23;--ok:#3fb950;--ng:#f85149;--warn:#d29922;--link:#4493f8}}
*{box-sizing:border-box}
body{margin:0;font-family:"Segoe UI","Hiragino Sans","Yu Gothic UI",Meiryo,sans-serif;color:var(--fg);background:var(--bg);line-height:1.6;font-size:14px}
main{max-width:1280px;margin:0 auto;padding:12px 20px 48px}
nav{background:var(--soft);border-bottom:1px solid var(--line);padding:8px 20px;display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px}
nav a.current{font-weight:700;color:var(--fg)}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:22px;margin:10px 0 6px}h2{font-size:17px;margin:26px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}h3{font-size:15px;margin:18px 0 6px}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;margin:6px 0 12px}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{background:var(--soft);white-space:nowrap;font-weight:600}
a.id{font-family:Consolas,Menlo,monospace;font-size:12.5px;white-space:nowrap}
.badge{display:inline-block;padding:0 8px;border-radius:10px;font-size:12px;font-weight:600;white-space:nowrap;border:1px solid var(--line)}
.badge.ok,.badge.low{color:var(--ok);border-color:var(--ok)}.badge.ng,.badge.high{color:var(--ng);border-color:var(--ng)}
.badge.warn,.badge.mid{color:var(--warn);border-color:var(--warn)}.badge.none{color:var(--muted)}
.none-text,.muted{color:var(--muted)}.missing{color:var(--ng)}
details{border:1px solid var(--line);border-radius:6px;margin:6px 0;padding:4px 10px}summary{cursor:pointer;font-weight:600}
.doc h1{font-size:17px}.doc h2{font-size:15px;border:none}
.record{border:1px solid var(--line);border-radius:6px;margin:10px 0;padding:8px 12px}.record h3{margin:0 0 4px}
.note{background:var(--soft);border-left:4px solid var(--line);padding:6px 10px;margin:8px 0}
.verdict{font-size:20px;font-weight:700;padding:8px 14px;border-radius:6px;margin:6px 0 8px;border:2px solid}
.verdict.ok{color:var(--ok);border-color:var(--ok)}.verdict.ng{color:var(--ng);border-color:var(--ng)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media (max-width:900px){.cols{grid-template-columns:1fr}}
.panel{border:1px solid var(--line);border-radius:6px;padding:8px 12px}.panel h2{margin:0 0 6px;border:none;font-size:16px}
.panel table{margin:2px 0 6px}.panel h3{margin:8px 0 2px;font-size:14px}.panel ul{margin:2px 0;padding-left:20px}
.numbers{display:flex;flex-wrap:wrap;gap:6px 18px;margin:8px 0;font-size:13px}.numbers b{font-size:16px}
"""


def _page(title: str, body: str, current: str = "", extra_nav: str = "") -> str:
    links = ['<a href="index.html"' + (' class="current"' if current == "index" else "") + ">目次</a>"]
    for key in VIEW_STAGES:
        cls = ' class="current"' if key == current else ""
        links.append(f'<a href="{key}.html"{cls}>{tm_core.STAGE_NAMES[key]}</a>')
    links.append('<a href="ids.html"' + (' class="current"' if current == "ids" else "") + ">ID索引</a>")
    return (
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{_escape(title)}</title><style>{CSS}</style></head><body>"
        f"<nav>{extra_nav}{''.join(links)}</nav><main><h1>{_escape(title)}</h1>{body}</main></body></html>"
    )


def _ids(project: Project, type_key: str) -> list[str]:
    return [r.id for r in project.of_type(type_key)]


# ---- 工程ごとのページ ----

def _stage_requirements(v: View) -> str:
    p = v.project
    rows = [[v.ref(r.id), v.refs(c for c in p.children(r.id) if type_of(c) == "SPEC")] for r in p.of_type("REQ")]
    asked = {link for q in p.of_type("Q") for link in q.links}
    no_spec = [r.id for r in p.of_type("REQ") if not any(type_of(c) == "SPEC" for c in p.children(r.id))]
    no_req = [s.id for s in p.of_type("SPEC") if not p.parents(s.id)]
    no_question = '<span class="missing">(質問表に記載なし)</span>'
    lonely = "".join(
        f"<li>{v.ref(i)} {'(質問表に記載あり)' if i in asked else no_question}</li>" for i in no_spec
    )
    return (
        "<h2>要求と仕様の紐づけ</h2>" + _table(["要求", "紐づく仕様"], rows, ["row-" + r.id for r in p.of_type("REQ")])
        + "<h2>仕様が無い要求</h2>" + (f"<ul>{lonely}</ul>" if lonely else "<p>ありません。</p>")
        + "<h2>要求に紐づかない仕様</h2>" + (f"<p>{v.refs(no_req)}</p>" if no_req else "<p>ありません。</p>")
    )


def _risk_order(project: Project) -> list[str]:
    def level(record):
        return (tm_core._to_int(record.fields.get("影響度", "")) or 0) * (tm_core._to_int(record.fields.get("発生確率", "")) or 0)
    return [r.id for r in sorted(project.of_type("RISK"), key=lambda r: (-level(r), tm_core._id_key(r.id)))]


def _stage_risk(v: View) -> str:
    return ("<h2>要求 → 仕様 → リスク</h2><p class=\"muted\">リスクレベルの高い順。リスクレベル = 影響度 × 発生確率。15〜25 が高、8〜14 が中、1〜7 が低。</p>"
            + v.chain(_risk_order(v.project), ["REQ", "SPEC", "RISK"], ["影響度", "発生確率", "リスクレベル", "区分"]))


def _stage_plan(v: View) -> str:
    p = v.project
    exits = [[v.ref(e.id, False), v.text(e.fields.get("終了条件", e.title)), v.text(e.fields.get("測り方", ""))] for e in p.of_type("EXIT")]
    return ("<h2>テスト終了条件</h2>" + _table(["ID", "終了条件", "測り方"], exits)
            + "<h2>要求・仕様・リスク → テストアプローチ</h2>"
            + v.chain(_ids(p, "TA"), ["REQ", "SPEC", "RISK", "TA"], ["テストタイプ", "実施方法"]))


def _stage_analysis(v: View) -> str:
    p = v.project
    parts = ["<h2>フィーチャーごとのテスト条件</h2>"]
    grouped: set[str] = set()
    for feature in p.of_type("FT"):
        conditions = [c for c in p.children(feature.id) if type_of(c) == "COND"]
        grouped |= set(conditions)
        parts.append(f"<h3>{v.ref(feature.id)}</h3><p class=\"muted\">仕様: {v.refs(v.related(feature.id, 'SPEC'), False)}"
                     f" / 要求: {v.refs(v.related(feature.id, 'REQ'), False)}</p>")
        parts.append(v.chain(conditions, ["COND", "TA", "RISK"], ["要求・仕様ID", "優先順位", "テストオラクル", "段階"]))
    rest = [c for c in _ids(p, "COND") if c not in grouped]
    if rest:
        parts.append("<h3 class=\"missing\">フィーチャーに紐づいていないテスト条件</h3>" + v.chain(rest, ["COND", "TA", "RISK"]))
    return "".join(parts)


def _htcs_of(project: Project, coverage_item: str) -> list[str]:
    return [c for c in project.children(coverage_item) if type_of(c) == "HTC"]


def _stage_design(v: View) -> str:
    p = v.project
    rows, row_ids = [], []
    for condition in p.of_type("COND"):
        items = [c for c in p.children(condition.id) if type_of(c) == "CI"]
        covered = [i for i in items if _htcs_of(p, i)]
        waiting = [i for i in covered
                   if all("回答待ち" in p.records[h].fields.get("状態", "") for h in _htcs_of(p, i))]
        attrs = {k: val for row in p.attrs.get(condition.id, []) for k, val in row.items()}
        rate = f"{round(100 * len(covered) / len(items))}%" if items else "-"
        rows.append([v.ref(condition.id), v.text(attrs.get("テスト技法", "")), v.text(attrs.get("カバレッジ基準", "")),
                     f"{len(covered)} / {len(items)}", rate, str(len(waiting)),
                     v.refs((i for i in items if i not in covered), True) if len(covered) < len(items) else ""])
        row_ids.append("cov-" + condition.id)
    return (
        "<h2>テスト条件ごとの技法とカバレッジ</h2><p class=\"muted\">カバレッジ = テストケースで通るカバレッジアイテム ÷ 出したカバレッジアイテム。"
        "「うち回答待ち」は、回答待ちのテストケースでしか通らないカバレッジアイテムの数(回答が来るまで実行できない)。</p>"
        + _table(["テスト条件", "テスト技法", "カバレッジ基準", "通る数 / 出した数", "カバレッジ", "うち回答待ち", "通していないカバレッジアイテム"], rows, row_ids)
        + "<h2>要求 → ハイレベルテストケース</h2>"
        + v.chain(_ids(p, "HTC"), ["REQ", "SPEC", "RISK", "COND", "CI", "HTC"], ["実施方法", "優先順位", "状態"])
        + "<h2>要求 → テストチャーター</h2>"
        + v.chain(_ids(p, "CH"), ["REQ", "RISK", "COND", "CH"], ["対象の領域", "時間枠(分)", "してはならないこと"])
    )


def _unimplemented_table(v: View, type_key: str) -> str:
    rows = []
    for entry in v.project.unimplemented.values():
        if type_of(entry.id) == type_key:
            others = [v.text(val) for key, val in list(entry.fields.items())[1:]]
            rows.append([v.ref(entry.id)] + others)
    headers = None
    for entry in v.project.unimplemented.values():
        if type_of(entry.id) == type_key:
            headers = [TYPES[type_key]] + list(entry.fields)[1:]
            break
    return _table(headers, rows) if rows else "<p>ありません。</p>"


def _stage_implementation(v: View) -> str:
    p = v.project
    rows = []
    for ltc in p.of_type("LTC"):
        rows.append([v.refs(v.related(ltc.id, "REQ"), False), v.refs(v.related(ltc.id, "COND"), False),
                     v.refs(v.related(ltc.id, "HTC")), v.ref(ltc.id), v.text(ltc.fields.get("実施方法", "")),
                     v.text(ltc.fields.get("期待値", "")), v.refs((c for c in p.children(ltc.id) if type_of(c) == "PROC"), False)])
    missing = [h for h in tm_core.unimplemented_htcs(p) if h not in p.unimplemented]
    coverage_rows, coverage_ids = [], []
    for condition in p.of_type("COND"):
        items = [c for c in p.children(condition.id) if type_of(c) == "CI"]
        if not items:
            continue
        done = [i for i in items
                if any(type_of(c) == "LTC" for h in _htcs_of(p, i) for c in p.children(h))]
        coverage_rows.append([v.ref(condition.id), f"{len(done)} / {len(items)}", f"{round(100 * len(done) / len(items))}%",
                              v.refs((i for i in items if i not in done), True) if len(done) < len(items) else ""])
        coverage_ids.append("impl-cov-" + condition.id)
    return (
        "<h2>要求 → ローレベルテストケース → テスト手順</h2>"
        + _table(["要求", "テスト条件", "ハイレベルテストケース", "ローレベルテストケース", "実施方法", "期待値", "テスト手順"], rows,
                 ["row-" + r.id for r in p.of_type("LTC")])
        + "<h2>カバレッジアイテムを、ローレベルテストケースでどこまで通せているか</h2>"
        "<p class=\"muted\">テスト設計で出したカバレッジアイテムのうち、ローレベルテストケースがあるテストケースで通るものの数。"
        "未実装のテストケースでしか通らないものは、通せていない。</p>"
        + _table(["テスト条件", "通せている数 / 出した数", "割合", "通せていないカバレッジアイテム"], coverage_rows, coverage_ids)
        + "<h2>未実装のテストケースと理由</h2>" + _unimplemented_table(v, "HTC")
        + ("<p class=\"missing\">ローレベルテストケースが無いのに、未実装に記録されていない: " + v.refs(missing) + "</p>" if missing else "")
    )


def _stage_e2e(v: View) -> str:
    p = v.project
    return (
        "<h2>要求 → E2E自動テストスクリプト</h2>"
        + v.chain(_ids(p, "SCR"), ["REQ", "COND", "LTC", "SCR"], ["ファイル", "テスト名"])
        + "<h2>自動化できなかったテストケースと理由</h2>" + _unimplemented_table(v, "LTC")
    )


def _results_table(v: View) -> str:
    p = v.project
    final = p.final_results()
    rows, row_ids = [], []
    for ltc in p.of_type("LTC"):
        result = final.get(ltc.id)
        if result is None:
            rows.append([v.ref(ltc.id), v.text(ltc.fields.get("実施方法", "")), _badge("未実行"), "", "", "", "テスト結果が無い"])
        else:
            evidence = "<br>".join(
                e if re.match(r"^[a-z]+://", e) else f'<a href="{v.file_base}{tm_core.EXECUTION_DIR}/{result.run}/{html_lib.escape(e)}">{_escape(e)}</a>'
                for e in result.evidence
            )
            rows.append([v.ref(ltc.id), v.text(result.method or ltc.fields.get("実施方法", "")), _badge(result.result),
                         _escape(result.run), evidence, v.refs(result.bugs, False) if result.bugs else "", v.text(result.memo)])
        row_ids.append("result-" + ltc.id)
    return _table(["ローレベルテストケース", "実施方法", "結果", "テストラン", "証跡", "欠陥レポート", "メモ"], rows, row_ids)


def _bugs_table(v: View, bugs) -> str:
    rows = [[v.ref(b.id), _badge(b.fields.get("重要度", "")), _badge(b.fields.get("状態", "")),
             v.text(b.fields.get("見つけた日時", "")), v.refs(v.project.parents(b.id), False),
             v.refs(v.related(b.id, "REQ"), False), v.refs(v.related(b.id, "RISK"), False)] for b in bugs]
    return _table(["欠陥レポート", "重要度", "状態", "見つけた日時", "見つけたテスト", "影響する要求", "影響するリスク"], rows) if rows else "<p>ありません。</p>"


def _sessions_table(v: View) -> str:
    p = v.project
    rows = []
    for session in p.of_type("SES"):
        bugs = [c for c in p.children(session.id) if type_of(c) == "BUG"]
        rows.append([v.ref(session.id, False), v.refs(p.parents(session.id)), v.text(session.fields.get("開始日時", "")),
                     v.text(session.fields.get("かかった時間(分)", "")), v.refs(bugs, False) if bugs else "なし",
                     v.file_link(session.file, "セッションシートを開く")])
    return _table(["セッション", "テストチャーター", "開始日時", "かかった時間(分)", "見つけた不具合", "セッションシート"], rows) if rows else "<p>ありません。</p>"


def _stage_execution(v: View) -> str:
    p = v.project
    m = tm_core.metrics(p)
    t = m["testcases"]
    parts = [
        f"<p class=\"numbers\"><span>テストケース <b>{t['total']}</b> 件</span><span>Pass <b>{t['Pass']}</b></span>"
        f"<span>Fail <b>{t['Fail']}</b></span><span>ブロック <b>{t['ブロック']}</b></span><span>未実行 <b>{t['未実行']}</b></span>"
        f"<span>テストラン: {_escape(', '.join(m['runs']) or 'なし')}</span></p>"
        "<p class=\"muted\">同じテストケースを何回か実行したときは、いちばん新しいテストランの結果を数える。</p>"
    ]
    for type_key in ["REQ", "SPEC", "RISK", "COND"]:
        ids = _risk_order(p) if type_key == "RISK" else _ids(p, type_key)
        rows = [[v.ref(i)] + v.counts(i) for i in ids]
        parts.append(f"<h2>{TYPES[type_key]}ごとの結果</h2>" + _table([TYPES[type_key]] + COUNT_HEADERS, rows))
    parts.append("<h2>テストケースごとの結果・証跡・欠陥レポート</h2>" + _results_table(v))
    parts.append("<h2>欠陥レポート</h2>" + _bugs_table(v, p.of_type("BUG")))
    parts.append("<h2>探索的テストのセッション</h2>" + _sessions_table(v))
    return "".join(parts)


_STAGE_BODIES = {
    "requirements": _stage_requirements, "risk": _stage_risk, "plan": _stage_plan, "analysis": _stage_analysis,
    "design": _stage_design, "implementation": _stage_implementation, "e2e": _stage_e2e, "execution": _stage_execution,
}


def _questions(v: View, stage: str) -> str:
    name = tm_core.STAGE_NAMES[stage]
    rows = [[v.ref(q.id, False), v.text(q.fields.get("質問", "")), v.text(q.fields.get("種類", "")),
             v.refs(q.links, False), v.text(q.fields.get("状態", "")), v.text(q.fields.get("回答", ""))]
            for q in v.project.of_type("Q") if q.fields.get("工程", "").strip() in (name, name.replace("作成", ""))]
    if not rows:
        return ""
    return "<h2>この工程で出た質問</h2>" + _table(["ID", "質問", "種類", "関連", "状態", "回答"], rows)


def render_stage(project: Project, stage: str, id_href: str = "ids.html", file_base: str = "../") -> str:
    view = View(project, id_href, file_base)
    body = _STAGE_BODIES[stage](view) + _questions(view, stage) + view.documents(tm_core.STAGE_DIRS[stage])
    return _page(tm_core.STAGE_NAMES[stage], body, current=stage)


def render_ids(project: Project, file_base: str = "../") -> str:
    """すべての成果物を1件ずつ載せ、上流と下流の両方にたどれるようにする。"""
    view = View(project, id_href="", file_base=file_base)
    final = project.final_results()
    parts = ["<p class=\"muted\">IDごとに、中身と、上流(要求の側)・下流(テスト結果の側)の紐づけを載せる。</p>"]
    for type_key, label in TYPES.items():
        records = project.of_type(type_key)
        if not records:
            continue
        parts.append(f"<h2>{label}</h2>")
        for record in records:
            fields = [[_escape(k), view.text(val)] for k, val in record.fields.items() if k != "ID" and val]
            for row in project.attrs.get(record.id, []):
                fields += [[_escape(k), view.text(val)] for k, val in list(row.items())[1:] if val]
            if record.id in final:
                fields.append(["最終のテスト結果", f"{_badge(final[record.id].result)} ({_escape(final[record.id].run)})"])
            up, down = project.ancestors(record.id), project.descendants(record.id)
            trace = []
            for title, group in (("上流", up), ("下流", down)):
                cells = [f"{TYPES[t]}: {view.refs((i for i in group if type_of(i) == t), False).replace('<br>', ' ')}"
                         for t in TYPES if any(type_of(i) == t for i in group)]
                trace.append([title, "<br>".join(cells) or '<span class="none-text">なし</span>'])
            related = sorted((l for l in record.links | record.mentions if l in project.records and l not in up),
                             key=tm_core._id_key)
            if related:
                trace.append(["そのほかの関連", view.refs(related, False).replace("<br>", " ")])
            trace.append(["書いてある場所", view.file_link(record.file)])
            parts.append(
                f'<section class="record" id="{record.id}"><h3>{record.id} {_escape(record.title[:80])}</h3>'
                + _table(["項目", "内容"], fields + trace) + "</section>"
            )
    return _page("ID索引", "".join(parts), current="ids")


def _render_index(project: Project) -> str:
    errors, warnings = tm_core.check(project)
    rows = []
    for key in VIEW_STAGES:
        folder = project.root / tm_core.STAGE_DIRS[key]
        rows.append([f'<a href="{key}.html">{tm_core.STAGE_NAMES[key]}</a>', "あり" if folder.is_dir() else '<span class="none-text">まだ</span>'])
    reports = sorted((project.root / tm_core.REPORT_DIR).glob("*/index.html"))
    latest = (f'<p>最新のテストレポート: <a href="../{tm_core.REPORT_DIR}/{reports[-1].parent.name}/index.html">'
              f'{reports[-1].parent.name}</a></p>') if reports else ""
    problems = "".join(f"<li>{_escape(e)}</li>" for e in errors)
    notes = "".join(f"<li>{_escape(w)}</li>" for w in warnings)
    body = (
        latest + "<h2>工程</h2>" + _table(["工程", "成果物"], rows)
        + f"<h2>トレーサビリティの確認</h2><p>エラー {len(errors)} 件、警告 {len(warnings)} 件"
        f"(成果物がある最後の工程「{tm_core.STAGE_NAMES[tm_core.detect_stage(project)]}」まで確認)</p>"
        + (f"<h3>エラー(紐づけの抜け・切れなど)</h3><ul>{problems}</ul>" if problems else "")
        + (f"<h3>警告(下流がまだ無いもの)</h3><ul>{notes}</ul>" if notes else "")
    )
    return _page("テスト成果物の目次", body, current="index")


def build_html(project: Project, out_dir: Path, stages: list[str] | None = None) -> list[Path]:
    """視認性アップ: 工程ごとのページ・目次・ID索引を作る。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = {"index.html": _render_index(project), "ids.html": render_ids(project)}
    for stage in stages or VIEW_STAGES:
        pages[f"{stage}.html"] = render_stage(project, stage)
    for stage in VIEW_STAGES:  # 目次やナビのリンクが切れないよう、指定していない工程のページも無ければ作る
        if f"{stage}.html" not in pages and not (out_dir / f"{stage}.html").exists():
            pages[f"{stage}.html"] = render_stage(project, stage)
    written = []
    for name, content in pages.items():
        (out_dir / name).write_text(content, encoding="utf-8")
        written.append(out_dir / name)
    return written


# ---- テストレポート ----

JUDGMENT_FILE = "判定.md"
MET, NOT_MET, UNJUDGED = "満たした", "満たしていない", "未判定"


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.*)$", line)
        if heading:
            current = heading.group(1).strip()
            sections[current] = ""
        elif current is not None:
            sections[current] += line + "\n"
    return sections


def _more(items: list[str], limit: int, anchor: str) -> str:
    shown = "".join(f"<li>{i}</li>" for i in items[:limit])
    rest = f'<li><a href="#{anchor}">ほか {len(items) - limit} 件</a></li>' if len(items) > limit else ""
    return f"<ul>{shown}{rest}</ul>" if items else ""


def _first_view(v: View, m: dict, judgments: dict[str, tuple[str, str]], lacking: str) -> str:
    rows, bad = [], 0
    for criterion in m["exit_criteria"]:
        verdict, reason = judgments.get(criterion["id"], (UNJUDGED, "判定が書かれていない"))
        if verdict != MET:
            verdict = verdict if verdict == NOT_MET else UNJUDGED
            bad += 1
        rows.append([v.ref(criterion["id"], False), v.text(criterion["text"]), _badge(verdict), v.text(reason)])
    if not m["exit_criteria"]:
        banner = '<div class="verdict ng">テスト計画に終了条件が無いので、判定できない</div>'
    elif bad:
        banner = f'<div class="verdict ng">満たしていない終了条件が {bad} 件ある</div>'
    else:
        banner = '<div class="verdict ok">すべての終了条件を満たした</div>'
    t = m["testcases"]
    numbers = (
        f"<p class=\"numbers\"><span>テストケース <b>{t['total']}</b> 件</span>"
        f"<span>実行率 <b>{t['execution_rate']}%</b> ({t['executed']} / {t['total']})</span>"
        f"<span>Pass <b>{t['Pass']}</b></span><span>Fail <b>{t['Fail']}</b></span></p>"
    )
    done = ("<div class=\"panel\"><h2>やるべきことをやったか</h2>"
            + _table(["ID", "終了条件", "判定", "根拠"], rows)
            + (f"<h3>足りないこと</h3>{md_to_html(lacking, v.known, v.id_href)}" if bad and lacking.strip() else "")
            + numbers + "</div>")

    bugs = [f"{_badge(b['severity'])} {v.ref(b['id'])}" for b in m["open_bugs"]]
    untested_req = [r for r in m["requirements"] if r["state"] == "まったくテストしていない"]
    partial_req = [r for r in m["requirements"] if r["state"] == "一部しか実行していない"]
    high = [r for r in m["risks"] if r["class"] == "高"]
    untested_risk = [r for r in high if r["state"] == "まったくテストしていない"]
    partial_risk = [r for r in high if r["state"] == "一部しか実行していない"]

    def gap(label: str, untested: list, partial: list, anchor: str) -> str:
        text = f"<h3>{label}: まったくテストしていない {len(untested)} 件、一部しか実行していない {len(partial)} 件</h3>"
        return text + _more([v.ref(r["id"]) for r in untested + partial], 3, anchor)

    problems = (
        "<div class=\"panel\"><h2>問題点は何か</h2>"
        f"<h3>修正されていない不具合: {len(bugs)} 件</h3>" + _more(bugs, 4, "bugs")
        + gap("カバーできていない要求", untested_req, partial_req, "req-coverage")
        + gap("カバーできていない高いリスク", untested_risk, partial_risk, "risk-coverage")
        + f"<p class=\"numbers\"><span><a href=\"#questions\">未回答の質問</a> <b>{len(m['open_questions'])}</b> 件</span>"
        f"<span><a href=\"#not-run\">未実行</a> <b>{t['未実行']}</b> 件</span>"
        f"<span><a href=\"#not-run\">ブロック</a> <b>{t['ブロック']}</b> 件</span>"
        f"<span><a href=\"#not-run\">未実装</a> <b>{t['未実装']}</b> 件</span></p></div>"
    )
    return f'<section id="first-view">{banner}<div class="cols">{done}{problems}</div></section>'


def _coverage_table(v: View, rows: list[dict], risk: bool) -> str:
    headers = (["リスク", "リスクレベル", "区分"] if risk else ["要求"]) + ["テスト条件"] + COUNT_HEADERS
    body = []
    for row in rows:
        cells = [v.ref(row["id"])] + ([str(row["level"]), _badge(row["class"])] if risk else [])
        cells += [str(row["conditions"]), str(row["testcases"]), str(row["Pass"]), str(row["Fail"]), str(row["ブロック"]),
                  str(row["未実行"]), str(row["未実装"]), str(row["sessions"]), str(row["bugs"]), _badge(row["state"])]
        body.append(cells)
    return _table(headers, body, ["cov-" + r["id"] for r in rows])


def build_report(project: Project, timestamp: str | None = None) -> Path:
    """テストレポートを作る。数字は成果物から数え直す。作った時点の成果物も一緒に保存する。"""
    report_root = project.root / tm_core.REPORT_DIR
    judgment_path = report_root / JUDGMENT_FILE
    if not judgment_path.is_file():
        raise ReportError(
            f"{judgment_path} が無い。終了条件ごとの判定と、数字では書けないこと(計画からの変更・教訓など)を"
            f"先に {JUDGMENT_FILE} に書く。"
        )
    judgment_text = judgment_path.read_text(encoding="utf-8-sig")
    judgments: dict[str, tuple[str, str]] = {}
    for table in tm_core.parse_tables(judgment_text):
        if table.headers and table.headers[0] == "終了条件ID":
            for row in table.rows:
                ids = tm_core.find_ids(row[0])
                if ids:
                    fields = dict(zip(table.headers, row))
                    judgments[ids[0]] = (fields.get("判定", "").strip(), fields.get("根拠", ""))
    sections = _sections(judgment_text)

    timestamp = timestamp or datetime.now().strftime("%Y%m%d%H%M%S")
    out = report_root / timestamp
    out.mkdir(parents=True, exist_ok=True)
    snapshot = out / "snapshot"
    if snapshot.exists():
        shutil.rmtree(snapshot)
    shutil.copytree(project.root, snapshot, ignore=shutil.ignore_patterns("html", tm_core.REPORT_DIR))
    shutil.copyfile(judgment_path, out / JUDGMENT_FILE)

    v = View(project, id_href="ids.html", file_base="snapshot/")
    m = tm_core.metrics(project)
    t = m["testcases"]
    errors, warnings = tm_core.check(project)

    method_rows = [[_escape(name)] + [str(counts[s]) for s in tm_core.RESULTS] for name, counts in m["by_method"].items()]
    not_run_rows = [[v.ref(r["id"]), _badge(r["status"]), v.text(r["reason"])] for r in m["not_run"]]
    not_run_rows += [[v.ref(r["id"]), _badge("未実装"), v.text(r["reason"])] for r in m["unimplemented"]]
    question_rows = [[v.ref(q["id"], False), _escape(q["stage"]), v.text(q["question"])] for q in m["open_questions"]]
    rollback = project.root / "戻し記録.md"
    rollback_html = md_to_html(rollback.read_text(encoding="utf-8-sig"), v.known, v.id_href) if rollback.is_file() else "<p>記録はありません。</p>"

    empty = '<p class="muted">記載なし</p>'
    written = "".join(
        f"<h2>{_escape(title)}</h2>{md_to_html(body, v.known, v.id_href) if body.strip() else empty}"
        for title, body in sections.items() if title not in ("終了条件の判定", "足りないこと")
    )
    details = (
        '<section id="details">'
        f'<div class="note">作成日時: {timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[8:10]}:{timestamp[10:12]}。'
        f'使ったテストラン: {_escape(", ".join(m["runs"]) or "なし")}。'
        "数字はすべて、このレポートを作った時点の成果物(snapshot フォルダ)から数え直したもの。"
        "同じテストケースを何回か実行したときは、いちばん新しいテストランの結果を数えている。</div>"
        '<h2 id="req-coverage">要求のカバレッジ</h2>'
        "<p class=\"muted\">要求ごとに、紐づくテストがどれだけ実行されたか。未実行・ブロック・未実装は、実行した数に含めない。"
        "状態の分母は「ローレベルテストケース + 未実装のハイレベルテストケース + テストチャーター」。</p>"
        + _coverage_table(v, m["requirements"], risk=False)
        + '<h2 id="risk-coverage">リスクのカバレッジ</h2><p class="muted">リスクレベルの高い順。リスクに直接紐づくテスト条件のテストを数える。</p>'
        + _coverage_table(v, m["risks"], risk=True)
        + "<h2>テスト結果の内訳</h2>"
        f"<p>実行率 {t['execution_rate']}% = 実行した {t['executed']} 件(Pass + Fail) ÷ ローレベルテストケース {t['total']} 件。"
        f"未実装の {t['未実装']} 件は分母に入っていない。</p>"
        + _table(["実施方法"] + tm_core.RESULTS, method_rows)
        + '<h2 id="bugs">修正されていない不具合</h2>'
        + _bugs_table(v, [project.records[b["id"]] for b in m["open_bugs"]])
        + '<h2 id="not-run">実行していないテストケース(未実行・ブロック・未実装)</h2>'
        + (_table(["テストケース", "状態", "理由"], not_run_rows) if not_run_rows else "<p>ありません。</p>")
        + '<h2 id="questions">未回答の質問</h2>'
        + (_table(["ID", "工程", "質問"], question_rows) if question_rows else "<p>ありません。</p>")
        + written
        + "<h2>「後からわかったことの戻し方」の記録</h2>" + rollback_html
        + "<h2>探索的テストのセッション</h2>" + _sessions_table(v)
        + "<h2>トレーサビリティ</h2>"
        f"<p>確認の結果: エラー {len(errors)} 件、警告 {len(warnings)} 件。"
        '<a href="ids.html">ID索引</a>から、どの成果物でも上流(要求の側)と下流(テスト結果・証跡・欠陥レポートの側)の両方にたどれる。'
        "工程ごとの追跡表は上のメニューから開ける。</p>"
        + ("<ul>" + "".join(f"<li class=\"missing\">{_escape(e)}</li>" for e in errors) + "</ul>" if errors else "")
        + "</section>"
    )
    first = _first_view(v, m, judgments, sections.get("足りないこと", ""))
    nav = '<a href="index.html" class="current">テストレポート</a>'
    page = _page("テストレポート", first + details, current="report")
    page = page.replace('<nav><a href="index.html">目次</a>', f"<nav>{nav}", 1)
    (out / "index.html").write_text(page, encoding="utf-8")

    def stage_page(content: str) -> str:
        return content.replace('<nav><a href="index.html">目次</a>', f'<nav><a href="index.html">テストレポート</a>', 1)

    (out / "ids.html").write_text(stage_page(render_ids(project, file_base="snapshot/")), encoding="utf-8")
    for stage in VIEW_STAGES:
        (out / f"{stage}.html").write_text(
            stage_page(render_stage(project, stage, file_base="snapshot/")), encoding="utf-8")
    return out
