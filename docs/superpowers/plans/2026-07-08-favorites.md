# お気に入り機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** localStorage保存のお気に入り(⭐️)をカード・詳細ページに追加し、カテゴリタブ先頭の「全て/お気に入り」で絞り込めるようにする（仕様: `docs/superpowers/specs/2026-07-08-favorites-design.md`）

**Architecture:** 共通ロジックは新規 `favorites.js`（storage API・ボタン結線・初回注意ダイアログの動的生成）に集約し、ホーム/詳細の両ページから読み込む。一覧の絞り込みは既存 `updateArticleVisible` にお気に入り軸を追加。カードは `<button>` のため☆は `<span role="button">` + stopPropagation。

**Tech Stack:** 素のJS / SCSS（sassコンテナ）/ localStorage

**制約: デプロイしない。**実装+ローカル検証+featureブランチへのコミットまで（mainマージ禁止）

**前提知識:**
- カードは `buildTopicInnerHTML`（`home.js`）のテンプレートで生成される `<button class="article-item">`。フッター左端は空き（日時は右上）
- タブ: `bindCategoryFilter` → `updateTab` → `setActiveTab` + `updateArticleVisible(currentCategory, currentWords)`。同一タブ再クリックで0（全て）へ
- **既存の潜在バグ**: `bindCategoryFilter` の初期化分岐が未定義関数 `filterByCategory` を呼ぶ（現状は初期activeタブが無いため未発火）。「全て」タブに `active` を付けると発火して ReferenceError になるため、本プランで修正する
- `setActiveTab` は `btn.dataset.category === category` の厳密比較（文字列vs数値で不一致になり得る → String化する）
- 詳細ページのscript: `common.js` → `detail.js`（`?v=__ASSET_VERSION__` 付き）。conversation_id はURLクエリ
- 検証: `cd Client && docker compose up` → localhost:8081

---

### Task 1: favorites.js とスタイル

**Files:**
- Create: `Client/public_html_app/javascript/favorites.js`
- Create: `Client/scss/pages/home/_favorites.scss`
- Modify: `Client/scss/pages/home/_index.scss`

- [ ] **Step 1: `favorites.js` を新規作成**

```js
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
 * 追加方向のトグル時は初回注意ダイアログ（一度きり）を表示する。
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
        if (index < 0) {
            showFavoriteNoticeOnce();
        }
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
            toggleFavorite(el.dataset.favoriteCid);
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
 * @returns {void}
 */
function showFavoriteNoticeOnce() {
    try {
        if (localStorage.getItem(FAVORITES_NOTICE_KEY) === "1") {
            return;
        }
        localStorage.setItem(FAVORITES_NOTICE_KEY, "1");
    } catch {
        return;
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
            <button type="button" class="button secondary favorite-notice-ok"><div class="text">OK</div></button>
        </div>`;
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay || e.target.closest(".favorite-notice-ok")) {
            overlay.remove();
        }
    });
    document.body.appendChild(overlay);
}
```

- [ ] **Step 2: `_favorites.scss` を新規作成**

```scss
@use "../../common" as common;

// お気に入り（カードの☆・お気に入りタブ・空状態）
// 仕様: docs/superpowers/specs/2026-07-08-favorites-design.md
body#home {
    .article-footer .favorite-toggle {
        margin-right: auto; // フッター左端（意見/投票は右寄せのまま）

        display: flex;
        align-items: center;
        padding: 4px 6px;

        cursor: pointer;
        pointer-events: all;

        i {
            font-size: var(--font-size-20px);
            color: var(--color-font-light);
        }
    }

    .category-button[data-category="fav"] i {
        margin-right: 4px;
        font-size: var(--font-size-14px);
    }

    .favorites-empty {
        display: none;
        text-align: center;
        color: var(--color-font-dark-secondary);
        padding: 32px 16px;

        &.show {
            display: block;
        }
    }
}

