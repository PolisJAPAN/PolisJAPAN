// ==============================
// 上部タブ関連
// ==============================

/**
 * 上部タブのクリック操作をバインドし、タブ切替を実行する。
 * 
 * #tab-group 内の .tab クリックで `switchTabs()` を呼び出し、
 * さらに「テーマへ移動」ボタン（.goto-theme-button）で "conversations" タブへ切り替える。
 * 
 * 依存: switchTabs
 * 
 * @async
 * @returns {Promise<void>} - 初期バインド完了時に解決。
 */
async function bindTabs() {
    document.querySelectorAll("#tab-group .tab").forEach(button => {
        button.addEventListener("click", () => {
            switchTabs(button.dataset.tab);
        });
    });

    document.querySelector(".goto-theme-button").addEventListener("click", () => {
        switchTabs("conversations");
    });
};

/**
 * 指定された識別子のタブをアクティブ化し、関連するコンテンツ領域のクラスを切り替える。
 * 
 * #tab-group の .tab の active クラスを更新し、`.tab-select` と `#app` の
 * className を `on-<tabIdentifier>` に切り替える。切り替え後、各スクロール領域を先頭へ戻す。
 * 
 * @param {string} tabIdentifier - 切り替え先タブの識別子（各 .tab の data-tab 値）。
 * @returns {void}
 */
function switchTabs(tabIdentifier) {
    const tabElements = document.querySelectorAll("#tab-group .tab");
    // アクティブボタン切替
    tabElements.forEach(btn => {
        btn.classList.remove("active")
        if (tabIdentifier === btn.dataset.tab) {
            btn.classList.add("active")
        }
    });

    // data-tabからクラス付け替え
    const tabSelect = document.querySelector("#tab-group .tab-select");
    const app = document.querySelector("#app");

    tabSelect.className = "tab-select on-" + tabIdentifier;
    app.className = "on-" + tabIdentifier;
    
    setTimeout(() => {
        document.querySelector(".polis-report").scrollTo({ top: 0, behavior: "instant" });
        document.querySelector(".polis").scrollTo({ top: 0, behavior: "instant" });
    }, 300);
}

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
 * TutorialManager を所定のセレクタ・色設定で生成し、init() を実行する。
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
        defaultThemeColor: "#F2F2F0",
        tutorialThemeColor: "#FFFFFF",
    });
    tutorialManager.init();
}

// ==============================
// Polis埋め込み関連
// ==============================

/**
 * クエリパラメータから conversation_id を取得する。
 * 
 * URLSearchParams により `?conversation_id=...` を解析し、未指定時は空文字を返す。
 * 
 * @returns {string} - 取得した会話ID。未指定時は ""。
 */
function getConversationId() {
    // distribution_id を取得
    const usp = new URLSearchParams(location.search);
    const conversationIdFromURL = usp.get('conversation_id');
    const conversationId = conversationIdFromURL ? conversationIdFromURL : "";

    return conversationId;
}

/**
 * Pol.is の埋め込みを初期化する。
 * 
 * getパラメータから取得したconbersation_idを
 * `.polis` 要素の data-conversation_id に設定し、
 * pol.is の埋め込みスクリプトを動的に読み込む。
 * 
 * 依存: getConversationId
 * 
 * @returns {void}
 */
function initializePolisIframe() {
    const conversationId = getConversationId();

    // DOM に挿入
    document.querySelector('.polis').dataset["conversation_id"] = conversationId;

    const s = document.createElement('script');
    s.async = true;
    s.src = 'https://pol.is/embed.js';
    document.head.appendChild(s);
}

// ==============================
// レポート関連
// ==============================

/**
 * レコードに指定グループ（letter: a〜z）の集計カラムが存在するか判定する。
 * 
 * `group-<letter>-agrees/disagrees/passes/votes` のいずれかが存在すれば true。
 * 
 * @param {Object} rec - 対象レコード。
 * @param {string} letter - グループ名（a〜z）。
 * @returns {boolean} - 対象グループが存在すれば true。
 */
function hasGroup(rec, letter) {
    const base = `group-${letter}`;
    return (
        Object.prototype.hasOwnProperty.call(rec, `${base}-agrees`) ||
        Object.prototype.hasOwnProperty.call(rec, `${base}-disagrees`) ||
        Object.prototype.hasOwnProperty.call(rec, `${base}-passes`) ||
        Object.prototype.hasOwnProperty.call(rec, `${base}-votes`)
    );
};

/**
 * 1グループ分の集計オブジェクトを作成する。
 * 
 * `group-<letter>-agrees/disagrees/passes` を数値化し、合計/率を算出する。
 * 
 * 依存: toInt
 * 
 * @param {Object} rec - 対象レコード。
 * @param {string} letter - グループ名（a〜z）。
 * @returns {{groupName:string, agrees:number, disagrees:number, passes:number, agreeRate:number, disagreeRate:number, passRate:number, totalVotes:number}}
 *          - グループ集計オブジェクト。
 */
