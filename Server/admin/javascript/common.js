// ==============================
// Cookie操作関連
// ==============================

function getCookie(name) {
    const m = document.cookie.match(new RegExp('(?:^|; )' + encodeURIComponent(name) + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : null;
}
function setCookie(name, value, days = 365) {
    const d = new Date();
    d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
    // HTTPS運用なら Secure を付与してください
    document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; expires=${d.toUTCString()}; path=/; SameSite=Lax`;
}
function deleteCookie(name) {
    document.cookie = `${encodeURIComponent(name)}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax`;
}


// ==============================
// 汎用処理
// ==============================

// 数値に正規化（"13" -> 13, null/undefined/NaN -> 0）
const toInt = (v) => {
    const n = typeof v === "number" ? v : parseInt(v, 10);
    return Number.isFinite(n) ? n : 0;
};

const toNum = (v) => {
    const n = typeof v === "number" ? v : Number(v);
    return Number.isFinite(n) ? n : 0;
};

const getRandomInt = (min, max) => {
    // min, max を整数に丸める
    min = Math.ceil(min);
    max = Math.floor(max);

    // Math.random() は 0以上1未満
    // → (max - min + 1) を掛けて範囲を作り、min を足す
    return Math.floor(Math.random() * (max - min + 1)) + min;
};

// theme-color を動的に変更する関数
const setThemeColor = (colorHEX, delayTime) => {
    let metaTag = document.querySelector("meta[name='theme-color']");

    setTimeout(() => {
        // metaタグが存在しなければ新規追加
        if (!metaTag) {
            metaTag = document.createElement("meta");
            metaTag.setAttribute("name", "theme-color");
            document.head.appendChild(metaTag);
        }
    
        // 色を設定
        metaTag.setAttribute("content", colorHEX);
    }, delayTime);
};

const formatIsoToJapaneseDate = (isoString) => {
    if (!isoString) return '';

    const date = new Date(isoString);
    if (isNaN(date)) return '';

    const year = date.getFullYear();
    const month = date.getMonth() + 1; // 月は0始まり
    const day = date.getDate();

    return `${year}年${month}月${day}日`;
};

/**
 * 指定URLへフォームPOST通信し、JSONを取得する非同期メソッド
 * @param {string} url - 通信先URL
 * @param {Object|FormData} data - POSTするデータ（オブジェクトまたはFormData）
 * @param {Object} [options={}] - オプション（例: ヘッダー追加など）
 * @returns {Promise<Object>} - JSONオブジェクトを返すPromise
 */
const fetchJsonPost = async (url, data, options = {}) => {
    let body;

    // dataがFormDataでなければ、自動変換
    if (data instanceof FormData) {
        body = data;
    } else {
        body = new FormData();
        for (const key in data) {
            if (Object.prototype.hasOwnProperty.call(data, key)) {
                body.append(key, data[key]);
            }
        }
    }

    // Content-Type は fetch が自動設定するため指定しない
    const headers = {
        'Accept': 'application/json',
        ...(options.headers || {})
    };

    const response = await fetch(url, {
        method: 'POST',
        headers,
        body,
        ...options
    });

    if (!response.ok) {
        throw new Error(`HTTPエラー: ${response.status} (${response.statusText})`);
    }

    try {
        return await response.json();
    } catch {
        throw new Error('レスポンスのJSONパースに失敗しました');
    }
};

// 可変 textarea 初期化関数
const autoResizeTextareas = () => {
    const textareas = document.querySelectorAll('textarea.auto-resize');
    textareas.forEach(textarea => {
        const resize = () => {
            textarea.style.height = 'auto'; // 一旦リセット
            textarea.style.height = `${textarea.scrollHeight}px`; // 実際の内容に合わせる
        };

        // 入力時に高さ更新
        textarea.addEventListener('input', resize);

        // 初期表示時にも一度実行
        resize();
    });
};


// ==============================
// 時刻関連
// ==============================

// 時刻取得 (AM4:00更新)
function getLogicalDayId(date = new Date()) {
    const shifted = new Date(date.getTime() - 4 * 60 * 60 * 1000); // 0:00-3:59 を前日扱い
    const y = shifted.getFullYear();
    const m = String(shifted.getMonth() + 1).padStart(2, "0");
    const d = String(shifted.getDate()).padStart(2, "0");
    return `${y}${m}${d}`; // "YYYYMMDD"
}


// ==============================
// CSV読み込み関連
// ==============================

const loadCsvAsJsonAsync = (url, options) => {loadCsvAsJson(url, options)}
async function loadCsvAsJson(url, { encoding = 'utf-8', delimiter = 'auto' } = {}) {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = await res.arrayBuffer();
    const text = new TextDecoder(encoding).decode(buf);
    const { rows, headers } = parseCSV(text, delimiter);
    // ヘッダーをキーにしてオブジェクト化
    return rows.map(r => {
        const obj = {};
        headers.forEach((h, i) => (obj[h] = r[i] ?? ''));
        return obj;
    });
}

function parseCSV(text, delimiter = 'auto') {
    // 改行を正規化
    text = text.replace(/\r\n?/g, '\n');

    // 区切り文字の自動判定（1行目を対象）
    if (delimiter === 'auto') {
        const firstLine = text.split('\n', 1)[0] ?? '';
        const cand = [',', '\t', ';'];
        delimiter = cand.reduce((best, d) => {
            const count = splitLine(firstLine, d).length;
            return count > best.count ? { d, count } : best;
        }, { d: ',', count: 0 }).d;
    }

    // 1文字ずつパース（クォート内の改行/カンマ対応）
    const rows = [];
    let row = [];
    let field = '';
    let inQuotes = false;

    for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (inQuotes) {
            if (ch === '"') {
                const next = text[i + 1];
                if (next === '"') { // エスケープされたダブルクォート
                    field += '"';
                    i++;
                } else {
                    inQuotes = false;
                }
            } else {
                field += ch;
            }
        } else {
            if (ch === '"') {
                inQuotes = true;
            } else if (ch === delimiter) {
                row.push(field);
                field = '';
            } else if (ch === '\n') {
                row.push(field);
                rows.push(row);
                row = [];
                field = '';
            } else {
                field += ch;
            }
        }
    }
    // 最終フィールド/行を反映
    row.push(field);
    rows.push(row);

    // ヘッダー抽出（BOM除去）
    const headers = (rows.shift() || []).map(h => h.replace(/^\uFEFF/, '').trim());

    // 列数不足/超過に緩く対応（不足は空文字、超過は無視）
    const normalized = rows.map(r => {
        const arr = r.slice(0, headers.length);
        while (arr.length < headers.length) arr.push('');
        return arr;
    });

    return { rows: normalized, headers, delimiter };
}

// 行内の簡易スプリット（自動判定用：クォートをそこまで厳密に扱う必要はない）
function splitLine(line, d) {
    let arr = [], cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {
        const c = line[i];
        if (c === '"') {
            if (inQ && line[i + 1] === '"') { cur += '"'; i++; }
            else inQ = !inQ;
        } else if (!inQ && c === d) {
            arr.push(cur); cur = '';
        } else {
            cur += c;
        }
    }
    arr.push(cur);
    return arr;
}


// ==============================
// クリップボード関連
// ==============================

// ユーティリティ：writeText が使えない場合のフォールバック
const legacyCopy = (text) => {
    const ta = document.createElement('textarea');

    ta.value = text;
    // なるべく画面に影響を出さない配置
    ta.style.position = 'fixed';
    ta.style.top = '-9999px';
    ta.setAttribute('readonly', '');
    
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);

    console.log(`クリップボードにコピーしました : ${text}`);
    
    return ok;
};

const copyText = async (text) => {
    // セキュアコンテキスト(https)で且つAPIがあれば使う
    if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
            await navigator.clipboard.writeText(text);
            console.log(`クリップボードにコピーしました : ${text}`);
            
            return true;
        } catch {
            // 明示フォールバック
            return legacyCopy(text);
        }
    }
    return legacyCopy(text);
};


// ==============================
// チュートリアル関連
// ==============================

/* 
使用箇所では下記のようにクラスごと初期化しておく

let tutorialManager = null;

// チュートリアルを初期化
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
*/

class TutorialManager {
    constructor(options = {}) {

        // DOMセレクタ
        this.rootSel = options.rootSel ?? "#tutorial";
        this.windowSel = options.windowSel ?? ".tutorial-window";
        this.helpBtnSel = options.helpBtnSel ?? ".help-button";
        this.skipBtnSel = options.skipBtnSel ?? ".skip-button";
        this.optoutCheckboxSel = options.optoutCheckboxSel ?? "#hidden-checkbox";

        // 保存キー
        this.KEY_LAST = options.keyLast ?? "tutorial_last_shown";
        this.KEY_OPTOUT = options.keyOptout ?? "tutorial_optout"; // "1"で自動表示抑止

        // 上部ヘッダー色指定
        this.defaultThemeColor = options.defaultThemeColor ?? "#FFF";
        this.tutorialThemeColor = options.tutorialThemeColor ?? "#FFF"; // "1"で自動表示抑止

        // 表示制御
        this.autoShowDelayMs = options.autoShowDelayMs ?? 800;
        this.dayRolloverHour = options.dayRolloverHour ?? 4; // 4時区切り

        // 内部状態
        this.current = 0;
    }

    // ============ 公開メソッド ============
    init = () => {
        // 必要な要素取得
        this.tutorial = document.querySelector(this.rootSel);
        if (!this.tutorial) return; // 画面にない場合は何もしない

        this.tutorialWindows = this.tutorial.querySelectorAll(this.windowSel);
        this.helpBtn = document.querySelector(this.helpBtnSel);
        this.skipBtn = this.tutorial.querySelector(this.skipBtnSel);
        this.optoutCheckbox = document.querySelector(this.optoutCheckboxSel);

        // 「次へ」ボタンを各ウィンドウに割り当て
        this.tutorialWindows.forEach((win, index) => {
            const nextBtn = win.querySelector(".tutorial-button .next-button");
            if (!nextBtn) return;
            nextBtn.addEventListener("click", () => this.handleNext(index));
        });

        // ヘルプ（手動表示）
        if (this.helpBtn) {
            this.helpBtn.addEventListener("click", this.startTutorial);
        }

        // スキップ（閉じる）
        if (this.skipBtn) {
            this.skipBtn.addEventListener("click", this.closeTutorial);
        }

        // チェックボックス（自動表示オプトアウト）
        if (this.optoutCheckbox) {
            this.optoutCheckbox.checked = this.getOptOut();
            this.optoutCheckbox.addEventListener("change", () => {
                this.setOptOut(this.optoutCheckbox.checked);
            });
        }

        // 初回ロード時の自動表示
        this.runAutoTutorial();
    };

    // ============ 表示系 ============
    // チュートリアルを頭から開始
    startTutorial = () => {
        if (!this.tutorialWindows?.length) return;
        // すべて非表示
        this.tutorialWindows.forEach((win) => win.classList.remove("show"));
        // 最初のウィンドウから
        this.current = 0;
        this.tutorialWindows[this.current].classList.add("show");
        // 全体表示
        this.tutorial.classList.add("show");
        setThemeColor(this.tutorialThemeColor, 0);
    };

    // チュートリアルを閉じる
    closeTutorial = () => {
        if (!this.tutorial) return;
        this.tutorialWindows?.forEach((win) => win.classList.remove("show"));
        this.tutorial.classList.remove("show");
        setThemeColor(this.defaultThemeColor, 0);
    };

    // チュートリアルのページ送り
    handleNext = (index) => {
        if (!this.tutorialWindows?.length) return;
        // 現在ウィンドウを閉じる
        this.tutorialWindows[this.current]?.classList.remove("show");
        // 次へ
        this.current = index + 1;
        if (this.current < this.tutorialWindows.length) {
            this.tutorialWindows[this.current].classList.add("show");
        } else {
            // 最後の次は閉じる
            this.closeTutorial();
        }
    };

    // 自動表示の条件にあてはまれば、チュートリアルを表示
    runAutoTutorial = () => {
        const autoRun = this.shouldAutoShowToday();
        if (autoRun) {
            setTimeout(() => {
                this.startTutorial();
                this.markShownToday();
            }, this.autoShowDelayMs);
        }
    };

    // ============ 自動表示判定 ============
    shouldAutoShowToday = () => {
        return !this.getOptOut() && getCookie(this.KEY_LAST) !== getLogicalDayId();
    };

    markShownToday = () => {
        setCookie(this.KEY_LAST, getLogicalDayId());
    };

    // ============ オプトアウト ============
    setOptOut = (on = true) => {
        if (on) setCookie(this.KEY_OPTOUT, "1");
        else deleteCookie(this.KEY_OPTOUT);
    };

    getOptOut = () => {
        return getCookie(this.KEY_OPTOUT) === "1";
    };
}

// ==============================
// モーダル関連
// ==============================

/* 
使用箇所では下記のようにクラスごと初期化しておく

let modalManager = null;
function initializeModal() {
    // モーダルを初期化
    modalManager = new ModalManager({
        rootSel: ".slide-modal",
        windowSel: ".modal-window",
        closeBtnSel: ".modal-close-button",
    });
    modalManager.init();
    modalManager.bindShowButton(".modal-show-button")
}
*/

class ModalManager {
    constructor(options = {}) {
        // DOMセレクタ
        this.rootSel = options.rootSel ?? ".slide-modal";
        this.windowSel = options.windowSel ?? ".modal-window";
        this.closeBtnSel = options.closeBtnSel ?? ".modal-close-button";
    }

    // ============ 公開メソッド ============
    init = () => {
        // 必要な要素取得
        this.modalRoot = document.querySelector(this.rootSel);
        if (!this.modalRoot) return; // 画面にない場合は何もしない

        this.modalWindow = this.modalRoot.querySelectorAll(this.windowSel);
        this.closeBtn = this.modalRoot.querySelector(this.closeBtnSel);

        // 閉じるボタン
        if (this.closeBtn) {
            this.closeBtn.addEventListener("click", this.closeModal);
        }

        // 背景クリックで閉じる
        this.modalRoot.addEventListener("click", this.closeModal);
    };

    // ============ 表示系 ============
    // 表示ボタンに処理を割り当て
    bindShowButton = (showButtonSel) => {
        // 必要な要素取得
        const showButton = document.querySelector(showButtonSel);
        if (!showButton) return;
        // 全体表示
        showButton.addEventListener("click", this.showModal);
    };

    // モーダルを表示
    showModal = () => {
        if (!this.modalRoot) return;
        // 全体表示
        this.modalRoot.classList.add("show");
    };

    // モーダルを閉じる
    closeModal = () => {
        if (!this.modalRoot) return;
        this.modalRoot.classList.remove("show");
    };
}