// 初回注意ダイアログ（ホーム/詳細共通のためページスコープなし）
.favorite-notice-overlay {
    position: fixed;
    inset: 0;
    z-index: var(--z-index-grobal-overlay);

    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;

    .favorite-notice-card {
        background: var(--color-light);
        border-radius: 16px;
        padding: 24px 20px;
        max-width: 360px;

        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
        text-align: center;

        .title {
            font-weight: 700;
            color: var(--color-font-dark);
        }
        .text {
            font-size: var(--font-size-14px);
            color: var(--color-font-dark-gray-2);
            line-height: 1.7;
        }
        .favorite-notice-ok {
            border: transparent;
            cursor: pointer;
        }
    }
}
```

- [ ] **Step 3: `_index.scss` に `@forward "favorites";` を追加**（現在5行の末尾に追加して6行に）

- [ ] **Step 4: 検証**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN
node --check Client/public_html_app/javascript/favorites.js && echo JS-OK
cd Client && docker compose run --rm sass sh -lc 'npx --yes sass@1.79.5 --no-source-map /src/style.scss /tmp/check.css && grep -c favorite /tmp/check.css'
```
Expected: `JS-OK` / エラーなし・1以上

- [ ] **Step 5: Commit**

```bash
git add Client/public_html_app/javascript/favorites.js Client/scss/pages/home/_favorites.scss Client/scss/pages/home/_index.scss
git commit -m "feat: お気に入りの共通ロジックとスタイルを追加（localStorage・初回注意ダイアログ）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: ホーム画面の統合（タブ・カード☆・フィルタ）

**Files:**
- Modify: `Client/public_html_app/index.html`
- Modify: `Client/public_html_app/javascript/home.js`

- [ ] **Step 1: index.html — タブ先頭に「全て」「お気に入り」を追加**

`.category-tab-wrapper` 内、`data-category=1` の前に:

```html
                        <button class="category-button active" data-category=0>全て</button>
                        <button class="category-button" data-category="fav"><i class="bi bi-star-fill"></i>お気に入り</button>
```

- [ ] **Step 2: index.html — 空状態メッセージとscript追加**

`<div class="article-container">`（閉じタグ含む2行）の直後に:

```html
        <div class="favorites-empty">お気に入りはまだありません。カードの☆で追加できます</div>
```

scriptタグ列の `common.js` の直後（`home.js` の前）に:

```html
    <script src="./javascript/favorites.js?v=__ASSET_VERSION__" defer></script>
```

- [ ] **Step 3: home.js — カードテンプレートに☆と data-cid を追加**

`buildTopicInnerHTML` のテンプレートで、`<button class="article-item"` の開始タグに `data-cid="${esc(conversationId)}"` を追加（`data-updated="..."` の後）。

`<div class="article-footer">` の直後（`.article-opinion-group` の前）に:

```js
                    <span class="favorite-toggle" role="button" tabindex="0" aria-label="お気に入り" data-favorite-cid="${esc(conversationId)}">
                        <i class="bi bi-star"></i>
                    </span>