function buildGroupObject(rec, letter) {
    const base = `group-${letter}`;
    const agrees = toInt(rec[`${base}-agrees`]);
    const disagrees = toInt(rec[`${base}-disagrees`]);
    const passes = toInt(rec[`${base}-passes`]);

    // 入力の votes があっても、合計値を信頼して再計算
    const totalVotes = agrees + disagrees + passes;

    const agreeRate =  (totalVotes > 0) ? (agrees / totalVotes) : 0;
    const disagreeRate = (totalVotes > 0) ? (disagrees / totalVotes) : 0;
    const passRate = (totalVotes > 0) ? (passes / totalVotes) : 0;

    return {
        "groupName": letter,
        "agrees" : agrees,
        "disagrees" : disagrees,
        "passes" : passes,
        "agreeRate" : agreeRate,
        "disagreeRate" : disagreeRate,
        "passRate" : passRate,
        "totalVotes": totalVotes,
    };
};

/**
 * 1レコードから、存在する全グループ（a〜z）の集計オブジェクト配列を生成する。
 * 
 * 依存: hasGroup, buildGroupObject
 * 
 * @param {Object} record - 対象レコード。
 * @returns {Array<Object>} - グループ集計オブジェクトの配列。
 */
function extractGroups(record) {
    const out = [];
    // ラベル行をチェックして存在するグループだけ配列に追加(例[a,b])
    for (let code = "a".charCodeAt(0); code <= "z".charCodeAt(0); code++) {
        const letter = String.fromCharCode(code);
        if (hasGroup(record, letter)) {
            out.push(buildGroupObject(record, letter));
        }
    }
    return out;
};

/**
 * 1レコードから、存在する全グループ名（a〜z）を配列で取得する。
 * 
 * 依存: hasGroup
 * 
 * @param {Object} record - 対象レコード。
 * @returns {string[]} - 存在するグループ名の配列（例: ["a","c","f"]）。
 */
function getGroups(record) {
    const out = [];
    for (let code = "a".charCodeAt(0); code <= "z".charCodeAt(0); code++) {
        const letter = String.fromCharCode(code);
        if (hasGroup(record, letter)) {
            out.push(letter);
        }
    }
    return out;
};


/**
 * 指定グループの賛成率を取得する。見つからない場合は 0 を返す。
 * 
 * `item.groupData` 内で groupName が一致する要素を検索し、agreeRate を返却。
 * 数値化が必要な場合は `agrees/totalVotes` から再計算する。
 * 
 * 依存: toInt
 * 
 * @param {Object} item - displayData要素（groupData配列を含む）。
 * @param {string} groupName - 対象グループ名。
 * @returns {number} - 賛成率（0〜1）。該当なしは 0。
 */
function getGroupAgreeRate(item, groupName) {
    const g = item.groupData?.find(
        (x) => (x.groupName || "").toLowerCase() === groupName.toLowerCase()
    );

    if (!g) return 0;

    return typeof g.agreeRate === "number"
        ? g.agreeRate
        : toInt(g.totalVotes) > 0
            ? toInt(g.agrees) / toInt(g.totalVotes)
            : 0;
};

/**
 * コメント部分に表示するアイコンのパス一覧
 */
const COMMENT_ICON_LIST = [
    "/images/report/men_01.png",
    "/images/report/men_02.png",
    "/images/report/men_03.png",
    "/images/report/women_01.png",
    "/images/report/women_02.png",
    "/images/report/women_03.png",
];

/**
 * グループ別データのキャッシュ（キーは小文字グループ名）
 * initializeArticles 内で設定される
 */
let groupDataCacheByName = null;

/**
 * グループ意見ツールチップの管理
 */
