"""成果物を人が読みやすいHTMLにする(視認性アップ)。テストレポートも作る。標準ライブラリだけで動く。"""
from __future__ import annotations

import html as html_lib
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import tm_core
from tm_core import TYPES, Project, type_of

VIEW_STAGES = [s for s in tm_core.STAGE_KEYS if s != "report"]

# ページの置き場所と名前。人が工程のフォルダを開いて見つけられるよう、日本語の名前にする
SUMMARY_DIR = "結果まとめ"
INDEX_PAGE = "目次.html"
IDS_PAGE = "ID索引.html"
REPORT_PAGE = "テストレポート.html"


def page_name(stage: str) -> str:
    """工程のページのファイル名(例: リスク分析.html)。"""
    return f"{tm_core.STAGE_NAMES[stage]}.html"


def _latest_report(project: Project) -> str | None:
    """いちばん新しいテストレポートの日時(フォルダ名)。無ければ None。"""
    names = sorted(p.parent.name for p in (project.root / tm_core.REPORT_DIR).glob(f"*/{REPORT_PAGE}"))
    return names[-1] if names else None


def _redirect_page(target: str, label: str) -> str:
    url = html_lib.escape(quote(target))
    return (
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        f'<meta http-equiv="refresh" content="0; url={url}"><title>{_escape(label)}</title></head>'
        f'<body><p>{_escape(label)}を開いています。開かないときは <a href="{url}">ここ</a> をクリックしてください。</p></body></html>'
    )


def write_report_entries(project: Project) -> list[Path]:
    """最新のテストレポートへ飛ぶ入口を、成果物のフォルダの直下と、テストレポートのフォルダに置く。
    人はまず最終結果を見たいが、レポートは日時のフォルダの奥にあって見つけにくいため。"""
    latest = _latest_report(project)
    if latest is None:
        return []
    label = f"最新のテストレポート({latest})"
    entries = {
        project.root / REPORT_PAGE: f"{tm_core.REPORT_DIR}/{latest}/{REPORT_PAGE}",
        project.root / tm_core.REPORT_DIR / REPORT_PAGE: f"{latest}/{REPORT_PAGE}",
    }
    for path, target in entries.items():
        path.write_text(_redirect_page(target, label), encoding="utf-8")
    return list(entries)


def _hrefs(base: str = "", index_page: str = INDEX_PAGE) -> dict[str, str]:
    """メニューのリンク先。base は、目次・ID索引・工程のページがあるフォルダへの相対パス。"""
    hrefs = {"index": base + index_page, "ids": base + IDS_PAGE}
    hrefs.update({stage: base + page_name(stage) for stage in VIEW_STAGES})
    return hrefs


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


_LIST_ITEM = re.compile(r"^(\s*)([*\-]|\d+\.)\s+(.*)$")


def _list_html(lines: list[str], i: int) -> tuple[str, int]:
    """lines[i] から始まる箇条書きをHTMLにする。字下げが深い行は、直前の項目の中の入れ子にする。"""
    first = _LIST_ITEM.match(lines[i])
    base, ordered = len(first.group(1)), first.group(2)[0].isdigit()
    items: list[str] = []
    while i < len(lines):
        m = _LIST_ITEM.match(lines[i])
        if not m or len(m.group(1)) < base:
            break
        if len(m.group(1)) > base:
            nested, i = _list_html(lines, i)
            if items:
                items[-1] += nested
            else:
                items.append(nested)
            continue
        if m.group(2)[0].isdigit() != ordered:
            break
        items.append(_inline(m.group(3)))
        i += 1
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{x}</li>" for x in items) + f"</{tag}>", i


def md_to_html(text: str, known_ids=None, id_href: str = IDS_PAGE) -> str:
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
        if _LIST_ITEM.match(line):
            flush()
            html, i = _list_html(lines, i)
            out.append(html)
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
        "Pass": "ok", "満たした": "ok", "達した": "ok", "達していない": "ng", "すべて実行してすべてPass": "ok", "クローズ": "ok", "低": "low",
        "Fail": "ng", "満たしていない": "ng", "未判定": "ng", "実行したがFailあり": "ng", "未修正": "ng", "高": "high",
        "ブロック": "warn", "一部しか実行していない": "warn", "修正済み": "warn", "中": "mid",
        "未実行": "none", "まったくテストしていない": "none", "未実装": "none",
    }
    return f'<span class="badge {kinds.get(text.strip(), "plain")}">{_escape(text)}</span>'


