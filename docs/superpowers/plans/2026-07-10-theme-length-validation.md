# テーマ作成時の文字数バリデーション Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** テーマ作成のタイトルを80文字・説明を200文字に制限（カウンター表示+進行/投稿ブロック+サーバー422）。既存データは許容。

**Architecture:** create.jsのフォームテンプレート（AI/マニュアル両モード×タイトル/説明=4箇所）にmaxlengthとカウンター要素を追加し、共通の`bindCharCounters()`/`getLengthError()`で表示更新と検証。サーバーはpydantic Fieldに`max_length`を2箇所追加。

**Tech Stack:** Vanilla JS / SCSS（docker sass）/ pydantic / pytest（`Server/web/tests/`）/ puppeteer-core

**仕様書:** `docs/superpowers/specs/2026-07-10-theme-length-validation-design.md`

**前提知識:**
- create.jsのフォームHTMLはモード切替時にテンプレート文字列から再構築される（AI用: title=980行付近/desc=1155行付近、マニュアル用: 1246/1391行付近）。**4箇所全てに同じ変更が必要**
- `initializeCreateForm`（412行付近）で themeInput/descriptionInput を取得、495行付近で inputイベント（下書き保存）をバインド → ここにカウンター初期化を足す
- AI生成は `descriptionInput.value = result["description"]`（156行付近）、下書き復元は472行付近 → JS代入後にカウンター手動更新が必要
- 「次へ」は `bindNextButtonEvents`（569行付近）で controllNo を進める → 進める前に検証を挟む
- 文字数は `[...str].length`（コードポイント）
- sass再コンパイル: `cd Client && docker compose up -d sass` + md5待ち、git操作前に stop

---

### Task 1: サーバー側 max_length + pytest

**Files:**
- Modify: `Server/web/api/schemas/theme.py:131-133`
- Create: `Server/web/tests/test_schemas_theme.py`

- [ ] **Step 1: 境界テストを書く**

```python
"""ThemePostDraftRequest の文字数バリデーションのテスト"""
import pytest
from pydantic import ValidationError

from api.schemas.theme import ThemePostDraftRequest


def _make(theme="テーマ", description="説明", **kw):
    return ThemePostDraftRequest(
        access_key="k", theme=theme, comments="c", description=description, category=1, **kw
    )


def test_theme_80_chars_accepted():
    assert _make(theme="あ" * 80).theme == "あ" * 80


def test_theme_81_chars_rejected():
    with pytest.raises(ValidationError):
        _make(theme="あ" * 81)


def test_description_200_chars_accepted():
    assert _make(description="い" * 200).description == "い" * 200


def test_description_201_chars_rejected():
    with pytest.raises(ValidationError):
        _make(description="い" * 201)
```

- [ ] **Step 2: 失敗確認** Run: `cd Server/web && python3 -m pytest tests/test_schemas_theme.py -v` → 81/201のケースがFAIL（現状は素通し）

- [ ] **Step 3: スキーマ変更**

```python
    theme: str = Field(max_length=80, description="テーマ(ユーザー設定)")
    comments: str = Field(description="コメント(ユーザー設定)")
    description: str = Field(max_length=200, description="説明(ユーザー設定)")
```

- [ ] **Step 4: 全テストPASS確認** Run: `cd Server/web && python3 -m pytest tests/ -q` → 既存含め全PASS

### Task 2: クライアント — maxlength・カウンター・検証

**Files:**
- Modify: `Client/public_html_app/javascript/create.js`
- Modify: `Client/scss/pages/home/_create.scss`

- [ ] **Step 1: 定数追加**（ファイル冒頭の`let descriptionInput = null;`付近）

```js
/** タイトルの最大文字数（コードポイント） */
const THEME_TITLE_MAX = 80;
/** 説明の最大文字数（コードポイント） */
const THEME_DESCRIPTION_MAX = 200;

/** コードポイント数を返す（サロゲートペアを1文字と数える） */
function countChars(str) {
    return [...(str ?? "")].length;
}
```

- [ ] **Step 2: テンプレート4箇所の変更**

タイトル（AI/マニュアル共通の形）:
```html
<textarea id="theme-title-textarea" class="hidden-input auto-resize target-input" rows="1" placeholder="テーマを入力" maxlength="80"></textarea>
```
`.input-group` 閉じタグ直後に:
```html
<div class="char-counter" data-counter-for="theme-title-textarea"></div>
```
説明も同様に `maxlength="200"` + `data-counter-for="description-textarea"`。

- [ ] **Step 3: カウンターとエラーの共通関数を追加**