```

- [ ] **Step 4: home.js — フィルタにお気に入り軸を追加**

`updateArticleVisible` 内の判定部:

```js
        const categoryMatch = (item.dataset.category === categoryId) || categoryId == 0; //0の場合はカテゴリ指定なし

        if (categoryMatch & searchWordMatch) {
```
を
```js
        // "fav" はカテゴリ横断でお気に入りのみ表示
        const favoritesMatch = categoryId !== "fav" || getFavorites().includes(item.dataset.cid);
        const categoryMatch = categoryId === "fav" || (item.dataset.category === categoryId) || categoryId == 0; //0の場合はカテゴリ指定なし

        if (categoryMatch && searchWordMatch && favoritesMatch) {
```
に変更。さらに `forEach` ループの直後（関数末尾）に空状態の切替を追加:

```js
    // お気に入りタブで0件のときだけ空状態メッセージを表示
    const empty = document.querySelector(".favorites-empty");
    if (empty) {
        const anyVisible = [...articles].some((item) => item.classList.contains("show"));
        empty.classList.toggle("show", categoryId === "fav" && !anyVisible);
    }
```

- [ ] **Step 5: home.js — タブ初期化まわりの修正（既存バグ対応込み）**

`setActiveTab` の比較をString化:

```js
        btn.classList.toggle('active', String(btn.dataset.category) === String(category))
```

`bindCategoryFilter` 内の初期化分岐（未定義の `filterByCategory` を呼ぶ既存の潜在バグ）:

```js
    // 初期表示
    const initialActive = document.querySelector('.category-button.active[data-category]');
    if (initialActive) {
        filterByCategory(initialActive.dataset.category);
    }
```
を
```js
    // 初期表示（マークアップ上のactiveタブを現在カテゴリとして採用）
    const initialActive = document.querySelector('.category-button.active[data-category]');
    if (initialActive) {
        currentCategory = initialActive.dataset.category;
    }
```
に変更。

- [ ] **Step 6: home.js — 結線と再フィルタ**

`DOMContentLoaded` ハンドラの `bindPageReturn();` の直後に追加:

```js
    bindFavoriteButtons();

    // お気に入りタブ表示中に☆を外したら即座に一覧へ反映する
    document.addEventListener("favorites:changed", () => {
        if (currentCategory === "fav") {
            updateArticleVisible(currentCategory, currentWords);
        }
    });
```

- [ ] **Step 7: 検証**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN
node --check Client/public_html_app/javascript/home.js && echo JS-OK
cd Client && docker compose up -d web-app && sleep 2
curl -s http://localhost:8081/ | grep -c 'data-category=0\|data-category="fav"\|favorites.js\|favorites-empty'
```
Expected: `JS-OK` / `4`

- [ ] **Step 8: Commit**

```bash
git add Client/public_html_app/index.html Client/public_html_app/javascript/home.js
git commit -m "feat: ホーム画面にお気に入りタブ・カード☆・絞り込みを追加

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 詳細ページの統合

**Files:**
- Modify: `Client/public_html_app/detail/index.html`
- Modify: `Client/public_html_app/javascript/detail.js`

- [ ] **Step 1: detail/index.html — ボタンとscript追加**

`bottom-menu-button-group` 内、`share-button` の**前**に:

```html
            <button class="favorite-button button secondary" aria-label="お気に入り">
                <i class="bi bi-star"></i>
            </button>
```

scriptタグ列の `common.js` の直後（`detail.js` の前）に:

```html
    <script src="/javascript/favorites.js?v=__ASSET_VERSION__" defer></script>
```

- [ ] **Step 2: detail.js — 初期化を追加**

ファイル内の関数定義群の末尾（既存 `DOMContentLoaded` リスナーの前）に:

```js
/**
 * お気に入りボタンを初期化する。
 *
 * URLの conversation_id を対象に favorites.js の共通結線を使う。
 * conversation_id が無い場合はボタンを非表示にする。
 *
 * 依存: bindFavoriteButtons（favorites.js）
 *
 * @returns {void}
 */
function initializeFavoriteButton() {
    const button = document.querySelector(".favorite-button");
    if (!button) {
        return;
    }
    const conversationId = new URLSearchParams(location.search).get("conversation_id");
    if (!conversationId) {
        button.style.display = "none";
        return;
    }
    button.dataset.favoriteCid = conversationId;
    bindFavoriteButtons();
}
```

既存の `DOMContentLoaded` リスナー内（初期化呼び出し群の末尾）に `initializeFavoriteButton();` を1行追加。

- [ ] **Step 3: 検証**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN
node --check Client/public_html_app/javascript/detail.js && echo JS-OK
curl -s http://localhost:8081/detail/ | grep -c "favorite-button\|favorites.js"
```
Expected: `JS-OK` / `2`

- [ ] **Step 4: Commit**

```bash
git add Client/public_html_app/detail/index.html Client/public_html_app/javascript/detail.js
git commit -m "feat: テーマ詳細ページにお気に入りボタンを追加

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: ブラウザ総合検証（コントローラー実施・デプロイしない）

**Files:** なし（style.css再生成のコミットのみ）

puppeteerで以下を実測+スクリーンショット目視（390px/320px）:

1. カードの☆タップ → `bi-star-fill` 化・localStorageに保存・**カード遷移しない**
2. 初回タップで注意ダイアログが表示され、OKで閉じる。2回目以降は出ない（ホーム/詳細どちらが先でも一度きり）
3. リロード後も★が保持される
4. 「お気に入り」タブで絞り込み・検索との併用・0件時の空状態メッセージ
5. お気に入りタブ表示中に★解除 → カードが即座に消える
6. 「全て」タブがデフォルトで選択状態・タブの排他動作（既存カテゴリ含む）が正常
7. 詳細ページの★とホームの状態同期（詳細で追加→ホームの一覧に反映）
8. 既存機能の回帰: ソート・検索・日時表示・ハンバーガー・お知らせが正常

最後に style.css×3 の再生成をコミットし、**mainへはマージしない**。報告には localhost での確認手順を含める

---

## 備考

- `favorites.js` のグローバル関数は `Favorite`/`favorites` 系の命名で、既存グローバル（common/home/create/detail/notice）と衝突しないこと（実装時にgrepで確認）
- カード内の☆は `<span role="button">`（`<button>` の入れ子は不正HTMLのため）。Enterキー操作は対象外（タッチ主体のUI。既存カードもbutton内テキストのみ）
