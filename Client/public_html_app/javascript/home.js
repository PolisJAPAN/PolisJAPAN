// ==============================
// ローディング関連
// ==============================

/**
 * アプリのローディング表示を遅延して非表示にする。
 * 
 * #app-loading が存在する場合、2秒後に show クラスを除去する。
 * 
 * @returns {void}
 */
function hideLoading() {
    const el = document.getElementById("app-loading");
    if (!el) return;
    setTimeout(() => el.classList.remove("show"), 2000);
}


// ==============================
// チュートリアル関連
// ==============================

/**
 * チュートリアル管理マネージャー
 */
let tutorialManager = null;

/**
 * チュートリアル機能を初期化する。
 * 
 * TutorialManager を所定のセレクタとキー設定で生成し、init() を実行する。
 * 
 * 依存: TutorialManager
 * 
 * @returns {void}
 */
function initializeTutorial() {
    tutorialManager = new TutorialManager({
        rootSel: "#tutorial",
        windowSel: ".tutorial-window",
        helpBtnSel: ".help-button",
        skipBtnSel: ".skip-button",
        optoutCheckboxSel: "#hidden-checkbox",
        keyLast: "tutorial_last_shown",
        keyOptout: "tutorial_optout",
    });
    tutorialManager.init();
}

// ==============================
// 話題リスト生成関連
// ==============================

/**
 * カテゴリ表示用のラベル
 */
const CATEGORY_LABELS = {
    1 : "社会・政治",
    2 : "お金・資産",
    3 : "男女・性別",
    4 : "外国人問題",
    5 : "テクノロジー",
    6 : "医療・福祉",
    7 : "生活",
    8 : "その他",
};

/**
 * 文字列をHTMLテキストとして安全に表示できるよう簡易エスケープする（XSS対策）。
 * 
 * `& < > " '` をそれぞれ HTML エンティティへ変換する。
 * 
 * @param {unknown} s - エスケープ対象。null/undefinedは空文字扱い。
 * @returns {string} - エスケープ済み文字列。
 */
