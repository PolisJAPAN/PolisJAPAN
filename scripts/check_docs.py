#!/usr/bin/env python3
"""ドキュメントと実装のずれを検出する。

使い方:
  python3 scripts/check_docs.py                      静的チェックのみ
  python3 scripts/check_docs.py --staged [--message-file F]
                                                     静的チェック + ステージ済み変更の連動チェック
  python3 scripts/check_docs.py --range A..B         静的チェック + コミット範囲の連動チェック

静的チェック: 文書が現在のコードと食い違っていないか（索引・パス・API・セレクタ・設定値）。
連動チェック: コードを変えたのに、対応する文書を変えていない変更を止める。
設定は docs/docmap.json。標準ライブラリだけで動く。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = "docs/docmap.json"
WAIVER = re.compile(r"^Docs:\s*変更不要\s*[（(]\s*\S.*[）)]\s*$", re.M)
WAIVER_EXAMPLE = "Docs: 変更不要（理由をここに書く）"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout


def nfc(text: str) -> str:
    # macOS はファイル名を分解形で返すことがあるため、比較前に合成形へそろえる
    return unicodedata.normalize("NFC", text)


def read(path: str) -> str:
    return nfc((ROOT / path).read_text(encoding="utf-8"))


def tracked_files() -> list[str]:
    # 追跡中と未追跡（ignore 対象を除く）のうち、作業ツリーにあるもの
    out = git("ls-files", "--cached", "--others", "--exclude-standard")
    return sorted({nfc(f) for f in out.splitlines() if (ROOT / f).exists()})


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


# ---------- 静的チェック ----------

def check_index(cfg: dict, files: list[str]) -> list[str]:
    """docs/ の全文書が索引に載っていて、索引に載っている文書が実在すること。"""
    index_path = cfg["index"]
    index = read(index_path)
    errors = []
    docs = [f for f in files if f.startswith("docs/") and f not in (index_path, CONFIG_PATH)]
    for doc in docs:
        if Path(doc).name not in index:
            errors.append(f"{index_path}: 索引に {doc} が載っていない")
    allowed = cfg.get("docs_allowed", [])
    for doc in docs:
        if not matches(doc, allowed):
            errors.append(
                f"{doc}: docs/ に置けるのは現状を記述する文書だけ"
                f"（{CONFIG_PATH} の docs_allowed に無い。計画書・検討書は置かない）"
            )
    return errors


PATH_TOKEN = re.compile(r"`((?:Client|Server|Infra|docs|scripts|\.github|\.githooks)/[^`\s]*)`")
MD_LINK = re.compile(r"\]\((?!https?://|#|mailto:)([^)\s#]+)")


def check_paths(cfg: dict, files: list[str]) -> list[str]:
    """文書中のリポジトリ内パスが実在すること。"""
    fileset = set(files)
    dirs = {str(p) for f in files for p in Path(f).parents}
    ignore = cfg.get("path_ignore", [])
    errors = []

    def exists(path: str) -> bool:
        path = path.rstrip("/")
        if any(c in path for c in "*?["):
            return any(fnmatch.fnmatch(f, path) or fnmatch.fnmatch(f, path + "/*") for f in files)
        return path in fileset or path in dirs

    for doc in doc_files(cfg, files):
        text = read(doc)
        for n, line in enumerate(text.splitlines(), 1):
            for token in PATH_TOKEN.findall(line):
                path = re.sub(r"(:\d+(-\d+)?)$", "", token).rstrip(".,、。")
                if any(c in path for c in "<>{}…") or matches(path, ignore):
                    continue
                if not exists(path):
                    errors.append(f"{doc}:{n}: 存在しないパス `{token}`")
            for link in MD_LINK.findall(line):
                resolved = (ROOT / Path(doc).parent / link).resolve()
                try:
                    rel = resolved.relative_to(ROOT).as_posix()
                except ValueError:
                    continue
                if not exists(rel) and not matches(rel, ignore):
                    errors.append(f"{doc}:{n}: リンク切れ ({link})")
    return errors


def doc_files(cfg: dict, files: list[str]) -> list[str]:
    return [f for f in files if matches(f, cfg["doc_globs"]) and f.endswith(".md")]


def check_routes(cfg: dict) -> list[str]:
    """マウントされている API と、仕様書の API 一覧が一致すること。"""
    rc = cfg.get("routes")
    if not rc:
        return []
    main = read(rc["main"])
    mounted = re.findall(r"include_router\((\w+)\.router\)", main)
    actual: set[str] = set()
    prefixes: set[str] = set()
    for name in mounted:
        src = read(f"{rc['routers_dir']}/{name}.py")
        m = re.search(r"APIRouter\([^)]*?prefix\s*=\s*[\"']([^\"']+)[\"']", src, re.S)
        prefix = m.group(1) if m else ""
        prefixes.add(prefix)
        for route in re.findall(r"@router\.(?:get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']", src):
            actual.add(prefix + route)
    doc = read(rc["doc"])
    documented = {
        p for p in re.findall(r"`(/[a-z_]+/[a-z_]+)`", doc)
        if any(p.startswith(pre + "/") for pre in prefixes)
    } - set(rc.get("ignore", []))
    errors = [f"{rc['doc']}: API `{p}` が実装にあるのに一覧に無い" for p in sorted(actual - documented)]
    errors += [f"{rc['doc']}: API `{p}` は実装に無い（マウントされていない）" for p in sorted(documented - actual)]
    return errors


def check_facts(cfg: dict) -> list[str]:
    """コード上の値（バージョン・上限・間隔・アラーム名など）が文書に書かれていること。"""
    errors = []
    for fact in cfg.get("facts", []):
        values = re.findall(fact["pattern"], read(fact["source"]))
        if not values:
            errors.append(f"{CONFIG_PATH}: 「{fact['label']}」が {fact['source']} から取り出せない（pattern を直す）")
            continue
        for value in dict.fromkeys(values):
            expect = fact.get("expect", "{0}").format(value)
            for doc in fact["docs"]:
                if expect not in read(doc):
                    errors.append(
                        f"{doc}: 「{fact['label']}」の現在値 “{expect}” が書かれていない（出典 {fact['source']}）"
                    )
    return errors


SELECTOR_SPAN = re.compile(r"`([^`]*[#.][A-Za-z][^`]*)`")
SELECTOR_NAME = re.compile(r"(?<![\w\-/\"'=])([#.])([A-Za-z][\w-]*)")


def check_selectors(cfg: dict, files: list[str]) -> list[str]:
    """画面仕様・テストケースに書いたセレクタの id / class がクライアントのコードに存在すること。"""
    sc = cfg.get("selectors")
    if not sc:
        return []
    ignore = set(sc.get("ignore", []))
    sources = [f for f in files if matches(f, sc["sources"]) and f.endswith((".html", ".js", ".css"))]
    corpus = "\n".join(read(f) for f in sources)
    words = set(re.findall(r"[A-Za-z][\w-]*", corpus))
    errors = []
    for doc in sc["docs"]:
        seen = set()
        for n, line in enumerate(read(doc).splitlines(), 1):
            for span in SELECTOR_SPAN.findall(line):
                if not re.match(r"^[#.\w\-\[\]=\"' >:()+~*,]+$", span) or "/" in span:
                    continue  # セレクタではない（ファイル名・コード片・文章など）
                if re.search(r"\.(js|html|css|scss|csv|md|py|yml|json|tf)\b", span):
                    continue
                bare = re.sub(r"\[[^\]]*\]", "", span)
                for sigil, name in SELECTOR_NAME.findall(bare):
                    key = sigil + name
                    if key in seen or key in ignore:
                        continue
                    seen.add(key)
                    if name not in words:
                        errors.append(f"{doc}:{n}: セレクタ `{key}` がクライアントのコードに見つからない")
    return errors


MERMAID_BLOCK = re.compile(r"^```mermaid\n(.*?)^```", re.S | re.M)
MERMAID_TYPES = ("flowchart", "graph", "sequenceDiagram", "stateDiagram-v2", "erDiagram", "classDiagram")


def check_mermaid(cfg: dict, files: list[str]) -> list[str]:
    """Mermaid の図が、GitHub で描画できない書き方になっていないこと（書き方の規則は docs/README.md）。"""
    errors = []
    for doc in doc_files(cfg, files):
        text = read(doc)
        for m in MERMAID_BLOCK.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            body = m.group(1)
            lines = [l.strip() for l in body.splitlines() if l.strip()]
            where = f"{doc}:{line_no}: Mermaid"
            if not lines or not lines[0].startswith(MERMAID_TYPES):
                errors.append(f"{where} の 1 行目が図の種類（{' / '.join(MERMAID_TYPES)}）ではない")
                continue
            if "`" in body or "#" in body:
                errors.append(f"{where} の中にバッククォートか # がある")
            if lines[0].startswith(("flowchart", "graph")):
                if sum(l.startswith("subgraph") for l in lines) != sum(l == "end" for l in lines):
                    errors.append(f"{where} の subgraph と end の数が合わない")
                if re.search(r"\b\w+(\[(?![\"(\[/])|\{(?![\"{]))", body):
                    errors.append(f"{where} にラベルを二重引用符で囲んでいないノードがある")
                if body.count('"') % 2:
                    errors.append(f"{where} の二重引用符の数が合わない")
    return errors


def static_checks(cfg: dict) -> list[str]:
    files = tracked_files()
    return (
        check_index(cfg, files)
        + check_paths(cfg, files)
        + check_routes(cfg)
        + check_facts(cfg)
        + check_selectors(cfg, files)
        + check_mermaid(cfg, files)
    )


# ---------- 連動チェック ----------

def check_coupling(cfg: dict, changed: list[str], messages: str) -> list[str]:
    """コードの変更に、対応する文書の変更が伴っていること。"""
    changed_set = set(changed)
    missing = []
    for rule in cfg["rules"]:
        hits = [
            f for f in changed
            if matches(f, rule["paths"]) and not matches(f, rule.get("exclude", []))
        ]
        if hits and not (changed_set & set(rule["docs"])):
            missing.append((rule, hits))
    if not missing or WAIVER.search(messages):
        return []
    errors = []
    for rule, hits in missing:
        shown = ", ".join(hits[:3]) + (f" ほか {len(hits) - 3} 件" if len(hits) > 3 else "")
        errors.append(
            f"「{rule['name']}」を変更したのに文書が更新されていない\n"
            f"    変更: {shown}\n"
            f"    更新する文書（該当するものを 1 つ以上）: {', '.join(rule['docs'])}"
        )
    errors.append(
        "文書に影響しない変更（リファクタリング等）なら、コミットメッセージに次の行を入れる:\n"
        f"    {WAIVER_EXAMPLE}"
    )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--message-file")
    ap.add_argument("--range")
    args = ap.parse_args()

    cfg = json.loads(read(CONFIG_PATH))
    required = [cfg["index"], *cfg["docs_allowed"], cfg.get("routes", {}).get("doc")]
    required += [d for r in cfg["rules"] for d in r["docs"]]
    required += [p for f in cfg.get("facts", []) for p in (f["source"], *f["docs"])]
    absent = sorted({p for p in required if p and not (ROOT / p).exists()})
    if absent:
        print(f"{CONFIG_PATH} が指しているファイルが無い: {', '.join(absent)}", file=sys.stderr)
        return 1
    errors = static_checks(cfg)

    if args.staged:
        changed = [nfc(f) for f in git("diff", "--cached", "--name-only").splitlines()]
        message = Path(args.message_file).read_text(encoding="utf-8") if args.message_file else ""
        errors += check_coupling(cfg, changed, message)
    elif args.range:
        changed = [nfc(f) for f in git("diff", "--name-only", args.range).splitlines()]
        messages = git("log", "--format=%B", args.range)
        errors += check_coupling(cfg, changed, messages)

    if errors:
        print("ドキュメントチェック: NG\n", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        print("\n運用ルールは docs/README.md を参照。", file=sys.stderr)
        return 1
    print("ドキュメントチェック: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