const GroupTooltip = (() => {
    let tooltipElement = null;
    let currentAnchor = null;

    /**
     * ツールチップのルート要素を生成して返す（初回のみ生成、以降はキャッシュを返却）。
     * クリック外しやスクロール/リサイズ時のクローズ処理もここで初期化する。
     *
     * @returns {HTMLDivElement} ツールチップ要素
     */
    function ensureTooltipElement() {
        if (tooltipElement) return tooltipElement;
        tooltipElement = document.createElement('div');
        tooltipElement.className = 'group-tooltip';
        tooltipElement.setAttribute('role', 'dialog');
        tooltipElement.style.display = 'none';

        // ツールチップ内の閉じるボタンはイベント委譲で処理
        tooltipElement.addEventListener('click', (ev) => {
            const closeBtn = ev.target && ev.target.closest('.group-tooltip-close');
            if (closeBtn) {
                ev.preventDefault();
                ev.stopPropagation();
                hide();
            }
        });

        document.body.appendChild(tooltipElement);

        // クリック外しで閉じる
        document.addEventListener('click', (ev) => {
            if (!tooltipElement || tooltipElement.style.display === 'none') return;
            if (tooltipElement.contains(ev.target)) return;
            if (currentAnchor && currentAnchor.contains(ev.target)) return;
            hide();
        });
        // スクロールやリサイズで閉じる
        window.addEventListener('scroll', hide, { passive: true });
        window.addEventListener('resize', hide);
        return tooltipElement;
    }

    /**
     * アンカー要素のビューポート座標をもとに、ツールチップの表示位置を決定する。
     * 画面下に収まらない場合は自動的に上側へ配置する。
     *
     * @param {DOMRect} anchorRect - 基準にする要素の getBoundingClientRect() 結果
     * @returns {void}
     */
    function positionTooltip(anchorRect) {
        const margin = 8;
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        const preferredTop = anchorRect.bottom + margin;
        const preferredLeft = Math.min(
            Math.max(anchorRect.left, margin),
            viewportWidth - margin - 360
        );

        tooltipElement.style.left = `${preferredLeft}px`;
        // 下に置けない場合は上に
        const tentativeTop = preferredTop;
        const height = tooltipElement.offsetHeight || 240;
        const fitsBelow = tentativeTop + height + margin <= viewportHeight;
        const finalTop = fitsBelow ? tentativeTop : Math.max(anchorRect.top - height - margin, margin);
        tooltipElement.style.top = `${finalTop}px`;
    }

    /**
     * 重複IDを避けるため、生成済みHTMLから group-* の id 属性を取り除く。
     *
     * @param {string} html - ツールチップへ挿入するHTML文字列
     * @returns {string} - id除去後のHTML文字列
     */
    function sanitizeGroupInfoHTML(html) {
        // id="group-*" は重複させないよう除去
        return html.replace(/\s+id="group-[^"]*"/, '');
    }

    /**
     * 指定グループの情報を取得し、ツールチップへHTMLを流し込んで表示する。
     *
     * @param {string} groupLetter - グループ名（a〜z）
     * @param {HTMLElement} anchorEl - 配置の基準にする要素
     * @returns {void}
     */
    function showForGroup(groupLetter, anchorEl) {
        if (!groupDataCacheByName) return;
        const key = String(groupLetter || '').toLowerCase();
        const groupData = groupDataCacheByName[key];
        if (!groupData) return;

        // ツールチップDOMを用意し、今回の基準要素（アンカー）を保持する
        const el = ensureTooltipElement();
        currentAnchor = anchorEl;

        // コンテンツ生成（既存の getGroupInfoInnerHTML と同内容）
        const rawHTML = getGroupInfoInnerHTML(groupData);
        // 重複IDを持たないようにサニタイズ
        const innerHTML = sanitizeGroupInfoHTML(rawHTML);
        // 閉じるボタン＋中身（グループ情報HTML）を文字列連結で挿入
        const html = `
            <button class="group-tooltip-close" aria-label="閉じる">×</button>
            <div class="group-tooltip-content">
                ${innerHTML}
            </div>
        `;
        el.innerHTML = html;

        // いったん表示してから、アンカー位置に基づいて最適な表示位置へ配置
        el.style.display = 'block';
        const rect = anchorEl.getBoundingClientRect();
        positionTooltip(rect);
    }

    /**
     * ツールチップを非表示にし、現在のアンカー参照もクリアする。
     *
     * @returns {void}
     */
    function hide() {
        if (!tooltipElement) return;
        tooltipElement.style.display = 'none';
        currentAnchor = null;
    }

    return { showForGroup, hide };
})();

/**
 * コメント群（全体指標）をHTMLに整形して返す。
 * 
 * displayDataList の各要素について、コメントと全体比率、各グループの円グラフを描画するHTMLを生成する。
 * 
 * 依存: getRandomInt
 * 
 * @param {Array<Object>} displayDataList - 表示用データ配列（comment, totalAgreeRate などを含む）。
 * @param {string} label - セクションタイトル文言。
 * @returns {string} - 生成されたHTML文字列。
 */
