# アプリ内お問い合わせモーダル Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ハンバーガーメニューの「お問い合わせ」をアプリ内の下からスライドするモーダル(入力→確認→完了、localStorage下書き保持)に置き換える。

**Architecture:** 既存の `slide-modal full-screen-modal` + `ModalManager`(common.js)を流用。新規 `contact.js` がモーダル制御・バリデーション・下書き・送信を担う。送信先はLPと同一の `POST https://contact.pol-is.jp/contact`(CORS `*` 確認済み、バックエンド変更なし)。

**Tech Stack:** Vanilla JS / SCSS(dockerのsassでコンパイル) / puppeteer-coreで検証(実送信はインターセプトでモック)

**仕様書:** `docs/superpowers/specs/2026-07-09-contact-modal-design.md`

**前提知識:**
- sassコンパイル: `cd Client && docker compose up -d sass` で watch 起動。`Client/public_html_app/style.css` のmd5変化で完了検知。git操作前に `docker compose stop sass`
- `ModalManager`: `new ModalManager({ rootSel: "#contact-modal" }).init()` で閉じるボタン(`.modal-close-button`)と背景クリックが配線される。`showModal()`/`closeModal()`
- script読み込み順: common → favorites → contact → home → create → notice(全て `?v=__ASSET_VERSION__`)
- localhost確認: `docker compose up -d` 後 http://localhost:8081/

---

### Task 1: index.html — モーダルDOM・メニュー項目・scriptタグ

**Files:**
- Modify: `Client/public_html_app/index.html`

- [ ] **Step 1: メニューの「お問い合わせ」をbuttonに変更**

`<a class="menu-item" href="https://pol-is.jp/contact/">...` を以下に置換:

```html
                    <button id="contact-menu-button" class="menu-item" type="button">
                        <i class="bi bi-envelope"></i>
                        <div class="text">お問い合わせ</div>
                    </button>
```

- [ ] **Step 2: `#theme-create-modal` の直前に `#contact-modal` を追加**

```html
    <div id="contact-modal" class="slide-modal full-screen-modal">
        <div class="label-group">
            <div class="label-header">
                <button class="modal-close-button">
                    <i class="bi bi-x"></i>
                </button>
                <div class="modal-title">お問い合わせ</div>
            </div>
            <div class="modal-text">返信が必要な内容にはメールアドレス宛にご連絡します</div>
        </div>
        <div class="modal-window">
            <div class="modal-scroll-area">
                <div class="modal-content">

                    <div class="contact-form-wrapper contact-step show">
                        <div class="contact-input-group">
                            <div class="contact-input-label">メールアドレス</div>
                            <input type="email" id="contact-mail-input" class="contact-input" autocomplete="email">
                            <div class="contact-input-description">お問い合わせへの返信に使用します。</div>
                        </div>
                        <div class="contact-input-group">
                            <div class="contact-input-label">お名前<span class="contact-optional">任意</span></div>
                            <input type="text" id="contact-name-input" class="contact-input" autocomplete="name">
                        </div>
                        <div class="contact-input-group">
                            <div class="contact-input-label">お問い合わせ内容</div>
                            <textarea id="contact-content-input" class="contact-input" rows="6"></textarea>
                        </div>
                        <div class="contact-error" id="contact-form-error"></div>
                        <button id="contact-confirm-button" class="button secondary">
                            <div class="text">確認する</div>
                        </button>
                    </div>

                    <div class="contact-confirm-wrapper contact-step">
                        <div class="contact-input-group">
                            <div class="contact-input-label">メールアドレス</div>
                            <div class="contact-input-confirm" id="contact-mail-confirm"></div>
                        </div>
                        <div class="contact-input-group">
                            <div class="contact-input-label">お名前</div>
                            <div class="contact-input-confirm" id="contact-name-confirm"></div>
                        </div>
                        <div class="contact-input-group">
                            <div class="contact-input-label">お問い合わせ内容</div>
                            <div class="contact-input-confirm" id="contact-content-confirm"></div>
                        </div>
                        <div class="contact-error" id="contact-send-error"></div>
                        <button id="contact-send-button" class="button secondary">
                            <i class="bi bi-send"></i>
                            <div class="text">送信する</div>
                        </button>
                        <button id="contact-back-button" class="button secondary-border">
                            <div class="text">戻る</div>
                        </button>
                    </div>

                    <div class="contact-complete-wrapper contact-step">
                        <i class="bi bi-check-circle contact-complete-icon"></i>
                        <div class="contact-complete-text">送信しました。<br>お問い合わせありがとうございます。</div>
                        <button id="contact-complete-close-button" class="button secondary">
                            <div class="text">閉じる</div>
                        </button>
                    </div>

                </div>
            </div>
        </div>
    </div>
```