class View:
    """1ページ分の描画の設定(ID索引とファイルへの相対パス)を持つ。"""

    def __init__(self, project: Project, id_href: str = IDS_PAGE, file_base: str = "../"):
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
.panel{border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:0 0 12px}.panel h2{margin:0 0 6px;border:none;font-size:16px}
.panel table{margin:2px 0 6px}.panel h3{margin:8px 0 2px;font-size:14px}.panel ul{margin:2px 0;padding-left:20px}
.numbers{display:flex;flex-wrap:wrap;gap:6px 18px;margin:8px 0;font-size:13px}.numbers b{font-size:16px}
:root{--pass:#2da44e;--fail:#cf222e;--block:#bf8700;--notrun:#d0d7de;--unimpl:#8c959f;--explored:#8250df}
@media (prefers-color-scheme: dark){:root{--notrun:#3d444d;--unimpl:#6e7781}}
.tabs input{position:absolute;opacity:0}.tabs label{display:inline-block;padding:6px 14px;border:1px solid var(--line);border-bottom:none;border-radius:6px 6px 0 0;cursor:pointer;margin-right:4px;background:var(--soft)}
.tabs input:checked+label{background:var(--bg);font-weight:700}.tabs input:focus-visible+label{outline:2px solid var(--link)}
.pane{display:none;border-top:1px solid var(--line)}
#tab-req:checked~#req-coverage,#tab-risk:checked~#risk-coverage{display:block}
.tabs>input:nth-of-type(1):checked~.pane:nth-of-type(1),.tabs>input:nth-of-type(2):checked~.pane:nth-of-type(2),.tabs>input:nth-of-type(3):checked~.pane:nth-of-type(3),.tabs>input:nth-of-type(4):checked~.pane:nth-of-type(4),.tabs>input:nth-of-type(5):checked~.pane:nth-of-type(5),.tabs>input:nth-of-type(6):checked~.pane:nth-of-type(6),.tabs>input:nth-of-type(7):checked~.pane:nth-of-type(7),.tabs>input:nth-of-type(8):checked~.pane:nth-of-type(8){display:block}
.tree details{border:none;border-radius:0;margin:0;padding:0}
.tree summary{font-weight:400;display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;padding:5px 8px;border-bottom:1px solid var(--line)}
.tree summary:hover{background:var(--soft)}
.tree summary.ng{box-shadow:inset 3px 0 0 var(--fail)}.tree summary.warn{box-shadow:inset 3px 0 0 var(--block)}.tree summary.ok{box-shadow:inset 3px 0 0 var(--pass)}.tree summary.ex{box-shadow:inset 3px 0 0 var(--unimpl)}
.tree .kids{margin-left:22px;border-left:1px dashed var(--line)}
.tree .lv-REQ>summary,.tree .lv-RISK>summary,.tree .card>summary{font-weight:600}
.kind{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 4px;white-space:nowrap}
.tree .title{flex:1 1 280px;min-width:0}
.bar{display:inline-flex;width:140px;height:10px;border-radius:5px;overflow:hidden;background:var(--notrun);flex:none}
.bar i,.legend i{display:inline-block;height:100%}.pass{background:var(--pass)}.fail{background:var(--fail)}.block{background:var(--block)}
.notrun{background:var(--notrun)}.unimpl{background:repeating-linear-gradient(45deg,var(--unimpl) 0 3px,transparent 3px 6px)}.explored{background:var(--explored)}
/* 帯の頭を行ごとにそろえるため、帯の右の2つの欄は決まった幅にする */
.rate{font-size:12.5px;white-space:nowrap;flex:none;width:130px}
.flags{flex:none;width:240px}.flags b{font-size:11.5px;font-weight:600;margin-right:6px;white-space:nowrap}.flags .f{color:var(--fail)}.flags .w{color:var(--block)}
.ci{font-size:11.5px;color:var(--muted);white-space:nowrap}
.leaf{padding:4px 8px;border-bottom:1px solid var(--line);font-size:13px}.leaf .memo{color:var(--muted);font-size:12px;margin-left:8px}
.card-note{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:6px 8px;padding:6px 10px;background:var(--soft);border-left:3px solid var(--line);font-size:13px}
.card-note dt{font-weight:600;color:var(--muted);white-space:nowrap}.card-note dd{margin:0}
.tree .sub{font-size:12px;font-weight:600;color:var(--muted);padding:6px 8px 2px}
.latest-report{font-size:18px;font-weight:700;border:2px solid var(--link);border-radius:6px;padding:10px 14px;margin:8px 0 14px}
.latest-report .muted{font-size:13px;font-weight:400}
.nowrap{white-space:nowrap}
details.reasons{border:none;margin:0;padding:0}details.reasons summary{font-weight:400;color:var(--link)}
.bug-compare{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:8px}.bug-compare>div{border:1px solid var(--line);border-radius:6px;padding:6px 10px}.bug-compare .exp{border-left:4px solid var(--pass)}.bug-compare .act{border-left:4px solid var(--fail)}.bug-compare p,.bug-compare ul,.bug-steps ol,.bug-steps p{margin:4px 0}.bug-steps{margin:8px;padding:0 2px}@media (max-width:700px){.bug-compare{grid-template-columns:1fr}}details.fold{border:none;border-top:1px solid var(--line);border-radius:0;margin:0 8px;padding:4px 2px}details.fold summary{font-weight:400;color:var(--link)}details.fold .doc{padding:2px 0 6px}
.pct{font-weight:700}.pct.ok{color:var(--ok)}.pct.warn{color:var(--warn)}.pct.ng{color:var(--ng)}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;margin:6px 0}.legend i{width:12px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}
"""


# ページの中のリンク(#id)で、閉じているタブの中へ飛んだときに、そのタブを開く(入れ子のタブも外側から開く)
_SHOW_HASH_SCRIPT = (
    "<script>function tmShowHash(){var id=decodeURIComponent(location.hash.slice(1));"
    "var e=id&&document.getElementById(id);if(!e)return;var p=e.closest('.pane');"
    "while(p){var tabs=p.parentElement,kids=[].slice.call(tabs.children);"
    "var panes=kids.filter(function(c){return c.classList.contains('pane')});"
    "var inputs=kids.filter(function(c){return c.tagName==='INPUT'});"
    "var i=panes.indexOf(p);if(inputs[i])inputs[i].checked=true;p=tabs.closest('.pane')}"
    "e.scrollIntoView()}addEventListener('hashchange',tmShowHash);tmShowHash()</script>"
)


def _page(title: str, body: str, current: str = "", hrefs: dict[str, str] | None = None,
          index_label: str = "目次") -> str:
    hrefs = hrefs or _hrefs()
    names = {"index": index_label, **tm_core.STAGE_NAMES, "ids": "ID索引"}
    links = [f'<a href="{hrefs[key]}"' + (' class="current"' if key == current else "") + f">{names[key]}</a>"
             for key in ["index", *VIEW_STAGES, "ids"]]
    return (
        "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{_escape(title)}</title><style>{CSS}</style></head><body>"
        f"<nav>{''.join(links)}</nav><main><h1>{_escape(title)}</h1>{body}</main>{_SHOW_HASH_SCRIPT}</body></html>"
    )


def _ids(project: Project, type_key: str) -> list[str]:
    return [r.id for r in project.of_type(type_key)]


# ---- 工程ごとのページ ----

def _card(v: View, record_id: str, title: str, badges: str = "", meta: str = "",
          notes: list[tuple[str, str]] = (), sub_label: str = "", leaves: str = "",
          card_id: str = "", cls: str = "") -> str:
    """1件をたためる行にする。開くと、notes(項目名と値)を囲みで、その下に sub_label の見出しと leaves を出す。"""
    note = "".join(f"<dt>{_escape(name)}</dt><dd>{v.text(value)}</dd>" for name, value in notes if value.strip())
    inner = ((f'<dl class="card-note">{note}</dl>' if note else "")
             + ((f'<div class="sub">{sub_label}</div>' if sub_label else "") + leaves if leaves else ""))
    summary_cls = f' class="{cls}"' if cls else ""
    return (f'<details class="card" id="{card_id or "row-" + record_id}"><summary{summary_cls}>'
            f'<span class="kind">{TYPES[type_of(record_id)]}</span>'
            f'{v.ref(record_id, False)} {badges} <span class="title">{_escape(title)}</span>{meta}</summary>'
            f'<div class="kids">{inner}</div></details>')


def _leaf(v: View, record_id: str, memo: str = "") -> str:
    """開いた中に並べる1行。文は途中で切らずに全部出す(表のIDのリンクは60文字で切るが、ここでは読みたいので)。"""
    memo_html = f' <span class="memo">{memo}</span>' if memo else ""
    record = v.project.records.get(record_id)
    text = f" {_escape(record.title)}" if record else ""
    return (f'<div class="leaf"><span class="kind">{TYPES[type_of(record_id)]}</span>{v.ref(record_id, False)}'
            f'{text}{memo_html}</div>')


def _other_fields(record, skip: set[str]) -> list[tuple[str, str]]:
    """表のほかの欄。ID・見出しに出したもの・紐づけの列(見出しが ID で終わる列)は除く。"""
    return [(k, val) for k, val in record.fields.items() if k not in skip and not k.endswith("ID")]


def _stage_requirements(v: View) -> str:
    p = v.project
    cards = []
    for r in p.of_type("REQ"):
        specs = sorted((c for c in p.children(r.id) if type_of(c) == "SPEC"), key=tm_core._id_key)
        cards.append(_card(
            v, r.id, r.title, meta=f'<span class="ci">紐づく仕様 {len(specs)}件</span>',
            notes=_other_fields(r, {"ID", "要求"}), sub_label="紐づく仕様",
            leaves="".join(_leaf(v, s) for s in specs)))
    asked = {link for q in p.of_type("Q") for link in q.links}
    no_spec = [r.id for r in p.of_type("REQ") if not any(type_of(c) == "SPEC" for c in p.children(r.id))]
    no_req = [s.id for s in p.of_type("SPEC") if not p.parents(s.id)]
    no_question = '<span class="missing">(質問表に記載なし)</span>'
    lonely = "".join(
        f"<li>{v.ref(i)} {'(質問表に記載あり)' if i in asked else no_question}</li>" for i in no_spec
    )
    return (
        "<h2>要求と紐づく仕様</h2><p class=\"muted\">行をクリックすると、要求のほかの欄(誰が・何のためになど)と、紐づく仕様が開く。</p>"
        + f'<div class="tree">{"".join(cards)}</div>'
        + "<h2>仕様が無い要求</h2>" + (f"<ul>{lonely}</ul>" if lonely else "<p>ありません。</p>")
        + "<h2>要求に紐づかない仕様</h2>" + (f"<p>{v.refs(no_req)}</p>" if no_req else "<p>ありません。</p>")
    )


def _risk_order(project: Project) -> list[str]:
    def level(record):
        return (tm_core._to_int(record.fields.get("影響度", "")) or 0) * (tm_core._to_int(record.fields.get("発生確率", "")) or 0)
    return [r.id for r in sorted(project.of_type("RISK"), key=lambda r: (-level(r), tm_core._id_key(r.id)))]


def _stage_risk(v: View) -> str:
    """リスクを1件ずつたためる行で並べ、開くと根拠・備考と、紐づく仕様(とその要求)が出る。"""
    blocks = []
    for risk_id in _risk_order(v.project):
        record = v.project.records[risk_id]
        f = record.fields
        specs = sorted(v.related(risk_id, "SPEC"), key=tm_core._id_key)
        level = (f'<span class="ci">影響度 {_escape(f.get("影響度", ""))} × 発生確率 {_escape(f.get("発生確率", ""))}'
                 f' = {_escape(f.get("リスクレベル", ""))}</span>')
        blocks.append(_card(
            v, risk_id, record.title, badges=_badge(f.get("区分", "")),
            meta=f'{level}<span class="ci">紐づく仕様 {len(specs)}件</span>',
            notes=[(name, f.get(name, "")) for name in ("根拠", "備考")], sub_label="紐づく仕様",
            leaves="".join(_leaf(v, s, f'{TYPES["REQ"]}: {v.refs(v.related(s, "REQ"), False)}') for s in specs)))
    return ("<h2>リスクと紐づく仕様</h2><p class=\"muted\">リスクレベルの高い順。行をクリックすると、根拠・備考と、紐づく仕様とその要求が開く。"
            "リスクレベル = 影響度 × 発生確率。15〜25 が高、8〜14 が中、1〜7 が低。</p>"
            f'<div class="tree">{"".join(blocks)}</div>')


def _stage_plan(v: View) -> str:
    p = v.project
    # 何を・どこまでテストするかを先に読めるよう、テストアイテムとテストスコープを上に出す
    sections = _plan_sections(p)
    head = "".join(f"<h2>{name}</h2>{md_to_html(sections[name], v.known, v.id_href)}"
                   for name in ("テストアイテム", "テストスコープ") if sections.get(name, "").strip())
    exits = [[v.ref(e.id, False), v.text(e.fields.get("終了条件", e.title)), v.text(e.fields.get("測り方", ""))] for e in p.of_type("EXIT")]
    approaches = [
        [v.text(ta.fields.get("テストタイプ", "")), f'{v.ref(ta.id, False)} {v.text(ta.fields.get("内容", ""))}',
         v.text(ta.fields.get("実施方法", ""))] + [v.refs(v.related(ta.id, t), False) for t in ("REQ", "SPEC", "RISK")]
        for ta in p.of_type("TA")]
    # テストアプローチの表の要求・仕様・リスクの列に、どれか1行でも出てくれば「満たしている」と数える
    excluded = _excluded_in_plan(sections.get("対象外/制約", ""))
    covered = {t: {i for ta in p.of_type("TA") for i in v.related(ta.id, t)} for t in ("REQ", "SPEC", "RISK")}
    coverage = _coverage_rows(v, covered, excluded, "テストアプローチ")
    return (head + "<h2>テスト終了条件</h2>" + _table(["ID", "終了条件", "測り方"], exits)
            + "<h2>テストアプローチが要求・仕様・リスクを満たしている割合</h2>"
            "<p class=\"muted\">下のテストアプローチの表の要求・仕様・リスクの列に、1行でも出てくるものを「満たしている」と数える。</p>"
            + _table(["", "満たしている数", "割合", "満たしていないものと理由"], coverage)
            + "<h2>テストアプローチ</h2>"
            + _table(["テストタイプ", "テストアプローチ", "実施方法", "要求", "仕様", "リスク"], approaches,
                     ["row-" + ta.id for ta in p.of_type("TA")]))


def _plan_sections(p: Project) -> dict[str, str]:
    plan_file = p.root / tm_core.STAGE_DIRS["plan"] / "テスト計画.md"
    return _sections(plan_file.read_text(encoding="utf-8-sig")) if plan_file.is_file() else {}


def _coverage_rows(v: View, covered: dict[str, set[str]], excluded: dict[str, str], by: str,
                   reason=None, universe: dict[str, list[str]] | None = None) -> list[list[str]]:
    """種類ごとに、押さえている数・割合・押さえていないものと理由の行を作る。割合は切り捨て(全部そろうまで100%にしない)。
    reason: ID → 理由のHTML(その工程だけの理由)。None を返したものは共通の理由にする。"""
    rows = []
    for type_key, done in covered.items():
        all_ids = universe[type_key] if universe else _ids(v.project, type_key)  # universe: 数える対象を絞るとき
        missing = [i for i in all_ids if i not in done]
        if all_ids:
            percent = 100 * (len(all_ids) - len(missing)) // len(all_ids)
            level = "ok" if not missing else ("ng" if len(missing) == len(all_ids) else "warn")
            rate = f'<span class="pct {level}">{percent}%</span>'  # 色はカードの線とそろえる(緑・黄・赤)
        else:
            rate = "-"
        reasons = "<br>".join(
            f"{v.ref(i, False)} {(reason(i) if reason else None) or _not_covered_reason(v, i, excluded, by)}" for i in missing)
        # 理由は長くなるので、件数だけ見せてたたんでおく
        folded = (f'<details class="reasons"><summary>{len(missing)}件(開くと理由が出る)</summary>{reasons}</details>'
                  if missing else '<span class="none-text">なし</span>')
        rows.append([f'<span class="nowrap">{TYPES[type_key]}</span>', f"{len(all_ids) - len(missing)} / {len(all_ids)}",
                     rate, folded])
    return rows


def _excluded_in_plan(section: str) -> dict[str, str]:
    """テスト計画の「対象外/制約」のうち「対象外」の表から、ID → 対象外にした理由。"""
    excluded: dict[str, str] = {}
    sub = ""
    rows: list[list[str]] = []
    for line in section.splitlines() + [""]:
        heading = re.match(r"^###\s+(.*)$", line)
        if heading:
            sub = heading.group(1)
        if line.strip().startswith("|") and "対象外" in sub:
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
            continue
        for cells in rows[1:]:  # 先頭は見出しの行
            if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
                continue
            for record_id in tm_core.find_ids(cells[0]):
                excluded[record_id] = cells[1] if len(cells) > 1 else ""
        rows = []
    return excluded


def _not_covered_reason(v: View, record_id: str, excluded: dict[str, str], by: str = "テストアプローチ") -> str:
    if record_id in excluded:
        return f'<span class="muted">対象外: {v.text(excluded[record_id])}</span>'
    p = v.project
    skip = p.records[record_id].fields.get("通さない理由", "").strip() if record_id in p.records else ""
    if skip:  # テスト設計で、このカバレッジアイテムは通さないと決めたもの
        return f'<span class="muted">通さない理由: {v.text(skip)}</span>'
    if type_of(record_id) == "REQ" and not any(type_of(c) == "SPEC" for c in p.children(record_id)):
        risks = sorted((r.id for r in p.of_type("RISK") if record_id in r.links | r.mentions), key=tm_core._id_key)
        tas = sorted({ta.id for ta in p.of_type("TA") if set(risks) & set(v.related(ta.id, "RISK"))}, key=tm_core._id_key)
        handled = (f"。{v.refs(risks, False).replace('<br>', '、')} として "
                   f"{v.refs(tas, False).replace('<br>', '、')} で扱う") if risks and tas else ""
        return f'<span class="muted">仕様が無い{handled}</span>'
    return f'<span class="missing">{by}が無い</span>'


def _stage_analysis(v: View) -> str:
    p = v.project
    # どこまで押さえたかを先に読めるよう、カバレッジをいちばん上に出す
    parts = [_condition_coverage(v), "<h2>フィーチャーごとのテスト条件</h2>"]
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


def _conds_of(p: Project, record_id: str) -> list[str]:
    """そのIDに直接紐づくテスト条件。"""
    return [c for c in p.children(record_id) if type_of(c) == "COND"]


def _specs_of(p: Project, req_id: str) -> list[str]:
    return [c for c in p.children(req_id) if type_of(c) == "SPEC"]


def _req_conds(p: Project, req_id: str) -> set[str]:
    """要求に直接と、その仕様を通して紐づくテスト条件。"""
    return set(_conds_of(p, req_id)) | {c for s in _specs_of(p, req_id) for c in _conds_of(p, s)}


def _tabs(name: str, panes: list[tuple[str, str, str]]) -> str:
    """タブで切り替える一覧。panes は (pane の id, タブの名前, 中身)。最初のタブを開いておく。"""
    inputs = "".join(
        f'<input type="radio" name="{name}" id="tab-{pane_id}"{" checked" if n == 0 else ""}><label for="tab-{pane_id}">{label}</label>'
        for n, (pane_id, label, _) in enumerate(panes))
    return f'<div class="tabs">{inputs}' + "".join(
        f'<div class="pane tree" id="{pane_id}">{body}</div>' for pane_id, _, body in panes) + "</div>"


def _condition_coverage(v: View) -> str:
    """テスト条件が、要求・仕様・リスク・テストアプローチをどこまで押さえているか。割合の表と、たどれる一覧。"""
    p = v.project
    excluded = _excluded_in_plan(_plan_sections(p).get("対象外/制約", ""))

    def conds(record_id: str) -> list[str]:
        return _conds_of(p, record_id)

    covered = {
        "REQ": {r for r in _ids(p, "REQ") if _req_conds(p, r)},
        "SPEC": {s for s in _ids(p, "SPEC") if conds(s)},
        "RISK": {r for r in _ids(p, "RISK") if conds(r)},
        "TA": {t for t in _ids(p, "TA") if conds(t)},
    }

    def color(record_id: str, count: int) -> str:
        return "ok" if count else ("ex" if record_id in excluded else "ng")

    def cond_leaves(ids) -> str:
        return "".join(_leaf(v, c, _badge(p.records[c].fields.get("優先順位", ""))) for c in sorted(ids, key=tm_core._id_key))

    def card(pane: str, record_id: str, title: str, counted, shown, children: str = "", parent: str = "") -> str:
        """counted: 件数に数えるテスト条件。shown: この行の直下に出すテスト条件(仕様の下に出るものは children に入る)。"""
        n = len(set(counted))
        return _card(v, record_id, title, meta=f'<span class="ci">テスト条件 {n}件</span>',
                     sub_label="仕様とテスト条件" if children else "テスト条件",
                     leaves=cond_leaves(shown) + children,
                     card_id=f"{pane}-{parent + '-' if parent else ''}{record_id}", cls=color(record_id, n))

    req_pane = "".join(
        card("an-req", r.id, r.title, _req_conds(p, r.id), conds(r.id), children="".join(
            card("an-req", s, p.records[s].title, conds(s), conds(s), parent=r.id) for s in _specs_of(p, r.id)))
        for r in p.of_type("REQ"))
    risk_pane = "".join(card("an-risk", r, p.records[r].title, conds(r), conds(r)) for r in _risk_order(p))
    ta_pane = "".join(card("an-ta", t.id, t.fields.get("内容", "") or t.title, conds(t.id), conds(t.id))
                      for t in p.of_type("TA"))
    return (
        "<h2>テスト条件のカバレッジ</h2>"
        "<p class=\"muted\">テスト条件の表で、要求・仕様・リスク・テストアプローチに直接紐づけたものを数える"
        "(要求は、その仕様に紐づくテスト条件も数える)。</p>"
        + _table(["", "押さえている数", "割合", "押さえていないものと理由"], _coverage_rows(v, covered, excluded, "テスト条件"))
        + "<p class=\"muted\">行をクリックすると、紐づくテスト条件が開く。左の線は、緑 = テスト条件がある、"
        "赤 = テスト条件が無い、灰色 = テスト計画で対象外にした。</p>"
        + _tabs("an-tab", [("an-req", "要求からたどる", req_pane), ("an-risk", "リスクからたどる", risk_pane),
                           ("an-ta", "テストアプローチからたどる", ta_pane)])
    )


def _htcs_of(project: Project, coverage_item: str) -> list[str]:
    return [c for c in project.children(coverage_item) if type_of(c) == "HTC"]


def _stage_design(v: View) -> str:
    # どこまで押さえたかを先に読めるよう、テストケースのカバレッジをいちばん上に出す
    return _testcase_coverage(v) + _technique_table(v) + _charter_cards(v)


def _testcase_coverage(v: View) -> str:
    """テストケース(ハイレベル)とテストチャーターが、要求からカバレッジアイテムまでをどこまで押さえているか。"""
    p = v.project
    excluded = _excluded_in_plan(_plan_sections(p).get("対象外/制約", ""))

    def kids(record_id: str, type_key: str) -> list[str]:
        return [c for c in p.children(record_id) if type_of(c) == type_key]

    def waiting(htc: str) -> bool:
        return "回答待ち" in p.records[htc].fields.get("状態", "")

    def tests_of(conds) -> tuple[set[str], set[str]]:
        """テスト条件に紐づくテストケース(カバレッジアイテム経由も含む)とテストチャーター。"""
        htcs, chs = set(), set()
        for c in conds:
            htcs |= set(kids(c, "HTC")) | {h for ci in kids(c, "CI") for h in kids(ci, "HTC")}
            chs |= set(kids(c, "CH"))
        return htcs, chs

    def has_tests(conds) -> bool:
        htcs, chs = tests_of(conds)
        return bool(htcs or chs)

    covered = {
        "REQ": {r for r in _ids(p, "REQ") if has_tests(_req_conds(p, r))},
        "SPEC": {s for s in _ids(p, "SPEC") if has_tests(_conds_of(p, s))},
        "RISK": {r for r in _ids(p, "RISK") if has_tests(_conds_of(p, r))},
        "COND": {c for c in _ids(p, "COND") if has_tests([c])},
        "CI": {i for i in _ids(p, "CI") if kids(i, "HTC")},
    }

    def htc_leaf(h: str) -> str:
        f = p.records[h].fields
        state = f' {_badge(f.get("状態", ""))}' if waiting(h) else ""
        return _leaf(v, h, f'{_escape(f.get("実施方法", ""))} {_badge(f.get("優先順位", ""))}{state}')

    # テスト条件からたどる: テスト条件 → カバレッジアイテム → テストケース(探索的テストの条件はテストチャーター)
    cond_cards = []
    for cond in p.of_type("COND"):
        items, chs = kids(cond.id, "CI"), kids(cond.id, "CH")
        ci_cards, done, partial = [], 0, False
        for ci in items:
            htcs = kids(ci, "HTC")
            reason = p.records[ci].fields.get("通さない理由", "").strip()
            if htcs and not all(waiting(h) for h in htcs):
                color, done = "ok", done + 1
            elif htcs:
                color, done, partial = "warn", done + 1, True
            else:
                color = "ex" if reason else "ng"
            ci_cards.append(_card(v, ci, p.records[ci].title, notes=[("通さない理由", reason)], sub_label="テストケース",
                                  leaves="".join(htc_leaf(h) for h in htcs), card_id=f"ds-cond-{ci}", cls=color))
        loose = [h for h in kids(cond.id, "HTC") if not set(p.records[h].links) & set(items)]
        if items:
            color = "ok" if done == len(items) and not partial else ("warn" if done or chs else "ng")
            meta = f'<span class="ci">カバレッジアイテム {done} / {len(items)}</span>'
        else:
            color = "ok" if chs or loose else "ng"
            meta = ""
        meta += f'<span class="ci">チャーター {len(chs)}件</span>' if chs else ""
        cond_cards.append(_card(
            v, cond.id, cond.title, meta=meta, sub_label="カバレッジアイテム・テストケース・チャーター",
            leaves="".join(ci_cards) + "".join(htc_leaf(h) for h in loose) + "".join(_leaf(v, c) for c in chs),
            card_id=f"ds-cond-{cond.id}", cls=color))

    # 要求からたどる: 要求 → 仕様 → テスト条件 → テストケース・テストチャーター
    def color_of(record_id: str, htcs, chs) -> str:
        if htcs and all(waiting(h) for h in htcs) and not chs:
            return "warn"
        return "ok" if htcs or chs else ("ex" if record_id in excluded else "ng")

    def tests_meta(htcs, chs) -> str:
        return f'<span class="ci">テストケース {len(htcs)}件・チャーター {len(chs)}件</span>'

    def cond_card(parent: str, c: str) -> str:
        # 同じテスト条件が複数の要求・仕様の下に出るので、行のidに親のIDを入れる
        htcs, chs = tests_of([c])
        return _card(v, c, p.records[c].title, meta=tests_meta(htcs, chs), sub_label="テストケース・チャーター",
                     leaves="".join(htc_leaf(h) for h in sorted(htcs, key=tm_core._id_key))
                     + "".join(_leaf(v, ch) for ch in sorted(chs, key=tm_core._id_key)),
                     card_id=f"ds-req-{parent}-{c}", cls=color_of(c, htcs, chs))

    def req_card(record_id: str, conds, shown, children: str = "", parent: str = "") -> str:
        htcs, chs = tests_of(conds)
        path = f"{parent}-{record_id}" if parent else record_id  # 同じ仕様が複数の要求の下に出るので、idにたどった道を入れる
        return _card(v, record_id, p.records[record_id].title, meta=tests_meta(htcs, chs),
                     sub_label="仕様とテスト条件" if children else "テスト条件",
                     leaves="".join(cond_card(path, c) for c in shown) + children,
                     card_id=f"ds-req-{path}", cls=color_of(record_id, htcs, chs))

    req_pane = "".join(
        req_card(r.id, _req_conds(p, r.id), _conds_of(p, r.id), "".join(
            req_card(s, _conds_of(p, s), _conds_of(p, s), parent=r.id) for s in _specs_of(p, r.id)))
        for r in p.of_type("REQ"))
    return (
        "<h2>テストケースのカバレッジ</h2>"
        "<p class=\"muted\">ハイレベルテストケースとテストチャーターが押さえているものを数える。要求・仕様・リスクは、"
        "直接紐づくテスト条件にテストケースかテストチャーターがあれば押さえていると数える。"
        "回答待ちのテストケースは、回答が来るまで実装も実行もされない(数には入れ、一覧で黄色にする)。</p>"
        + _table(["", "押さえている数", "割合", "押さえていないものと理由"],
                 _coverage_rows(v, covered, excluded, "テストケース・テストチャーター"))
        + "<p class=\"muted\">行をクリックすると、下の成果物が開く。左の線は、緑 = 押さえている、"
        "黄 = 一部だけ・回答待ちのテストケースだけ、赤 = 無い、灰色 = 通さない理由がある・テスト計画で対象外にした。</p>"
        + _tabs("ds-tab", [("ds-cond", "テスト条件からたどる", "".join(cond_cards)),
                           ("ds-req", "要求からたどる", req_pane)])
    )


def _technique_table(v: View) -> str:
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
        "「うち回答待ち」は、回答待ちのテストケースでしか通らないカバレッジアイテムの数。"
        "回答待ちのテストケースは回答が来るまで実装も実行もされないので、テストベースから決められるのに回答待ちにしていないかを確かめる。</p>"
        + _table(["テスト条件", "テスト技法", "カバレッジ基準", "通る数 / 出した数", "カバレッジ", "うち回答待ち", "通していないカバレッジアイテム"], rows, row_ids)
    )


def _charter_cards(v: View) -> str:
    p = v.project
    cards = [
        _card(v, ch.id, ch.fields.get("目的", "") or ch.title, meta=f'<span class="ci">{_escape(ch.fields.get("時間枠(分)", ""))}分</span>',
              notes=_other_fields(ch, {"ID", "目的"}), sub_label="テスト条件",
              leaves="".join(_leaf(v, c) for c in p.parents(ch.id)), card_id=f"ch-{ch.id}")
        for ch in p.of_type("CH")]
    return ("<h2>テストチャーター</h2><p class=\"muted\">行をクリックすると、対象の領域・時間枠・してはならないことと、"
            "紐づくテスト条件が開く。</p>" + (f'<div class="tree">{"".join(cards)}</div>' if cards else "<p>ありません。</p>"))


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
    missing = [h for h in tm_core.unimplemented_htcs(p) if h not in p.unimplemented]
    # どこまで実装したかを先に読めるよう、ローレベルテストケースのカバレッジをいちばん上に出す
    return (
        _ltc_coverage(v) + _ltc_cards(v)
        + "<h2>未実装のテストケースと理由</h2>" + _unimplemented_table(v, "HTC")
        + ("<p class=\"missing\">ローレベルテストケースが無いのに、未実装に記録されていない: " + v.refs(missing) + "</p>" if missing else "")
    )


def _ltc_coverage(v: View) -> str:
    """ローレベルテストケースが、要求からハイレベルテストケースまでをどこまで押さえているか。
    探索的テストのテスト条件は、ローレベルテストケースにしないので、テストチャーターがあれば押さえていると数える。"""
    p = v.project
    excluded = _excluded_in_plan(_plan_sections(p).get("対象外/制約", ""))

    def kids(record_id: str, type_key: str) -> list[str]:
        return [c for c in p.children(record_id) if type_of(c) == type_key]

    def htcs_of_cond(cond: str) -> list[str]:
        return sorted(set(kids(cond, "HTC")) | {h for ci in kids(cond, "CI") for h in kids(ci, "HTC")}, key=tm_core._id_key)

    def ltcs_of(htcs) -> list[str]:
        return sorted({l for h in htcs for l in kids(h, "LTC")}, key=tm_core._id_key)

    def cond_done(cond: str) -> bool:
        return bool(ltcs_of(htcs_of_cond(cond)) or kids(cond, "CH"))

    covered = {
        "REQ": {r for r in _ids(p, "REQ") if any(cond_done(c) for c in _req_conds(p, r))},
        "SPEC": {s for s in _ids(p, "SPEC") if any(cond_done(c) for c in _conds_of(p, s))},
        "RISK": {r for r in _ids(p, "RISK") if any(cond_done(c) for c in _conds_of(p, r))},
        "COND": {c for c in _ids(p, "COND") if cond_done(c)},
        "CI": {i for i in _ids(p, "CI") if ltcs_of(kids(i, "HTC"))},
        "HTC": {h for h in _ids(p, "HTC") if kids(h, "LTC")},
    }

    def htc_reason(h: str) -> str:
        if h in p.unimplemented:
            return f"未実装: {v.text(p.unimplemented[h].reason)}"
        state = p.records[h].fields.get("状態", "")
        return f"回答待ち: {v.text(state)}" if "回答待ち" in state else ""

    def reason(record_id: str) -> str | None:
        """ハイレベルテストケースとカバレッジアイテムは、未実装・回答待ちの理由を出す。ほかは共通の理由。"""
        t = type_of(record_id)
        if t == "HTC":
            why = htc_reason(record_id)
        elif t == "CI" and not p.records[record_id].fields.get("通さない理由", "").strip():
            why = "、".join(f"{v.ref(h, False)} {htc_reason(h)}" for h in kids(record_id, "HTC") if htc_reason(h))
        elif t == "COND":  # どのハイレベルテストケースが、なぜ実装されていないか
            why = "、".join(f"{v.ref(h, False)} {htc_reason(h)}" for h in htcs_of_cond(record_id) if htc_reason(h))
        elif t in ("SPEC", "RISK", "REQ") and record_id not in excluded:  # どのテスト条件で止まっているか
            conds = [c for c in (_req_conds(p, record_id) if t == "REQ" else _conds_of(p, record_id)) if htcs_of_cond(c)]
            why = (f"テスト条件 {v.refs(sorted(conds, key=tm_core._id_key), False).replace('<br>', '、')} の"
                   "ハイレベルテストケースが未実装・回答待ち") if conds else ""
        else:
            return None
        return f'<span class="muted">{why}</span>' if why else None

    def ltc_leaf(l: str, with_htc: bool = False) -> str:
        f = p.records[l].fields
        origin = f' {v.refs(parents_of(l, "HTC"), False)} から' if with_htc else ""
        return _leaf(v, l, f'{_escape(f.get("実施方法", ""))} {_badge(f.get("優先順位", ""))}{origin}')

    def parents_of(record_id: str, type_key: str) -> list[str]:
        return [x for x in p.parents(record_id) if type_of(x) == type_key]

    def impl_rate(htcs) -> str:
        """その行の下のハイレベルテストケースのうち、ローレベルテストケースまで実装した数と割合(切り捨て)。"""
        htcs = set(htcs)
        if not htcs:
            return ""
        done = sum(1 for h in htcs if kids(h, "LTC"))
        return f'<span class="ci">実装したハイレベル {done} / {len(htcs)} ({100 * done // len(htcs)}%)</span>'

    def htc_card(path: str, h: str) -> str:
        ltcs = kids(h, "LTC")
        why = htc_reason(h)
        color = "ok" if ltcs else ("warn" if "回答待ち" in why and h not in p.unimplemented else "ng")
        return _card(v, h, p.records[h].title, meta=f'<span class="ci">ローレベル {len(ltcs)}件</span>',
                     notes=[("理由", why)] if not ltcs else [], sub_label="ローレベルテストケース",
                     leaves="".join(ltc_leaf(l) for l in ltcs), card_id=f"im-cond-{path}-{h}", cls=color)

    # テスト条件からたどる: テスト条件 → ハイレベルテストケース → ローレベルテストケース(探索的テストはチャーター)
    cond_cards = []
    for cond in p.of_type("COND"):
        htcs, chs = htcs_of_cond(cond.id), kids(cond.id, "CH")
        done = [h for h in htcs if kids(h, "LTC")]
        if htcs:
            color = "ok" if len(done) == len(htcs) else ("warn" if done or chs else "ng")
            meta = impl_rate(htcs)
        else:
            color, meta = ("ok" if chs else "ng"), ""
        meta += f'<span class="ci">チャーター {len(chs)}件</span>' if chs else ""
        cond_cards.append(_card(
            v, cond.id, cond.title, meta=meta, sub_label="ハイレベルテストケース・チャーター",
            leaves="".join(htc_card(cond.id, h) for h in htcs) + "".join(_leaf(v, c) for c in chs),
            card_id=f"im-cond-{cond.id}", cls=color))

    # 要求からたどる: 要求 → 仕様 → テスト条件 → ローレベルテストケース(もとのハイレベルテストケースを添える)
    def cond_card(parent: str, c: str) -> str:
        htcs, chs = htcs_of_cond(c), kids(c, "CH")
        ltcs = ltcs_of(htcs)
        lost = [h for h in htcs if not kids(h, "LTC")]
        leaves = ("".join(ltc_leaf(l, with_htc=True) for l in ltcs)
                  + "".join(_leaf(v, h, f'<span class="missing">ローレベルテストケースが無い{"。" + htc_reason(h) if htc_reason(h) else ""}</span>')
                            for h in lost)
                  + "".join(_leaf(v, ch) for ch in chs))
        color = "ok" if (ltcs or chs) and not lost else ("warn" if ltcs or chs else "ng")
        return _card(v, c, p.records[c].title,
                     meta=impl_rate(htcs) + f'<span class="ci">ローレベル {len(ltcs)}件・チャーター {len(chs)}件</span>',
                     sub_label="ローレベルテストケース・チャーター", leaves=leaves, card_id=f"im-req-{parent}-{c}", cls=color)

    def req_card(record_id: str, conds, shown, children: str = "", parent: str = "") -> str:
        path = f"{parent}-{record_id}" if parent else record_id
        htcs = {h for c in conds for h in htcs_of_cond(c)}
        ltcs = ltcs_of(htcs)
        chs = {ch for c in conds for ch in kids(c, "CH")}
        color = "ok" if ltcs or chs else ("ex" if record_id in excluded else "ng")
        return _card(v, record_id, p.records[record_id].title,
                     meta=impl_rate(htcs) + f'<span class="ci">ローレベル {len(ltcs)}件・チャーター {len(chs)}件</span>',
                     sub_label="仕様とテスト条件" if children else "テスト条件",
                     leaves="".join(cond_card(path, c) for c in shown) + children, card_id=f"im-req-{path}", cls=color)

    req_pane = "".join(
        req_card(r.id, _req_conds(p, r.id), _conds_of(p, r.id), "".join(
            req_card(s, _conds_of(p, s), _conds_of(p, s), parent=r.id) for s in _specs_of(p, r.id)))
        for r in p.of_type("REQ"))
    return (
        "<h2>ローレベルテストケースのカバレッジ</h2>"
        "<p class=\"muted\">ローレベルテストケースが押さえているものを数える。探索的テストのテスト条件は、ローレベルテストケースに"
        "しないので、テストチャーターがあれば押さえていると数える。要求・仕様・リスクは、直接紐づくテスト条件で数える。"
        "行の「実装したハイレベル」は、その下のハイレベルテストケースのうち、ローレベルテストケースまで実装した数と割合。</p>"
        + _table(["", "押さえている数", "割合", "押さえていないものと理由"],
                 _coverage_rows(v, covered, excluded, "ローレベルテストケース", reason))
        + "<p class=\"muted\">行をクリックすると、下の成果物が開く。左の線は、緑 = 押さえている、"
        "黄 = 一部だけ・回答待ち、赤 = 無い(未実装を含む)、灰色 = テスト計画で対象外にした。</p>"
        + _tabs("im-tab", [("im-cond", "テスト条件からたどる", "".join(cond_cards)),
                           ("im-req", "要求からたどる", req_pane)])
    )


def _ltc_cards(v: View) -> str:
    p = v.project
    cards = []
    for ltc in p.of_type("LTC"):
        f = ltc.fields
        origin = [x for x in p.parents(ltc.id) if type_of(x) == "HTC"]
        procs = [c for c in p.children(ltc.id) if type_of(c) == "PROC"]
        cards.append(_card(
            v, ltc.id, f.get("テストケース", "") or ltc.title, badges=_badge(f.get("優先順位", "")),
            meta=f'<span class="ci">{_escape(f.get("実施方法", ""))}</span>',
            notes=_other_fields(ltc, {"ID", "テストケース", "実施方法", "優先順位"}),
            sub_label="もとのハイレベルテストケースとテスト手順",
            leaves="".join(_leaf(v, x) for x in origin + procs), card_id=f"ltc-{ltc.id}"))
    return ("<h2>ローレベルテストケース</h2><p class=\"muted\">行をクリックすると、事前条件・入力データ・期待値などと、"
            "もとのハイレベルテストケース・テスト手順が開く。</p>"
            + (f'<div class="tree">{"".join(cards)}</div>' if cards else "<p>ありません。</p>"))


def _stage_e2e(v: View) -> str:
    # どこまで自動化したかを先に読めるよう、スクリプトのカバレッジをいちばん上に出す
    return (
        _script_coverage(v)
        + "<h2>自動化できなかったテストケースと理由</h2>" + _unimplemented_table(v, "LTC")
    )


def _script_coverage(v: View) -> str:
    """E2E自動テストのローレベルテストケースに、スクリプトがどこまでそろったか。
    要求・仕様・テスト条件は、E2E自動テストのローレベルテストケースを持つものだけを数え、その全部にスクリプトがあればそろったとする。"""
    p = v.project

    def kids(record_id: str, type_key: str) -> list[str]:
        return [c for c in p.children(record_id) if type_of(c) == type_key]

    def e2e_ltcs_of_cond(cond: str) -> list[str]:
        htcs = set(kids(cond, "HTC")) | {h for ci in kids(cond, "CI") for h in kids(ci, "HTC")}
        return sorted({l for h in htcs for l in kids(h, "LTC") if "E2E" in p.records[l].fields.get("実施方法", "")},
                      key=tm_core._id_key)

    def e2e_ltcs(conds) -> list[str]:
        return sorted({l for c in conds for l in e2e_ltcs_of_cond(c)}, key=tm_core._id_key)

    def scripted(l: str) -> bool:
        return bool(kids(l, "SCR"))

    conds_of = {"REQ": lambda r: _req_conds(p, r), "SPEC": lambda s: _conds_of(p, s), "COND": lambda c: [c]}
    universe = {t: [i for i in _ids(p, t) if e2e_ltcs(conds_of[t](i))] for t in conds_of}
    universe["LTC"] = [l.id for l in p.of_type("LTC") if "E2E" in l.fields.get("実施方法", "")]
    covered = {t: {i for i in ids if all(scripted(l) for l in e2e_ltcs(conds_of[t](i)))}
               for t, ids in universe.items() if t != "LTC"}
    covered["LTC"] = {l for l in universe["LTC"] if scripted(l)}

    def ltc_reason(l: str) -> str:
        if l in p.unimplemented:
            return f"自動化できなかった: {v.text(p.unimplemented[l].reason)}"
        return "スクリプトが無い"

    def reason(record_id: str) -> str:
        if type_of(record_id) == "LTC":
            why = ltc_reason(record_id)
        else:
            lost = [l for l in e2e_ltcs(conds_of[type_of(record_id)](record_id)) if not scripted(l)]
            why = "、".join(f"{v.ref(l, False)} {ltc_reason(l)}" for l in lost)
        cls = "muted" if record_id in p.unimplemented else "missing"
        return f'<span class="{cls}">{why}</span>'

    def color(ltcs) -> str:
        done = sum(1 for l in ltcs if scripted(l))
        return "ok" if done == len(ltcs) else ("warn" if done else "ng")

    def rate(ltcs) -> str:
        done = sum(1 for l in ltcs if scripted(l))
        return f'<span class="ci">スクリプトのあるE2E {done} / {len(ltcs)} ({100 * done // len(ltcs)}%)</span>' if ltcs else ""

    # テスト名からたどる: テスト(スクリプト) → ローレベル → ハイレベル → テスト条件 → 仕様 → 要求(出どころを上へ)
    test_cards = []
    for s in p.of_type("SCR"):
        f = s.fields
        upstream = [i for t in ("LTC", "HTC", "COND", "SPEC", "REQ") for i in v.related(s.id, t)]
        test_cards.append(_card(
            v, s.id, f.get("テスト名", "") or s.title, notes=[("ファイル", f.get("ファイル", ""))],
            sub_label="出どころ(ローレベル → ハイレベル → テスト条件 → 仕様 → 要求)",
            leaves="".join(_leaf(v, i) for i in upstream), card_id=f"e2e-test-{s.id}", cls="ok"))

    # 要求からたどる: 要求 → 仕様 → テスト条件 → E2E自動テストのローレベルテストケース → スクリプト
    def ltc_leaf(l: str) -> str:
        scrs = kids(l, "SCR")
        f = p.records[l].fields
        if scrs:
            memo = " ".join(f'{v.ref(s, False)} {_escape(p.records[s].fields.get("ファイル", ""))}' for s in scrs)
        else:
            memo = f'<span class="{"muted" if l in p.unimplemented else "missing"}">{ltc_reason(l)}</span>'
        return _leaf(v, l, f'{_badge(f.get("優先順位", ""))} {memo}')

    def card(record_id: str, conds, shown, children: str = "", parent: str = "") -> str:
        path = f"{parent}-{record_id}" if parent else record_id
        ltcs = e2e_ltcs(conds)
        leaves = "".join(ltc_leaf(l) for l in ltcs) if type_of(record_id) == "COND" else \
            "".join(card(c, [c], [c], parent=path) for c in shown if e2e_ltcs([c])) + children
        label = "E2E自動テストのローレベルテストケース" if type_of(record_id) == "COND" else (
            "仕様とテスト条件" if children else "テスト条件")
        return _card(v, record_id, p.records[record_id].title, meta=rate(ltcs), sub_label=label, leaves=leaves,
                     card_id=f"e2e-req-{path}", cls=color(ltcs))

    req_pane = "".join(
        card(r, _req_conds(p, r), _conds_of(p, r), "".join(
            card(s, _conds_of(p, s), _conds_of(p, s), parent=r) for s in _specs_of(p, r) if s in universe["SPEC"]))
        for r in universe["REQ"])
    return (
        "<h2>E2E自動テストスクリプトのカバレッジ</h2>"
        "<p class=\"muted\">実施方法がE2E自動テストのローレベルテストケースに、スクリプトがあるかを数える。"
        "要求・仕様・テスト条件は、E2E自動テストのローレベルテストケースを持つものだけを数え、その全部にスクリプトがあればそろったとする。</p>"
        + _table(["", "そろった数", "割合", "そろっていないものと理由"],
                 _coverage_rows(v, covered, {}, "スクリプト", reason, universe))
        + "<p class=\"muted\">行をクリックすると、下の成果物が開く。左の線は、緑 = 全部にスクリプトがある、"
        "黄 = 一部だけ、赤 = 無い。</p>"
        + _tabs("e2e-tab", [("e2e-test", "テスト名からたどる", "".join(test_cards)), ("e2e-req", "要求からたどる", req_pane)])
    )


_RESULT_COLOR = {"Pass": "ok", "Fail": "ng", "ブロック": "warn", "未実行": "ex"}


def _result_cards(v: View, ltcs, prefix: str = "ex-ltc") -> str:
    """ローレベルテストケースを1件1行にし、開くとメモ・テストラン・証跡・欠陥レポートが出る。
    prefix: 行のidの頭。同じテストケースを別のタブにも出すときに、idが重ならないよう変える。"""
    p = v.project
    final = p.final_results()
    cards = []
    for ltc in ltcs:
        result = final.get(ltc.id)
        status = result.result if result else "未実行"
        notes, leaves = [], ""
        if result is None:
            notes = [("メモ", "テスト結果が無い")]
        else:
            notes = [("テストラン", result.run), ("メモ", result.memo)]
            leaves = "".join(
                f'<div class="leaf"><span class="kind">証跡</span> '
                + (_escape(e) if re.match(r"^[a-z]+://", e) else
                   f'<a href="{v.file_base}{tm_core.EXECUTION_DIR}/{result.run}/{html_lib.escape(e)}">{_escape(e)}</a>')
                + "</div>" for e in result.evidence)
            leaves += "".join(_leaf(v, b) for b in result.bugs)
        cards.append(_card(v, ltc.id, ltc.title, badges=_badge(status),
                           meta=f'<span class="ci">{_escape((result.method if result else "") or ltc.fields.get("実施方法", ""))}</span>',
                           notes=notes, sub_label="証跡と欠陥レポート", leaves=leaves,
                           card_id=f"{prefix}-{ltc.id}", cls=_RESULT_COLOR.get(status, "")))
    return f'<div class="tree">{"".join(cards)}</div>' if cards else "<p>ありません。</p>"


def _session_cards(v: View) -> str:
    p = v.project
    cards = []
    for ses in p.of_type("SES"):
        f = ses.fields
        charters = p.parents(ses.id)
        bugs = [c for c in p.children(ses.id) if type_of(c) == "BUG"]
        title = " / ".join(p.records[c].title for c in charters if c in p.records) or ses.title
        cards.append(_card(
            v, ses.id, title, badges=_badge(f"不具合 {len(bugs)}件") if bugs else "",
            meta=f'<span class="ci">{_escape(f.get("かかった時間(分)", ""))}分</span>',
            notes=[("開始日時", f.get("開始日時", "")), ("実施者", f.get("実施者", ""))],
            sub_label="テストチャーター・見つけた不具合・セッションシート",
            leaves="".join(_leaf(v, c) for c in charters) + "".join(_leaf(v, b) for b in bugs)
            + f'<div class="leaf"><span class="kind">ファイル</span> {v.file_link(ses.file, "セッションシートを開く")}</div>',
            card_id=f"ex-ses-{ses.id}", cls="warn" if bugs else "ok"))
    return f'<div class="tree">{"".join(cards)}</div>' if cards else "<p>ありません。</p>"


_BUG_ITEM = re.compile(r"^[-*]\s+([^:：]{1,40}?)[:：]\s*(.*)$")


def _bug_items(text: str) -> tuple[list[tuple[str, str, str]], str]:
    """欠陥レポートの節を「- 項目名: 内容」ごとに分ける。(項目名, 1行目の内容, 字下げした続き) の並びと、
    項目にならなかった行を返す。"""
    items: list[tuple[str, str, list[str]]] = []
    rest: list[str] = []
    for line in text.splitlines():
        m = _BUG_ITEM.match(line)
        if m:
            items.append((m.group(1).strip(), m.group(2).strip(), []))
        elif items and (line.startswith((" ", "\t")) or not line.strip()):
            items[-1][2].append(line)
        elif line.strip():
            rest.append(line)
    dedented = [(name, head, "\n".join(l[2:] if l.startswith("  ") else l.lstrip() for l in body).strip())
                for name, head, body in items]
    return dedented, "\n".join(rest)


def _evidence_links(v: View, text: str) -> list[str]:
    """証跡の欄の「RUN-…/証跡/ファイル」を、テストランのフォルダのファイルへのリンクにする。
    フォルダを省いて続けて書いたファイルは、直前と同じフォルダのものとする。"""
    # ファイル名に「、」「。」などが入ることがあるので、まず証跡フォルダにある実際のファイル名を文の中から探す
    found = []
    for run in dict.fromkeys(re.findall(r"(RUN-[\w-]+)/証跡/", text)):
        base = v.project.root / tm_core.EXECUTION_DIR / run / "証跡"
        for f in (base.rglob("*") if base.is_dir() else []):
            name = f.relative_to(base).as_posix()
            for m in re.finditer(re.escape(name), text):
                if f.is_file() and (m.start() == 0 or not re.match(r"[\w.-]", text[m.start() - 1])):
                    found.append((m.start(), f"{run}/証跡/{name}"))
    if found:
        paths = list(dict.fromkeys(path for _, path in sorted(found)))
        return [f'<a href="{v.file_base}{tm_core.EXECUTION_DIR}/{html_lib.escape(path)}">{_escape(path)}</a>' for path in paths]
    links, folder = [], ""
    for token in re.split(r"[、,。]\s*", text):
        token = re.split(r"\s*[(（]", token.strip())[0].strip()  # ファイル名のあとの注記「(…」は外す
        if not token or token.endswith(("）", ")")):  # 注記の続き(括弧の中で「、」で区切られた残り)
            continue
        m = re.search(r"(RUN-[\w-]+/証跡/)(.*)$", token)
        if m:
            folder, path = m.group(1), m.group(1) + m.group(2)
        elif folder and re.search(r"\.\w+$", token) and "/" not in token and " " not in token:
            path = folder + token
        else:
            links.append(v.text(token))
            continue
        links.append(f'<a href="{v.file_base}{tm_core.EXECUTION_DIR}/{html_lib.escape(path)}">{_escape(path)}</a>')
    return links


def _bug_cards(v: View) -> str:
    """欠陥レポートを1件1行にする。開くと、期待値と実際の結果を並べ、その下に再現手順を出す。
    ほかの項目(原因・証跡・見つけたテスト・影響など)は、たたんでおく。"""
    p = v.project
    path = p.root / tm_core.EXECUTION_DIR / "欠陥レポート.md"
    details = _sections(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}

    def md(text: str) -> str:
        return md_to_html(text, v.known, v.id_href)

    def fold(title: str, body: str) -> str:
        return f'<details class="fold"><summary>{title}</summary><div class="doc">{body}</div></details>'

    def affected(bug, type_key: str) -> str:
        # 要求・リスクのカバレッジと同じ数え方にする(欠陥レポートに範囲が書かれていればそれに従う)
        if tm_core.bug_scope(bug) == set():
            return tm_core.OUT_OF_SCOPE
        return ", ".join(i for i in _ids(p, type_key) if tm_core.bug_affects(p, bug.id, i)) or "なし"

    cards = []
    open_ids = {b.id for b in tm_core.open_bugs(p)}
    for bug in tm_core.open_bugs(p) + [b for b in p.of_type("BUG") if b.id not in open_ids]:
        f = bug.fields
        detail = next((body for title, body in details.items() if bug.id in tm_core.find_ids(title)), "")
        items, rest = _bug_items(detail)
        named = {"steps": None, "expected": None, "actual": None}
        others = []
        for name, head, body in items:
            key = ("steps" if name.startswith("再現できる手順") else "expected" if name.startswith("期待値")
                   else "actual" if name.startswith("実際の結果") else None)
            if key and named[key] is None:
                named[key] = (name, head, body)
            else:
                others.append((name, head, body))

        inner = ""
        if named["expected"] or named["actual"]:
            def box(cls: str, entry) -> str:
                if entry is None:
                    return f'<div class="{cls}"><b>{"期待値" if cls == "exp" else "実際の結果"}</b><p class="muted">記載なし</p></div>'
                name, head, body = entry
                shown = head if cls == "act" else "\n".join(x for x in (head, body) if x)
                return f'<div class="{cls}"><b>{_escape(name)}</b>{md(shown)}</div>'
            inner += f'<div class="bug-compare">{box("exp", named["expected"])}{box("act", named["actual"])}</div>'
        if named["steps"]:
            name, head, body = named["steps"]
            inner += f'<div class="bug-steps"><b>{_escape(name)}</b>{md(chr(10).join(x for x in (head, body) if x))}</div>'
        if named["actual"] and named["actual"][2]:
            count = sum(1 for line in named["actual"][2].splitlines() if _LIST_ITEM.match(line))
            inner += fold(f"実際の結果の詳しい内容({count}件)", md(named["actual"][2]))

        evidence = [o for o in others if o[0].startswith("証跡")]
        memo = [o for o in others if o[0].startswith("メモ")]
        rest_items = [o for o in others if o not in evidence and o not in memo]
        for name, head, body in rest_items:  # 原因の見立て・手がかり・重要度の理由など、書いてある順に
            inner += fold(_escape(name), md("\n".join(x for x in (head, body) if x)))
        for name, head, body in evidence:
            links = _evidence_links(v, " ".join(x for x in (head, body) if x))
            inner += fold(f"{_escape(name)}({len(links)}件)", "<ul>" + "".join(f"<li>{l}</li>" for l in links) + "</ul>")
        found = p.parents(bug.id)
        ltcs = [t for t in found if type_of(t) == "LTC"]
        sessions = [t for t in found if type_of(t) == "SES"]
        inner += fold(f"見つけたテスト(LTC {len(ltcs)}件・セッション {len(sessions)}件)",
                      "".join(_leaf(v, t) for t in found) or '<p class="muted">なし</p>')
        impact = [("影響する要求", affected(bug, "REQ")), ("影響するリスク", affected(bug, "RISK")),
                  ("テスト対象・環境", f.get("テスト対象・環境", ""))]
        inner += fold("影響する要求・リスク・テスト対象と環境",
                      '<dl class="card-note">' + "".join(f"<dt>{k}</dt><dd>{v.text(val)}</dd>" for k, val in impact if val) + "</dl>")
        for name, head, body in memo:
            inner += fold(_escape(name), md("\n".join(x for x in (head, body) if x)))
        if rest.strip():
            inner += fold("そのほかの記載", md(rest))

        state = f.get("状態", "").strip()
        cards.append(_card(
            v, bug.id, f.get("タイトル", "") or bug.title,
            badges=_badge(f.get("重要度", "")) + " " + _badge(state),
            meta=f'<span class="ci">{_escape(f.get("見つけた日時", ""))}</span>',
            leaves=inner, card_id=f"ex-bug-{bug.id}", cls="ok" if state in tm_core.BUG_CLOSED else "ng"))
    return f'<div class="tree">{"".join(cards)}</div>' if cards else "<p>ありません。</p>"


def _stage_execution(v: View) -> str:
    docs = _questions(v, "execution") + v.documents(tm_core.STAGE_DIRS["execution"])
    return _tabs("ex-tab", _execution_panes(v, tm_core.metrics(v.project)) + [("ex-docs", "質問・ドキュメント", docs)])


def _execution_panes(v: View, m: dict, summary_extra: str = "") -> list[tuple[str, str, str]]:
    """テスト実行の結果のタブ(まとめ・Fail・E2E・手動・探索的テスト・欠陥レポート)。テストレポートでも使う。
    summary_extra: まとめのタブの最後に足すもの。"""
    p = v.project
    t = m["testcases"]
    method_rows = [[_escape(name)] + [str(counts[s]) for s in tm_core.RESULTS] for name, counts in m["by_method"].items()]
    # 探索的テストは Pass・Fail を付けないので、チャーター・セッション・時間・見つけた不具合で別に出す
    charters, sessions = m["charters"], p.of_type("SES")
    found = {b for s in sessions for b in p.children(s.id) if type_of(b) == "BUG"}
    still_open = found & {b.id for b in tm_core.open_bugs(p)}
    timebox = sum(c["timebox"] or 0 for c in charters)
    exploratory = _table(
        ["テストチャーター", "探索した", "セッション", "時間(合計 / 時間枠、分)", "時間枠に達した", "セッションに紐づく不具合"],
        [[str(len(charters)), str(sum(1 for c in charters if c["sessions"])), str(len(sessions)),
          f"{sum(c['minutes'] for c in charters):g} / {timebox:g}",
          f"{sum(1 for c in charters if c['reached'])} / {len(charters)}",
          f"{len(found)}件" + (f"(うち未修正 {len(still_open)}件)" if still_open else "")]]) if charters else "<p>ありません。</p>"
    summary = (
        f"<p class=\"numbers\"><span>テストケース <b>{t['total']}</b> 件</span><span>Pass <b>{t['Pass']}</b></span>"
        f"<span>Fail <b>{t['Fail']}</b></span><span>ブロック <b>{t['ブロック']}</b></span><span>未実行 <b>{t['未実行']}</b></span>"
        f"<span>探索的テストのセッション <b>{len(sessions)}</b></span>"
        f"<span>テストラン: {_escape(', '.join(m['runs']) or 'なし')}</span></p>"
        "<p class=\"muted\">同じテストケースを何回か実行したときは、いちばん新しいテストランの結果を数える。</p>"
        + "<h3>テストケース</h3>" + _table(["実施方法"] + tm_core.RESULTS, method_rows)
        + "<h3>探索的テスト</h3>" + exploratory
        + _trace_tree(v, m)
        + summary_extra
    )
    ltcs = p.of_type("LTC")
    e2e = [l for l in ltcs if "E2E" in l.fields.get("実施方法", "")]
    manual = [l for l in ltcs if l not in e2e]
    final = p.final_results()
    failed = [l for l in ltcs if l.id in final and final[l.id].result == "Fail"]
    bugs = p.of_type("BUG")
    return [
        ("ex-sum", "まとめ", summary),
        ("ex-fail", f"Fail({len(failed)})", _result_cards(v, failed, prefix="ex-fail-ltc")),
        ("ex-e2e", f"E2E自動テスト({len(e2e)})", _result_cards(v, e2e)),
        ("ex-manual", f"手動テスト({len(manual)})", _result_cards(v, manual)),
        ("ex-ses", f"探索的テスト({len(p.of_type('SES'))})", _session_cards(v)),
        ("ex-bug", f"欠陥レポート({len(bugs)})", _bug_cards(v)),
    ]


_STAGE_BODIES = {
    "requirements": _stage_requirements, "risk": _stage_risk, "plan": _stage_plan, "analysis": _stage_analysis,
    "design": _stage_design, "implementation": _stage_implementation, "e2e": _stage_e2e, "execution": _stage_execution,
}


def _observed_evidence(v: View, observed: str) -> str:
    """質問表の「実機の動き」に書かれた証跡(RUN-…/証跡/…)を、ファイルへのリンクの行にする。"""
    if "/証跡/" not in observed:
        return ""
    return "".join(f'<div class="leaf"><span class="kind">証跡</span> {link}</div>' for link in _evidence_links(v, observed))


def _questions(v: View, stage: str) -> str:
    name = tm_core.STAGE_NAMES[stage]
    cards = [
        _card(v, q.id, q.fields.get("質問", "") or q.title, badges=_badge(q.fields.get("状態", "")),
              notes=_other_fields(q, {"ID", "工程", "質問", "状態"}), sub_label="関連するもの",
              leaves="".join(_leaf(v, link) for link in sorted(q.links, key=tm_core._id_key))
              + _observed_evidence(v, q.fields.get("実機の動き", "")))
        for q in v.project.of_type("Q") if q.fields.get("工程", "").strip() in (name, name.replace("作成", ""))]
    if not cards:
        return ""
    return ("<h2>この工程で出た質問</h2><p class=\"muted\">行をクリックすると、種類・回答が必要な理由・実機の動き・回答と、関連するものが開く。</p>"
            f'<div class="tree">{"".join(cards)}</div>')


def render_stage(project: Project, stage: str, file_base: str = "../", hrefs: dict[str, str] | None = None,
                 index_label: str = "目次") -> str:
    hrefs = hrefs or _hrefs()
    view = View(project, hrefs["ids"], file_base)
    body = _STAGE_BODIES[stage](view)
    if stage != "execution":  # テスト実行のページは、質問とドキュメントをタブの中に入れる
        body += _questions(view, stage) + view.documents(tm_core.STAGE_DIRS[stage])
    return _page(tm_core.STAGE_NAMES[stage], body, current=stage, hrefs=hrefs, index_label=index_label)


def render_ids(project: Project, file_base: str = "../", hrefs: dict[str, str] | None = None,
               index_label: str = "目次") -> str:
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
    return _page("ID索引", "".join(parts), current="ids", hrefs=hrefs, index_label=index_label)


def _render_index(project: Project) -> str:
    errors, warnings = tm_core.check(project)
    rows = []
    for key in VIEW_STAGES:
        folder = project.root / tm_core.STAGE_DIRS[key]
        rows.append([f'<a href="{page_name(key)}">{tm_core.STAGE_NAMES[key]}</a>', "あり" if folder.is_dir() else '<span class="none-text">まだ</span>'])
    report = _latest_report(project)
    latest = (f'<div class="latest-report"><a href="../{tm_core.REPORT_DIR}/{report}/{REPORT_PAGE}">最新のテストレポートを開く</a>'
              f' <span class="muted">({report[:4]}-{report[4:6]}-{report[6:8]} {report[8:10]}:{report[10:12]} 作成)</span></div>'
              ) if report else ""
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


def build_html(project: Project, stages: list[str] | None = None) -> list[Path]:
    """視認性アップ: 結果まとめ のフォルダに目次・ID索引・工程ごとのページを作る。
    工程のフォルダがあれば、その中にも同じ工程のページを作る(人は工程のフォルダで結果を探すため)。"""
    summary = project.root / SUMMARY_DIR
    summary.mkdir(parents=True, exist_ok=True)
    pages = {summary / INDEX_PAGE: _render_index(project), summary / IDS_PAGE: render_ids(project)}
    for stage in stages or VIEW_STAGES:
        pages[summary / page_name(stage)] = render_stage(project, stage)
        folder = project.root / tm_core.STAGE_DIRS[stage]
        if folder.is_dir():
            pages[folder / page_name(stage)] = render_stage(project, stage, hrefs=_hrefs(f"../{SUMMARY_DIR}/"))
    for stage in VIEW_STAGES:  # 目次やナビのリンクが切れないよう、指定していない工程のページも無ければ作る
        path = summary / page_name(stage)
        if path not in pages and not path.exists():
            pages[path] = render_stage(project, stage)
    for path, content in pages.items():
        path.write_text(content, encoding="utf-8")
    return list(pages) + write_report_entries(project)


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
    # 満たしていない・未判定の終了条件を先に並べ、狭い画面でもファーストビューに入るようにする。
    ok_rows, bad_rows, bad_ids = [], [], []
    for criterion in m["exit_criteria"]:
        verdict, reason = judgments.get(criterion["id"], (UNJUDGED, "判定が書かれていない"))
        if verdict != MET:
            verdict = verdict if verdict == NOT_MET else UNJUDGED
            bad_ids.append(criterion["id"])
        row = [v.ref(criterion["id"], False), v.text(criterion["text"]), _badge(verdict), v.text(reason)]
        (ok_rows if verdict == MET else bad_rows).append(row)
    rows, bad = bad_rows + ok_rows, len(bad_ids)
    if not m["exit_criteria"]:
        banner = '<div class="verdict ng">テスト計画に終了条件が無いので、判定できない</div>'
    elif bad:
        banner = f'<div class="verdict ng">満たしていない終了条件が {bad} 件ある({v.text("、".join(bad_ids))})</div>'
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
        f"<h3>修正されていない不具合: {len(bugs)} 件</h3>" + _more(bugs, 4, "ex-bug")
        + gap("カバーできていない要求", untested_req, partial_req, "req-coverage")
        + gap("カバーできていない高いリスク", untested_risk, partial_risk, "risk-coverage")
        + f"<p class=\"numbers\"><span><a href=\"#questions\">未回答の質問</a> <b>{len(m['open_questions'])}</b> 件"
        f"(うち実機の動きあり <b>{sum(1 for q in m['open_questions'] if q['observed'])}</b> 件)</span>"
        f"<span><a href=\"#not-run\">未実行</a> <b>{t['未実行']}</b> 件</span>"
        f"<span><a href=\"#not-run\">ブロック</a> <b>{t['ブロック']}</b> 件</span>"
        f"<span><a href=\"#not-run\">未実装</a> <b>{t['未実装']}</b> 件</span></p></div>"
    )
    # 1列で、帯 → 問題点 → やるべきことをやったか(終了条件ごとの判定)の順に並べる。問題点を先に読めるようにする
    return f'<section id="first-view">{banner}{problems}{done}</section>'


# ---- テストレポート: 開いてたどれるトレーサビリティ ----

# たどる順。キーの種類の下に、値の種類を開く。
_TREE_CHILDREN = {"REQ": ["SPEC", "COND"], "SPEC": ["COND"], "RISK": ["COND"], "COND": ["HTC", "CH"],
                  "HTC": ["LTC"], "CH": ["SES"]}
# 色帯の並び(数えるキー, CSSのクラス)
_TREE_SEGMENTS = [("Pass", "pass"), ("Fail", "fail"), ("ブロック", "block"), ("未実行", "notrun"),
                  ("未実装", "unimpl"), ("探索済み", "explored"), ("未探索", "notrun")]


class _Tree:
    """要求(またはリスク)から、テスト結果・証跡・欠陥レポートまでを、開いてたどれる入れ子にする。"""

    def __init__(self, v: View):
        self.v, self.p = v, v.project
        self.final = self.p.final_results()
        self.unimplemented = set(tm_core.unimplemented_htcs(self.p))

    def kids(self, record_id: str, types: list[str]) -> list[str]:
        return [c for c in self.p.children(record_id) if type_of(c) in types]

    def counts(self, record_id: str) -> dict:
        """その成果物から下のテストの内訳。"""
        t = type_of(record_id)
        zero = {k: 0 for k, _ in _TREE_SEGMENTS} | {"bugs": 0}
        if t in ("REQ", "SPEC", "RISK", "COND"):
            row = tm_core.coverage(self.p, record_id)
            return zero | {k: row[k] for k in tm_core.RESULTS} | {
                "未実装": row["未実装"], "探索済み": row["charters_done"],
                "未探索": row["charters"] - row["charters_done"], "bugs": row["open_bugs"]}
        if t == "HTC":
            c = dict(zero, 未実装=1 if record_id in self.unimplemented else 0)
            for ltc in self.kids(record_id, ["LTC"]):
                c[tm_core._status(self.final, ltc)] += 1
            open_ids = {b.id for b in tm_core.open_bugs(self.p)}
            c["bugs"] = len({b for ltc in self.kids(record_id, ["LTC"]) for b in self.kids(ltc, ["BUG"]) if b in open_ids})
            return c
        sessions = self.kids(record_id, ["SES"])  # CH
        open_ids = {b.id for b in tm_core.open_bugs(self.p)}
        return dict(zero, 探索済み=1 if sessions else 0, 未探索=0 if sessions else 1,
                    bugs=len({b for s in sessions for b in self.kids(s, ["BUG"]) if b in open_ids}))

    def bar(self, c: dict) -> tuple[str, str]:
        total = sum(c[k] for k, _ in _TREE_SEGMENTS)
        if not total:
            return '<span class="rate none-text">テストなし</span>', "none"
        parts = "".join(f'<i class="{cls}" style="width:{100 * c[k] / total:.1f}%" title="{k} {c[k]}"></i>'
                        for k, cls in _TREE_SEGMENTS if c[k])
        executed = c["Pass"] + c["Fail"] + c["探索済み"]
        waiting = c["未実行"] + c["ブロック"] + c["未探索"]
        flags = ([f'<b class="f">Fail {c["Fail"]}</b>'] if c["Fail"] else []) \
            + ([f'<b class="w">未実行 {waiting}</b>'] if waiting else []) \
            + ([f'<b class="w">未実装 {c["未実装"]}</b>'] if c["未実装"] else []) \
            + ([f'<b class="f">不具合 {c["bugs"]}</b>'] if c["bugs"] else [])
        level = "ng" if c["Fail"] or c["bugs"] else ("warn" if executed < total else "ok")
        return (f'<span class="bar">{parts}</span>'
                f'<span class="rate">実行 {executed}/{total}({round(100 * executed / total)}%)</span>'
                f'<span class="flags">{"".join(flags)}</span>'), level

    def coverage_items(self, cond_id: str) -> str:
        items = self.kids(cond_id, ["CI"])
        if not items:
            return ""
        covered = [i for i in items if any(h not in self.unimplemented for h in self.kids(i, ["HTC"]))]
        return (f'<span class="ci" title="テスト設計で出したカバレッジアイテムのうち、実装したテストケースで通るもの">'
                f'カバレッジアイテム {len(covered)}/{len(items)}</span>')

    def label(self, record_id: str) -> str:
        record = self.p.records[record_id]
        title = (record.fields.get("テストケース", "") if type_of(record_id) == "LTC" else "") or record.title
        level = f' {_badge(record.fields.get("区分", ""))}' if type_of(record_id) == "RISK" else ""
        return (f'<span class="kind">{TYPES[type_of(record_id)]}</span>{self.v.ref(record_id, False)}{level}'
                f' <span class="title">{_escape(title[:70])}</span>')

    def leaf_ltc(self, ltc: str) -> str:
        result = self.final.get(ltc)
        if result is None:
            return f'<div class="leaf" data-id="{ltc}">{self.label(ltc)} {_badge("未実行")} テスト結果が無い</div>'
        files = [e for e in result.evidence if not re.match(r"^[a-z]+://", e)]
        evidence = " ".join(
            f'<a href="{self.v.file_base}{tm_core.EXECUTION_DIR}/{result.run}/{html_lib.escape(e)}">'
            f'証跡{n if len(files) > 1 else ""}</a>' for n, e in enumerate(files, 1))
        bugs = " ".join(self.v.ref(b, False) for b in result.bugs)
        memo = f'<div class="memo">{self.v.text(result.memo[:200])}</div>' if result.memo and result.result != "Pass" else ""
        return (f'<div class="leaf" data-id="{ltc}">{self.label(ltc)} {_badge(result.result)}'
                f' <span class="none-text">{_escape(result.run)}</span> {evidence} {bugs}{memo}</div>')

    def leaf_session(self, ses: str) -> str:
        record = self.p.records[ses]
        bugs = " ".join(self.v.ref(b, False) for b in self.kids(ses, ["BUG"]))
        return (f'<div class="leaf" data-id="{ses}">{self.label(ses)}'
                f' <span class="none-text">{_escape(record.fields.get("かかった時間(分)", ""))}分</span>'
                f' {self.v.file_link(record.file, "セッションシート")} {bugs}</div>')

    def node(self, record_id: str, top: bool = False) -> str:
        t = type_of(record_id)
        if t == "LTC":
            return self.leaf_ltc(record_id)
        if t == "SES":
            return self.leaf_session(record_id)
        # 利用の流れのテスト条件(要求に直接紐づくもの)は、仕様のあとに出す。
        # 要求の仕様にも紐づくテスト条件は、その仕様の下に出るので、要求の直下には出さない。
        children = sorted(self.kids(record_id, _TREE_CHILDREN[t]), key=lambda c: (type_of(c) != "SPEC", tm_core._id_key(c)))
        if t == "REQ":
            specs = {c for c in children if type_of(c) == "SPEC"}
            children = [c for c in children if type_of(c) == "SPEC" or not specs & self.p.records[c].links]
        bar, level = self.bar(self.counts(record_id))
        extra = self.coverage_items(record_id) if t == "COND" else ""
        inner = "".join(self.node(c) for c in children)
        if t == "HTC" and record_id in self.unimplemented:
            entry = self.p.unimplemented.get(record_id)
            reason = entry.reason if entry else self.p.records[record_id].fields.get("状態", "") or "理由の記録が無い"
            inner += f'<div class="leaf none-text">未実装: {self.v.text(reason)}</div>'
        inner = inner or '<div class="leaf none-text">この下にテストが無い</div>'
        anchor = f' id="tree-{record_id}"' if top else ""
        return (f'<details class="lv-{t}"{anchor} data-id="{record_id}"><summary class="{level}">{self.label(record_id)}'
                f'{bar}{extra}</summary><div class="kids">{inner}</div></details>')


def _trace_tree(v: View, m: dict) -> str:
    tree = _Tree(v)
    legend = "".join(f'<span><i class="{cls}"></i>{name}</span>' for name, cls in [
        ("Pass", "pass"), ("Fail", "fail"), ("ブロック", "block"), ("未実行・未探索", "notrun"),
        ("未実装", "unimpl"), ("探索的テスト済み", "explored")])
    req = "".join(tree.node(r["id"], top=True) for r in m["requirements"])
    risk = "".join(tree.node(r["id"], top=True) for r in m["risks"])
    return (
        '<h2 id="trace">要求とリスクのカバレッジ(トレーサビリティ)</h2>'
        "<p class=\"muted\">行をクリックすると、紐づく下の成果物が開く(要求 → 仕様 → テスト条件 → テストケース・テストチャーター → 結果・証跡・欠陥レポート)。"
        "左の線は、赤 = Fail か修正されていない不具合がある、黄 = 実行していないものがある、緑 = すべて実行して Pass。"
        "「実行 x/y」= 実行したもの(Pass + Fail + 探索したテストチャーター) ÷ (ローレベルテストケース + 未実装のハイレベルテストケース + テストチャーター)。"
        "テスト条件の「カバレッジアイテム」は、テスト設計で出したパターンのうち、実装したテストケースで通るものの数。"
        "リスクは、リスクに直接紐づくテスト条件のテストを数え、リスクレベルの高い順に並べる。</p>"
        f'<div class="legend">{legend}</div>'
        '<div class="tabs">'
        '<input type="radio" name="trace-tab" id="tab-req" checked><label for="tab-req">要求からたどる</label>'
        '<input type="radio" name="trace-tab" id="tab-risk"><label for="tab-risk">リスクからたどる</label>'
        f'<div class="pane tree" id="req-coverage">{req}</div>'
        f'<div class="pane tree" id="risk-coverage">{risk}</div></div>'
    )


def _charter_time_table(v: View, rows: list[dict]) -> str:
    body = [[v.ref(r["id"]), f"{r['minutes']:g}", str(r["timebox"]) if r["timebox"] is not None else "-",
             _badge("達した" if r["reached"] else "達していない"), v.refs(r["sessions"], False) if r["sessions"] else "なし"]
            for r in rows]
    return (_table(["テストチャーター", "セッションの時間(分)", "時間枠(分)", "判定", "セッション"], body,
                   ["time-" + r["id"] for r in rows]) if rows else "<p>ありません。</p>")


def _coverage_table(v: View, rows: list[dict], label: str) -> str:
    headers = [label, "テスト条件"] + COUNT_HEADERS
    body = []
    for row in rows:
        cells = [v.ref(row["id"]), str(row["conditions"]), str(row["testcases"]), str(row["Pass"]), str(row["Fail"]),
                 str(row["ブロック"]), str(row["未実行"]), str(row["未実装"]), str(row["sessions"]), str(row["bugs"]),
                 _badge(row["state"])]
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
    # 写しには成果物だけを入れる(視認性アップで作ったページは入れない)
    generated = ["html", SUMMARY_DIR, tm_core.REPORT_DIR, REPORT_PAGE] + [page_name(s) for s in VIEW_STAGES]
    shutil.copytree(project.root, snapshot, ignore=shutil.ignore_patterns(*generated))
    shutil.copyfile(judgment_path, out / JUDGMENT_FILE)

    hrefs = _hrefs(index_page=REPORT_PAGE)
    v = View(project, id_href=IDS_PAGE, file_base="snapshot/")
    m = tm_core.metrics(project)
    t = m["testcases"]
    errors, warnings = tm_core.check(project)

    not_run_rows = [[v.ref(r["id"]), _badge(r["status"]), v.text(r["reason"])] for r in m["not_run"]]
    not_run_rows += [[v.ref(r["id"]), _badge("未実装"), v.text(r["reason"])] for r in m["unimplemented"]]
    question_rows = [[v.ref(q["id"], False), _escape(q["stage"]), v.text(q["question"]),
                      v.text(q["observed"]) + _observed_evidence(v, q["observed"])] for q in m["open_questions"]]
    rollback = project.root / "戻し記録.md"
    rollback_html = md_to_html(rollback.read_text(encoding="utf-8-sig"), v.known, v.id_href) if rollback.is_file() else "<p>記録はありません。</p>"

    empty = '<p class="muted">記載なし</p>'
    written = "".join(
        f"<h2>{_escape(title)}</h2>{md_to_html(body, v.known, v.id_href) if body.strip() else empty}"
        for title, body in sections.items() if title not in ("終了条件の判定", "足りないこと")
    )
    # 判定: 最初に開くタブ。やるべきことをやったかと、問題点
    judge = (
        _first_view(v, m, judgments, sections.get("足りないこと", ""))
        + f'<div class="note" id="details">作成日時: {timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[8:10]}:{timestamp[10:12]}。'
        f'使ったテストラン: {_escape(", ".join(m["runs"]) or "なし")}。'
        "数字はすべて、このレポートを作った時点の成果物(snapshot フォルダ)から数え直したもの。"
        "同じテストケースを何回か実行したときは、いちばん新しいテストランの結果を数えている。"
        f"実行率 {t['execution_rate']}% = 実行した {t['executed']} 件(Pass + Fail) ÷ ローレベルテストケース {t['total']} 件"
        f"(未実装の {t['未実装']} 件は分母に入っていない)。</div>"
    )
    # まとめのタブには、テスト実行のページの中身に加えて、仕様のカバレッジとチャーターの時間を出す
    summary_extra = (
        '<h2 id="spec-coverage">仕様のカバレッジ</h2><p class="muted">仕様ごとに、その仕様を直接確かめるテスト条件のテストを数える。</p>'
        + _coverage_table(v, m["specs"], "仕様")
        + '<h2 id="charter-time">テストチャーターごとのセッションの時間</h2>'
        "<p class=\"muted\">セッションシートの「かかった時間(分)」(中断を除いた時間)の合計を、テストチャーターの時間枠と比べる。</p>"
        + _charter_time_table(v, m["charters"])
    )
    # 判定の記録: 判定.md に書いたこと、実行していないもの、未回答の質問、戻し記録、トレーサビリティの確認
    record = (
        written
        + '<h2 id="not-run">実行していないテストケース(未実行・ブロック・未実装)</h2>'
        + (_table(["テストケース", "状態", "理由"], not_run_rows) if not_run_rows else "<p>ありません。</p>")
        + '<h2 id="questions">未回答の質問</h2>'
        + (_table(["ID", "工程", "質問", "実機の動き"], question_rows) if question_rows else "<p>ありません。</p>")
        + "<h2>「後からわかったことの戻し方」の記録</h2>" + rollback_html
        + "<h2>トレーサビリティ</h2>"
        f"<p>確認の結果: エラー {len(errors)} 件、警告 {len(warnings)} 件。"
        f'<a href="{IDS_PAGE}">ID索引</a>から、どの成果物でも上流(要求の側)と下流(テスト結果・証跡・欠陥レポートの側)の両方にたどれる。'
        "工程ごとの追跡表は上のメニューから開ける。</p>"
        + ("<ul>" + "".join(f"<li class=\"missing\">{_escape(e)}</li>" for e in errors) + "</ul>" if errors else "")
    )
    body = _tabs("rp-tab", [("rp-judge", "判定", judge)] + _execution_panes(v, m, summary_extra)
                 + [("rp-record", "判定の記録", record)])
    page = _page("テストレポート", body, current="index", hrefs=hrefs, index_label="テストレポート")
    (out / REPORT_PAGE).write_text(page, encoding="utf-8")
    (out / IDS_PAGE).write_text(
        render_ids(project, file_base="snapshot/", hrefs=hrefs, index_label="テストレポート"), encoding="utf-8")
    for stage in VIEW_STAGES:
        (out / page_name(stage)).write_text(
            render_stage(project, stage, file_base="snapshot/", hrefs=hrefs, index_label="テストレポート"),
            encoding="utf-8")
    write_report_entries(project)
    summary = project.root / SUMMARY_DIR
    if summary.is_dir():  # テストレポートの工程では視認性アップをしないので、目次のレポートへのリンクをここで更新する
        (summary / INDEX_PAGE).write_text(_render_index(project), encoding="utf-8")
    return out
