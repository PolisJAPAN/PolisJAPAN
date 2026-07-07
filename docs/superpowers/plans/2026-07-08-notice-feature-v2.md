# お知らせ機能 v2 Implementation Plan（HTMLファイル方式への改訂）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v1のCSV+Markdown方式を、リポジトリ内HTMLファイル+JSレジストリ方式に置き換える（仕様v2: `docs/superpowers/specs/2026-07-08-notice-feature-design.md`）

**Architecture:** `notice.js` 冒頭の配列 `NOTICES` が一覧の源。本文は `public_html_app/notice/*.html`（フラグメント）をfetchして `.notice-body-inner` に挿入。モーダル・アコーディオン・Cookie既読・自動表示はv1実装を踏襲。HTML/モーダルのマークアップ（Task 2実装済み）とアコーディオンSCSSは変更不要

**Tech Stack:** 素のJS / SCSS。CSV・Markdownパーサは削除

**前提（実装済みで変更しないもの）:**
- `index.html` の `#notice-modal`・`#notice-menu-button`・scriptタグ（コミット05fe7c1）
- `_notice.scss` のアコーディオン骨格（124cf49）・`_hamburger.scss`（b95227fまで）
- v1の `notice.js`（f2e2135）は**全面書き換え**の対象

---

### Task 1: notice.js 全面書き換え + 初回お知らせHTML

**Files:**
- Rewrite: `Client/public_html_app/javascript/notice.js`
- Create: `Client/public_html_app/notice/001-release.html`

- [ ] **Step 1: `notice.js` を以下の内容で全面置き換え**

```js
// ==============================
// お知らせ機能（HTMLファイル + レジストリ駆動）
// 仕様: docs/superpowers/specs/2026-07-08-notice-feature-design.md
// ==============================

/**
 * お知らせ一覧（新しいものを上に追加していく）。
 *
 * id: 増分整数（既読判定に使用。必ず過去より大きい値を振ること）
 * path: 本文HTML（フラグメント）のパス。取得時に ?v=<id> がキャッシュバスターとして付く
 */
const NOTICES = [
    { id: 1, date: "2026-07-08", title: "お知らせ機能を追加しました", path: "./notice/001-release.html" },
];

/** 既読の最大お知らせIDを保存するCookie名 */
const NOTICE_SEEN_COOKIE = "notice_last_seen_id";

/** お知らせモーダルのManager */
let noticeModalManager = null;

/** 本文HTMLの取得結果キャッシュ（id → HTML文字列） */
const noticeBodyCache = new Map();

/**
 * id降順に並べたお知らせ一覧を返す。
 *
 * @returns {Array<{id: number, date: string, title: string, path: string}>}
 */
function getSortedNotices() {
    return [...NOTICES].sort((a, b) => b.id - a.id);
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
    const notices = getSortedNotices();
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
    const notices = getSortedNotices();
    if (notices.length > 0) {
        setCookie(NOTICE_SEEN_COOKIE, String(notices[0].id));
    }
}

/**
 * 新着お知らせがあれば自動でモーダルを開く。
 *
 * 未読判定: 最大ID > Cookieの既読ID。チュートリアル表示中はスキップ（次回訪問時に表示）。
 *
 * @returns {void}
 */
function checkAndAutoOpenNotice() {
    const notices = getSortedNotices();
    if (notices.length === 0) {
        return;
    }
    const seenId = parseInt(getCookie(NOTICE_SEEN_COOKIE) ?? "0", 10) || 0;
    const tutorialShowing = document.querySelector("#tutorial.show") !== null;
    if (notices[0].id > seenId && !tutorialShowing) {
        openNoticeModal();
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
```

- [ ] **Step 2: 初回お知らせ `Client/public_html_app/notice/001-release.html` を新規作成**

既製スタイルの実例を兼ねる（フラグメント。DOCTYPE等は書かない）:

```html
<p>Polis JAPANに<strong>お知らせ機能</strong>が追加されました。今後、新機能やメンテナンスの情報をここでお伝えします。</p>
<h3>使い方</h3>
<ul>
    <li>右下のメニューボタン → 「お知らせ」でいつでも開けます</li>
    <li>新しいお知らせがあるときは自動で表示されます</li>
</ul>
<div class="notice-box">
    ご意見・不具合のご報告は<a href="https://pol-is.jp/contact/" target="_blank" rel="noopener noreferrer">お問い合わせ</a>からお寄せください。
</div>
```

- [ ] **Step 3: 検証**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN
node --check Client/public_html_app/javascript/notice.js && echo JS-OK
grep -c "loadCsvAsJson\|renderNoticeMarkdown\|noticeEscapeHtml" Client/public_html_app/javascript/notice.js || echo CSV-MD-REMOVED
cd Client && docker compose up -d web-app && sleep 2
curl -s -o /dev/null -w "notice html: %{http_code}\n" "http://localhost:8081/notice/001-release.html?v=1"
```
Expected: `JS-OK`、`CSV-MD-REMOVED`（旧方式の残骸ゼロ）、`notice html: 200`

- [ ] **Step 4: Commit**

```bash
git add Client/public_html_app/javascript/notice.js Client/public_html_app/notice/001-release.html
git commit -m "refactor: お知らせをHTMLファイル+レジストリ方式に変更（CSV+Markdown廃止）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 本文用の既製スタイル追加