- [ ] **Step 3: scriptタグ追加**

`favorites.js` の行の直後に:

```html
    <script src="./javascript/contact.js?v=__ASSET_VERSION__"></script>
```

### Task 2: contact.js 本体

**Files:**
- Create: `Client/public_html_app/javascript/contact.js`

- [ ] **Step 1: 実装**(下記全文。関数名は仕様書と一致させる)

```js
// ==============================
// アプリ内お問い合わせモーダル
// 仕様: docs/superpowers/specs/2026-07-09-contact-modal-design.md
// ==============================

/** 送信先（LPフォームと同一。CORSは * のためアプリ/ローカルから直接POST可） */
const CONTACT_API_URL = "https://contact.pol-is.jp/contact";

/** 下書き保存に使うlocalStorageキー */
const CONTACT_DRAFT_KEY = "contact_draft";

/** 下書き保存のデバウンス(ms) */
const CONTACT_DRAFT_DEBOUNCE_MS = 300;

/** お問い合わせモーダルのManager */
let contactModalManager = null;

/** 下書き保存のデバウンスタイマー */
let contactDraftTimer = null;

/** 入力3フィールドを取得する */
function getContactInputs() {
    return {
        mail: document.querySelector("#contact-mail-input"),
        name: document.querySelector("#contact-name-input"),
        content: document.querySelector("#contact-content-input"),
    };
}

/** 現在の入力値（trim済み）を返す */
function readContactValues() {
    const inputs = getContactInputs();
    return {
        mail: (inputs.mail?.value ?? "").trim(),
        name: (inputs.name?.value ?? "").trim(),
        content: (inputs.content?.value ?? "").trim(),
    };
}

/**
 * 入力値を検証してエラーメッセージを返す（問題なければ null）。
 * 内容とメールは必須。メールは @ を含む簡易チェックのみ。
 */
function validateContactInput(values) {
    if (values.content === "") {
        return "お問い合わせ内容を入力してください";
    }
    if (values.mail === "" || !values.mail.includes("@")) {
        return "メールアドレスを入力してください";
    }
    return null;
}

/** 下書きをlocalStorageへ保存する（使えない環境では何もしない） */
function saveContactDraft() {
    try {
        localStorage.setItem(CONTACT_DRAFT_KEY, JSON.stringify(readContactValues()));
    } catch {
        // プライベートブラウズ等。下書きなしで通常動作
    }
}

/** 下書きをフィールドへ復元する */
function restoreContactDraft() {
    let draft = null;
    try {
        draft = JSON.parse(localStorage.getItem(CONTACT_DRAFT_KEY) ?? "null");
    } catch {
        return;
    }
    if (!draft || typeof draft !== "object") {
        return;
    }
    const inputs = getContactInputs();
    if (inputs.mail && typeof draft.mail === "string") inputs.mail.value = draft.mail;
    if (inputs.name && typeof draft.name === "string") inputs.name.value = draft.name;
    if (inputs.content && typeof draft.content === "string") inputs.content.value = draft.content;
}

/** 下書きとフィールドをクリアする */
function clearContactDraft() {
    try {
        localStorage.removeItem(CONTACT_DRAFT_KEY);
    } catch {
        // 握りつぶし
    }
    const inputs = getContactInputs();
    if (inputs.mail) inputs.mail.value = "";
    if (inputs.name) inputs.name.value = "";
    if (inputs.content) inputs.content.value = "";
}

/**
 * 3画面（入力/確認/完了）を切り替える。
 * @param {"form"|"confirm"|"complete"} step
 */
function showContactStep(step) {
    const modal = document.querySelector("#contact-modal");
    modal.querySelector(".contact-form-wrapper").classList.toggle("show", step === "form");
    modal.querySelector(".contact-confirm-wrapper").classList.toggle("show", step === "confirm");
    modal.querySelector(".contact-complete-wrapper").classList.toggle("show", step === "complete");
}

/** エラーメッセージ欄を更新する（空文字で非表示） */
function setContactError(selector, message) {
    const el = document.querySelector(selector);
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("show", message !== "");
}

/**
 * お問い合わせを送信する。
 * @returns {Promise<boolean>} 成功なら true（例外・非2xxは false）
 */
async function submitContact(payload) {
    try {
        const res = await fetch(CONTACT_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        return res.ok;
    } catch {
        return false;
    }
}

/** モーダルを入力画面の状態で開く */
function openContactModal() {
    setContactError("#contact-form-error", "");
    setContactError("#contact-send-error", "");
    showContactStep("form");
    contactModalManager.showModal();
}

/** フォーム各ボタン・入力イベントを配線する */
function bindContactForm() {
    const inputs = getContactInputs();

    // 下書き: 入力の都度デバウンス保存
    [inputs.mail, inputs.name, inputs.content].forEach((input) => {
        input?.addEventListener("input", () => {
            clearTimeout(contactDraftTimer);
            contactDraftTimer = setTimeout(saveContactDraft, CONTACT_DRAFT_DEBOUNCE_MS);
        });
    });

    // 確認する: バリデーション→確認画面へ転記
    document.querySelector("#contact-confirm-button").addEventListener("click", (e) => {
        e.preventDefault();
        const values = readContactValues();
        const error = validateContactInput(values);
        if (error) {
            setContactError("#contact-form-error", error);
            return;
        }
        setContactError("#contact-form-error", "");
        // XSS防止のためtextContentで転記（改行はCSSのpre-wrapで表現）
        document.querySelector("#contact-mail-confirm").textContent = values.mail;
        document.querySelector("#contact-name-confirm").textContent = values.name || "（未入力）";
        document.querySelector("#contact-content-confirm").textContent = values.content;
        setContactError("#contact-send-error", "");
        showContactStep("confirm");
    });

    // 戻る
    document.querySelector("#contact-back-button").addEventListener("click", (e) => {
        e.preventDefault();
        showContactStep("form");
    });

    // 送信する: 成功→下書きクリア+完了 / 失敗→留まってエラー表示
    const sendButton = document.querySelector("#contact-send-button");
    sendButton.addEventListener("click", async (e) => {
        e.preventDefault();
        if (sendButton.disabled) return;
        sendButton.disabled = true;
        const label = sendButton.querySelector(".text");
        const originalLabel = label.textContent;
        label.textContent = "送信中…";
        setContactError("#contact-send-error", "");

        const ok = await submitContact(readContactValues());

        sendButton.disabled = false;
        label.textContent = originalLabel;
        if (ok) {
            clearContactDraft();
            showContactStep("complete");
        } else {
            setContactError("#contact-send-error", "送信に失敗しました。時間をおいて再度お試しください。");
        }
    });

    // 完了画面の閉じる
    document.querySelector("#contact-complete-close-button").addEventListener("click", (e) => {
        e.preventDefault();
        contactModalManager.closeModal();
    });
}

/** お問い合わせモーダルを初期化する */
function initializeContactModal() {
    const modal = document.querySelector("#contact-modal");
    if (!modal) {
        return;
    }
    contactModalManager = new ModalManager({ rootSel: "#contact-modal" });
    contactModalManager.init();

    bindContactForm();
    restoreContactDraft();

    const menuButton = document.querySelector("#contact-menu-button");
    if (menuButton) {
        menuButton.addEventListener("click", () => {
            // ハンバーガーメニューを閉じてからモーダルを開く（notice.jsと同じ方式）
            document.querySelector("#hamburger-menu")?.classList.remove("open");
            document.querySelector("#bottom-menu")?.classList.remove("hamburger-open");
            document
                .querySelector("#hamburger-menu .hamburger-trigger")
                ?.setAttribute("aria-expanded", "false");
            openContactModal();
        });
    }
}

document.addEventListener("DOMContentLoaded", initializeContactModal);
```