function buildTopicInnerHTML(displayDataList, label) {
    const listHtmlList = displayDataList.map(data => {

        console.log(data);

        // 可変になるグループ部分のHTMLを先に作成
        const groupHtml = data.groupData.map(groupData => {
            const positivePercent = Math.round((groupData.agreeRate * 100) * 10) / 10;
            const negativePercent = Math.round((groupData.disagreeRate * 100) * 10) / 10;
            const passPercent = Math.round((groupData.passRate * 100) * 10) / 10;

            return`
            <div class="circle-graph-item" data-group="${String(groupData.groupName).toLowerCase()}" role="button" tabindex="0" aria-label="グループ${String(groupData.groupName).toUpperCase()}の代表意見を表示">
                <div class="graph-circle" style="
                    background-image: 
                        radial-gradient(#fff 55%, transparent 55%), 
                        conic-gradient(var(--color-graph-positive) ${positivePercent}%, var(--color-graph-negative) ${positivePercent}% ${positivePercent + negativePercent}%, var(--color-graph-neutral) ${positivePercent + negativePercent}% 100%);
                ">${String(groupData.groupName).toUpperCase()}</div>
                <div class="data-text-group">
                    <div class="data-text positive">${positivePercent}<span class="percent">%</span><span class="percent">(${groupData.agrees})</span></div>
                    <div class="data-text negative">${negativePercent}<span class="percent">%</span><span class="percent">(${groupData.disagrees})</span></div>
                    <div class="data-text neutral">${passPercent}<span class="percent">%</span><span class="percent">(${groupData.passes})</span></div>
                </div>
            </div>
        `}).join('');


        return `
            <div class="comments-item">
                <div class="comments-text-group">
                    <div class="comment-person-img-group">
                        <img class="comment-person-img" src="${COMMENT_ICON_LIST[getRandomInt(0, (COMMENT_ICON_LIST.length - 1))]}" alt="">
                    </div>
                    <div class="comments-text">
                        <div class="comment-arrow">
                            <svg xmlns="http://www.w3.org/2000/svg" width="33" height="54" viewBox="0 0 33 54" fill="none">
                                <path d="M19.4839 50.9938C18.7096 53.9943 14.4486 53.9943 13.6743 50.9938L0.579104 0.250003L32.5791 0.250005L19.4839 50.9938Z" fill="#202426"/>
                            </svg>
                        </div>
                        <div class="comment-text-content">
                            ${data.comment}
                        </div>
                    </div>
                </div>
                <div class="graph-group">
                    <div class="graph-container">
                        <div class="data-text-group">
                            <div class="data-text positive"><span class="percent">賛成</span>${Math.round((data.totalAgreeRate) * 100)}<span class="percent">%</span></span><span class="percent">(${data.totalAgrees})</span></div>
                            <div class="data-text negative"><span class="percent">反対</span>${Math.round((data.totalDisagreeRate) * 100)}<span class="percent">%</span></span><span class="percent">(${data.totalDisagrees})</span></div>
                            <div class="data-text neutral"><span class="percent">どちらでもない</span>${Math.round((data.totalPassRate) * 100)}<span class="percent">%</span></span><span class="percent">(${data.totalPasses})</span></div>
                        </div>
                        <div class="graph-item">
                            <div class="graph-bar positive" style="width:${(data.totalAgreeRate) * 100}%"></div>
                            <div class="graph-bar negative" style="width:${(data.totalDisagreeRate) * 100}%"></div>
                            <div class="graph-bar neutral" style="width:${(data.totalPassRate) * 100}%"></div>
                        </div>
                    </div>
                    <div class="caption">グループ別の回答割合</div>
                    <div class="group-graph-container">
                        ${groupHtml}
                    </div>
                    <div class="graph-sample">
                        <div class="graph-sample-element"><div class="graph-sample-square agree"></div><div class="graph-sample-text">賛成</div></div>
                        <div class="graph-sample-element"><div class="graph-sample-square disagree"></div><div class="graph-sample-text">反対</div></div>
                        <div class="graph-sample-element"><div class="graph-sample-square pass"></div><div class="graph-sample-text">わからない/どちらでもない</div></div>
                    </div>
                </div>
            </div>
    `;
    });

    const firstFiveList = listHtmlList.slice(0, 5);  // 先頭5件
    const remainingList = listHtmlList.slice(5);     // 6件目以降

    const firstFiveListHTML = `
        <div class="comment-list">
            ${firstFiveList.join("")}
        </div>
    `
    const remainingListHTML = (remainingList.length > 0) ? `
        <div id="top-comments-acordion" class="comment-acordion-list acordion">
            <div class="scroll-content">
                ${remainingList.join("")}
            </div>
        </div>
    ` : "";

    const groupHtml = `
        <div class="comment-wrapper">
            <div class="title">${label}</div>
            ${firstFiveListHTML}
            ${remainingListHTML}
            <button class="accordion-button button secondary-border" data-target="#top-comments-acordion">もっと見る</button>
        </div>
    `;

    return groupHtml;
}

/**
 * グループ円グラフ（circle-graph-item）にツールチップをバインドする
 * @returns {void}
 */
