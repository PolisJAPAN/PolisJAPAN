# ホーム画面ハンバーガーメニュー Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** アプリのホーム画面左下に、円形⇔角丸パネルにモーフ展開するハンバーガーメニューを追加する（仕様: `docs/superpowers/specs/2026-07-07-hamburger-menu-design.md`）

**Architecture:** 静的HTML + SCSS +素のJS。`#bottom-menu` 内に `<nav>`（トリガー円ボタン + 絶対配置パネル）を追加し、`.open` クラスの付け外しでCSSトランジションが走る。パネルは閉時にトリガーの背後に隠れた小さい円で、開時に width/height/border-radius を遷移させてモーフを表現する。

**Tech Stack:** SCSS（`Client/scss/`、sassコンテナで自動コンパイル）、Bootstrap Icons（読み込み済み）、テスト基盤なし → ローカルDocker配信（localhost:8081）での目視確認

**前提知識:**
- 検証環境: `cd Client && docker compose up` → http://localhost:8081/ （本番無反映。`docs/クライアント動作確認ガイド.md`）
- 既存の下部ボタンは `.button.secondary`（`--color-dark` 背景・角丸32pxピル・padding 14px 32px）
- `#bottom-menu` は `display:flex; align-items:center` の左寄せ行（`scss/pages/home/_menu.scss:78`）
- **トリガーの高さ合わせは `align-self: stretch` + `aspect-ratio: 1/1` で実現**（隣のピルの高さに自動追従。px指定しない）
- z-index変数: `--z-index-grobal-menu: 3000` / モーダルは4000（パネルはbottom-menu内なので追加のz-index層は不要）

---

### Task 1: SCSSパーシャル追加

**Files:**
- Create: `Client/scss/pages/home/_hamburger.scss`
- Modify: `Client/scss/pages/home/_index.scss`

- [ ] **Step 1: `_hamburger.scss` を新規作成**

以下の内容をそのまま作成する:

```scss
@use "../../common" as common;

// ハンバーガーメニュー（モーフ展開）
// 仕様: docs/superpowers/specs/2026-07-07-hamburger-menu-design.md
// クラスは汎用設計（将来他画面でも #bottom-menu 内に置けば動く）
.hamburger-menu {
    position: relative;

    // 隣のピルボタン（.button）と高さを揃える: 行の中で伸ばして正方形にする
    align-self: stretch;
    display: flex;
    align-items: center;

    // ---- トリガー（円ボタン） ----
    .hamburger-trigger {
        position: relative;
        z-index: 2;

        height: 100%;
        aspect-ratio: 1 / 1;
        border-radius: 50%;

        background-color: var(--color-dark);
        border: transparent;
        filter: drop-shadow(0px 4px 8px rgba(9, 8, 39, 0.25));

        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        gap: 5px;

        cursor: pointer;
        pointer-events: all;

        .bar {
            display: block;
            width: 20px;
            height: 2px;
            border-radius: 2px;
            background-color: var(--color-font-light);
            transition: transform 0.3s, opacity 0.2s;
        }
    }

    // ---- パネル（閉時はトリガーの背後に隠れる小さな円） ----
    .hamburger-panel {
        position: absolute;
        left: 0;
        bottom: 0;
        z-index: 1;

        width: 40px;
        height: 40px;
        border-radius: 24px;
        overflow: hidden;

        background-color: var(--color-dark);
        filter: drop-shadow(0px 4px 8px rgba(9, 8, 39, 0.25));

        pointer-events: none;
        transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1),
                    height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
                    border-radius 0.35s;

        .panel-inner {
            width: 224px;
            padding: 16px 16px 60px;

            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .menu-item {
            display: flex;
            flex-direction: row;
            align-items: center;
            gap: 10px;

            padding: 10px 12px;
            border-radius: 32px;

            color: var(--color-font-light);
            font-size: 14px;
            font-weight: 600;
            text-decoration: none;
            white-space: nowrap;

            opacity: 0;
            transform: translateY(8px);
            transition: opacity 0.2s, transform 0.2s, background-color 0.3s;

            &:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
        }

        .menu-sub-row {
            display: flex;
            flex-direction: row;
            gap: 12px;
            padding: 4px 12px 0;

            opacity: 0;
            transform: translateY(8px);
            transition: opacity 0.2s, transform 0.2s;

            .menu-sub-item {
                color: rgba(255, 255, 255, 0.6);
                font-size: 11px;
                text-decoration: none;
                white-space: nowrap;

                &:hover {
                    color: var(--color-font-light);
                }
            }
        }
    }

    // ---- 展開状態 ----
    &.open {
        .hamburger-trigger {
            .bar:nth-child(1) { transform: translateY(7px) rotate(45deg); }
            .bar:nth-child(2) { opacity: 0; }
            .bar:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }
        }

        .hamburger-panel {
            width: 224px;
            height: 150px;
            border-radius: 24px;
            pointer-events: all;

            .menu-item,
            .menu-sub-row {
                opacity: 1;
                transform: none;
            }
            .menu-item    { transition-delay: 0.18s; }
            .menu-sub-row { transition-delay: 0.26s; }
        }
    }
}

// 展開中は既存ボタンをフェードアウト（閉じると復帰）
#bottom-menu {
    .help-button, .create-button {
        transition: opacity 0.3s 0.15s;
    }
    &.hamburger-open {
        .help-button, .create-button {
            opacity: 0;
            pointer-events: none;
        }
    }
}

// アニメーションを好まない設定では即時開閉
@media (prefers-reduced-motion: reduce) {
    .hamburger-menu {
        .hamburger-trigger .bar,
        .hamburger-panel,
        .hamburger-panel .menu-item,
        .hamburger-panel .menu-sub-row {
            transition: none;
        }
    }
    #bottom-menu .help-button, #bottom-menu .create-button {
        transition: none;
    }
}
```