- [ ] **Step 2: 構文チェック**

Run: `node --check Client/public_html_app/javascript/contact.js`
Expected: エラーなし

### Task 3: SCSS

**Files:**
- Create: `Client/scss/pages/home/_contact.scss`
- Modify: `Client/scss/pages/home/_index.scss`（`@forward "contact";` を追加）

- [ ] **Step 1: `_contact.scss` 作成**

```scss
@use "../../common" as common;

// アプリ内お問い合わせモーダル（#contact-modal）
body#home {
    #contact-modal {
        .contact-step {
            display: none;
            flex-direction: column;
            gap: 20px;
            width: 100%;

            &.show {
                display: flex;
            }
        }

        .contact-input-group {
            @include common.stack;
            @include common.width-full;
            gap: 6px;

            .contact-input-label {
                @include common.font-weight-black;
                @include common.font-size-small;
                color: #989898;

                .contact-optional {
                    font-weight: 400;
                    font-size: var(--font-size-12px);
                    color: var(--color-font-dark-secondary);
                    margin-left: 8px;
                }
            }

            .contact-input {
                @include common.width-full;
                box-sizing: border-box;
                padding: 10px 12px;
                border: 1px solid var(--color-font-dark-secondary-2);
                border-radius: 8px;
                background-color: var(--color-light);
                font-size: var(--font-size-14px);
                color: var(--color-font-dark);

                &:focus {
                    outline: none;
                    border-color: var(--color-main);
                }
            }

            textarea.contact-input {
                resize: vertical;
                line-height: 1.6;
            }

            .contact-input-description {
                font-size: var(--font-size-12px);
                color: var(--color-font-dark-secondary);
            }

            .contact-input-confirm {
                @include common.width-full;
                box-sizing: border-box;
                padding: 10px 12px;
                border-radius: 8px;
                background-color: var(--color-bg-gray);
                font-size: var(--font-size-14px);
                color: var(--color-font-dark);
                line-height: 1.6;
                white-space: pre-wrap;
                word-break: break-word;
                min-height: 1.6em;
            }
        }

        .contact-error {
            display: none;
            font-size: var(--font-size-12px);
            color: #d33;

            &.show {
                display: block;
            }
        }

        // ボタンは中央寄せ・共通トーン
        .button {
            align-self: center;
            border: transparent;

            &.secondary-border {
                border: 1px solid var(--color-dark);
            }
        }

        .contact-complete-wrapper {
            align-items: center;
            text-align: center;
            padding: 24px 0;

            .contact-complete-icon {
                font-size: 48px;
                color: var(--color-main);
            }

            .contact-complete-text {
                font-size: var(--font-size-14px);
                color: var(--color-font-dark-gray-2);
                line-height: 1.8;
            }
        }
    }
}
```

