// ==============================
// お知らせ機能（HTMLファイル + レジストリ駆動）
// 仕様: docs/superpowers/specs/2026-07-08-notice-feature-design.md
// ==============================

/**
 * お知らせ一覧（この配列の順序がそのまま表示順。通常は新しいものを上に追加していく）。
 *
 * id: 増分整数（既読判定に使用。必ず過去より大きい値を振ること。表示順には影響しない）
 * path: 本文HTML（フラグメント）のパス。取得時に ?v=<id> がキャッシュバスターとして付く
 */
const NOTICES = [
    { id: 4, date: "2026-07-09", title: "お気に入り機能を追加しました", path: "./notice/004-favorites.html" },
    { id: 5, date: "2026-07-09", title: "改善要望を募集しています", path: "./notice/005-feedback.html" },
    { id: 3, date: "2026-07-08", title: "アクセス障害と復旧のお知らせ", path: "./notice/003-incident-recovery.html" },
    { id: 2, date: "2026-07-08", title: "テーマ一覧に並び替えと日時表示を追加しました", path: "./notice/002-sort-and-dates.html" },
    { id: 1, date: "2026-07-08", title: "お知らせ機能を追加しました", path: "./notice/001-release.html" },
];

/** 既読の最大お知らせIDを保存するCookie名 */
const NOTICE_SEEN_COOKIE = "notice_last_seen_id";

/** お知らせモーダルのManager */
let noticeModalManager = null;

/** 本文HTMLの取得結果キャッシュ（id → HTML文字列） */
const noticeBodyCache = new Map();

/**
 * 表示順（配列の記載順）のお知らせ一覧を返す。
 *
 * @returns {Array<{id: number, date: string, title: string, path: string}>}
 */
function getDisplayNotices() {
    return [...NOTICES];
}

/**
 * 既読判定用の最大お知らせIDを返す（お知らせが無い場合は0）。
 *
 * @returns {number}
 */
function getMaxNoticeId() {
    return NOTICES.reduce((max, n) => Math.max(max, n.id), 0);
}

/**
 * お知らせ本文HTMLを取得する（結果はキャッシュ）。
 *
 * @async
 * @param {{id: number, path: string}} notice - レジストリのエントリ
 * @returns {Promise<string>} - 本文HTML（フラグメント）
 */
async function fetchNoticeBody(notice) {
    if (noticeBodyCache.has(notice.id)) {
        return noticeBodyCache.get(notice.id);
    }
    const res = await fetch(`${notice.path}?v=${notice.id}`, { cache: "no-store" });
    if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
    }
    const html = await res.text();
    noticeBodyCache.set(notice.id, html);
    return html;
}

/**
 * お知らせ一覧をモーダル内に描画し、本文を並列で読み込む。
 *
 * 一覧・タイトル・日付はリポジトリ管理のレジストリ由来（第一者コンテンツ）のため
 * サニタイズはしない。先頭（最新）のみ初期展開。
 *
 * @returns {void}
 */
function renderNoticeList() {
    const container = document.querySelector("#notice-modal .notice-list");
    const notices = getDisplayNotices();
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
                    <div class="notice-date">${n.date}</div>
                    <div class="notice-title">${n.title}</div>
                </div>
                <i class="bi bi-chevron-down"></i>
            </button>
            <div class="notice-body" id="notice-body-${n.id}">
                <div class="notice-body-inner"></div>
            </div>
        </div>`
        )
        .join("");

    // アコーディオン開閉
    container.querySelectorAll(".notice-header").forEach((btn) => {
        btn.addEventListener("click", () => {
            const item = btn.closest(".notice-item");
            const open = item.classList.toggle("open");
            btn.setAttribute("aria-expanded", String(open));
        });
    });

    // 本文を並列で読み込んで流し込む（失敗した項目のみエラー表示）
    notices.forEach(async (n) => {
        const inner = container.querySelector(`#notice-body-${n.id} .notice-body-inner`);
        try {
            inner.innerHTML = await fetchNoticeBody(n);
        } catch (e) {
            console.warn("お知らせ本文の取得に失敗:", n.path, e);
            inner.innerHTML = '<p class="notice-error">読み込めませんでした</p>';
        }
    });
}

/**
 * お知らせモーダルを開き、既読Cookieを最新IDへ更新する。
 *
 * @returns {void}
 */
function openNoticeModal() {
    renderNoticeList();
    noticeModalManager.showModal();
    const maxId = getMaxNoticeId();
    if (maxId > 0) {
        setCookie(NOTICE_SEEN_COOKIE, String(maxId));
    }
}

/**
 * 新着お知らせがあれば自動でモーダルを開く。
 *
 * 未読判定: 最大ID > Cookieの既読ID。
 * チュートリアル表示中は、閉じられるのを待ってから続けて表示する
 * （閉じずに離脱した場合は次回訪問時に表示）。
 *
 * @returns {void}
 */
function checkAndAutoOpenNotice() {
    const maxId = getMaxNoticeId();
    if (maxId === 0) {
        return;
    }
    const seenId = parseInt(getCookie(NOTICE_SEEN_COOKIE) ?? "0", 10) || 0;
    if (maxId <= seenId) {
        return;
    }

    const tutorial = document.querySelector("#tutorial");
    if (tutorial && tutorial.classList.contains("show")) {
        // チュートリアルが閉じたら（.showが外れたら）少し間を置いて表示する
        const observer = new MutationObserver(() => {
            if (!tutorial.classList.contains("show")) {
                observer.disconnect();
                setTimeout(openNoticeModal, 400);
            }
        });
        observer.observe(tutorial, { attributes: true, attributeFilter: ["class"] });
        return;
    }
    openNoticeModal();
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