function esc(s) {
    return String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * JSON配列から話題カードのHTMLを生成し、`.article-container` へ挿入する。
 * 
 * 各記事は `a.article-item` として描画され、カテゴリや票数は data-* 属性にも設定される。
 * コンテナ要素が無い場合は例外を投げる。
 * 
 * 依存: esc
 * 
 * @param {Array<Object>} csvData - テーマ一覧データ配列（id, title, description, category, conversation_id, comments, votes 等）。
 * @returns {void}
 * @throws {Error} - 親要素 `.article-container` が見つからない場合。
 */
function buildTopicInnerHTML(csvData) {
    // 生成用の親要素取得
    const container = document.querySelector('.article-container');
    if (!container) throw new Error(`親要素が見つかりません: .article-container`);
    container.innerHTML = '';

    const html = csvData.map(item => {
        if(!item || !item.id)
        {
            return "";
        } 

        // DOMに当てはめる各要素をCSVJSONの要素から取り出し。
        const title = item.title;
        const description = item.description;
        const categoryId = item.category;
        const conversationId = item.conversation_id;
        const uniqueId = item.id;

        const comments = item.comments;
        const votes = item.votes;

        const categoryLabel = CATEGORY_LABELS[categoryId] ?? '';

        // ここで `${...}` による差し込みがすべて見えます
        return `
        <a class="article-item" href="/detail/?conversation_id=${conversationId}" data-category=${esc(categoryId)} data-id=${uniqueId} data-population=${votes}>
            <img class="corner-bg" src="/images/common/corner-spaced.png" alt="">
            <div class="category-label">#${esc(categoryLabel)}</div>
            <div class="article-window cat-${esc(categoryId)}">
                <div class="article-title-area">
                    <div class="article-title">${esc(title)}</div>
                </div>
                <div class="article-footer">
                    <div class="article-opinion-group">
                        <i class="bi bi-megaphone-fill"></i>
                        <div class="text">${comments}</div>
                    </div>
                    <div class="article-vote-group">
                        <i class="bi bi-people-fill"></i>
                        <div class="text">${votes}</div>
                    </div>
                </div>
            </div>
        </a>
    `;
    }).join('');

    container.innerHTML += html;
}


// ==============================
// ソート・検索関連
// ==============================

// 現在表示中のカテゴリ 　0ならフィルターなし
let currentCategory = 0;
// 現在表示中の検索ワード。未入力の場合は空配列とする
let currentWords = [];
// 現在選択されているソートルール
let currentSort = "new";

/**
 * 検索語の正規化を行う。全角・半角差を吸収し、小文字化する。
 * 
 * @param {string} s - 正規化対象。
 * @returns {string} - 正規化後の文字列。
 */
function norm(s) {
    return String(s ?? '').normalize('NFKC').toLowerCase();
}

/**
 * 入力文字列を空白（半角/全角）で分割してトークン配列へ変換する。
 * 
 * 空トークンは除外し、`norm()` を適用した上で返す。
 * 
 * 依存: norm
 * 
 * @param {unknown} q - クエリ文字列。
 * @returns {string[]} - 検索語トークン配列。
 */
function tokenize(q) {
    return norm(q).split(/[\u3000\s]+/).filter(Boolean);
}


/**
 * 検索を高速化するため、各 `.article-item` に索引用テキストを `data-searchtext` として付与する。
 * 
 * `.article-title` と `.category-label` の文字列を結合し、`norm()` を適用して保存する。
 * 
 * 依存: norm
 * 
 * @param {string} [containerSelector='.article-container'] - 記事コンテナのセレクタ。
 * @returns {void}
 */
function indexArticlesForSearch(containerSelector = '.article-container') {
    // 親コンテナの取得
    const container = document.querySelector(containerSelector);
    if (!container) return;

    // 小要素の記事アイテムを取得
    const items = container.querySelectorAll('.article-item');

    // 各アイテムにに処理
    items.forEach(item => {
        // タイトルとカテゴリーを保存
        const title = item.querySelector('.article-title')?.textContent || '';
        const category = item.querySelector('.category-label')?.textContent || '';

        // datasetとしてサーチ用文字列をDOMに付与
        item.dataset.searchtext = norm(`${title} ${category}`);
    });
}

/**
 * ローカル検索を実行し、結果に応じて記事の表示/非表示を切り替える。
 * 
 * 入力欄 #search-input の値をトークン化して `currentWords` に保存し、
 * `updateArticleVisible()` を呼び出す。
 * 
 * 依存: tokenize, updateArticleVisible
 * 
 * @returns {void}
 */
function applyLocalSearch() {
    const input = document.querySelector("#search-input");
    const container = document.querySelector(".article-container");
    if (!input || !container) return;

    const words = tokenize(input.value);

    //　保存
    currentWords = words;
    updateArticleVisible(currentCategory, currentWords);
}

/**
 * 検索UIを初期化する。クリック/Enter/blurで検索を実行し、初期索引化も行う。
 * 
 * #search-input と #search-button をバインドし、DOMContentLoaded 時に `indexArticlesForSearch()` を実行する。
 * 
 * 依存: applyLocalSearch, indexArticlesForSearch
 * 
 * @returns {void}
 */
function setupSearchUI() {
    const input = document.getElementById('search-input');
    const button = document.getElementById('search-button');
    if (!input || !button) return;

    // クリック
    button.addEventListener('click', (e) => {
        e.preventDefault();
        applyLocalSearch();
    });

    // Enter
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            applyLocalSearch();
        }
    });

    // フォーカスが外れた時（blur）
    input.addEventListener('blur', (e) => {
        applyLocalSearch();
    });

    // 初回の索引化（記事描画直後にも呼び直してください）
    document.addEventListener('DOMContentLoaded', () => {
        indexArticlesForSearch();
    });
}

/**
 * 記事の表示制御本体。カテゴリと検索語の両条件（AND）で `.article-item` の表示を切り替える。
 * 
 * 索引が無い要素はフォールバックでテキスト全体を対象に検索する。
 * 
 * @param {string|number} categoryId - 表示対象カテゴリ。0 はフィルターなし。
 * @param {string[]} words - 検索語トークン配列。空配列なら検索なし。
 * @returns {void}
 */
function updateArticleVisible(categoryId, words) {
    // 記事アイテム一覧を取得
    const articles = document.querySelectorAll('.article-container .article-item[data-category]');

    articles.forEach((item) => {
        let searchWordMatch = true;

        if (words.length > 0) {
            // 事前索引がなければフォールバックで item 全体のテキストを使う
            const hay = item.dataset.searchtext || norm(item.textContent || '');
            searchWordMatch = words.every(word => hay.includes(word)); // AND 条件で全てチェック
        }
        const categoryMatch = (item.dataset.category === categoryId) || categoryId == 0; //0の場合はカテゴリ指定なし

        if (categoryMatch & searchWordMatch) {
            item.classList.add("show");
        } else {
            item.classList.remove("show");
        }
    });
}

/**
 * カテゴリタブの active 表示を更新する。
 * 
 * `.category-tab-group .category-button[data-category]` のうち、指定カテゴリのみ active にする。
 * 
 * @param {string|number} category - 対象カテゴリ。
 * @returns {void}
 */
function setActiveTab(category) {
    // カテゴリー指定ボタンを取得
    const tabs = document.querySelectorAll('.category-tab-group .category-tab-wrapper .category-button[data-category]');

    tabs.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.category === category)
    });
};

/**
 * カテゴリタブの選択をトグルし、記事の表示を更新する。
 * 
 * 同じカテゴリを再選択した場合は選択解除（0）に戻す。
 * 
 * 依存: setActiveTab, updateArticleVisible
 * 
 * @param {string|number} category - クリックされたカテゴリ。
 * @returns {void}
 */