- [ ] **Step 2: `_index.scss` に読み込みを追加**

`Client/scss/pages/home/_index.scss` を以下の内容にする（`@forward "hamburger";` を追加）:

```scss
@forward "app";
@forward "menu";
@forward "create";
@forward "hamburger";
```

- [ ] **Step 3: コンパイル確認**

Run:
```bash
cd Client && docker compose run --rm sass sh -lc 'npx --yes sass@1.79.5 --no-source-map /src/style.scss /tmp/check.css && grep -c hamburger /tmp/check.css'
```
Expected: エラーなく終了し、`hamburger` の出現回数（1以上の数字）が表示される

- [ ] **Step 4: Commit**

```bash
git add Client/scss/pages/home/_hamburger.scss Client/scss/pages/home/_index.scss
git commit -m "feat: ハンバーガーメニューのスタイルを追加（モーフ展開・既存ボタンと高さ揃え）"
```

---

### Task 2: HTMLマークアップ追加

**Files:**
- Modify: `Client/public_html_app/index.html:168-177`（`#bottom-menu` 内）

- [ ] **Step 1: `#bottom-menu` の先頭にトリガーとパネルを追加**

現在のマークアップ:

```html
    <div id="bottom-menu">
        <button class="help-button button secondary">
            <i class="bi bi-question-circle"></i>
            <div class="text">使い方</div>
        </button>
        <button class="create-button button secondary">
            <i class="bi bi-plus"></i>
            <div class="text">テーマを作成</div>
        </button>
    </div>
```

これを以下に変更する（`help-button` の前に `<nav>` を挿入。既存2ボタンは無変更）:

```html
    <div id="bottom-menu">
        <nav id="hamburger-menu" class="hamburger-menu" aria-label="サイトメニュー">
            <div class="hamburger-panel">
                <div class="panel-inner">
                    <a class="menu-item" href="https://pol-is.jp/contact/">
                        <i class="bi bi-envelope"></i>
                        <div class="text">お問い合わせ</div>
                    </a>
                    <div class="menu-sub-row">
                        <a class="menu-sub-item" href="https://pol-is.jp/terms/">利用規約</a>
                        <a class="menu-sub-item" href="https://pol-is.jp/policy/">プライバシーポリシー</a>
                    </div>
                </div>
            </div>
            <button class="hamburger-trigger" aria-label="メニュー" aria-expanded="false">
                <span class="bar"></span>
                <span class="bar"></span>
                <span class="bar"></span>
            </button>
        </nav>
        <button class="help-button button secondary">
            <i class="bi bi-question-circle"></i>
            <div class="text">使い方</div>
        </button>
        <button class="create-button button secondary">
            <i class="bi bi-plus"></i>
            <div class="text">テーマを作成</div>
        </button>
    </div>
```

- [ ] **Step 2: 配信確認**

Run:
```bash
cd Client && docker compose up -d web-app && sleep 2 && curl -s http://localhost:8081/ | grep -c "hamburger-trigger"
```
Expected: `1`

- [ ] **Step 3: Commit**

```bash
git add Client/public_html_app/index.html
git commit -m "feat: ホーム画面にハンバーガーメニューのマークアップを追加"
```

---

### Task 3: 開閉ロジック（JS）

**Files:**
- Modify: `Client/public_html_app/javascript/home.js`（末尾の関数群と `DOMContentLoaded` ハンドラ）

- [ ] **Step 1: `bindHamburgerMenu` 関数を追加**

`home.js` の最後の関数定義（`bindPageReturn` など）の後、`DOMContentLoaded` リスナーの前に以下を追加する:

