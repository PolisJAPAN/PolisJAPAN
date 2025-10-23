# csv_loader.py
from __future__ import annotations
import httpx
from typing import Any, Iterable, List, Tuple, Dict, Optional

class CSV():
    """
    CSV文字列のパースおよび、オブジェクト配列からのCSV文字列生成を行うユーティリティクラス。
    """

    @classmethod
    def _split_line_for_guess(cls, line: str, d: str) -> List[str]:
        """
        区切り文字自動判定用の簡易スプリット（1行分）。

        クォートの厳密性は不要という前提で、推定のためだけに使用する。
        JS版の `splitLine` 相当の挙動を模す。

        Args:
            line (str): 対象行（1行分）の文字列。
            d (str): 試行する区切り文字（`,` / `\\t` / `;` など）。

        Returns:
            List[str]: 推定に用いる簡易分割結果。
        """
        arr, cur, in_q = [], "", False
        i, n = 0, len(line)
        while i < n:
            c = line[i]
            if c == '"':
                if in_q and i + 1 < n and line[i + 1] == '"':
                    cur += '"'
                    i += 1
                else:
                    in_q = not in_q
            elif not in_q and c == d:
                arr.append(cur)
                cur = ""
            else:
                cur += c
            i += 1
        arr.append(cur)
        return arr

    @classmethod
    def _analyze_csv(cls, text: str, delimiter: str = "auto") -> Tuple[List[List[str]], List[str], str]:
        """
        CSVテキストを低レベルに解析し、行データとヘッダー、使用区切り文字を返す。

        仕様:
            - 改行の正規化（`\\r\\n`/`\\r` -> `\\n`）
            - 区切り自動判定（1行目を対象。候補: `,` / `\\t` / `;`）
            - クォート（`"`）内の改行・区切り文字・二重引用符(`""`)に対応
            - BOM除去（ヘッダー先頭の `\\ufeff` を除去）
            - 行ごとの列数をヘッダー列数に合わせる（不足は `''` でパディング、超過は切り捨て）
            - 空白行（全フィールド空白）は除去

        Args:
            text (str): 解析対象のCSVテキスト。
            delimiter (str): 区切り文字。`"auto"` の場合は自動推定。

        Returns:
            Tuple[List[List[str]], List[str], str]:
                - 正規化済みデータ行（ヘッダー行除く）
                - ヘッダー配列
                - 使用された区切り文字
        """
        # 改行を正規化
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 区切り文字の自動判定（1行目のみ）
        if delimiter == "auto":
            lines = text.split("\n")
            first_line = next((ln for ln in lines if ln.strip() != ""), "")
            candidates = [",", "\t", ";"]
            best_d, best_count = ",", 0
            for d in candidates:
                count = len(cls._split_line_for_guess(first_line, d))
                if count > best_count:
                    best_d, best_count = d, count
            delimiter = best_d

        rows: List[List[str]] = []
        row: List[str] = []
        field = ""
        in_quotes = False

        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if in_quotes:
                if ch == '"':
                    # 連続する二重引用符はエスケープ
                    if i + 1 < n and text[i + 1] == '"':
                        field += '"'
                        i += 1
                    else:
                        in_quotes = False
                else:
                    field += ch
            else:
                if ch == '"':
                    in_quotes = True
                elif ch == delimiter:
                    row.append(field)
                    field = ""
                elif ch == "\n":
                    row.append(field)
                    rows.append(row)
                    row = []
                    field = ""
                else:
                    field += ch
            i += 1

        # 最終フィールド/行
        row.append(field)
        rows.append(row)

        # ヘッダー抽出（BOM除去 + trim）
        headers = rows.pop(0) if rows else []
        headers = [h.lstrip("\ufeff").strip() for h in headers]

        # 列数整形（不足は ''、超過は切り捨て）
        cols = len(headers)
        normalized: List[List[str]] = []
        for r in rows:
            # 空白行判定（全フィールドが空または空白のみ）
            if all(((v or "").strip() == "") for v in r):
                continue
            
            arr = r[:cols]
            while len(arr) < cols:
                arr.append("")
            normalized.append(arr)

        return normalized, headers, delimiter

    @classmethod
    def rows_to_objects(cls, rows: List[List[str]], headers: List[str]) -> List[Dict[str, str]]:
        """
        行配列とヘッダー配列から、`[{header: value, ...}, ...]` 形式のオブジェクト配列へ変換する。

        Args:
            rows (List[List[str]]): データ行の二次元配列。
            headers (List[str]): ヘッダー名の配列。

        Returns:
            List[Dict[str, str]]: ヘッダー名をキーに持つレコード辞書のリスト。
        """
        out: List[Dict[str, str]] = []
        for r in rows:
            obj = {h: (r[i] if i < len(r) and r[i] is not None else "") for i, h in enumerate(headers)}
            out.append(obj)
        return out
    
    @classmethod
    def parse_csv(cls, text: str, delimiter: str = "auto") -> List[Dict[str, str]]:
        """
        CSVテキストを解析してオブジェクト配列へ変換する高レベル関数。

        内部で `_analyze_csv()` により区切り判定と正規化を行い、`rows_to_objects()` で
        ヘッダー付きのレコード配列に変換する。

        Args:
            text (str): 解析対象のCSVテキスト。
            delimiter (str): 区切り文字。`"auto"` の場合は `,` / `\\t` / `;` を自動判定。

        Returns:
            List[Dict[str, str]]: 解析結果のレコード辞書リスト。
        """
        rows, headers_list, used_d = cls._analyze_csv(text, delimiter)
        result = cls.rows_to_objects(rows, headers_list)
        return result
    
    # ==============================
    # オブジェクト配列 -> CSV文字列
    # ==============================
    @classmethod
    def to_csv(
        cls,
        records: Iterable[dict],
        headers: list[str],
        *,
        delimiter: str = ",",
        include_bom: bool = True,
        newline: str = "\n",
    ) -> str:
        """
        ヘッダー順に `records` をCSV化して文字列で返す。

        仕様:
            - 値は `str` へ変換（`None` は空文字）
            - 値に 区切り/改行/二重引用符/前後空白 が含まれる場合はクォート
            - 二重引用符は `""` にエスケープ
            - 不足キーは `''`、余分なキーは無視
            - `include_bom=True` の場合、先頭に UTF-8 BOM (`\\ufeff`) を付与

        Args:
            records (Iterable[dict]): 出力対象のレコード群。各要素は辞書。
            headers (list[str]): 出力順を規定するヘッダー名の配列。
            delimiter (str, optional): 区切り文字。既定は `','`。
            include_bom (bool, optional): 先頭に UTF-8 BOM を付与するか。既定は True。
            newline (str, optional): 行区切り文字。既定は `\\n`。

        Returns:
            str: 生成されたCSV文字列。
        """

        def _to_str(v: Any) -> str:
            # None -> '', それ以外は str 化
            if v is None:
                return ""
            return str(v)

        def _needs_quote(s: str) -> bool:
            # 区切り/改行/二重引用符/前後空白がある場合はクォート
            return (
                delimiter in s
                or "\n" in s
                or "\r" in s
                or '"' in s
                or s != s.strip()
            )

        def _quote(s: str) -> str:
            s_escaped = s.replace('"', '""')
            return f'"{s_escaped}"'

        def _emit_row(cells: list[str]) -> str:
            out = []
            for cell in cells:
                cell = _to_str(cell)
                out.append(_quote(cell) if _needs_quote(cell) else cell)
            return delimiter.join(out)

        # 1) ヘッダー行
        header_line = _emit_row(headers)

        # 2) データ行（不足キーは ''）
        lines = [header_line]
        for rec in records:
            row = [rec.get(h, "") for h in headers]
            lines.append(_emit_row(row))

        body = newline.join(lines)
        return ("\ufeff" + body) if include_bom else body