function bindCircleGraphTooltips() {
    const items = document.querySelectorAll('.group-graph-container .circle-graph-item');
    if (!items || items.length === 0) return;

    items.forEach((item) => {
        const groupLetter = item.dataset.group;
        if (!groupLetter) return;

        const showHandler = (ev) => {
            ev.stopPropagation();
            GroupTooltip.showForGroup(groupLetter, item);
        };

        item.addEventListener('click', showHandler);
        item.addEventListener('touchend', showHandler, { passive: true });
        item.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                showHandler(ev);
            }
        });
    });
}

/**
 * 指定のアコーディオン（パネル）の高さを、内部コンテンツの高さに合わせて更新する。
 *
 * @param {HTMLElement} panelElement - 対象のパネル要素（.modal-stepper）。
 * @returns {void}
 */
function adjustTargetAcordion() {
    const accordionElements = document.querySelectorAll('.acordion');
    
    if (!accordionElements) return;

    accordionElements.forEach((accordion) => {
        const scrollContent = accordion.querySelector('.scroll-content');
        let idealHeight = (scrollContent.scrollHeight + 8);

        if (!accordion.classList.contains("show")) {
            idealHeight = 0;
        };
    
        accordion.style.maxHeight = (idealHeight) + 'px';
        
        requestAnimationFrame(function () {
            accordion.style.maxHeight = (idealHeight) + 'px';
        });
    })
}

function bindAccordionToggle() {
    const accordionButtonList = document.querySelectorAll('.accordion-button');
    
    accordionButtonList.forEach((accordionButton) => {
        accordionButton.addEventListener('click', () => {
            console.log("アコーディオン開閉処理発火");
            
            const targetSelector = accordionButton.dataset.target;
            if (!targetSelector) { return; }

            const targetElement = document.querySelector(targetSelector);
            if (!targetElement) { return; }

            const shouldShow = !targetElement.classList.contains('show');
            targetElement.classList.toggle('show', shouldShow);

            adjustTargetAcordion();
            scrollPolisReportToAccordion(targetElement, shouldShow);

            accordionButton.textContent = shouldShow ? "閉じる" : "もっと見る"
        });
    });
}

/**
 * .polis-report 内で、指定アコーディオン要素の上部が
 * コンテナの上に来るようにスクロールする。
 *
 * @param {HTMLElement} accordionElement - スクロール位置を合わせたいアコーディオン要素
 * @returns {void}
 */
function scrollPolisReportToAccordion(accordionElement, show) {
    if (!accordionElement) {
        return;
    }

    // accordionElement の祖先から .polis-report を探す
    const polisReportElement = accordionElement.closest('.polis-report');

    // 祖先に .polis-report が無い場合は画面全体スクロールにフォールバック
    if (!polisReportElement) {
        accordionElement.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
        });
        return;
    }

    // .polis-report（スクロールコンテナ）の位置とサイズを取得する
    // → viewport（画面）から見た相対的な座標が入る
    const reportRect = polisReportElement.getBoundingClientRect();

    // 折りたたみ要素（アコーディオン本体）の位置とサイズを取得する
    // → これも viewport 基準
    const accordionRect = accordionElement.getBoundingClientRect();

    /**
     * スクロール先の scrollTop を計算する。
     *
     * polisReportElement.scrollTop
     *   …現在のスクロール位置
     *
     * (accordionRect.top - reportRect.top)
     *   …画面上での相対位置の差分（アコーディオンの上端が、
     *     .polis-report の上端からどれだけ下にあるか）
     *
     * → 現在のスクロール量に、この差分を足すことで、
     *    アコーディオン要素の上端が .polis-report の上端に
     *    ちょうど揃う scrollTop の値を算出している。
     */
    const targetScrollTop =
        polisReportElement.scrollTop + (accordionRect.top - reportRect.top) + (show ? 0 : (window.innerHeight / 2 * -1));

    polisReportElement.scrollTo({
        top: targetScrollTop,
        behavior: 'smooth',
    });
}


/**
 * コメント群（特定グループ指標）をHTMLに整形して返す。
 * 
 * 指定グループ `groupName` の賛成/反対/パス比率バーのみを表示するレイアウトを生成する。
 * 
 * @param {Array<Object>} displayDataList - 表示用データ配列（各要素は groupData を含む）。
 * @param {string} label - セクションタイトル文言。
 * @param {string} groupName - 対象グループ名。
 * @returns {string} - 生成されたHTML文字列。
 */