```js
/**
 * ハンバーガーメニューの開閉を制御する。
 *
 * トリガークリックでトグル、パネル外クリック・Escキーで閉じる。
 * 開閉状態は .hamburger-menu の .open と #bottom-menu の .hamburger-open で表現し、
 * 見た目の変化はすべてCSS側（_hamburger.scss）が担う。
 */
function bindHamburgerMenu() {
    const menu = document.querySelector("#hamburger-menu");
    if (!menu) {
        return;
    }
    const trigger = menu.querySelector(".hamburger-trigger");
    const bottomMenu = document.querySelector("#bottom-menu");

    const setOpen = (open) => {
        menu.classList.toggle("open", open);
        bottomMenu.classList.toggle("hamburger-open", open);
        trigger.setAttribute("aria-expanded", String(open));
    };

    trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        setOpen(!menu.classList.contains("open"));
    });

    // パネル外をタップしたら閉じる
    document.addEventListener("click", (e) => {
        if (menu.classList.contains("open") && !menu.contains(e.target)) {
            setOpen(false);
        }
    });

    // Escキーで閉じる
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && menu.classList.contains("open")) {
            setOpen(false);
        }
    });
}
```

- [ ] **Step 2: `DOMContentLoaded` で呼び出す**

`home.js` 末尾の初期化ハンドラに1行追加する:

```js
// ウィンドウ初期化時にイベントを割り当て
document.addEventListener("DOMContentLoaded", async () => {
    initializeTutorial();

    // 記事データの取得・描画が完了してから後続の処理を実行する
    await initializeArticles();

    bindCategoryFilter();
    bindSort();
    sortArticles(currentSort);
    updateArticleVisible(currentCategory, currentWords);
    BindHorizontalScroll();
    bindArticleLink();
    bindPageReturn();
    bindHamburgerMenu();
});
```

- [ ] **Step 3: 構文確認**

Run:
```bash
node --check Client/public_html_app/javascript/home.js && echo OK
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add Client/public_html_app/javascript/home.js
git commit -m "feat: ハンバーガーメニューの開閉ロジックを追加（外側タップ・Esc対応）"
```

---

### Task 4: 総合動作確認（ローカル・本番無反映）

**Files:** なし（確認のみ。微調整が出たら該当ファイルを修正して追いコミット）

- [ ] **Step 1: ローカル環境を起動**

Run:
```bash
cd Client && docker compose up -d
```
http://localhost:8081/ をブラウザで開く（sassコンテナがstyle.cssを再生成するまで数秒待つ。反映されない場合はスーパーリロード）

- [ ] **Step 2: 目視チェックリスト**

以下を1つずつ確認する:

1. 左下に円形ボタンが表示され、**「使い方」「テーマを作成」と高さが一致**している（DevToolsで両者の `offsetHeight` が同値であること: `document.querySelector(".hamburger-trigger").offsetHeight === document.querySelector(".help-button").offsetHeight`）
2. クリックで円→角丸パネルにモーフ展開し、3本線が×になる
3. 項目が時差フェードインし、「お問い合わせ」が通常サイズ・「利用規約・プライバシーポリシー」が小さい表示
4. 展開中は「使い方」「テーマを作成」がフェードアウトし、閉じると復帰する
5. パネル外クリックで閉じる／Escキーで閉じる
6. 各リンクが `pol-is.jp/contact/`・`/terms/`・`/policy/` に遷移する（同一タブ）
7. モバイル幅（DevToolsのレスポンシブモード・iPhone SE等）で崩れない
8. テーマ作成モーダル・チュートリアルを開いたとき、パネルやトリガーが上に被らない
9. `aria-expanded` が開閉に追従する（DevToolsのElementsで確認）

- [ ] **Step 3: 微調整（必要な場合のみ）**

パネルの `width: 224px / height: 150px` は内容フィットの目安値。文字はみ出し・余白過多があれば `_hamburger.scss` の `.hamburger-panel`（開時サイズ）と `.panel-inner` の padding を調整し、チェックリスト該当項目を再確認する

- [ ] **Step 4: 後片付けと最終コミット**

Run:
```bash
cd Client && docker compose down
git status --short   # 想定外の変更が残っていないこと（sassが再生成した style.css は含めてよい）
```
`style.css`（コンパイル成果物）に差分がある場合はコミットする:
```bash
git add Client/public_html_app/style.css Client/public_html/style.css Client/public_html_admin/style.css
git commit -m "build: ハンバーガーメニュー追加に伴うstyle.css再生成"
```

- [ ] **Step 5: 完了報告**

実装ブランチは `feature/ux-improvements`。本番反映はユーザーの判断で main へマージしたときに `deploy-client.yml` が自動実行する（このプランの範囲では**マージしない**）

---

## 備考

- **テーマ詳細画面には設置しない**（仕様のスコープ外）。`_hamburger.scss` のクラスは汎用なので、将来は該当画面の `#bottom-menu` に同じマークアップを足すだけで展開できる
- style.css はsassコンテナの生成物だが、リポジトリにコミットされる運用（S3にそのまま同期されるため）
