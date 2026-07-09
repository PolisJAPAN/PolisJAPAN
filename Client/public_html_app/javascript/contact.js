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

/**
 * 入力3フィールドを取得する。
 *
 * @returns {{mail: HTMLElement|null, name: HTMLElement|null, content: HTMLElement|null}}
 */
function getContactInputs() {
    return {
        mail: document.querySelector("#contact-mail-input"),
        name: document.querySelector("#contact-name-input"),
        content: document.querySelector("#contact-content-input"),
    };
}

/**
 * 現在の入力値（trim済み）を返す。
 *
 * @returns {{mail: string, name: string, content: string}}
 */
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
 *
 * @param {{mail: string, name: string, content: string}} values
 * @returns {string|null}
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

/**
 * 下書きをlocalStorageへ保存する（使えない環境では何もしない）。
 *
 * @returns {void}
 */
function saveContactDraft() {
    try {
        localStorage.setItem(CONTACT_DRAFT_KEY, JSON.stringify(readContactValues()));
    } catch {
        // プライベートブラウズ等。下書きなしで通常動作
    }
}

/**
 * 下書きをフィールドへ復元する（ページ読込時に1回）。
 *
 * @returns {void}
 */
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

/**
 * 下書きとフィールドをクリアする（送信成功時のみ呼ぶ）。
 *
 * @returns {void}
 */
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
 *
 * @param {"form"|"confirm"|"complete"} step
 * @returns {void}
 */
function showContactStep(step) {
    const modal = document.querySelector("#contact-modal");
    modal.querySelector(".contact-form-wrapper").classList.toggle("show", step === "form");
    modal.querySelector(".contact-confirm-wrapper").classList.toggle("show", step === "confirm");
    modal.querySelector(".contact-complete-wrapper").classList.toggle("show", step === "complete");
}

/**
 * エラーメッセージ欄を更新する（空文字で非表示）。
 *
 * @param {string} selector - エラー欄のセレクタ
 * @param {string} message - 表示するメッセージ（"" で非表示）
 * @returns {void}
 */
function setContactError(selector, message) {
    const el = document.querySelector(selector);
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("show", message !== "");
}

/**
 * お問い合わせを送信する。
 *
 * @async
 * @param {{mail: string, name: string, content: string}} payload
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

/**
 * モーダルを入力画面の状態で開く。
 *
 * @returns {void}
 */
function openContactModal() {
    setContactError("#contact-form-error", "");
    setContactError("#contact-send-error", "");
    showContactStep("form");
    contactModalManager.showModal();
}

/**
 * フォーム各ボタン・入力イベントを配線する。
 *
 * @returns {void}
 */
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

/**
 * お問い合わせモーダルを初期化する（モーダル・メニュー項目・下書き復元）。
 *
 * @returns {void}
 */
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