function getGroupCommentsInnerHTML(groupData) {
    const displayDataList = groupData.groupAgreedData;
    const label = `グループ${String(groupData.groupName).toUpperCase()}が賛成した意見`;
    const groupName =  groupData.groupName;

    const listHtmlList = displayDataList.map(data => {
        // 表示対象データを取得
        const targetData = data.groupData.find(g => g.groupName === groupName)

        const positivePercent = Math.round((targetData.agreeRate) * 100);
        const negativePercent = Math.round((targetData.disagreeRate) * 100);
        const passPercent = Math.round((targetData.passRate) * 100);
        
        return `
            <div class="comments-item">
                <div class="comments-text-group">
                    <div class="comment-person-img-group">
                        <img class="comment-person-img" src="${COMMENT_ICON_LIST[getRandomInt(0, (COMMENT_ICON_LIST.length - 1))]}" alt="">
                    </div>
                    <div class="comments-text">
                        <div class="comment-arrow">
                            <svg xmlns="http://www.w3.org/2000/svg" width="33" height="54" viewBox="0 0 33 54" fill="none">
                                <path d="M19.4839 50.9938C18.7096 53.9943 14.4486 53.9943 13.6743 50.9938L0.579104 0.250003L32.5791 0.250005L19.4839 50.9938Z" fill="#202426"/>
                            </svg>
                        </div>
                        <div class="comment-text-content">
                            ${data.comment}
                        </div>
                    </div>
                </div>
                <div class="graph-group">
                    <div class="caption"></i>回答の割合</div>
                    <div class="graph-container">
                        <div class="data-text-group">
                            <div class="data-text positive"><span class="percent">賛成</span>${positivePercent}<span class="percent">%</span><span class="percent">(${targetData.agrees})</span></div>
                            <div class="data-text negative"><span class="percent">反対</span>${negativePercent}<span class="percent">%</span><span class="percent">(${targetData.disagrees})</span></div>
                            <div class="data-text neutral"><span class="percent">どちらでもない</span>${passPercent}<span class="percent">%</span><span class="percent">(${targetData.passes})</span></div>
                        </div>
                        <div class="graph-item">
                            <div class="graph-bar positive" style="width:${positivePercent}%"></div>
                            <div class="graph-bar negative" style="width:${negativePercent}%"></div>
                            <div class="graph-bar neutral" style="width:${passPercent}%"></div>
                        </div>
                    </div>
                </div>
            </div>
    `;
    });

    const firstFiveList = listHtmlList.slice(0, 5);  // 先頭5件
    const remainingList = listHtmlList.slice(5);     // 6件目以降

    const firstFiveListHTML = `
        <div class="comment-list">
            ${firstFiveList.join("")}
        </div>
    `
    const remainingListHTML = (remainingList.length > 0) ? `
        <div id="group-${groupData.groupName}-comments-acordion" class="comment-acordion-list acordion">
            <div class="scroll-content">
                ${remainingList.join("")}
            </div>
        </div>
    ` : "";


    const groupHtml = `
        <div class="comment-wrapper">
            <div class="title">${label}</div>
            ${firstFiveListHTML}
            ${remainingListHTML}
            <button class="accordion-button button secondary-border" data-target="#group-${groupData.groupName}-comments-acordion">もっと見る</button>
        </div>
    `;

    return groupHtml;
}

/**
 * コメント群（特定グループ指標）をHTMLに整形して返す。
 * 
 * 指定グループ `groupName` の賛成/反対/パス比率バーのみを表示するレイアウトを生成する。
 * 
 * @param {Array<Object>} displayDataList - 表示用データ配列（各要素は groupData を含む）。
 * @param {string} label - セクションタイトル文言。
 * @param {string} groupName - 対象グループ名。
 * @returns {string} - 生成されたHTML文字列。
 */
function getGroupInfoInnerHTML(groupData) {
    const displayDataList = groupData.groupAgreedData;
    const groupName =  groupData.groupName;

    const listHtml = displayDataList.slice(0, 3).map(data => {
        // 表示対象データを取得
        const targetData = data.groupData.find(g => g.groupName === groupName)
        return `
            <div class="group-comment">
                <div class="text">${data.comment}</div>
            </div>
    `;
    }).join('');

    const groupHtml = `
        <div id="group-${String(groupData.groupName).toLowerCase()}" class="group-item">
            <div class="group-name-label-group group-${String(groupData.groupName).toLowerCase()}">
                <div class="group-name-label">
                    グループ${String(groupData.groupName).toUpperCase()}
                </div>
            </div>
            <div class="group-comment-group">
                <div class="group-comment-title">このグループの代表的な意見</div>
                <div class="group-comment-list">
                    ${listHtml}
                </div>
            </div>
        </div>
    `;

    return groupHtml;
}

/**
 * 全体の賛成率（totalAgreeRate）で降順ソートする。
 * 同率の場合は totalVotes の多い順。
 * 
 * 依存: toNum, toInt
 * 
 * @param {Array<Object>} list - ソート対象配列。
 * @returns {Array<Object>} - 新しい配列を返す（元配列は変更しない）。
 */