- [ ] **Step 2: `_index.scss` に `@forward "contact";` を追加**（favoritesの後）

- [ ] **Step 3: sassコンパイル**

```bash
cd Client && before=$(md5 -q public_html_app/style.css) && docker compose up -d sass
# md5変化を待つループで完了検知
grep -c "contact-input-confirm" public_html_app/style.css   # 1以上ならOK
```

### Task 4: ブラウザ検証（puppeteer・実送信なしモック）

**Files:**
- Create: scratchpad `check-contact.js`

- [ ] **Step 1: 検証スクリプト**（要点。実送信は `setRequestInterception` でモック）

```js
await page.setRequestInterception(true);
page.on("request", (req) => {
  if (req.url().startsWith("https://contact.pol-is.jp/contact")) {
    if (MODE === "fail") req.respond({ status: 500, body: "{}" });
    else req.respond({ status: 200, contentType: "application/json", body: "{}" });
    return;
  }
  req.continue();
});
```

チェック項目（仕様書のテスト節と同一）:
1. メニュー→お問い合わせでモーダル表示・`location.href` 不変
2. 空のまま確認→エラー表示・遷移しない
3. 入力→確認画面へ転記（改行含む・textContent）
4. 送信成功モック→完了画面・`contact_draft` 消滅
5. 送信失敗モック→確認画面のままエラー表示・下書き保持
6. 入力→リロード→復元
7. 回帰: テーマ作成・お知らせ・お気に入りモーダル動作

- [ ] **Step 2: 実行し全✅とスクショ目視**

### Task 5: コミット

- [ ] `docker compose stop sass` → index.html / contact.js / _contact.scss / _index.scss / style.css×3 を feature/ux-improvements にコミット・push（**mainマージ・デプロイはユーザー指示後**）
