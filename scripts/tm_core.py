"""成果物(Markdown)を読み取り、トレーサビリティの確認と集計を行う。標準ライブラリだけで動く。

成果物の決まりは shared/conventions.md に書いてある。このファイルはその決まりを機械的に確かめる側。
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ROOT = "テスト成果物"

# IDの頭の文字 → 成果物の種類。並び順は上流から下流。
TYPES = {
    "REQ": "要求",
    "SPEC": "仕様",
    "Q": "質問",
    "RISK": "リスク",
    "EXIT": "テスト終了条件",
    "TA": "テストアプローチ",
    "FT": "フィーチャー",
    "COND": "テスト条件",
    "CI": "カバレッジアイテム",
    "HTC": "ハイレベルテストケース",
    "CH": "テストチャーター",
    "LTC": "ローレベルテストケース",
    "TD": "テストデータ",
    "PROC": "テスト手順",
    "SCR": "E2E自動テストスクリプト",
    "SES": "テストセッションシート",
    "BUG": "欠陥レポート",
    "RB": "戻し記録",
}

# (キー, 工程の名前, フォルダ)
STAGES = [
    ("requirements", "要求仕様整理", "01_要求仕様"),
    ("risk", "リスク分析", "02_リスク分析"),
    ("plan", "テスト計画", "03_テスト計画"),
    ("analysis", "テスト分析", "04_テスト分析"),
    ("design", "テスト設計", "05_テスト設計"),
    ("implementation", "テスト実装", "06_テスト実装"),
    ("e2e", "E2E自動テストスクリプト作成", "07_E2E自動テストスクリプト"),
    ("execution", "テスト実行", "08_テスト実行"),
    ("report", "テストレポート", "09_テストレポート"),
]
STAGE_KEYS = [s[0] for s in STAGES]
STAGE_NAMES = {s[0]: s[1] for s in STAGES}
STAGE_DIRS = {s[0]: s[2] for s in STAGES}
EXECUTION_DIR = STAGE_DIRS["execution"]
REPORT_DIR = STAGE_DIRS["report"]

# 子の種類 → たどってよい親の種類(トレーサビリティの紐づけ)
HIER_PARENTS = {
    "SPEC": ["REQ"],
    "RISK": ["SPEC"],
    "TA": ["SPEC", "RISK"],
    "FT": ["SPEC"],
    "COND": ["FT", "TA", "SPEC", "RISK", "REQ"],
    "CI": ["COND"],
    "HTC": ["COND", "CI"],
    "CH": ["COND"],
    "LTC": ["HTC"],
    "PROC": ["LTC"],
    "SCR": ["LTC"],
    "SES": ["CH"],
    "BUG": ["LTC", "SES"],
}
# 必ず要る紐づけ。内側のリストは「このどれか1つ」、外側は「すべて」。
REQUIRED = {
    "SPEC": [["REQ"]],
    "TA": [["SPEC", "RISK"]],
    "FT": [["SPEC"]],
    "COND": [["FT"], ["TA"]],
    "CI": [["COND"]],
    "HTC": [["COND"]],
    "CH": [["COND"]],
    "LTC": [["HTC"]],
    "PROC": [["LTC"]],
    "SCR": [["LTC"]],
    "SES": [["CH"]],
    "BUG": [["LTC", "SES"]],
}
# リスク・テストアプローチ・フィーチャーは複数の仕様にまたがるので、ここを経由して上下にたどると
# 関係のない要求や仕様までカバーしたこと(影響を受けること)になる。カバレッジも影響範囲も経由しない。
# テスト条件は、確かめる仕様・要求・リスクを自分の列に直接書くので、経由しなくてもたどれる。
NO_PASS_THROUGH = {"RISK", "TA", "FT"}

# カバレッジアイテムの表のこの列に理由があれば、テストケースで通していなくても警告しない(カバレッジには数えない)
CI_SKIP_REASON = "通さない理由"
# 欠陥レポートのこの列に要求・仕様のIDがあれば、その要求・仕様の不具合として数える。
# 「スコープ外」なら、どの要求・リスクの不具合にも数えない。空なら、見つけたテストからたどる。
BUG_SCOPE = "要求・仕様ID"
OUT_OF_SCOPE = "スコープ外"

RESULTS = ["Pass", "Fail", "ブロック", "未実行"]
SEVERITIES = ["高", "中", "低"]
BUG_STATES = ["未修正", "修正済み", "クローズ", "却下"]
BUG_CLOSED = {"クローズ", "却下"}
QUESTION_ANSWERED = ("回答済み", "反映済み")

ID_RE = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(sorted(TYPES, key=len, reverse=True)) + r")-(\d+)(?![0-9])"
)
_SEPARATOR_CELL = re.compile(r"^:?-+:?$")
# 成果物の名前に使わない列(誰が・いつ・どれだけ、を書く列)
_NOT_TITLE = {"実施者", "日時", "開始日時", "終了日時", "見つけた日時", "かかった時間(分)"}
# テストベースの写し: 変わったところを比べるために置く、テストベースそのもの。成果物ではない
TEST_BASE_COPY_DIR = "テストベースの写し"
_EXCLUDED_DIRS = {"html", "結果まとめ", REPORT_DIR, "snapshot", TEST_BASE_COPY_DIR}
# テストランのフォルダの実行情報。「テスト対象の版: …」の行から、その回にテストした版を読む
RUN_INFO_FILE = "実行情報.md"
_VERSION_LINE = re.compile(r"^\s*(?:[-*]\s*)?テスト対象の版\s*[:：]\s*(.+?)\s*$", re.M)


def find_ids(text: str) -> list[str]:
    """文章の中のIDを、出てきた順に重複なしで返す。"""
    found: list[str] = []
    for match in ID_RE.finditer(text or ""):
        if match.group(0) not in found:
            found.append(match.group(0))
    return found


def type_of(record_id: str) -> str:
    return record_id.split("-")[0]


def risk_class(level: int) -> str:
    if level >= 15:
        return "高"
    if level >= 8:
        return "中"
    return "低"


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    line: int


def _split_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    cells, current, i = [], "", 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] == "|":
            current += "|"
            i += 2
            continue
        if text[i] == "|":
            cells.append(current.strip())
            current = ""
        else:
            current += text[i]
        i += 1
    if current.strip():
        cells.append(current.strip())
    return cells


def _is_separator(line: str) -> bool:
    cells = _split_row(line)
    return bool(cells) and all(_SEPARATOR_CELL.match(c) for c in cells)


def parse_tables(text: str) -> list[Table]:
    """Markdownの表を読み取る。コードブロックの中は読まない。"""
    lines = text.splitlines()
    tables: list[Table] = []
    in_code = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("```"):
            in_code = not in_code
        elif not in_code and stripped.startswith("|") and i + 1 < len(lines) and _is_separator(lines[i + 1]):
            headers = _split_row(lines[i])
            rows, j = [], i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                row = _split_row(lines[j])
                row += [""] * (len(headers) - len(row))
                rows.append(row[: len(headers)])
                j += 1
            tables.append(Table(headers, rows, i + 1))
            i = j
            continue
        i += 1
    return tables


@dataclass
class Record:
    id: str
    type: str
    fields: dict[str, str]
    file: str
    line: int
    links: set[str] = field(default_factory=set)      # 「〜ID」の列に書かれたID(紐づけ)
    mentions: set[str] = field(default_factory=set)   # それ以外の列の文章に出てくるID

    @property
    def title(self) -> str:
        """その成果物の名前。紐づけの列(見出しが ID で終わる列)と、実施者・日時・時間の列は飛ばし、最初の中身の列を使う。"""
        for key, value in self.fields.items():
            name = key.strip()
            if not name.endswith("ID") and name not in _NOT_TITLE and value:
                return value
        for key, value in self.fields.items():  # 紐づけの列しか無いときは、その値を使う
            if key != "ID" and value:
                return value
        return ""


@dataclass
class Result:
    ltc: str
    result: str
    method: str
    evidence: list[str]
    bugs: list[str]
    memo: str
    run: str
    file: str


@dataclass
class Unimplemented:
    id: str
    reason: str
    file: str
    fields: dict[str, str]


class Project:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.records: dict[str, Record] = {}
        self.attrs: dict[str, list[dict[str, str]]] = {}
        self.results: list[Result] = []
        self.unimplemented: dict[str, Unimplemented] = {}
        self.load_issues: list[tuple[str, str]] = []  # (ファイル, 読み取りで見つけたエラー)
        self.references: list[tuple[str, str, str]] = []  # (ファイル, 書いてある場所, 参照先ID)
        self._children: dict[str, list[str]] | None = None

    @property
    def load_errors(self) -> list[str]:
        return [message for _, message in self.load_issues]

    def of_type(self, type_key: str) -> list[Record]:
        return sorted((r for r in self.records.values() if r.type == type_key), key=lambda r: _id_key(r.id))

    def parents(self, record_id: str) -> list[str]:
        record = self.records.get(record_id)
        if record is None:
            return []
        allowed = HIER_PARENTS.get(record.type, [])
        return sorted((l for l in record.links if type_of(l) in allowed and l in self.records), key=_id_key)

    def children(self, record_id: str) -> list[str]:
        if self._children is None:
            index: dict[str, list[str]] = {}
            for record in self.records.values():
                for parent in self.parents(record.id):
                    index.setdefault(parent, []).append(record.id)
            self._children = {key: sorted(value, key=_id_key) for key, value in index.items()}
        return self._children.get(record_id, [])

    def ancestors(self, record_id: str) -> set[str]:
        return self._walk(record_id, self.parents)

    def descendants(self, record_id: str) -> set[str]:
        """下流をたどる。起点はどの種類でも広げるが、途中の NO_PASS_THROUGH の種類からは先へ進まない。"""
        return self._walk(record_id, self.children)

    def _walk(self, start: str, step) -> set[str]:
        seen: set[str] = set()
        stack = [start]
        while stack:
            current = stack.pop()
            for nxt in step(current):
                if nxt in seen or nxt == start:
                    continue
                seen.add(nxt)
                if type_of(nxt) not in NO_PASS_THROUGH:
                    stack.append(nxt)
        return seen

    def runs(self) -> list[str]:
        return sorted({r.run for r in self.results} | {
            p.name for p in (self.root / EXECUTION_DIR).glob("RUN-*") if p.is_dir()
        })

    def run_versions(self) -> dict[str, str | None]:
        """テストランごとに、実行情報.md の「テスト対象の版:」に書かれた版。書かれていなければ None。"""
        versions: dict[str, str | None] = {}
        for run in self.runs():
            info = self.root / EXECUTION_DIR / run / RUN_INFO_FILE
            match = _VERSION_LINE.search(info.read_text(encoding="utf-8-sig")) if info.is_file() else None
            versions[run] = match.group(1).strip() if match else None
        return versions

    def final_results(self) -> dict[str, Result]:
        """テストケースごとに、いちばん新しいテストランの結果を返す。"""
        final: dict[str, Result] = {}
        for result in sorted(self.results, key=lambda r: r.run):
            final[result.ltc] = result
        return final


def _id_key(record_id: str):
    prefix, _, number = record_id.partition("-")
    order = list(TYPES).index(prefix) if prefix in TYPES else len(TYPES)
    return (order, int(number) if number.isdigit() else 0)


def _split_evidence(cell: str) -> list[str]:
    parts = re.split(r"<br\s*/?>|,|、", cell or "")
    return [p.strip() for p in parts if p.strip()]


def load_project(root: Path | str) -> Project:
    root = Path(root)
    project = Project(root)
    if not root.is_dir():
        project.load_issues.append(("", f"成果物のフォルダが無い: {root}"))
        return project
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part in _EXCLUDED_DIRS for part in rel.parts):
            continue
        rel_text = rel.as_posix()
        for table in parse_tables(path.read_text(encoding="utf-8-sig")):
            _load_table(project, table, rel, rel_text)
    return project


def _load_table(project: Project, table: Table, rel: Path, rel_text: str) -> None:
    first = table.headers[0] if table.headers else ""
    in_run = len(rel.parts) >= 3 and rel.parts[0] == EXECUTION_DIR and rel.parts[1].startswith("RUN-")
    for offset, row in enumerate(table.rows):
        fields = dict(zip(table.headers, row))
        cell = row[0].strip() if row else ""
        line = table.line + 2 + offset
        if first == "ID":
            if not cell:
                continue
            if not ID_RE.fullmatch(cell):
                project.load_issues.append((rel_text, f"{rel_text}:{line}: IDの形が正しくない「{cell}」"))
                continue
            if cell in project.records:
                project.load_issues.append(
                    (rel_text, f"{cell}: IDが重複している ({project.records[cell].file} と {rel_text})")
                )
                continue
            # 紐づけにするのは「〜ID」の列だけ。備考などの文章に出てくるIDまで紐づけにすると、
            # 関係のない要求やリスクをカバーしたことになってしまう。
            pairs = list(zip(table.headers[1:], row[1:]))
            links = set(find_ids(" ".join(v for h, v in pairs if h.strip().endswith("ID")))) - {cell}
            mentions = set(find_ids(" ".join(v for h, v in pairs if not h.strip().endswith("ID")))) - {cell} - links
            project.records[cell] = Record(cell, type_of(cell), fields, rel_text, line, links, mentions)
            continue
        # 定義ではない表(テスト結果、未実装、テストスイートなど)。「〜ID」の列に書かれたIDは、
        # 定義されているものを指しているはずなので、あとで確かめられるように控えておく。
        for header, value in zip(table.headers, row):
            if header.strip().endswith("ID"):
                for referenced in find_ids(value):
                    project.references.append((rel_text, f"{rel_text}:{line}", referenced))
        ids = find_ids(cell)
        if not first.endswith("ID") or len(ids) != 1:
            continue
        target = ids[0]
        if in_run and first == "ローレベルテストケースID" and "結果" in fields:
            bugs = [b for b in find_ids(fields.get("欠陥レポートID", "")) if type_of(b) == "BUG"]
            project.results.append(Result(
                ltc=target,
                result=fields.get("結果", "").strip(),
                method=fields.get("実施方法", ""),
                evidence=_split_evidence(fields.get("証跡", "")),
                bugs=bugs,
                memo=fields.get("メモ", ""),
                run=rel.parts[1],
                file=rel_text,
            ))
        elif rel.name == "未実装.md":
            reason = fields.get("理由", row[1] if len(row) > 1 else "")
            project.unimplemented[target] = Unimplemented(target, reason, rel_text, fields)
        else:
            project.attrs.setdefault(target, []).append(fields)


def detect_stage(project: Project) -> str:
    """成果物がある、いちばん後ろの工程。"""
    present = {r.type for r in project.records.values()}
    if project.results or "SES" in present:
        return "execution"
    for stage, types in [
        ("e2e", {"SCR"}), ("implementation", {"LTC"}), ("design", {"HTC", "CH"}),
        ("analysis", {"FT", "COND"}), ("plan", {"TA"}), ("risk", {"RISK"}),
    ]:
        if present & types:
            return stage
    return "requirements"


def _labels(types: list[str]) -> str:
    return "・".join(TYPES[t] for t in types)


def _to_int(text: str) -> int | None:
    try:
        return int(str(text).strip())
    except ValueError:
        return None


def check(project: Project, stage: str | None = None) -> tuple[list[str], list[str]]:
    """トレーサビリティと決まりを確かめる。(エラー, 警告) を返す。

    エラーは必ず直すもの(紐づけの抜け・切れ、決まりに合わない値)。
    警告はレビューで理由を確かめるもの(下流がまだ無い、文章の中に定義されていないIDがある)。
    """
    issues, warnings = _check(project, stage)
    return [message for _, message in issues], warnings


def check_scoped(project: Project, stage: str) -> tuple[list[str], list[str], list[str]]:
    """(その工程までのエラー, 下流の工程に残っているエラー, 警告) を返す。

    前の工程に戻って成果物を変えると、下流はまだ古いIDに紐づいたまま残る。
    それはその工程のエージェントが直すものではないので、分けて出す。
    """
    index = STAGE_KEYS.index(stage)
    issues, warnings = _check(project, stage)
    own = [message for file, message in issues if _stage_index_of(file) <= index]
    downstream = [message for file, message in issues if _stage_index_of(file) > index]
    return own, downstream, warnings


def _stage_index_of(file: str) -> int:
    """そのファイルが、どの工程の成果物か。質問表など工程のフォルダの外にあるものは 0。"""
    folder = file.split("/")[0]
    for index, (_, _, stage_dir) in enumerate(STAGES):
        if folder == stage_dir:
            return index
    return 0


def _check(project: Project, stage: str | None) -> tuple[list[tuple[str, str]], list[str]]:
    issues = list(project.load_issues)
    warnings: list[str] = []
    stage = stage or detect_stage(project)
    index = STAGE_KEYS.index(stage)
    records = project.records

    def error(file: str, message: str) -> None:
        issues.append((file, message))

    for record in sorted(records.values(), key=lambda r: _id_key(r.id)):
        if record.type == "RB":
            continue  # 戻し記録には、消したIDも書くので確かめない
        for link in sorted(record.links, key=_id_key):
            if link not in records:
                error(record.file, f"{record.id}: 定義されていない {link} に紐づいている ({record.file})")
        for group in REQUIRED.get(record.type, []):
            if not any(type_of(link) in group for link in record.links):
                error(record.file, f"{record.id}: {_labels(group)}への紐づけが無い ({record.file})")
        for mention in sorted(record.mentions, key=_id_key):
            if mention not in records:
                warnings.append(f"{record.id}: 文章の中に、定義されていない {mention} が書かれている ({record.file})")
    for file, where, target in project.references:
        if target not in records:
            error(file, f"{where}: 定義されていない {target} が書かれている")

    for risk in project.of_type("RISK"):
        impact, chance = _to_int(risk.fields.get("影響度", "")), _to_int(risk.fields.get("発生確率", ""))
        if impact is None or chance is None or not (1 <= impact <= 5 and 1 <= chance <= 5):
            error(risk.file, f"{risk.id}: 影響度と発生確率は 1〜5 の数字で書く ({risk.file})")
            continue
        level = _to_int(risk.fields.get("リスクレベル", ""))
        if level != impact * chance:
            error(risk.file,
                  f"{risk.id}: リスクレベルは 影響度×発生確率 = {impact * chance} のはず"
                  f" (書かれているのは {risk.fields.get('リスクレベル', '')})")
        expected = risk_class(impact * chance)
        if risk.fields.get("区分", "").strip() != expected:
            error(risk.file,
                  f"{risk.id}: 区分は「{expected}」のはず"
                  f" (リスクレベル {impact * chance}、書かれているのは「{risk.fields.get('区分', '')}」)")
    for result in project.results:
        if result.result not in RESULTS:
            error(result.file,
                  f"{result.ltc}: テスト結果「{result.result}」は使えない"
                  f" ({' / '.join(RESULTS)} のどれかにする) ({result.file})")
    for bug in project.of_type("BUG"):
        if bug.fields.get("重要度", "").strip() not in SEVERITIES:
            error(bug.file, f"{bug.id}: 重要度は {' / '.join(SEVERITIES)} のどれかにする ({bug.file})")
        if bug.fields.get("状態", "").strip() not in BUG_STATES:
            error(bug.file, f"{bug.id}: 状態は {' / '.join(BUG_STATES)} のどれかにする ({bug.file})")

    def lacks(record: Record, types: list[str]) -> bool:
        return not any(type_of(c) in types for c in project.children(record.id))

    def warn(type_key: str, children: list[str], message: str, skip=lambda r: False) -> None:
        for record in project.of_type(type_key):
            if lacks(record, children) and not skip(record):
                warnings.append(f"{record.id}: {message} ({record.title[:30]})")

    asked = {link for q in project.of_type("Q") for link in q.links}
    warn("REQ", ["SPEC"], "仕様が無い要求。質問表に記載が要る", skip=lambda r: r.id in asked)
    if index >= STAGE_KEYS.index("plan"):
        warn("RISK", ["TA"], "テストアプローチが無い高いリスク", skip=lambda r: r.fields.get("区分", "").strip() != "高")
        # 仕様にテストアプローチが直接無くても、仕様のリスクにあればよい
        warn("SPEC", ["TA"], "テストアプローチが無い仕様",
             skip=lambda r: any(type_of(c) == "RISK" and not lacks(records[c], ["TA"]) for c in project.children(r.id)))
    if index >= STAGE_KEYS.index("analysis"):
        warn("SPEC", ["FT"], "フィーチャーが無い仕様")
        warn("TA", ["COND"], "テスト条件が無いテストアプローチ")
        warn("FT", ["COND"], "テスト条件が無いフィーチャー")
        warn("RISK", ["COND"], "テスト条件が無いリスク")
    if index >= STAGE_KEYS.index("design"):
        warn("COND", ["HTC", "CH"], "テストケースもテストチャーターも無いテスト条件")
        warn("CI", ["HTC"], "テストケースで通していないカバレッジアイテム。通さないなら「通さない理由」に書く",
             skip=lambda r: bool(r.fields.get(CI_SKIP_REASON, "").strip()))
    if index >= STAGE_KEYS.index("implementation"):
        warn("HTC", ["LTC"], "ローレベルテストケースが無く、未実装にも記録されていない",
             skip=lambda r: r.id in project.unimplemented)
        warn("LTC", ["PROC"], "テスト手順が無い手動テスト",
             skip=lambda r: "手動" not in r.fields.get("実施方法", ""))
    if index >= STAGE_KEYS.index("e2e"):
        warn("LTC", ["SCR"], "スクリプトが無く、未実装にも記録されていないE2E自動テスト",
             skip=lambda r: "E2E" not in r.fields.get("実施方法", "") or r.id in project.unimplemented)
    if index >= STAGE_KEYS.index("execution"):
        final = project.final_results()
        for ltc in project.of_type("LTC"):
            if ltc.id not in final:
                warnings.append(f"{ltc.id}: テスト結果が無い ({ltc.title[:30]})")
        warn("CH", ["SES"], "セッションを行っていないテストチャーター")
    return issues, warnings


def impact(project: Project, ids: list[str]) -> dict[str, list[str]]:
    """変えたIDの下流にあるIDを、種類ごとに返す。

    質問のIDを渡したときは、その質問の関連IDに書かれた成果物と、
    状態や備考に質問のIDを書いて回答を待っている成果物、それらの下流を返す。
    リスク・テストアプローチ・フィーチャーは影響を受けるものとして出すが、そこから先へは広げない
    (そこを変えたときは、その工程をやり直したあとで、変えたIDを渡して出し直す)。
    """
    affected: set[str] = set()
    for record_id in ids:
        starts = [record_id]
        if type_of(record_id) == "Q" and record_id in project.records:
            starts = [link for link in project.records[record_id].links if link in project.records]
            starts += [r.id for r in project.records.values()
                       if r.type not in ("Q", "RB") and record_id in (r.links | r.mentions)]
            affected |= set(starts)
        for start in starts:
            affected |= project.descendants(start)
    affected -= set(ids)
    grouped: dict[str, list[str]] = {}
    for record_id in sorted(affected, key=_id_key):
        grouped.setdefault(type_of(record_id), []).append(record_id)
    return grouped


def _status(final: dict[str, Result], ltc_id: str) -> str:
    result = final.get(ltc_id)
    return result.result if result and result.result in RESULTS else "未実行"


def unimplemented_htcs(project: Project) -> list[str]:
    """ローレベルテストケースになっていないハイレベルテストケース。"""
    return [h.id for h in project.of_type("HTC") if not any(type_of(c) == "LTC" for c in project.children(h.id))]


def open_bugs(project: Project) -> list[Record]:
    bugs = [b for b in project.of_type("BUG") if b.fields.get("状態", "").strip() not in BUG_CLOSED]
    order = {s: i for i, s in enumerate(SEVERITIES)}
    return sorted(bugs, key=lambda b: (order.get(b.fields.get("重要度", "").strip(), len(order)), _id_key(b.id)))


def bug_scope(bug: Record) -> set[str] | None:
    """欠陥レポートが影響する要求・仕様を、欠陥レポートに書かれているときだけ返す。

    None は「書かれていない(見つけたテストからたどる)」、空の集合は「スコープ外」。
    """
    text = bug.fields.get(BUG_SCOPE, "").strip()
    if OUT_OF_SCOPE in text:
        return set()
    ids = {i for i in find_ids(text) if type_of(i) in ("REQ", "SPEC")}
    return ids or None


def bug_affects(project: Project, bug_id: str, record_id: str) -> bool:
    """その欠陥レポートを、要求・仕様・リスクなど record_id の不具合として数えるか。"""
    scope = bug_scope(project.records[bug_id])
    if scope is None:
        return bug_id in project.descendants(record_id)
    related = {record_id} | project.ancestors(record_id) | project.descendants(record_id)
    return bool(scope & related)


def coverage(project: Project, record_id: str) -> dict:
    """要求やリスクなど1件について、下流のテストがどれだけ実行されたかを数える。"""
    final = project.final_results()
    down = {d for d in project.descendants(record_id) if type_of(d) != "BUG"}
    down |= {b.id for b in project.of_type("BUG") if bug_affects(project, b.id, record_id)}
    not_implemented = set(unimplemented_htcs(project))
    ltcs = [d for d in down if type_of(d) == "LTC"]
    charters = [d for d in down if type_of(d) == "CH"]
    row = {status: 0 for status in RESULTS}
    for ltc in ltcs:
        row[_status(final, ltc)] += 1
    open_ids = {b.id for b in open_bugs(project)}
    row.update({
        "id": record_id,
        "title": project.records[record_id].title,
        "conditions": sum(1 for d in down if type_of(d) == "COND") + (1 if type_of(record_id) == "COND" else 0),
        "testcases": len(ltcs),
        "未実装": sum(1 for d in down if d in not_implemented),
        "charters": len(charters),
        "charters_done": sum(1 for c in charters if any(type_of(x) == "SES" for x in project.children(c))),
        "sessions": sum(1 for d in down if type_of(d) == "SES"),
        "bugs": sum(1 for d in down if type_of(d) == "BUG"),
        "open_bugs": sum(1 for d in down if d in open_ids),
    })
    total = len(ltcs) + row["未実装"] + len(charters)
    executed = row["Pass"] + row["Fail"] + row["charters_done"]
    # 状態は Fail が先に立つので、Fail があっても実行していないテストが残っていることは、ここで別に数える
    row["remaining"] = total - executed
    if executed == 0:
        row["state"] = "まったくテストしていない"
    elif row["Fail"] or row["open_bugs"]:
        row["state"] = "実行したがFailあり"
    elif executed == total:
        row["state"] = "すべて実行してすべてPass"
    else:
        row["state"] = "一部しか実行していない"
    return row


def _to_float(text: str) -> float | None:
    try:
        return float(str(text).strip())
    except ValueError:
        return None


def charter_time(project: Project) -> list[dict]:
    """テストチャーターごとに、セッションの時間(中断を除いて書かれたもの)の合計が時間枠に達したか。"""
    rows = []
    for charter in project.of_type("CH"):
        sessions = [c for c in project.children(charter.id) if type_of(c) == "SES"]
        minutes = sum(_to_float(project.records[s].fields.get("かかった時間(分)", "")) or 0.0 for s in sessions)
        timebox = _to_int(charter.fields.get("時間枠(分)", ""))
        rows.append({"id": charter.id, "timebox": timebox, "minutes": minutes, "sessions": sessions,
                     "reached": timebox is not None and minutes >= timebox})
    return rows


def result_versions(project: Project) -> dict:
    """数えている結果(Pass・Fail)のうち、今の版(版が書かれたいちばん新しいテストランの版)で確かめていないもの。

    一部だけ実行し直すと、実行し直さなかったテストケースは前の版の結果のまま数えられる。それを見分けるため。
    どのテストランにも版が書かれていなければ、何も出さない。
    """
    versions = project.run_versions()
    known = [run for run in sorted(versions) if versions[run]]
    if not known:
        return {"current": None, "current_run": None, "older": [], "unknown": []}
    current_run = known[-1]
    current = versions[current_run]
    older, unknown = [], []
    final = project.final_results()
    for ltc in sorted(final, key=_id_key):
        result = final[ltc]
        if result.result not in ("Pass", "Fail"):
            continue
        version = versions.get(result.run)
        if version is None:
            unknown.append({"id": ltc, "run": result.run})
        elif version != current:
            older.append({"id": ltc, "run": result.run, "version": version})
    return {"current": current, "current_run": current_run, "older": older, "unknown": unknown}


def metrics(project: Project) -> dict:
    """テストレポートに載せる数字を、成果物から数え直す。"""
    final = project.final_results()
    ltcs = project.of_type("LTC")
    testcases = {status: 0 for status in RESULTS}
    by_method: dict[str, dict[str, int]] = {}
    for ltc in ltcs:
        status = _status(final, ltc.id)
        testcases[status] += 1
        method = ltc.fields.get("実施方法", "").strip() or "(実施方法なし)"
        by_method.setdefault(method, {s: 0 for s in RESULTS})[status] += 1
    executed = testcases["Pass"] + testcases["Fail"]
    not_implemented = unimplemented_htcs(project)
    testcases.update({
        "total": len(ltcs),
        "executed": executed,
        "execution_rate": round(100 * executed / len(ltcs), 1) if ltcs else 0.0,
        "未実装": len(not_implemented),
    })

    risks = []
    for risk in project.of_type("RISK"):
        row = coverage(project, risk.id)
        impact_value, chance = _to_int(risk.fields.get("影響度", "")), _to_int(risk.fields.get("発生確率", ""))
        row["level"] = (impact_value or 0) * (chance or 0)
        row["class"] = risk_class(row["level"])
        risks.append(row)
    risks.sort(key=lambda r: (-r["level"], _id_key(r["id"])))

    not_run = []
    for ltc in ltcs:
        status = _status(final, ltc.id)
        if status in ("未実行", "ブロック"):
            result = final.get(ltc.id)
            not_run.append({"id": ltc.id, "title": ltc.title, "status": status,
                            "reason": result.memo if result else "テスト結果が無い"})
    unimplemented = []
    for htc_id in not_implemented:
        record = project.records[htc_id]
        entry = project.unimplemented.get(htc_id)
        reason = entry.reason if entry else record.fields.get("状態", "") or "理由の記録が無い"
        unimplemented.append({"id": htc_id, "title": record.title, "reason": reason})

    return {
        "testcases": testcases,
        "by_method": by_method,
        "requirements": [coverage(project, r.id) for r in project.of_type("REQ")],
        "specs": [coverage(project, s.id) for s in project.of_type("SPEC")],
        "charters": charter_time(project),
        "risks": risks,
        "open_bugs": [
            {"id": b.id, "title": b.title, "severity": b.fields.get("重要度", ""), "state": b.fields.get("状態", ""),
             "links": sorted(b.links, key=_id_key)}
            for b in open_bugs(project)
        ],
        "open_questions": [
            {"id": q.id, "stage": q.fields.get("工程", ""), "question": q.fields.get("質問", ""),
             "observed": q.fields.get("実機の動き", "").strip()}  # 実機確認スキルが書く、答える人のための情報
            for q in project.of_type("Q")
            if not q.fields.get("状態", "").strip().startswith(QUESTION_ANSWERED)
        ],
        "not_run": not_run,
        "unimplemented": unimplemented,
        "exit_criteria": [
            {"id": e.id, "text": e.fields.get("終了条件", e.title), "measure": e.fields.get("測り方", "")}
            for e in project.of_type("EXIT")
        ],
        "runs": project.runs(),
        "versions": result_versions(project),
        "sessions": [s.id for s in project.of_type("SES")],
    }


# ---- E2E自動テストの実行結果の取り込み ----

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def parse_playwright_report(data: dict) -> dict[str, dict]:
    """PlaywrightのJSONレポートを、ローレベルテストケースのidごとの結果にする。

    スクリプト全体が成功したかどうかは見ない。idが付いたテスト1件ずつの結果だけを使う。
    """
    collected: dict[str, dict] = {}

    def visit(suite: dict, inherited: list[str]) -> None:
        own = [i for i in find_ids(suite.get("title", "")) if type_of(i) == "LTC"] or inherited
        for spec in suite.get("specs", []):
            ids = [i for i in find_ids(spec.get("title", "")) if type_of(i) == "LTC"] or own
            for ltc in ids:
                entry = collected.setdefault(ltc, {"statuses": [], "evidence": [], "errors": [], "failed_in": []})
                for test in spec.get("tests", []):
                    entry["statuses"].append(test.get("status", ""))
                    if test.get("status") in ("unexpected", "flaky") and test.get("projectName"):
                        entry["failed_in"].append(test["projectName"])
                    for result in test.get("results", []):
                        if result.get("status") == "passed":
                            continue
                        entry["evidence"] += [a["path"] for a in result.get("attachments", []) if a.get("path")]
                        message = (result.get("error") or {}).get("message", "")
                        if message:
                            entry["errors"].append(_ANSI.sub("", message).strip().splitlines()[0][:120])
        for child in suite.get("suites", []):
            visit(child, own)

    for suite in data.get("suites", []):
        visit(suite, [])

    parsed: dict[str, dict] = {}
    for ltc, entry in collected.items():
        statuses = entry["statuses"]
        memo = "; ".join(dict.fromkeys(entry["errors"]))
        if entry["failed_in"]:
            memo = f"失敗したブラウザ: {', '.join(dict.fromkeys(entry['failed_in']))}。" + memo
        if "unexpected" in statuses:
            result = "Fail"
        elif "flaky" in statuses:
            result, memo = "Fail", "不安定(失敗したあと再実行で成功した)。" + memo
        elif "expected" in statuses:
            result = "Pass"
        else:
            result, memo = "未実行", "スキップされた、またはテストが実行されなかった"
        parsed[ltc] = {"result": result, "evidence": list(dict.fromkeys(entry["evidence"])), "memo": memo}
    return parsed


def write_e2e_results(root: Path | str, run_id: str, parsed: dict[str, dict], expected: list[str],
                      report: Path | str | None = None) -> Path:
    """idごとの結果を、テストランのフォルダに表として書く。証跡のファイルがあればコピーする。

    report(PlaywrightのJSONレポート)を渡すと、idつきの結果のもとなので、どの行の証跡にも書く。
    テストランのフォルダの外にあれば `証跡/` にコピーする(次の実行で消えないように)。
    """
    run_dir = Path(root) / EXECUTION_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    report_evidence = []
    if report is not None and Path(report).is_file():
        report_path = Path(report).resolve()
        if not report_path.is_relative_to(run_dir.resolve()):
            target = run_dir / "証跡" / report_path.name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(report_path, target)
            report_path = target.resolve()
        report_evidence = [report_path.relative_to(run_dir.resolve()).as_posix()]
    lines = [
        "# テスト結果(E2E自動テスト)",
        "",
        "E2E自動テストスクリプトの実行結果を、ローレベルテストケースのidで対応づけたもの。",
        "",
        "| ローレベルテストケースID | 実施方法 | 結果 | 証跡 | 欠陥レポートID | メモ |",
        "|---|---|---|---|---|---|",
    ]
    for ltc in sorted(set(expected) | set(parsed), key=_id_key):
        entry = parsed.get(ltc) or {
            "result": "未実行", "evidence": [],
            "memo": "実行結果にこのidのテストが無い(スクリプト全体の成否からは結果を付けない)",
        }
        evidence = []
        for number, source in enumerate(entry["evidence"], 1):
            source_path = Path(source)
            if source_path.is_file():
                target = run_dir / "証跡" / f"{ltc}_{number}_{source_path.name}"
                target.parent.mkdir(exist_ok=True)
                shutil.copyfile(source_path, target)
                evidence.append(target.relative_to(run_dir).as_posix())
            else:
                evidence.append(source)
        if ltc in parsed:
            evidence += report_evidence
        memo = entry["memo"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {ltc} | E2E自動テスト | {entry['result']} | {'<br>'.join(evidence)} | | {memo} |")
    path = run_dir / "テスト結果_E2E自動.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
