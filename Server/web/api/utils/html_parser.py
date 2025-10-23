from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag


class HTMLParser:
    """
    HTMLのパースを行う静的ヘルパー。
    BeautifulSoupを毎回内部で生成し、インスタンス化不要で呼び出せる。
    """
    
    class parse_type():
        TEXT = "TEXT"
        LINK = "LINK"
        GROUP = "GROUP"
        
    # =========================
    # HTML 抽出（スコープ指定）
    # =========================
    @classmethod
    def get_scope_html(
        cls,
        html: str,
        scope_selector: Optional[str] = None,
        *,
        outer: bool = True,
        exclude_script : bool = False
    ) -> str:
        """
        HTML文字列から指定スコープの要素部分を抽出して返す。

        Args:
            html (str): 対象となるHTML文字列。
            scope_selector (Optional[str]): BeautifulSoupのCSSセレクタ形式で指定するスコープ要素。
            outer (bool): `True`の場合はouterHTML（要素自身を含む）。`False`の場合はinnerHTML（内部のみ）。
            exclude_script (bool): `True`の場合、scriptや不可視要素を除外して返す。

        Returns:
            str: 抽出されたHTML文字列。該当要素が見つからない場合は空文字列。
        """
        soup = BeautifulSoup(html, "html.parser")
        scope: Tag = soup.select_one(scope_selector) if scope_selector else soup
        
        if not scope:
            return ""
        
        if exclude_script:
            clone = BeautifulSoup(cls._to_outer_html(scope), "html.parser")
            cls._prune_non_visible(clone)
        
        return cls._to_outer_html(clone) if outer else cls._to_inner_html(clone)

    @classmethod
    def get_page_text_and_links(
        cls,
        html: str,
        base_url: Optional[str] = None,
        scope_selector: Optional[str] = None,
        *,
        inline_link: bool = True,
        inline_format: Optional[Callable[[str, str], str]] = None,
    ) -> Dict[str, object]:
        """
        HTML全体、または指定スコープ内のテキストおよびリンク一覧を抽出する。

        Args:
            html (str): 解析対象のHTML文字列。
            base_url (Optional[str]): 相対URLを絶対URLへ変換する際に用いる基準URL。
            scope_selector (Optional[str]): 対象範囲を限定するCSSセレクタ。未指定時は文書全体。
            inline_link (bool): Trueの場合、本文中の<a>をインライン形式 `[text](url)` に展開。
            inline_format (Optional[Callable[[str, str], str]]):
                リンクのインライン展開フォーマットをカスタムする関数 `(text, url) -> str`。

        Returns:
            Dict[str, object]: 以下のキーを持つ辞書。
                - "text" (str): 抽出テキスト（必要に応じてインライン展開済み）。
                - "links" (List[str]): 重複除去済みのリンクURL一覧。`base_url` 指定時は絶対URL化。
        """
        soup = BeautifulSoup(html, "html.parser")
        # セレクタ指定で選択範囲を取得
        scope: Tag = soup.select_one(scope_selector) if scope_selector else soup

        # 範囲が取得できなければ早期リターン
        if not scope:
            return {"text": "", "links": []}

        # 不可視ソースをサニタイズ
        cls._prune_non_visible(scope)
        
        # タグ構造として出力されるリンクをインライン化
        if inline_link:
            cls._expand_inline_links(scope, base_url, inline_format)

        # テキストを取得
        text = scope.get_text(separator="\n", strip=True)
        links = cls._extract_links(scope, base_url)
        return {"text": text, "links": links}

    @classmethod
    def get_single_item_by_schema(
        cls,
        html: str,
        item_selector: str,
        schema: Dict[str, Tuple[str, str]],
        *,
        base_url: Optional[str] = None,
        text_separator: str = "\n",
    ) -> dict:
        """
        指定セレクタに一致した最初の要素に対して、スキーマ定義に従い値を抽出して返す。

        Args:
            html (str): 解析対象のHTML文字列。
            item_selector (str): 対象要素を特定するCSSセレクタ（最初の1件を使用）。
            schema (Dict[str, Tuple[str, str]]): 抽出定義。`{出力キー: (抽出モード, サブセレクタ)}`。
            base_url (Optional[str]): 相対URLを絶対URLへ変換する際に用いる基準URL。
            text_separator (str): テキスト結合時の区切り文字。

        Returns:
            dict: スキーマのキーを持つ抽出結果の辞書。対象要素が見つからない場合は空辞書。
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # セレクタで内容を取得
        item = soup.select_one(item_selector)
        
        # 取得できなかった場合は空で返却
        if not item:
            return {}

        result = cls._get_content_by_schema(item, schema, base_url, text_separator)
            
        return result
    
    @classmethod
    def get_items_by_schema(
        cls,
        html: str,
        item_selector: str,
        schema: Dict[str, Tuple[str, str]],
        *,
        base_url: Optional[str] = None,
        text_separator: str = "\n",
    ) -> List[Dict[str, str]]:
        """
        HTMLから指定セレクタに一致する要素群を抽出し、スキーマ定義に基づいて構造化データを生成する。

        `item_selector` でマッチした各要素（item）に対し、`schema` で定義されたルールを適用して
        テキスト・リンクなどを抽出し、`dict` 形式のリストとして返す。

        Args:
            html (str): 処理対象のHTML文字列。
            item_selector (str): BeautifulSoup形式のCSSセレクタ。各「行」や「項目」を指す。
            schema (Dict[str, Tuple[str, str]]): 各フィールドの抽出ルールを定義するスキーマ辞書。
                - キー: 出力時のフィールド名。
                - 値: `(抽出モード, サブセレクタ)` のタプル。
                - 抽出モードは例として `"TEXT"`, `"LINK"`, `"HTML"` などを想定。
                - サブセレクタは各item内で相対的に指定されるCSSセレクタ。
            base_url (Optional[str]): 相対リンクを絶対URLに変換するためのベースURL。
            text_separator (str): 複数テキストノードを結合する際の区切り文字。デフォルトは改行。

        Returns:
            List[Dict[str, str]]: 各itemに対応する辞書のリスト。
                各辞書は `schema` のキーに対応する抽出結果を持つ。
        """
        soup = BeautifulSoup(html, "html.parser")
        # セレクタで内容を取得
        items = soup.select(item_selector)
        # 取得できなかった場合は空で返却
        if not items:
            return []

        results: List[Dict[str, str]] = []
        # 項目ごとに抽出
        for item in items:
            row: Dict[str, str] = {}
            row = cls._get_content_by_schema(item, schema, base_url, text_separator)
            results.append(row)
            
        return results


    # -------------------------
    # internal helpers
    # -------------------------
    @classmethod
    def _get_content_by_schema(cls, 
            scope_html,
            schema: Dict[str, Tuple[str, str]],
            base_url: Optional[str] = None,
            text_separator: str = "\n",
        ) -> dict:
        """
        スキーマ定義に従ってHTMLスコープからテキスト・リンク・グループ情報を抽出し、
        dict形式で返す。
        
        各キーに対して (モード, サブセレクタ) が定義されており、モードに応じて抽出方法が分岐する。
        - TEXT: テキスト抽出（script等は除外）
        - LINK: href属性または内部aタグからリンク抽出
        - GROUP: 指定範囲内の複数テキスト要素を結合して抽出

        Args:
            scope_html: 抽出対象のBeautifulSoupタグオブジェクト。
            schema (Dict[str, Tuple[str, str]]): 抽出ルールを定義したスキーマ辞書。
            base_url (Optional[str]): 相対リンクを絶対URLに変換する際のベースURL。
            text_separator (str): テキスト結合時の区切り文字。

        Returns:
            dict: 抽出結果をキー名ごとに格納した辞書。
        """
        
        result: Dict[str, str] = {}
            
        # スキーマで指定された要素を１つずつ探しにいく
        for key, (mode, sub_selector) in schema.items():

            # -------------------------------
            # 特殊セレクタ: ###SELF###
            # -------------------------------
            if sub_selector == "###SELF###":
                scope = scope_html
            else:
                scope = cls._scoped_select_one(scope_html, sub_selector)

            # -------------------------------
            # 共通の存在チェック
            # -------------------------------
            if not scope:
                result[key] = ""
                continue

            # -------------------------------
            # 種別ごとの分岐
            # -------------------------------
            if mode == cls.parse_type.TEXT:
                clone = BeautifulSoup(str(scope), "html.parser")
                cls._prune_non_visible(clone)
                result[key] = clone.get_text(separator=text_separator, strip=True)

            elif mode == cls.parse_type.LINK:
                # 自身 or 子孫の最初の <a href>
                href = scope.get("href")
                if not href:
                    a = scope.select_one("a[href]")
                    href = a.get("href") if a else None
                url = urljoin(base_url, href) if (base_url and href) else href
                result[key] = url or ""

            elif mode == cls.parse_type.GROUP:
                targets = cls._scoped_select_all(scope_html, sub_selector) if sub_selector else [scope_html]
                if not targets:
                    result[key] = ""
                    continue
                chunks: List[str] = []
                for t in targets:
                    clone = BeautifulSoup(str(t), "html.parser")
                    cls._prune_non_visible(clone)
                    txt = clone.get_text(separator=text_separator, strip=True)
                    if txt:
                        chunks.append(txt)
                result[key] = text_separator.join(chunks)

            else:
                raise ValueError(f"Unsupported mode: {mode} (key='{key}')")
            
        return result
    
    
    @classmethod
    def _to_outer_html(cls, el: Tag) -> str:
        """
        タグ自身を含む outerHTML 文字列を返す。

        Args:
            el (Tag): 対象となる BeautifulSoup タグオブジェクト。

        Returns:
            str: 要素自身を含む HTML 文字列（outerHTML 相当）。
        """
        return str(el)

    @classmethod
    def _to_inner_html(cls, el: Tag) -> str:
        """
        タグ直下の子ノードを結合し、innerHTML 文字列として返す。

        Args:
            el (Tag): 対象となる BeautifulSoup タグオブジェクト。

        Returns:
            str: 要素の内側（子ノード）の HTML 文字列（innerHTML 相当）。
        """
        return "".join(str(c) for c in el.contents)
    
    @classmethod
    def _scoped_select_one(cls, root: Tag, sel: Optional[str]) -> Optional[Tag]:
        """
        セレクタにスコープ補正 (:scope) を付与して、最初に一致する要素を取得する。

        BeautifulSoup が :scope 非対応の場合は、直下子要素を対象とするフォールバックを行う。

        Args:
            root (Tag): 検索の基点となるタグ。
            sel (Optional[str]): CSS セレクタ文字列。相対コンビネータ（>, +, ~）にも対応。

        Returns:
            Optional[Tag]: 最初に一致したタグオブジェクト。該当なしの場合は None。
        """
        if not sel:
            return root
        s = sel.strip()
        needs_scope = s[:1] in {">", "+", "~"}
        scoped = f":scope {s}" if needs_scope else s
        try:
            return root.select_one(scoped)
        except Exception:
            # フォールバック: '>' のみサポート
            if needs_scope and s.startswith(">"):
                child_sel = s[1:].strip()  # 例: '> .title' -> '.title'
                if not child_sel:
                    # ':scope > ' だけの指定は直下の最初の要素を返す想定にするならここで返す
                    for child in root.find_all(recursive=False):
                        return child
                    return None
                for child in root.find_all(recursive=False):
                    hit = child.select_one(child_sel)
                    if hit:
                        return hit
            raise

    @classmethod
    def _scoped_select_all(cls, root: Tag, sel: Optional[str]) -> List[Tag]:
        """
        セレクタにスコープ補正 (:scope) を付与して、複数の要素を取得する。

        BeautifulSoup が :scope 非対応の場合は、直下子要素を対象とするフォールバックを行う。

        Args:
            root (Tag): 検索の基点となるタグ。
            sel (Optional[str]): CSS セレクタ文字列。相対コンビネータ（>, +, ~）にも対応。

        Returns:
            List[Tag]: 一致したタグオブジェクトのリスト。該当なしの場合は空リスト。
        """
        if not sel:
            return [root]
        s = sel.strip()
        needs_scope = s[:1] in {">", "+", "~"}
        scoped = f":scope {s}" if needs_scope else s
        try:
            return root.select(scoped)
        except Exception:
            if needs_scope and s.startswith(">"):
                child_sel = s[1:].strip()
                out: List[Tag] = []
                if not child_sel:
                    return list(root.find_all(recursive=False))
                for child in root.find_all(recursive=False):
                    hits = child.select(child_sel)
                    if hits:
                        out.extend(hits)
                return out
            raise

    
    @classmethod
    def _extract_links(cls, scope: Tag, base_url: Optional[str]) -> List[str]:
        """
        指定範囲内の a[href] タグを抽出し、重複を除去してリンクURLのリストを返す。

        Args:
            scope (Tag): 抽出対象の BeautifulSoup タグオブジェクト。
            base_url (Optional[str]): 相対URLを絶対URLに変換するためのベースURL。

        Returns:
            List[str]: 抽出されたリンクURLのリスト。重複は削除済み。
        """
        hrefs: List[str] = []
        seen = set()
        for a in scope.select("a[href]"):
            href = a.get("href")
            if not href:
                continue
            url = urljoin(base_url, href) if base_url else href
            if url not in seen:
                seen.add(url)
                hrefs.append(url)
        return hrefs

    @classmethod
    def _expand_inline_links(
        cls,
        scope: Tag,
        base_url: Optional[str],
        inline_format: Optional[Callable[[str, str], str]] = None,
    ) -> None:
        """
        aタグを本文内にインライン展開し、[text](URL) 形式に変換する。

        Args:
            scope (Tag): 対象となる BeautifulSoup タグオブジェクト。
            base_url (Optional[str]): 相対URLを絶対URLに変換するためのベースURL。
            inline_format (Optional[Callable[[str, str], str]]):
                カスタムフォーマット関数。text, url を引数に取る。
                未指定の場合は "[text](url)" 形式を使用。

        Returns:
            None
        """
        fmt = inline_format or (lambda text, url: f"[{text}]({url})")
        for a in scope.select("a[href]"):
            href = a.get("href")
            if not href:
                continue
            url = urljoin(base_url, href) if base_url else href

            # aテキストが空の場合のフォールバック（画像リンク等）
            link_text = a.get_text(strip=True)
            if not link_text:
                # img alt などを利用、それも無ければURLをそのまま
                img = a.find("img", alt=True)
                link_text = (img["alt"].strip() if img and img.get("alt") else url)

            a.replace_with(fmt(link_text, url))

    @classmethod
    def _prune_non_visible(cls, scope: Tag) -> None:
        """
        指定範囲内の非表示要素（script, style, noscript）を削除する。

        Args:
            scope (Tag): 対象となる BeautifulSoup タグオブジェクト。

        Returns:
            None
        """
        for tag in scope.select("script, style, noscript"):
            tag.decompose()
