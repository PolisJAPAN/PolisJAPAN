// ==============================
// お知らせ機能（csv/notices.csv 駆動）
// 仕様: docs/superpowers/specs/2026-07-08-notice-feature-design.md
// ==============================

/** お知らせCSVの取得先 */
const NOTICE_CSV_URL = "/csv/notices.csv";

/** 既読の最大お知らせIDを保存するCookie名 */
const NOTICE_SEEN_COOKIE = "notice_last_seen_id";

/** お知らせモーダルのManager */
let noticeModalManager = null;

/** 取得済みのお知らせ（id降順）。null=未取得 */
let noticesCache = null;

/**
 * HTMLエスケープ（notice.js内で完結させるための専用ヘルパー）。
 *
 * @param {string} s - エスケープする文字列
 * @returns {string} - エスケープ済み文字列
 */
function noticeEscapeHtml(s) {
    return String(s)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

/**
 * エスケープ済みテキスト1行分にインライン記法（太字・リンク・裸URL）を適用する。
 *
 * 入力は noticeEscapeHtml 済みであること（このため任意HTMLは注入できない）。
 *
 * @param {string} text - エスケープ済みの1行
 * @returns {string} - インライン記法をタグ化したHTML
 */
function noticeInlineMarkdown(text) {
    // [テキスト](URL) — URLは http/https のみ許可
    text = text.replace(
        /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    // 生成済みタグの中を壊さないよう、タグ以外の部分にだけ太字と裸URLリンク化を適用する
    text = text
        .split(/(<[^>]+>)/)
        .map((seg) => {
            if (seg.startsWith("<")) {
                return seg;
            }
            return seg
                .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
                .replace(
                    /(https?:\/\/[^\s<]+)/g,
                    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
                );
        })
        .join("");
    return text;
}

/**
 * お知らせ本文（Markdownサブセット）をHTMLへ変換する。
 *
 * 対応記法: `## 見出し`（行頭）/ `- 箇条書き`（行頭）/ `**太字**` /
 * `[テキスト](URL)` / 裸URL自動リンク / 改行。
 * 先に全体をHTMLエスケープするため、本文由来のタグ注入（XSS）は構造的に不可能。
 *
 * @param {string} body - CSVのbodyカラムの生テキスト
 * @returns {string} - 描画用HTML
 */
function renderNoticeMarkdown(body) {
    const lines = noticeEscapeHtml(body).split(/\r?\n/);
    const parts = [];
    let listItems = [];

    const flushList = () => {
        if (listItems.length > 0) {
            parts.push("<ul>" + listItems.map((t) => `<li>${t}</li>`).join("") + "</ul>");
            listItems = [];
        }
    };

    for (const line of lines) {
        const listMatch = line.match(/^-\s+(.*)$/);
        if (listMatch) {
            listItems.push(noticeInlineMarkdown(listMatch[1]));
            continue;
        }
        flushList();

        const headingMatch = line.match(/^##\s+(.*)$/);
        if (headingMatch) {
            parts.push(`<strong class="notice-heading">${noticeInlineMarkdown(headingMatch[1])}</strong>`);
            continue;
        }
        parts.push(noticeInlineMarkdown(line) + "<br>");
    }
    flushList();
    return parts.join("");
}

/**
 * notices.csv を取得してid降順の配列にする（結果はキャッシュ）。
 *
 * 不正な行（idが整数でない・titleが無い）はスキップして console.warn を出す。
 *
 * @async
 * @returns {Promise<Array<{id: number, date: string, title: string, body: string}>>}
 */
async function loadNotices() {
    if (noticesCache !== null) {
        return noticesCache;
    }
    const rows = await loadCsvAsJson(NOTICE_CSV_URL);
    const notices = [];
    for (const row of rows) {
        const idText = String(row.id ?? "").trim();
        const title = String(row.title ?? "").trim();
        if (!/^\d+$/.test(idText) || !title) {
            console.warn("お知らせCSVの不正な行をスキップ:", row);
            continue;
        }
        notices.push({
            id: parseInt(idText, 10),
            date: row.date ?? "",
            title,
            body: row.body ?? "",
        });
    }
    notices.sort((a, b) => b.id - a.id);
    noticesCache = notices;
    return noticesCache;
}

/**
 * お知らせ一覧をモーダル内に描画する（先頭=最新のみ初期展開）。
 *
 * @param {Array<{id: number, date: string, title: string, body: string}>} notices
 * @returns {void}
 */
function renderNoticeList(notices) {
    const container = document.querySelector("#notice-modal .notice-list");
    if (notices.length === 0) {
        container.innerHTML = '<div class="notice-empty">お知らせはありません</div>';
        return;
    }
    container.innerHTML = notices
        .map(
            (n, i) => `
        <div class="notice-item${i === 0 ? " open" : ""}">
            <button class="notice-header" type="button" aria-expanded="${i === 0}" aria-controls="notice-body-${n.id}">
                <div class="notice-meta">
                    <div class="notice-date">${noticeEscapeHtml(n.date)}</div>
                    <div class="notice-title">${noticeEscapeHtml(n.title)}</div>
                </div>
                <i class="bi bi-chevron-down"></i>
            </button>
            <div class="notice-body" id="notice-body-${n.id}">
                <div class="notice-body-inner">${renderNoticeMarkdown(n.body)}</div>
            </div>
        </div>`
        )
        .join("");

    container.querySelectorAll(".notice-header").forEach((btn) => {
        btn.addEventListener("click", () => {
            const item = btn.closest(".notice-item");
            const open = item.classList.toggle("open");
            btn.setAttribute("aria-expanded", String(open));
        });
    });
}

/**
 * お知らせモーダルを開き、一覧を描画して既読Cookieを更新する。
 *
 * 取得失敗（404含む）時はエラーメッセージを表示する。
 *
 * @async
 * @returns {Promise<void>}
 */
async function openNoticeModal() {
    const container = document.querySelector("#notice-modal .notice-list");
    container.innerHTML = '<div class="notice-empty">読み込み中…</div>';
    noticeModalManager.showModal();
    try {
        const notices = await loadNotices();
        renderNoticeList(notices);
        if (notices.length > 0) {
            setCookie(NOTICE_SEEN_COOKIE, String(notices[0].id));
        }
    } catch (e) {
        console.warn("お知らせの取得に失敗:", e);
        container.innerHTML = '<div class="notice-empty">お知らせを読み込めませんでした</div>';
    }
}

/**
 * 新着お知らせがあれば自動でモーダルを開く。
 *
 * 未読判定: 最大ID > Cookieの既読ID。チュートリアル表示中はスキップ（次回訪問時に表示）。
 * CSV未設置（404）等の取得失敗は静かに無視する。
 *
 * @async
 * @returns {Promise<void>}
 */
async function checkAndAutoOpenNotice() {
    try {
        const notices = await loadNotices();
        if (notices.length === 0) {
            return;
        }
        const seenId = parseInt(getCookie(NOTICE_SEEN_COOKIE) ?? "0", 10) || 0;
        const tutorialShowing = document.querySelector("#tutorial.show") !== null;
        if (notices[0].id > seenId && !tutorialShowing) {
            openNoticeModal();
        }
    } catch {
        // CSV未設置（404）や通信失敗は自動表示しないだけ
    }
}

/**
 * お知らせ機能を初期化する（モーダル・メニュー項目・新着チェック）。
 *
 * @returns {void}
 */
function initializeNotice() {
    const modal = document.querySelector("#notice-modal");
    if (!modal) {
        return;
    }
    noticeModalManager = new ModalManager({ rootSel: "#notice-modal" });
    noticeModalManager.init();

    const menuButton = document.querySelector("#notice-menu-button");
    if (menuButton) {
        menuButton.addEventListener("click", () => {
            // ハンバーガーメニューを閉じてからモーダルを開く
            document.querySelector("#hamburger-menu")?.classList.remove("open");
            document.querySelector("#bottom-menu")?.classList.remove("hamburger-open");
            document
                .querySelector("#hamburger-menu .hamburger-trigger")
                ?.setAttribute("aria-expanded", "false");
            openNoticeModal();
        });
    }

    // チュートリアルの自動表示（common.jsのautoShowDelayMs=800ms）が確実に先に済むよう
    // マージンを取って新着チェックする（表示中ならスキップし、次回訪問時に出す）
    setTimeout(checkAndAutoOpenNotice, 2000);
}

document.addEventListener("DOMContentLoaded", initializeNotice);