function updateTab(category) {
    let targetCategory = category;
    // 選択中カテゴリと同じ場合は選択解除
    if (category == currentCategory)
    {
        targetCategory = 0;
    }

    // 表示中のカテゴリを保存
    currentCategory = targetCategory;

    // 表示更新
    setActiveTab(currentCategory);
    updateArticleVisible(currentCategory, currentWords)
}

/**
 * カテゴリフィルタのイベントを初期化する。
 * 
 * 各カテゴリボタンのクリックで `updateTab()` を実行し、初期状態では active ボタンがあればそのカテゴリでフィルタする。
 * 
 * 依存: updateTab
 * 
 * @returns {void}
 */
function bindCategoryFilter() {
    // カテゴリー指定ボタンを取得
    const tabs = document.querySelectorAll('.category-tab-group .category-tab-wrapper .category-button[data-category]');

    // イベントバインド
    tabs.forEach((btn) => {
        btn.addEventListener('click', (e) => {
            const category = btn.dataset.category;
            e.preventDefault();
            updateTab(category);
        });
    });

    // 初期表示
    const initialActive = document.querySelector('.category-button.active[data-category]');
    if (initialActive) {
        filterByCategory(initialActive.dataset.category);
    }
}

/**
 * 記事の並べ替えを行う。結果はDOM順序へ反映される。
 * 
 * "new" で id 降順、"old" で id 昇順、"popular" で votes 降順。
 * 
 * @param {"new"|"old"|"popular"} type - ソート種別。
 * @returns {void}
 */
function sortArticles(type){
    // .article-item を配列化
    const articleContainer = document.querySelector(".article-container");
    const articles = Array.from(articleContainer.querySelectorAll(".article-item"));

    let sorted = [];
    if (type === "new") {
        // 新しい順 → conversation_id 降順（数値想定）
        sorted = articles.sort((a, b) => {
            const idA = a.dataset.id;
            const idB = b.dataset.id;
            return idB - idA;
        });
    } else if (type === "old") {
        // 古い順 → conversation_id 昇順
        sorted = articles.sort((a, b) => {
            const idA = a.dataset.id;
            const idB = b.dataset.id;
            return idA - idB;
        });
    } else if (type === "popular") {
        // 人気順 → votes の多い順
        sorted = articles.sort((a, b) => {
            const votesA = a.dataset.population;
            const votesB = b.dataset.population;
            return votesB - votesA;
        });
    }

    // DOMを並べ替え
    sorted.forEach((el) => articleContainer.appendChild(el));
}

/**
 * ソートUI（ドロップダウン）の表示切替と選択処理を初期化する。
 * 
 * クリックでメニューを開閉し、項目クリックで `sortArticles()` を実行してメニューを閉じる。
 * 
 * 依存: sortArticles
 * 
 * @returns {void}
 */
function bindSort() {
    // 各ボタンを取得する
    const sortButton = document.querySelector(".sort-button");
    const sortSelect = document.querySelector(".sort-select");
    const sortItems = sortSelect.querySelectorAll(".select-element");

    // ドロップダウンメニューの表示切替
    sortButton.addEventListener("click", () => {
        if (sortSelect.classList.contains("show")) {
            sortSelect.classList.remove("show");
        } else {
            sortSelect.classList.add("show");
        }
    });

    // ソート選択肢クリック処理
    sortItems.forEach((item) => {
        item.addEventListener("click", () => {
            //　クリックされたボタンのvalueでselect処理を発火
            const value = item.dataset.value;

            // ソート処理を実行
            sortArticles(value);

            // 現在のソート処理を実行
            currentSort = value;

            // セレクトを閉じる
            sortSelect.classList.remove("show");
        });
    });
};

// ==============================
// 話題リスト初期化関連
// ==============================

/**
 * 記事一覧を初期化する。CSVを読み込み、描画と検索UIのセットアップを行う。
 * 
 * `/csv/themes.csv` を取得・パースして `buildTopicInnerHTML()` で描画し、`setupSearchUI()` を呼ぶ。
 * 
 * 依存: loadCsvAsJson, buildTopicInnerHTML, setupSearchUI
 * 
 * @async
 * @returns {Promise<void>} - 初期化完了時に解決。
 */
async function initializeArticles() {
    const csvJson = await loadCsvAsJson("/csv/themes.csv")
    // 描画
    buildTopicInnerHTML(csvJson)
    setupSearchUI();
}


// ウィンドウ初期化時にイベントを割り当て
document.addEventListener("DOMContentLoaded", () => {
    initializeTutorial();
    initializeArticles();

    setTimeout(
        () => {
            bindCategoryFilter();
            bindSort();
            sortArticles(currentSort);
            updateArticleVisible(currentCategory, currentWords);
            BindHorizontalScroll();
        }, 500
    )
});