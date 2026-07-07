# お知らせ機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** S3の `csv/notices.csv` を読み取り、ハンバーガーメニューから開くスライドモーダルにお知らせをアコーディオン表示する。新着があれば自動表示（仕様: `docs/superpowers/specs/2026-07-08-notice-feature-design.md`）

**Architecture:** 静的HTML+SCSS+素のJS。既存部品を最大限流用する — `loadCsvAsJson`（5分キャッシュバスター付きCSV取得）、`ModalManager`（スライドモーダル開閉）、`setCookie`/`getCookie`。Markdownは「先に全HTMLエスケープ→サブセット記法のみタグ化」の安全設計で自前実装（ライブラリなし）

**Tech Stack:** SCSS（sassコンテナ自動コンパイル）、Bootstrap Icons、puppeteer-core（検証用・scratchpadに導入済み）

**前提知識:**
- 検証: `cd Client && docker compose up` → http://localhost:8081/（`docs/クライアント動作確認ガイド.md`）
- `loadCsvAsJson(url)` は ヘッダー行をキーにしたオブジェクト配列を返す（`common.js:311`）。BOMはTextDecoderが除去。`parseCSV` は引用符内の改行・カンマ・`""` に対応
- `ModalManager`: `new ModalManager({rootSel})` → `.init()` → `.showModal()`/`.closeModal()`。背景クリックで閉じる機構も内蔵（`common.js:734`）
- `setCookie(name, value, days=365)` / `getCookie(name)`（`common.js:20,32`）
- ハンバーガーメニュー: `#hamburger-menu`（`.open`）と `#bottom-menu`（`.hamburger-open`）のクラスで開閉。パネルの開時サイズは `_hamburger.scss` の `&.open .hamburger-panel { height: 150px }`
- チュートリアル表示中は `#tutorial` に `.show` が付く。ヘッドレス検証時のチュートリアル抑制は **Cookie** `tutorial_optout=1`（localStorageではない）

---

### Task 1: notice.js（取得・Markdown・描画・自動表示）

**Files:**
- Create: `Client/public_html_app/javascript/notice.js`

- [ ] **Step 1: `notice.js` を新規作成**

以下の内容をそのまま作成する:

```js
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
    // **太字**
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // 裸URLの自動リンク（生成済みタグの中は触らないよう、タグ以外の部分にだけ適用）
    text = text
        .split(/(<[^>]+>)/)
        .map((seg) =>
            seg.startsWith("<")
                ? seg
                : seg.replace(
                      /(https?:\/\/[^\s<]+)/g,
                      '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
                  )
        )
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
        if (!/^\d+$/.test(idText) || !row.title) {
            console.warn("お知らせCSVの不正な行をスキップ:", row);
            continue;
        }
        notices.push({
            id: parseInt(idText, 10),
            date: row.date ?? "",
            title: row.title,
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

    // チュートリアルの表示判定（home.jsのinitializeTutorial）が終わってから新着チェックする
    setTimeout(checkAndAutoOpenNotice, 1000);
}

document.addEventListener("DOMContentLoaded", initializeNotice);
```

- [ ] **Step 2: 構文確認**

Run: `node --check Client/public_html_app/javascript/notice.js && echo OK`
Expected: `OK`

- [ ] **Step 3: Markdown変換の単体テスト（nodeで純関数のみ検証）**

Run:
```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN && node -e '
const src = require("fs").readFileSync("Client/public_html_app/javascript/notice.js", "utf8");
// DOM非依存の純関数部分だけ評価する（document行以降を除去）
const pure = src.split("async function loadNotices")[0];
eval(pure);
const out = renderNoticeMarkdown("## 見出し\n**太字**と[リンク](https://pol-is.jp/)\n- 項目1\n- 項目2 https://example.com\n<script>alert(1)</script>");
console.log(out);
const ok = out.includes("notice-heading")
  && out.includes("<strong>太字</strong>")
  && out.includes("href=\"https://pol-is.jp/\"")
  && out.includes("<ul><li>項目1</li>")
  && out.includes("href=\"https://example.com\"")
  && !out.includes("<script")
  && out.includes("&lt;script&gt;");
console.log(ok ? "MARKDOWN-OK" : "MARKDOWN-NG");
process.exit(ok ? 0 : 1);
'
```
Expected: 変換結果の後に `MARKDOWN-OK`

