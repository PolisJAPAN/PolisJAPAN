// ==============================
// お気に入り機能（localStorage駆動・ホーム/詳細共通）
// 仕様: docs/superpowers/specs/2026-07-08-favorites-design.md
// ==============================

/** お気に入りのconversation_id配列を保存するlocalStorageキー */
const FAVORITES_STORAGE_KEY = "favorite_conversations";

/** 初回注意ダイアログ表示済みフラグのlocalStorageキー */
const FAVORITES_NOTICE_KEY = "favorite_notice_shown";

/**
 * お気に入りのconversation_id配列を取得する。
 *
 * localStorage不可・値が壊れている場合は空配列（機能を黙って無効化）。
 *
 * @returns {string[]} - conversation_idの配列
 */
function getFavorites() {
    try {
        const raw = localStorage.getItem(FAVORITES_STORAGE_KEY);
        const list = raw ? JSON.parse(raw) : [];
        return Array.isArray(list) ? list : [];
    } catch {
        return [];
    }
}

/**
 * 指定のconversation_idがお気に入りか判定する。
 *
 * @param {string} cid - conversation_id
 * @returns {boolean}
 */
function isFavorite(cid) {
    return getFavorites().includes(String(cid));
}

/**
 * お気に入りをトグルし、トグル後の状態を返す。
 *
 * localStorage不可時は状態を変えず現状を返す。
 *
 * @param {string} cid - conversation_id
 * @returns {boolean} - トグル後にお気に入りなら true
 */
function toggleFavorite(cid) {
    const id = String(cid);
    try {
        const list = getFavorites();
        const index = list.indexOf(id);
        if (index >= 0) {
            list.splice(index, 1);
        } else {
            list.push(id);
        }
        localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(list));
        return index < 0;
    } catch {
        return isFavorite(id);
    }
}

/**
 * お気に入りボタンの見た目（星アイコン・aria-pressed）を現状態に同期する。
 *
 * @param {HTMLElement} el - data-favorite-cid を持つ要素
 * @returns {void}
 */
function updateFavoriteButtonView(el) {
    const active = isFavorite(el.dataset.favoriteCid);
    el.setAttribute("aria-pressed", String(active));
    const icon = el.querySelector("i");
    if (icon) {
        icon.classList.toggle("bi-star-fill", active);
        icon.classList.toggle("bi-star", !active);
    }
}

/**
 * `[data-favorite-cid]` 要素にお気に入りトグルを結線する（多重結線は防止）。
 *
 * クリックはカード遷移等に伝播させない。トグル後は同一cidの全ボタンを同期し、
 * `favorites:changed` イベントをdocumentへ発火する（一覧の再フィルタ用）。
 *
 * @param {ParentNode} [root=document] - 走査ルート
 * @returns {void}
 */
function bindFavoriteButtons(root = document) {
    root.querySelectorAll("[data-favorite-cid]").forEach((el) => {
        if (el.dataset.favoriteBound === "1") {
            return;
        }
        el.dataset.favoriteBound = "1";
        updateFavoriteButtonView(el);
        el.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            const added = toggleFavorite(el.dataset.favoriteCid);
            if (added && !showFavoriteNoticeOnce()) {
                // 初回ダイアログを出さなかった場合（2回目以降）はトーストで通知する
                showFavoriteToast("お気に入りに追加しました");
            }
            document
                .querySelectorAll(`[data-favorite-cid="${el.dataset.favoriteCid}"]`)
                .forEach(updateFavoriteButtonView);
            document.dispatchEvent(new CustomEvent("favorites:changed"));
        });
    });
}

/**
 * 初回のお気に入り追加時に、ブラウザ内保存であることの注意ダイアログを一度だけ表示する。
 *
 * @returns {boolean} ダイアログを表示した場合は true（表示済み・保存不可の場合は false）
 */
function showFavoriteNoticeOnce() {
    try {
        if (localStorage.getItem(FAVORITES_NOTICE_KEY) === "1") {
            return false;
        }
    } catch {
        return false;
    }
    const overlay = document.createElement("div");
    overlay.className = "favorite-notice-overlay";
    overlay.innerHTML = `
        <div class="favorite-notice-card" role="dialog" aria-label="お気に入りの保存について">
            <div class="title"><i class="bi bi-star-fill"></i> お気に入りに追加しました</div>
            <div class="text">
                お気に入りは<strong>このブラウザ内</strong>に保存されます。<br>
                端末やブラウザを変えた場合や、プライベートブラウズでは引き継がれません。
            </div>
            <button type="button" class="button secondary favorite-notice-ok"><i class="bi bi-check-lg"></i><div class="text">OK</div></button>
        </div>`;
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay || e.target.closest(".favorite-notice-ok")) {
            overlay.remove();
        }
    });
    document.body.appendChild(overlay);
    // 表示に成功してから既読化する（表示失敗時に二度と出なくなるのを防ぐ）
    try {
        localStorage.setItem(FAVORITES_NOTICE_KEY, "1");
    } catch {
        // 保存できない環境では毎回表示されるが許容
    }
    return true;
}

let favoriteToastTimer = null;

/**
 * 画面下部（ボタンの上あたり）に通知トーストをフェードイン表示する。
 * 連続タップ時は同じトーストを使い回して表示時間を延長する。
 *
 * @param {string} message 表示するメッセージ
 * @returns {void}
 */
function showFavoriteToast(message) {
    let toast = document.querySelector(".favorite-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.className = "favorite-toast";
        toast.innerHTML = `<i class="bi bi-star-fill"></i><div class="text"></div>`;
        document.body.appendChild(toast);
    }
    toast.querySelector(".text").textContent = message;
    // 非表示→表示を確実にトランジションさせる（追加直後の同フレーム適用を避ける）
    requestAnimationFrame(() => toast.classList.add("show"));
    clearTimeout(favoriteToastTimer);
    favoriteToastTimer = setTimeout(() => toast.classList.remove("show"), 2000);
}