function sortByTotalAgreeRate(list) {
    return list.slice().sort((a, b) => {
        const ra = toNum(a.totalAgreeRate);
        const rb = toNum(b.totalAgreeRate);
        if (ra !== rb) return rb - ra;
        return toInt(b.totalVotes) - toInt(a.totalVotes); // 同率なら票数多い順
    });
};

/**
 * 指定グループの賛成率で降順ソートする。
 * 同率の場合は当該グループの totalVotes の多い順。
 * 
 * 依存: getGroupAgreeRate
 * 
 * @param {Array<Object>} list - ソート対象配列（各要素は groupData を含む）。
 * @param {string} groupName - 対象グループ名。
 * @returns {Array<Object>} - 新しい配列を返す（元配列は変更しない）。
 */
function sortByGroupAgreeRate(list, groupName) {

    return list.slice().sort((a, b) => {
        const ra = getGroupAgreeRate(a, groupName);
        const rb = getGroupAgreeRate(b, groupName);
        if (ra !== rb) return rb - ra;
        const va = a.groupData?.find((g) => g.groupName === groupName)?.totalVotes || 0;
        const vb = b.groupData?.find((g) => g.groupName === groupName)?.totalVotes || 0;
        return vb - va; // 同率なら票数多い順
    });
};

function getDisplayDataFromCSVJSON(csvJson) {
    // 各グラフ表示用のリストに加工
    const displayData = csvJson.map((rowData) => {
        const comment = rowData.comment;
        const commentId = rowData["comment-id"];
        const totalAgrees = rowData["total-agrees"];
        const totalDisagrees = rowData["total-disagrees"];
        const totalPasses = rowData["total-passes"];
        const totalVotes = rowData["total-votes"];

        // 入力の votes があっても、合計値を信頼して再計算
        const totalAgreeRate = (totalVotes > 0) ? (totalAgrees / totalVotes) : 0;
        const totalDisagreeRate = (totalVotes > 0) ? (totalDisagrees / totalVotes) : 0;
        const totalPassRate = (totalVotes > 0) ? (totalPasses / totalVotes) : 0;

        const result = {
            "comment" : comment,
            "commentId" : commentId,
            "totalAgrees" : totalAgrees,
            "totalDisagrees" : totalDisagrees,
            "totalPasses" : totalPasses,
            "totalVotes" : totalVotes,
            "totalAgreeRate" : totalAgreeRate,
            "totalDisagreeRate" : totalDisagreeRate,
            "totalPassRate" : totalPassRate,
        };

        const groupData = extractGroups(rowData)
        result.groupData = groupData;

        return result;
    })

    return displayData;
}

/**
 * 記事セクション（全体および各グループ）を初期化して描画する。
 * 
 * conversation_id に紐づく CSV を取得・パースし、表示用に加工したのち、
 * 「みんなが賛成した意見」と各グループ別のリストHTMLを生成・挿入する。
 * 
 * 依存: getConversationId, loadCsvAsJson, extractGroups, getGroups, sortByTotalAgreeRate, sortByGroupAgreeRate,
 *       buildTopicInnerHTML, getGroupCommentsInnerHTML
 * 
 * @async
 * @returns {Promise<void>} - 描画完了時に解決。
 * @throws {Error} - コンテナ要素が見つからない場合など。
 */
async function initializeArticles() {
    const conversationId = getConversationId();
    // CSVからデータをパース
    const csvJson = await loadCsvAsJson(`/csv/report/report_${conversationId}.csv`)

    // 各グラフ表示用のリストに加工
    const displayData = getDisplayDataFromCSVJSON(csvJson);

    // 含まれるグループ一覧を取得
    const groups = getGroups(csvJson[0]);

    // 全体の賛成率が高いリストを取得
    const sortedByTotal = sortByTotalAgreeRate(displayData);

    // 各グループの賛成率が高いリストを取得
    const sortedByGroup = groups.map((groupName) => {
        const sortedByGroup = sortByGroupAgreeRate(displayData, groupName);
        const result = {
            "groupName" : groupName,
            "groupAgreedData" : sortedByGroup,
        }

        return result;
    })
    
    // グループデータのキャッシュを準備（ツールチップで利用）
    groupDataCacheByName = {};
    sortedByGroup.forEach((g) => {
        groupDataCacheByName[String(g.groupName).toLowerCase()] = g;
    });

    // 取得したデータから各DOMを生成する
    // 生成用の親要素取得
    const container = document.querySelector('.report-list-container');
    const groupInfoContainer = document.querySelector('.group-info-container .group-item-list');

    if (!container || !groupInfoContainer) throw new Error(`親要素が見つかりません: .report-container`);

    container.innerHTML = '';
    // 全体のリスト
    const totalHTML = buildTopicInnerHTML(sortedByTotal, "みんなが賛成した意見");

    // グループ別のリスト
    const groupHTML = sortedByGroup.map((groupData) => {
        return getGroupCommentsInnerHTML(groupData);
    }).join("");

    container.innerHTML += totalHTML;
    container.innerHTML += groupHTML;

    // 円グラフのツールチップをバインド
    bindCircleGraphTooltips();

    // グループ紹介
    const groupInfoHTML = sortedByGroup.map((groupData) => {
        return getGroupInfoInnerHTML(groupData);
    }).join("");

    groupInfoContainer.innerHTML = groupInfoHTML;
}