- [ ] **Step 4: Commit**

```bash
git add Client/public_html_app/javascript/notice.js
git commit -m "feat: お知らせ機能のJSを追加（CSV取得・Markdownサブセット・新着自動表示）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: HTMLマークアップ（モーダル・メニュー項目・script読み込み）

**Files:**
- Modify: `Client/public_html_app/index.html`

- [ ] **Step 1: ハンバーガーメニューに「お知らせ」を追加**

`.panel-inner` 内、「お問い合わせ」`<a>` の**直前**に以下を挿入する:

```html
                    <button id="notice-menu-button" class="menu-item" type="button">
                        <i class="bi bi-bell"></i>
                        <div class="text">お知らせ</div>
                    </button>
```

- [ ] **Step 2: お知らせモーダルを追加**

`#theme-create-modal`（`</div>` で閉じる箇所、`#loading-overlay` の前）の後に以下を挿入する:

```html
    <div id="notice-modal" class="slide-modal full-screen-modal">
        <div class="label-group">
            <div class="label-header">
                <button class="modal-close-button">
                    <i class="bi bi-x"></i>
                </button>
                <div class="modal-title">お知らせ</div>
            </div>
            <div class="modal-text">Polis JAPANからのお知らせ</div>
        </div>
        <div class="modal-window">
            <div class="modal-scroll-area">
                <div class="modal-content">
                    <div class="notice-list"></div>
                </div>
            </div>
        </div>
    </div>
```

- [ ] **Step 3: scriptタグを追加**

`<script src="./javascript/create.js" defer></script>` の直後に:

```html
    <script src="./javascript/notice.js" defer></script>
```

- [ ] **Step 4: 配信確認**

Run:
```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN/Client && docker compose up -d web-app && sleep 2 \
  && curl -s http://localhost:8081/ | grep -c "notice-modal\|notice-menu-button\|notice.js"
```
Expected: `3`

- [ ] **Step 5: Commit**

```bash
git add Client/public_html_app/index.html
git commit -m "feat: お知らせモーダルとメニュー項目のマークアップを追加

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: SCSS（アコーディオン・パネル高さ拡張・buttonリセット）

**Files:**
- Create: `Client/scss/pages/home/_notice.scss`
- Modify: `Client/scss/pages/home/_index.scss`
- Modify: `Client/scss/pages/home/_hamburger.scss`（パネル開時高さ 150px → 196px）

- [ ] **Step 1: `_notice.scss` を新規作成**

```scss
@use "../../common" as common;

// お知らせモーダル（アコーディオンリスト）
// 仕様: docs/superpowers/specs/2026-07-08-notice-feature-design.md
#notice-modal {
    .notice-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .notice-item {
        background-color: var(--color-bg-gray);
        border-radius: 16px;
        overflow: hidden;

        .notice-header {
            width: 100%;
            display: flex;
            flex-direction: row;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 14px 16px;

            background: none;
            border: none;
            font: inherit;
            text-align: left;
            cursor: pointer;

            .notice-meta {
                min-width: 0;
            }
            .notice-date {
                font-size: var(--font-size-12px);
                color: var(--color-font-dark-secondary);
            }
            .notice-title {
                font-size: var(--font-size-14px);
                font-weight: 600;
                color: var(--color-font-dark);
            }
            i {
                flex: none;
                color: var(--color-font-dark-gray);
                transition: transform 0.25s;
            }
        }

        // 開閉は grid-template-rows の 0fr/1fr トランジション（高さ自動対応）
        .notice-body {
            display: grid;
            grid-template-rows: 0fr;
            transition: grid-template-rows 0.3s ease;

            .notice-body-inner {
                overflow: hidden;
                padding: 0 16px;
                font-size: var(--font-size-14px);
                color: var(--color-font-dark-gray-2);
                line-height: 1.7;

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
            }
        }

        &.open {
            .notice-header i {
                transform: rotate(180deg);
            }
            .notice-body {
                grid-template-rows: 1fr;
            }
            .notice-body .notice-body-inner {
                padding-bottom: 14px;
            }
        }
    }

    .notice-empty {
        text-align: center;
        color: var(--color-font-dark-secondary);
        padding: 24px 0;
    }
}