```js
/** 入力に対応するカウンター表示を更新する */
function updateCharCounter(input) {
    if (!input) return;
    const counter = parentNode.querySelector(`.char-counter[data-counter-for="${input.id}"]`);
    if (!counter) return;
    const max = input.id === "theme-title-textarea" ? THEME_TITLE_MAX : THEME_DESCRIPTION_MAX;
    const count = countChars(input.value);
    counter.textContent = `${count}/${max}`;
    counter.classList.toggle("over", count >= max);
}

/** タイトル/説明の文字数エラーを返す（なければnull） */
function getLengthError(stepperEl) {
    const title = stepperEl.querySelector("#theme-title-textarea");
    if (title && countChars(title.value) > THEME_TITLE_MAX) {
        return `タイトルは${THEME_TITLE_MAX}文字以内で入力してください`;
    }
    const desc = stepperEl.querySelector("#description-textarea");
    if (desc && countChars(desc.value) > THEME_DESCRIPTION_MAX) {
        return `説明は${THEME_DESCRIPTION_MAX}文字以内で入力してください`;
    }
    return null;
}

/** ステッパー内にエラーメッセージを表示/消去する */
function setStepperError(stepperEl, message) {
    let el = stepperEl.querySelector(".stepper-error");
    if (!el) {
        const nextButton = stepperEl.querySelector(".next-button");
        el = document.createElement("div");
        el.className = "stepper-error";
        nextButton.parentNode.insertBefore(el, nextButton);
    }
    el.textContent = message ?? "";
    el.classList.toggle("show", Boolean(message));
}
```

- [ ] **Step 4: 配線**
  - `initializeCreateForm` 内（input取得後）: `[themeInput, descriptionInput].forEach((el) => { updateCharCounter(el); el?.addEventListener("input", () => updateCharCounter(el)); });`
  - AI生成代入後（`descriptionInput.value = result["description"];` の直後）: `updateCharCounter(descriptionInput);`
  - 下書き復元後（472行付近の復元処理の後）: `updateCharCounter(themeInput); updateCharCounter(descriptionInput);`
  - `bindNextButtonEvents` のclickハンドラ先頭に:
    ```js
    const stepperEl = buttonElement.closest(".modal-stepper");
    const lengthError = getLengthError(stepperEl);
    setStepperError(stepperEl, lengthError);
    if (lengthError) return;
    ```
  - `requestThemePostDraftAPI` 冒頭に（保険）:
    ```js
    if (countChars(themeInput.value) > THEME_TITLE_MAX || countChars(descriptionInput.value) > THEME_DESCRIPTION_MAX) {
        console.warn("文字数超過のため投稿を中止");
        return;
    }
    ```

- [ ] **Step 5: SCSS**（`_create.scss` の `.input-group` 定義の後に兄弟として）

```scss
.char-counter {
    width: 100%;
    text-align: right;
    font-size: var(--font-size-12px);
    color: var(--color-font-dark-secondary);
    margin-top: -8px; // input-groupとの間を詰める

    &.over {
        color: #d33;
        font-weight: 600;
    }
}

.stepper-error {
    display: none;
    width: 100%;
    text-align: center;
    font-size: var(--font-size-12px);
    color: #d33;

    &.show {
        display: block;
    }
}
```

- [ ] **Step 6: `node --check` + sassコンパイル + カウンター出力確認**（style.cssに`char-counter`が入ること）

### Task 3: ブラウザ検証（puppeteer・localhost）

チェック項目（post_draft/generate系はsetRequestInterceptionでモック）:
1. カウンター初期表示「0/80」「0/200」・入力で追従・80字で赤
2. maxlength: 81文字目が入らない（既に80字のとき type しても増えない）
3. JSで201文字を説明に代入 → カウンター201/200（赤）→「次へ」でエラー表示・ステップ進まない
4. 収めると次へ進める（エラー消える）
5. マニュアル/AIモード切替後もカウンター動作（フォーム再構築のため）
6. スクリーンショット目視（カウンター・エラーの見た目）→ ユーザーにローカル確認案内

### Task 4: コミット（feature/ux-improvements、デプロイなし）

```bash
git add Client/public_html_app/javascript/create.js Client/scss/pages/home/_create.scss \
  Client/public_html/style.css Client/public_html_app/style.css Client/public_html_admin/style.css \
  Server/web/api/schemas/theme.py Server/web/tests/test_schemas_theme.py
git commit -m "feat: テーマ作成にタイトル80字・説明200字のバリデーションを追加"
```
