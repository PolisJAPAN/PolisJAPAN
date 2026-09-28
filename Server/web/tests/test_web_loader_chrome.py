"""fill_input のBMP外文字(絵文字等)対応のテスト。

ChromeDriverの send_keys はBMP外の文字(例: 🙇 U+1F647)を打鍵できず
WebDriverException を送出する。fill_input は例外で落ちずに
JS直書きフォールバックで全文(絵文字含む)を反映しなければならない。
"""
from selenium.common.exceptions import WebDriverException

from api.utils.web_loader_chrome import WebLoaderChrome

NON_BMP_TEXT = "想定してください\U0001F647‍♀️"  # 🙇‍♀️
BMP_TEXT = "普通のテキストです❓"


class FakeElement:
    """ChromeDriver同様、BMP外文字の send_keys で例外を投げる入力要素。"""
    tag_name = "textarea"

    def __init__(self):
        self.sent_keys: list[tuple] = []

    def is_displayed(self):
        return True

    def get_attribute(self, name):
        return None

    def clear(self):
        pass

    def send_keys(self, *args):
        for arg in args:
            if any(ord(c) > 0xFFFF for c in str(arg)):
                raise WebDriverException(
                    "unknown error: ChromeDriver only supports characters in the BMP")
        self.sent_keys.append(args)


class FakeDriver:
    def __init__(self, element):
        self._element = element
        self.scripts: list[tuple] = []

    def find_element(self, by, selector):
        return self._element

    def find_elements(self, by, selector):
        return [self._element]

    def execute_script(self, script, *args):
        self.scripts.append((script, args))
        return None


def _loader(driver):
    loader = WebLoaderChrome.__new__(WebLoaderChrome)
    loader._driver = driver
    return loader


def test_fill_input_non_bmp_text_falls_back_to_js():
    el = FakeElement()
    drv = FakeDriver(el)
    loader = _loader(drv)

    # 例外で落ちないこと
    loader.fill_input("css selector", "textarea", NON_BMP_TEXT)

    # JS直書きパスに絵文字込みの全文が渡ること
    js_texts = [args for _, args in drv.scripts if NON_BMP_TEXT in args]
    assert js_texts, f"JS直書きに全文が渡っていない: {drv.scripts}"


def test_fill_input_bmp_text_still_uses_send_keys():
    el = FakeElement()
    drv = FakeDriver(el)
    loader = _loader(drv)

    loader.fill_input("css selector", "textarea", BMP_TEXT)

    assert any(BMP_TEXT in args for args in el.sent_keys)


class StaleOnTypeElement(FakeElement):
    """本文入力時のみStaleElementReferenceExceptionを投げる要素。"""
    def send_keys(self, *args):
        from selenium.common.exceptions import StaleElementReferenceException
        for arg in args:
            if str(arg) == BMP_TEXT:
                raise StaleElementReferenceException("stale element reference")
        super().send_keys(*args)


def test_fill_input_does_not_swallow_stale_element_error():
    # BMP制限以外のWebDriverExceptionは従来どおり伝播する（握りつぶさない）
    import pytest
    from selenium.common.exceptions import StaleElementReferenceException
    el = StaleOnTypeElement()
    drv = FakeDriver(el)
    loader = _loader(drv)

    with pytest.raises(StaleElementReferenceException):
        loader.fill_input("css selector", "textarea", BMP_TEXT)


def test_fill_input_non_bmp_on_unwritable_element_raises():
    # JS直書きできない要素形状(inputでもtextareaでもcontenteditableでもない)で
    # BMP外文字を渡された場合、無言の空振りではなく明示的に失敗する
    import pytest
    el = FakeElement()
    el.tag_name = "div"  # get_attribute("contenteditable")はNone
    drv = FakeDriver(el)
    loader = _loader(drv)

    with pytest.raises(RuntimeError):
        loader.fill_input("css selector", "div.editor", NON_BMP_TEXT)


def test_fill_input_with_enter_presses_enter_after_value_is_set():
    # with_enter=True のEnterは値の反映(JS直書き含む)より後に送られること
    from selenium.webdriver.common.keys import Keys
    el = FakeElement()
    drv = FakeDriver(el)
    events = []
    orig_send = el.send_keys
    orig_script = drv.execute_script

    def send_spy(*args):
        orig_send(*args)
        if Keys.RETURN in args:
            events.append("enter")

    def script_spy(script, *args):
        if any(NON_BMP_TEXT in str(a) for a in args):
            events.append("js-write")
        return orig_script(script, *args)

    el.send_keys = send_spy
    drv.execute_script = script_spy

    loader = _loader(drv)
    loader.fill_input("css selector", "textarea", NON_BMP_TEXT, with_enter=True)

    assert events == ["js-write", "enter"]