@media (prefers-reduced-motion: reduce) {
    #notice-modal .notice-item {
        .notice-body,
        .notice-header i {
            transition: none;
        }
    }
}
```

- [ ] **Step 2: `_index.scss` に追加**

`Client/scss/pages/home/_index.scss` を以下にする:

```scss
@forward "app";
@forward "menu";
@forward "create";
@forward "hamburger";
@forward "notice";
```

- [ ] **Step 3: `_hamburger.scss` の調整2点**

(a) パネル開時の高さを拡張（項目が2→3段になるため）。`&.open` 内の:

```scss
        .hamburger-panel {
            width: $panel-width;
            height: 150px;
```
を
```scss
        .hamburger-panel {
            width: $panel-width;
            height: 196px;
```
に変更。

(b) button型 `.menu-item` の見た目を `<a>` と揃える。`.hamburger-panel` 内の `.menu-item {` ルールの直前に以下を追加:

```scss
        // button要素のmenu-item（お知らせ等）をaと同じ見た目にするリセット
        button.menu-item {
            width: 100%;
            background: none;
            border: none;
            font: inherit;
            cursor: pointer;
        }

```

- [ ] **Step 4: コンパイル確認**

Run:
```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN/Client && docker compose run --rm sass sh -lc 'npx --yes sass@1.79.5 --no-source-map /src/style.scss /tmp/check.css && grep -c notice-item /tmp/check.css'
```
Expected: エラーなし、1以上の数字

- [ ] **Step 5: Commit**

```bash
git add Client/scss/pages/home/_notice.scss Client/scss/pages/home/_index.scss Client/scss/pages/home/_hamburger.scss
git commit -m "feat: お知らせアコーディオンのスタイルとメニューパネル高さ拡張

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: nginxローカル検証経路（notices.csvのローカル優先）

**Files:**
- Modify: `Client/nginx_app/default.conf`

- [ ] **Step 1: exact-match location と named location を追加**

既存の `location /csv/ { ... }` ブロックの**直前**に以下を追加する:

```nginx
    # ローカル検証用: notices.csv はローカルファイルがあればそれを配信、無ければ本番へプロキシ
    location = /csv/notices.csv {
        add_header Cache-Control "no-store" always;
        try_files $uri @csv_proxy;
    }

    location @csv_proxy {
        set $csv_upstream https://app.pol-is.jp;
        proxy_pass $csv_upstream;
        proxy_set_header Host app.pol-is.jp;
        proxy_ssl_server_name on;
        proxy_connect_timeout 5s;
        proxy_hide_header Cache-Control;
        add_header Cache-Control "no-store" always;
    }
```

- [ ] **Step 2: 動作確認（ローカルファイルなし→本番404、あり→ローカル配信）**

Run:
```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN/Client
docker compose restart web-app && sleep 3
echo -n "ローカル無し(本番プロキシ→404想定): "; curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8081/csv/notices.csv
printf 'id,date,title,body\n1,2026-07-08,テスト,ローカル配信テスト\n' > public_html_app/csv/notices.csv
echo -n "ローカル有り: "; curl -s http://localhost:8081/csv/notices.csv | head -1
rm public_html_app/csv/notices.csv
```
Expected: 1行目 `404`（本番未設置のため）、2行目 `id,date,title,body`

- [ ] **Step 3: Commit**

```bash
git add Client/nginx_app/default.conf
git commit -m "feat: ローカル検証用にnotices.csvのローカル優先配信を追加

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 総合ブラウザ検証（puppeteer・本番無反映）

**Files:**
- なし（検証のみ。style.css再生成分をコミット。微調整が出たら該当ファイル修正+追いコミット）

- [ ] **Step 1: テストCSVを設置してフル起動**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN/Client && docker compose up -d
cat > public_html_app/csv/notices.csv <<'EOF'
id,date,title,body
3,2026-07-08,新機能のお知らせ,"メニューから**お知らせ**が見られるようになりました。
## 使い方
- ハンバーガーメニューの🔔をタップ
- 詳細は[こちら](https://pol-is.jp/)
裸URLもリンク化: https://example.com"
2,2026-07-05,XSSテスト,"<script>alert(1)</script><img src=x onerror=alert(2)>"
1,2026-07-01,サイト公開,Polis JAPANを公開しました
EOF
```

- [ ] **Step 2: puppeteerで自動検証**

scratchpad（`npm i puppeteer-core` 済みの場所）に検証スクリプトを書き実行する。検証項目と期待値:

1. **新着自動表示**: Cookie `tutorial_optout=1`（チュートリアル抑制）のみで訪問 → 1秒後に `#notice-modal.show` が付く
2. **初期展開**: `.notice-item` が3件・**先頭(id=3)のみ** `.open`
3. **Markdown**: 先頭itemの本文に `<strong>お知らせ</strong>`・`notice-heading`・`<ul>`・`href="https://pol-is.jp/"`・`href="https://example.com"` が存在
4. **XSS無害化**: `#notice-modal` 内に `script` 要素・`img` 要素が**存在しない**（`document.querySelectorAll("#notice-modal script, #notice-modal img").length === 0`）かつ本文テキストに `<script>` が見える
5. **Cookie更新**: モーダル表示後 `document.cookie` に `notice_last_seen_id=3`
6. **既読なら自動表示しない**: 同一ページを再読み込み → `#notice-modal.show` が付かない
7. **アコーディオン開閉**: 2件目のヘッダーをクリック → `.open` 付与・`aria-expanded=true`
8. **メニューから開く**: ハンバーガー開 → 「お知らせ」タップ → メニューが閉じ・モーダルが開く
9. **チュートリアル併存**: Cookie無し（チュートリアル表示）で訪問 → `#tutorial.show` があり `#notice-modal.show` は**付かない**
10. **404経路**: `rm public_html_app/csv/notices.csv` 後に新規訪問（Cookie無しの新コンテキスト+tutorial_optout） → 自動表示なし。メニューから開くと「お知らせを読み込めませんでした」表示
11. スクリーンショット: モーダル表示状態（モバイル390px）を撮り**目視確認**（アコーディオンの見た目・シェブロン回転）

- [ ] **Step 3: テストCSVを消し、style.css再生成をコミット**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN/Client
rm -f public_html_app/csv/notices.csv
git status --short   # style.css×3 のみのはず
git add public_html/style.css public_html_app/style.css public_html_admin/style.css
git commit -m "build: お知らせ機能追加に伴うstyle.css再生成

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 4: 完了報告**

ユーザーの目視確認用にテストCSVを再設置するかどうか、および本番 `notices.csv` の初回投入（`aws s3 cp` — 内容はユーザーに確認）を報告に含める。**mainへのマージ・S3への投入はこのプランの範囲外**（ユーザー承認後）

---

## 備考

- お知らせ本文のMarkdownは「エスケープ→限定変換」のため、CSVに何が書かれてもタグ注入は起きない（Task 5-4で実地検証）
- 本番CSVが未設置の間、機能は自動表示せず静かに眠る（安全なロールアウト）
- `notice.js` のグローバル関数名は `notice` プレフィックスで統一し、`home.js`/`create.js` との衝突を避けている
