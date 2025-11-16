from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from typing import List, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
        ElementClickInterceptedException, 
        ElementNotInteractableException, 
        JavascriptException, 
        StaleElementReferenceException, 
        TimeoutException,
    )
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from api.utils.time import Time

@dataclass
class PageInfo:
    """
    ページ情報を保持するデータクラス。

    Attributes:
        url (str): ページのURL。
        title (str): ページタイトル。
        h1 (Optional[str]): 最初の <h1> タグのテキスト。
        links (List[str]): ページ内のリンク一覧（hrefのリスト）。
    """
    
    url: str
    title: str
    h1: Optional[str]
    links: List[str]


class WebLoaderChrome:
    """
    Selenium + Chrome WebDriverを利用してページを取得・操作するユーティリティクラス。

    - ヘッドレスモード対応（`--headless=new`）
    - BeautifulSoupによるHTML解析補助を実装
    - スクリーンショット、クリック、フォーム送信、入力操作などを提供

    Attributes:
        _driver (webdriver.Chrome): 内部で利用するSelenium Chromeドライバインスタンス。
    """
    
    _driver : webdriver.Chrome
    """WebDriverインスタンス"""

    def __init__(self, headless: bool = True, page_load_timeout: int = 30):
        """
        WebLoaderChrome のインスタンスを初期化。

        Args:
            headless (bool): ヘッドレスモードで起動するかどうか。
            page_load_timeout (int): ページ読み込みのタイムアウト秒数。
        """
        self._driver = self._create_driver(headless=headless, page_load_timeout=page_load_timeout)

    def close(self) -> None:
        """
        ドライバを終了してリソースを解放する。
        """
        
        if getattr(self, "_driver", None):
            try:
                self._driver.quit()
            finally:
                self._driver = None
    
    def restart(self) -> None:
        """
        現在のブラウザを完全に終了して再起動する。
        """
        
        self.close()
        self._driver = self._create_driver()

    def __enter__(self) -> "WebLoaderChrome":
        """with構文で利用するためのエントリポイント。"""
        return self

    def __exit__(self, exc_type, exc, tb):
        """with構文の終了時にドライバを閉じる。"""
        self.close()

    # -------------------------
    # internal
    # -------------------------
    def _create_driver(self, headless: bool = True, page_load_timeout: int = 30) -> webdriver.Chrome:
        """
        Chrome WebDriverを作成して返す。

        Args:
            headless (bool): ヘッドレスモードを使用するかどうか。
            page_load_timeout (int): ページロードのタイムアウト秒数。

        Returns:
            webdriver.Chrome: 新しく作成されたドライバインスタンス。
        """
        
        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15")
        opts.add_argument("--window-size=1920,1080")

        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=opts)
        driver.set_page_load_timeout(page_load_timeout)
        driver.implicitly_wait(0)
        return driver

    # -------------------------
    # public
    # -------------------------
    def get_page_info(self, url: str, wait_sec: int = 15) -> PageInfo:
        """
        指定URLのページを開き、タイトル・H1・リンク情報を取得する。

        Args:
            url (str): 対象のURL。
            wait_sec (int): body要素が出現するまでの最大待機秒数。

        Returns:
            PageInfo: ページ情報（タイトル・h1・リンク一覧）。
        """
        drv = self._driver
        
        drv.get(url)

        WebDriverWait(drv, wait_sec).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        html = drv.page_source
        soup = BeautifulSoup(html, "html.parser")

        title = (soup.title.string.strip() if soup.title and soup.title.string else "")
        h1_tag = soup.find("h1")
        h1 = h1_tag.get_text(strip=True) if h1_tag else None
        links = [a.get("href") for a in soup.select("a[href]")]
        links = [str(l) for l in links if l]

        return PageInfo(url=url, title=title, h1=h1, links=links)
    
    # -------------------------
    # public
    # -------------------------
    def get_driver(self, url: str, wait_sec: int = 15) -> webdriver.Chrome:
        """
        指定URLを開いてWebDriverインスタンスを返す。

        Args:
            url (str): 対象URL。
            wait_sec (int): body要素の出現までの最大待機秒数。

        Returns:
            webdriver.Chrome: 操作可能なWebDriverインスタンス。
        """
        drv = self._driver
        drv.get(url)

        WebDriverWait(drv, wait_sec).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        return drv
    
    def save_screenshot(self, key: str) -> None:
        """
        現在のページのスクリーンショットをファイルとして保存する。

        Args:
            key (str): ファイル名の識別キー。
        """
        filename = f"screenshot_{key}_{Time.to_filename_format(Time.now())}.png"
        self._driver.save_screenshot(f"/app/screenshot/{filename}")
        
    def wait_for(self, by: str, value: str, timeout: int = 15, visible: bool = True):
        """
        要素が出現するまで待機して返す。

        Args:
            by (str): 検索方法（例: By.CSS_SELECTOR）。
            value (str): 検索セレクタ。
            timeout (int): 最大待機秒数。
            visible (bool): Trueなら可視状態、Falseなら存在のみ確認。

        Returns:
            WebElement: 見つかった要素。
        """
        cond = EC.visibility_of_element_located if visible else EC.presence_of_element_located
        return WebDriverWait(self._driver, timeout).until(cond((by, value)))
    
    def exists_wait(self, by: str, selector: str, timeout: int = 5) -> bool:
        """
        指定要素がtimeout秒以内に出現すればTrue、出なければFalseを返す。

        Args:
            by (str): 検索方法。
            selector (str): CSSセレクタまたはXPath。
            timeout (int): 最大待機秒数。

        Returns:
            bool: 要素が存在すればTrue、存在しなければFalse。
        """
        try:
            WebDriverWait(self._driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return True
        except TimeoutException:
            return False
        
    def wait_for_text(self, by: str, selector: str, expected_text: str, timeout: int = 15, exact: bool = True, strip: bool = True) -> bool:
        """
        特定の要素のテキストが指定値になるまで待機する。

        Args:
            by (str): 検索方法。
            selector (str): セレクタ。
            expected_text (str): 期待されるテキスト。
            timeout (int): 最大待機秒数。
            exact (bool): 完全一致（True）または部分一致（False）。
            strip (bool): 比較時に空白を除去するか。

        Returns:
            bool: 一致すればTrue、タイムアウト時はFalse。
        """
        drv = self._driver

        def _text_matches(driver):
            try:
                el = driver.find_element(by, selector)
                text = el.text or ""
                if strip:
                    text = text.strip()
                if exact:
                    return text == expected_text
                else:
                    return expected_text in text
            except Exception:
                return False

        try:
            WebDriverWait(drv, timeout).until(_text_matches)
            return True
        except TimeoutException:
            return False

    def click(self, by: str, selector: str, timeout: int = 15, scroll: bool = True, js_fallback: bool = True) -> None:
        """
        指定セレクタの最初の要素をクリックする。

        Args:
            by (str): 検索方法（CSS/XPathなど）。
            selector (str): セレクタ文字列。
            timeout (int): 待機秒数。
            scroll (bool): クリック前に中央へスクロールするか。
            js_fallback (bool): 通常クリック失敗時にJavaScript clickを試すか。

        Raises:
            RuntimeError: 要素が見つからない・クリックできない場合。
        """
        drv = self._driver
        try:
            # 可視になるまで待つ
            el = WebDriverWait(drv, timeout).until(
                EC.visibility_of_element_located((by, selector))
            )

            if scroll:
                drv.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", el)

            # クリック可能まで明示待機
            WebDriverWait(drv, timeout).until(EC.element_to_be_clickable((by, selector)))

            try:
                ActionChains(drv).move_to_element(el).pause(0.05).click(el).perform()
            except (ElementClickInterceptedException, StaleElementReferenceException):
                # 1回だけ再取得して再試行
                try:
                    el = drv.find_element(by, selector)
                    if scroll:
                        drv.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", el)
                    ActionChains(drv).move_to_element(el).pause(0.05).click(el).perform()
                except (ElementClickInterceptedException, StaleElementReferenceException):
                    if not js_fallback:
                        raise
                    drv.execute_script("arguments[0].click();", el)

        except TimeoutException as e:
            raise RuntimeError(f"click timeout: selector={selector}, by={by}, reason={e}")
        except Exception as e:
            raise RuntimeError(f"click failed: selector={selector}, by={by}, reason={e}")
    
    def click_button_contains_text(self, text_keyword: str, timeout: int = 15) -> None:
        """
        内部テキストに指定キーワードを含むボタンをクリックする。

        Args:
            text_keyword (str): ボタンに含まれるべき文字列。
            timeout (int): 要素待機秒数。

        Raises:
            RuntimeError: 該当ボタンが見つからない・クリックできない場合。
        """
        drv = self._driver

        try:
            # XPath: ボタンまたはロール=button の要素で内部テキストに部分一致
            xpath_selector = (
                f"//button[contains(normalize-space(.), '{text_keyword}')]"
                f" | //*[@role='button' and contains(normalize-space(.), '{text_keyword}')]"
            )

            # ボタンが見えるまで待機
            target_element = WebDriverWait(drv, timeout).until(
                EC.visibility_of_element_located(("xpath", xpath_selector))
            )

            # 中央にスクロール
            drv.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                target_element
            )

            # クリック可能になるまで待つ
            WebDriverWait(drv, timeout).until(
                EC.element_to_be_clickable(("xpath", xpath_selector))
            )

            # 通常のクリック
            try:
                ActionChains(drv).move_to_element(target_element).pause(0.05).click(target_element).perform()
            except (ElementClickInterceptedException, StaleElementReferenceException):
                # 1回だけ再取得して再クリック
                target_element = drv.find_element("xpath", xpath_selector)
                drv.execute_script(
                    "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                    target_element
                )
                ActionChains(drv).move_to_element(target_element).pause(0.05).click(target_element).perform()

        except Exception as e:
            raise RuntimeError(f"click_button_contains_text failed: text='{text_keyword}', reason={e}")

    
    def fill_input(self, by: str, selector: str, text: str, with_enter: bool = False, timeout: int = 15, clear_first: bool = True) -> None:
        """
        入力系要素（input/textarea/contenteditable）へテキストを入力する。

        まず通常のキーボード入力（`send_keys`）を試し、失敗した場合は
        JavaScript で値を書き込み、`input` / `change` イベントを発火させる。
        React 等の制御コンポーネントでも反映されるよう、プロパティセッタ経由で設定を試みる。

        Args:
            by (str): 検索方法（例: `By.CSS_SELECTOR` / `By.XPATH`）。
            selector (str): セレクタ文字列。
            text (str): 入力するテキスト。
            with_enter (bool): 入力後に Enter キーを送る場合は True。
            timeout (int): 要素の可視化を待機する最大秒数。
            clear_first (bool): 入力前に既存値をクリアするか。

        Raises:
            RuntimeError:
                - 要素が見つからない、または可視化されない場合（Timeout）
                - 要素が非インタラクティブで入力できない場合
        """
        drv = self._driver
        try:
            # 1) 可視になるまで待機（clickableだとオーバーレイで失敗しやすい）
            el = WebDriverWait(drv, timeout).until(
                EC.visibility_of_element_located((by, selector))
            )

            # 2) スクロール＆フォーカス
            drv.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            try:
                ActionChains(drv).move_to_element(el).pause(0.05).click(el).perform()
            except Exception:
                # マウス操作に失敗するケースは JS click を試す
                try:
                    drv.execute_script("arguments[0].click();", el)
                except Exception:
                    pass  # 次の手順でフォーカス/入力を試みる

            tag = (el.tag_name or "").lower()
            is_contenteditable = (el.get_attribute("contenteditable") or "").lower() == "true"

            # 3) クリア（必要なら）
            if clear_first:
                try:
                    # Ctrl/⌘+A → Delete の方が確実
                    el.send_keys(Keys.CONTROL, "a")
                    el.send_keys(Keys.DELETE)
                    # macOS の場合 Command+A も試す
                    el.send_keys(Keys.COMMAND, "a")
                    el.send_keys(Keys.DELETE)
                except Exception:
                    # フォールバック: clear()
                    try:
                        el.clear()
                    except Exception:
                        pass

            # 4) まずは通常の send_keys
            try:
                if is_contenteditable:
                    # contenteditable は一旦空にしてから
                    drv.execute_script("arguments[0].innerHTML = '';", el)
                el.send_keys(text)
            except ElementNotInteractableException:
                # 下の JS 直接設定へフォールバック
                pass

            # 5) 必要なら Enter
            if with_enter:
                try:
                    el.send_keys(Keys.RETURN)
                except Exception:
                    pass

            # 6) 値が入っていない/反映されていない場合は JS 直書き + input/change 発火
            #    - textarea/input: value プロパティを設定
            #    - contenteditable: textContent を設定
            try:
                if tag in ("input", "textarea"):
                    # React 対策: プロパティセッタ経由で設定 → input/change
                    drv.execute_script("""
                        const el = arguments[0];
                        const value = arguments[1];
                        const proto = Object.getPrototypeOf(el);
                        const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                        if (desc && desc.set) {
                            desc.set.call(el, value);
                        } else {
                            el.value = value;
                        }
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    """, el, text)
                elif is_contenteditable:
                    drv.execute_script("""
                        const el = arguments[0];
                        const value = arguments[1];
                        el.textContent = value;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    """, el, text)
            except JavascriptException:
                # JS 実行が許可されていない/shadow DOM などで失敗した場合は握りつぶす
                pass

        except TimeoutException:
            raise RuntimeError(f"fill_input timeout: element not found or not visible (selector={selector})")
        except ElementNotInteractableException:
            raise RuntimeError(f"fill_input failed: element not interactable (selector={selector})")
        
    def submit_form(self, by: str, selector: str, timeout: int = 10, click_button: bool = False) -> None:
        """
        フォーム送信を行うユーティリティ。

        `click_button=True` の場合は、フォーム内の `type=submit` ボタンをクリックして送信する。
        それ以外は対象要素に対して `form.submit()` を実行する。

        Args:
            by (str): 検索方法（例: `By.CSS_SELECTOR` / `By.XPATH`）。
            selector (str): フォームもしくは送信ボタンのセレクタ。
            timeout (int): 要素検出の最大待機秒数。
            click_button (bool): 送信ボタンをクリックして送信するか。

        Raises:
            RuntimeError: 送信対象が見つからない、もしくは送信に失敗した場合。
        """
        drv = self._driver

        try:
            WebDriverWait(drv, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            el = drv.find_element(by, selector)

            if click_button:
                # フォーム内の送信ボタンを探してクリック
                try:
                    button = el.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
                    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
                    button.click()
                    return
                except Exception:
                    pass  # ボタンがない場合は次の手段へ

            # デフォルトはネイティブsubmit()
            drv.execute_script("arguments[0].submit();", el)

        except Exception as e:
            raise RuntimeError(f"submit_form failed: selector={selector}, reason={e}")
    
    def set_checkbox(self, by: str, selector: str, check: bool = True, timeout: int = 10, scroll: bool = True) -> None:
        """
        チェックボックス（`<input type="checkbox">`）の状態を変更する。

        既に希望の状態になっている場合は何もしない。

        Args:
            by (str): 検索方法（例: `By.CSS_SELECTOR` / `By.XPATH`）。
            selector (str): チェックボックス要素のセレクタ。
            check (bool): 設定したい状態。True で ON、False で OFF。
            timeout (int): 要素検出の最大待機秒数。
            scroll (bool): クリック前に要素を中央へスクロールするか。

        Raises:
            RuntimeError:
                - 指定時間内に要素が見つからない場合
                - クリック操作に失敗した場合
        """
        drv = self._driver
        try:
            el = WebDriverWait(drv, timeout).until(
                EC.presence_of_element_located((by, selector))
            )

            if scroll:
                drv.execute_script("arguments[0].scrollIntoView({block:'center'});", el)

            current = el.is_selected()
            if current == check:
                return  # すでに希望状態

            el.click()  # トグル

        except TimeoutException:
            raise RuntimeError(f"set_checkbox timeout: selector={selector}")
        except Exception as e:
            raise RuntimeError(f"set_checkbox failed: selector={selector}, reason={e}")
        
    def navigate(self, url: str, timeout: int = 15) -> None:
        """
        同一タブで指定URLに遷移する。

        Args:
            url (str): 遷移先URL。
            timeout (int): body 要素が出現するまでの最大待機秒数。

        Raises:
            TimeoutException: ページの主体要素が既定時間内に読み込まれない場合。
        """
        drv = self._driver
        drv.get(url)

        # 例：body があるまで待つ
        WebDriverWait(drv, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    
    def get_href(self, by: str, selector: str, timeout: int = 10, index: int = 0) -> str:
        """
        指定セレクタで見つかったリンク要素（a）の `href` を取得する。

        複数ヒット時は `index` で対象を選択する。

        Args:
            by (str): 検索方法（例: `By.CSS_SELECTOR` / `By.XPATH`）。
            selector (str): a 要素を特定するセレクタ。
            timeout (int): 要素検出の最大待機秒数。
            index (int): 複数ヒット時のインデックス（0 起点）。

        Returns:
            str: 取得した href の値。

        Raises:
            RuntimeError: 要素が見つからない、または取得に失敗した場合。
        """
        drv = self._driver
        try:
            WebDriverWait(drv, timeout).until(
                EC.presence_of_all_elements_located((by, selector))
            )
            elems = drv.find_elements(by, selector)
            if not elems or index >= len(elems):
                raise TimeoutException(f"element not found: selector={selector}, index={index}")
            href = elems[index].get_attribute("href")
            
            if href == None:
                href = ""
                
            return href
        except Exception as e:
            raise RuntimeError(f"get_href failed: selector={selector}, reason={e}")
        
    def get_text(self, by: str, selector: str, timeout: int = 10, index: int = 0) -> str:
        """
        指定セレクタで見つかった要素の表示テキストを取得する。

        複数ヒット時は `index` で対象を選択する。返却値は `strip()` 済み。

        Args:
            by (str): 検索方法（例: `By.CSS_SELECTOR` / `By.XPATH`）。
            selector (str): 対象要素のセレクタ。
            timeout (int): 要素検出の最大待機秒数。
            index (int): 複数ヒット時のインデックス（0 起点）。

        Returns:
            str: 取得したテキスト（前後空白を除去）。

        Raises:
            RuntimeError: 要素が見つからない、または取得に失敗した場合。
        """
        drv = self._driver
        try:
            WebDriverWait(drv, timeout).until(
                EC.presence_of_all_elements_located((by, selector))
            )
            elems = drv.find_elements(by, selector)
            if not elems or index >= len(elems):
                raise TimeoutException(f"element not found: selector={selector}, index={index}")
            text = elems[index].text.strip()
            return text
        except Exception as e:
            raise RuntimeError(f"get_href failed: selector={selector}, reason={e}")
    
    def get_current_html(self) -> str:
        """
        現在表示中ページの HTML ソースを取得する。

        Returns:
            str: `driver.page_source` の文字列。
        """
        drv = self._driver
        html = drv.page_source
        return html
        
    # -------------------------
    # public
    # -------------------------
    def wait_seconds(self, seconds: float, poll_frequency: float = 0.2) -> None:
        """
        指定した秒数だけスクリプトの実行を一時停止する（ブロッキングウェイト）。

        一般的な `time.sleep()` と異なり、細かいポーリング間隔でループを行うため、
        長時間の待機中でも外部割り込み処理などに対応しやすい。
        待機終了条件は「指定秒数を経過した時点」。

        Args:
            seconds (float): 待機する時間（秒）。小数値を指定可能。
            poll_frequency (float): チェック間隔（秒）。短すぎるとCPU使用率が上がるため注意。

        Example:
            ```python
            loader.wait_seconds(2.5)  # 2.5秒待機
            ```
        """
        if seconds <= 0:
            return
        deadline = monotonic() + seconds
        while True:
            remain = deadline - monotonic()
            if remain <= 0:
                break
            sleep(min(poll_frequency, remain))

    # --- helpers ---
    def _xqath_quote(self, s: str) -> str:
        """
        XPath式内で使用する文字列を安全にクォートする。

        単一引用符 `'` と二重引用符 `"` が混在する文字列に対応し、
        XPathの `concat()` 関数形式に変換することで正しいクエリ文字列を生成する。

        Args:
            s (str): エスケープ対象の文字列。

        Returns:
            str: XPath式で使用可能なクォート済み文字列。

        Example:
            ```python
            _xqath_quote("O'Reilly")  # -> concat('O', "'", 'Reilly')
            ```
        """

        if "'" not in s:
            return f"'{s}'"
        if '"' not in s:
            return f'"{s}"'
        parts = s.split("'")
        return "concat(" + ", \"'\", ".join([f"'{p}'" for p in parts]) + ")"