**Files:**
- Modify: `Client/scss/pages/home/_notice.scss`

- [ ] **Step 1: `.notice-body-inner` の中身を既製スタイルに置き換え**

現在の `.notice-body-inner` 内のコンテンツ向け定義:

```scss
                a {
                    color: var(--color-main);
                    text-decoration: underline;
                    word-break: break-all;
                }
                ul {
                    padding-left: 1.2em;
                    margin: 4px 0;
                }
                .notice-heading {
                    display: block;
                    margin: 8px 0 2px;
                    color: var(--color-font-dark);
                }
```

を以下に置き換える（`.notice-heading` はMarkdown廃止に伴い削除）:

```scss
                // ---- 本文用の既製スタイル（お知らせHTMLはタグ+少数クラスで書ける） ----
                p {
                    margin: 0 0 8px;
                }
                h3 {
                    font-size: var(--font-size-14px);
                    font-weight: 700;
                    color: var(--color-font-dark);
                    margin: 12px 0 4px;
                }
                ul, ol {
                    padding-left: 1.4em;
                    margin: 4px 0 8px;
                }
                li {
                    margin: 2px 0;
                }
                a {
                    color: var(--color-main);
                    text-decoration: underline;
                    word-break: break-all;
                }
                strong {
                    color: var(--color-font-dark);
                }
                img {
                    width: 100%;
                    height: auto;
                    border-radius: 16px;
                    margin: 4px 0 8px;
                }
                // 補足・注意用の囲みボックス
                .notice-box {
                    background-color: var(--color-light);
                    border-radius: 12px;
                    padding: 10px 12px;
                    margin: 8px 0;
                    font-size: var(--font-size-12px);
                }
                // ボタン風リンク（既存 .button.secondary と同トーン）
                .notice-button {
                    display: flex;
                    width: fit-content;
                    align-items: center;
                    gap: 8px;

                    background-color: var(--color-dark);
                    color: var(--color-font-light);
                    border-radius: 32px;
                    padding: 10px 20px;
                    margin: 8px 0;

                    font-weight: 600;
                    text-decoration: none;
                }
                .notice-error {
                    color: var(--color-font-dark-secondary);
                }
```

- [ ] **Step 2: コンパイル確認**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN/Client && docker compose run --rm sass sh -lc 'npx --yes sass@1.79.5 --no-source-map /src/style.scss /tmp/check.css && grep -c "notice-box\|notice-button" /tmp/check.css'
```
Expected: エラーなし、2以上

- [ ] **Step 3: Commit**

```bash
git add Client/scss/pages/home/_notice.scss
git commit -m "feat: お知らせ本文用の既製スタイルを追加（見出し・リスト・画像・囲み・ボタン風リンク）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 総合ブラウザ検証（puppeteer・本番無反映）

**Files:** なし（検証のみ + style.css再生成コミット。微調整は該当ファイル修正+追いコミット）

- [ ] **Step 1: フル起動**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN/Client && docker compose up -d
```
sassの再コンパイルを待つ（style.cssのmd5変化で確認）。

- [ ] **Step 2: puppeteerで自動検証**（scratchpadに puppeteer-core 導入済み。チュートリアル抑制は Cookie `tutorial_optout=1`）

1. **新着自動表示**: 初回訪問（notice Cookie無し）→ 2秒強待ち → `#notice-modal.show` が付く
2. **初期展開**: `.notice-item` が1件で `.open`、本文に `001-release.html` の内容（`notice-box` 等）が挿入されている
3. **Cookie更新**: `notice_last_seen_id=1` が付与される
4. **既読なら自動表示しない**: リロード → 2.5秒待っても `.show` が付かない
5. **メニューから開く**: ハンバーガー開 → 「お知らせ」タップ → メニューが閉じモーダルが開く。文字サイズがaの項目と揃っている（fontWeight 600 / 14px）
6. **アコーディオン開閉**: ヘッダークリックで `.open` トグルと `aria-expanded` 反転、シェブロン回転
7. **fetch失敗経路**: page.evaluateで `NOTICES` に存在しないpathのエントリを一時追加して `renderNoticeList()` を再実行 → 該当項目のみ「読み込めませんでした」
8. **チュートリアル併存**: Cookie全消しの新コンテキスト → `#tutorial.show` があり `#notice-modal.show` は付かない
9. スクリーンショット（モバイル390px・モーダル表示状態）を撮り**目視確認**（既製スタイルの見た目・notice-boxの質感）

- [ ] **Step 3: style.css再生成のコミットと完了報告**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN/Client
git status --short   # style.css×3 のみのはず
git add public_html/style.css public_html_app/style.css public_html_admin/style.css
git commit -m "build: お知らせ機能に伴うstyle.css再生成

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

完了報告には「お知らせの追加手順」（HTML作成→NOTICES配列に追記→マージ）を含める。mainマージはスコープ外

---

## 備考

- v1プラン（2026-07-08-notice-feature.md）のTask 4（nginxのnotices.csvローカル経路）は**中止**。HTMLはリポジトリ内なのでローカル配信がそのまま機能する
- 本文HTMLは第一者コンテンツ（リポジトリ管理・レビューを通る）のためサニタイズ不要。外部入力は一切流入しない