// ==============================
// クリップボード関連
// ==============================

/**
 * モーダル管理用のマネージャー
 */
let modalManager = null;

/**
 * コピー完了通知用モーダルを初期化する。
 * 
 * `#copy-complete-modal` を対象に ModalManager を生成し、init() を実行する。
 * 
 * 依存: ModalManager
 * 
 * @returns {void}
 */
function initializeModal() {
    // モーダルを初期化
    modalManager = new ModalManager({
        rootSel: "#copy-complete-modal",
        windowSel: ".modal-window",
        closeBtnSel: ".modal-close-button",
    });
    modalManager.init();
}

/**
 * 共有ボタンのクリック/タップで、会話詳細URLをクリップボードへコピーし、完了モーダルを表示する。
 * 
 * コピー後はボタンを一時的に無効化してフィードバックを行う。
 * 
 * 依存: initializeModal, getConversationId, copyText, ModalManager#showModal
 * 
 * @returns {void}
 */
function bindClipBoardCopy() {
    // 完了後のモーダルを初期化
    initializeModal();

    // ボタンクリックで data-copy をコピー（イベント委譲でもOK）
    const shareButton = document.querySelector('.share-button');
    
    // クリップボードコピー用のハンドラ
    const handler = async (ev) => {
        ev.preventDefault();
        
        const conversationId = getConversationId();
        const text = `https://share.pol-is.jp/link?conversation_id=${conversationId}`;
        const share_text = `\
テーマ : ${detailData.title}
${text}
#Polis #ブロードリスニング\
        `;

        const simpleLinkInputGroup = document.querySelector('#simple-link-share-input-group');
        const snsShareInputGroup = document.querySelector('#sns-message-share-input-group');
        // 初期化
        simpleLinkInputGroup.querySelector('.copy-complete-tip').classList.remove("show");
        snsShareInputGroup.querySelector('.copy-complete-tip').classList.remove("show");

        simpleLinkInputGroup.querySelector('.share-input').value = text;
        snsShareInputGroup.querySelector('.share-input').value = share_text;

        simpleLinkInputGroup.querySelector('.copy-button').addEventListener('click', () => {
            copyText(text);
            simpleLinkInputGroup.querySelector('.copy-complete-tip').classList.add("show");
            setTimeout(() => {
                simpleLinkInputGroup.querySelector('.copy-complete-tip').classList.remove("show");
            }, 1500);
        });
        snsShareInputGroup.querySelector('.copy-button').addEventListener('click', () => {
            copyText(share_text);
            snsShareInputGroup.querySelector('.copy-complete-tip').classList.add("show");
            setTimeout(() => {
                snsShareInputGroup.querySelector('.copy-complete-tip').classList.remove("show");
            }, 1500);
        });

        autoResizeTextareas(null, 0);
        modalManager.showModal();
    };

    // クリック・タップ双方を網羅
    shareButton.addEventListener('click', handler, { passive: false });
    shareButton.addEventListener('touchend', handler, { passive: false });
}

let detailData = null;

async function initializeLink() {
    const conversationId = getConversationId();
    const csvJson = await loadCsvAsJson("/csv/themes.csv")
    const targetConversation = csvJson.find((conversation) => conversation.conversation_id === conversationId);
    const reportDetailButton = document.querySelector('#detail-report-button');
    reportDetailButton.setAttribute("href", `https://pol.is/report/${targetConversation.report_id}`);
    detailData = targetConversation;
}

/**
 * リンク要素への処理を追加
 * 
 * @returns {void}
 */
function bindDetailLink() {
    const targetElements = [document.querySelector(".back")];

    targetElements.forEach((element) => {
        element.addEventListener("click", (e) => {
            e.stopPropagation();
            
            setGrobalLoading(true);

            setTimeout(() => {
                window.location = `${window.location.origin}${element.getAttribute("href")}`;
            }, 500);
        });
    });
}

// ウィンドウ初期化時にイベントを割り当て
document.addEventListener("DOMContentLoaded", () => {
    bindTabs();
    hideLoading();
    initializeTutorial();
    initializePolisIframe();
    bindClipBoardCopy();
    initializeArticles();
    initializeLink();
    bindDetailLink();
    bindPageReturn();
    setTimeout(() => {
        bindAccordionToggle();
    }, 500);
});