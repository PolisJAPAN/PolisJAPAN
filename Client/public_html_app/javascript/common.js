// ==============================
// 定数
// ==============================

/**　API通信先エンドポイント */
const API_URL = "https://api.pol-is.jp/"

/**　ロボットアクセス避けの操作キー */
const USER_ACCESS_KEY = "UbtWv4Kcjbn4Bk0fTn"

// ==============================
// Cookie操作関連
// ==============================

/**
 * 指定名のCookie値を取得する。
 * @param {string} name - 取得したいCookieのキー名。
 * @returns {string|null} - 見つかった場合はデコード済みの値、存在しない場合はnull。
 */
function getCookie(name) {
    const m = document.cookie.match(new RegExp('(?:^|; )' + encodeURIComponent(name) + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : null;
}

/**
 * 指定名でCookieを保存（更新）する。SameSite=Lax、path=/ を付与する。
 * @param {string} name - 保存するCookieのキー名。
 * @param {string} value - 保存するCookieの値（自動でURLエンコードされる）。
 * @param {number} [days=365] - 有効期限（日数）。現在時刻からの相対日数で設定。
 * @returns {void}
 */
function setCookie(name, value, days = 365) {
    const d = new Date();
    d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
    // HTTPS運用なら Secure を付与してください
    document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; expires=${d.toUTCString()}; path=/; SameSite=Lax`;
}

/**
 * 指定名のCookieを削除する。過去日時のexpiresを設定して無効化する。
 * @param {string} name - 削除するCookieのキー名。
 * @returns {void}
 */
function deleteCookie(name) {
    document.cookie = `${encodeURIComponent(name)}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax`;
}

// ==============================
// localStorage操作関連
// ==============================

/**
 * 指定キーのlocalStorage値を取得する。
 * @param {string} key - 取得したいキー名。
 * @returns {string|null} - 見つかった場合は値、存在しない場合はnull。
 */
function getLocalStorage(key) {
    try {
        const value = localStorage.getItem(key);
        return value !== null ? value : null;
    } catch (_error) {
        console.error(_error);
        return null;
    }
}

/**
 * 指定キーでlocalStorageに保存（更新）する。
 * @param {string} key - 保存するキー名。
 * @param {string} value - 保存する値。
 * @returns {void}
 */
function setLocalStorage(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch (_error) {
        console.error(_error);
    }
}

/**
 * 指定キーのlocalStorageを削除する。
 * @param {string} key - 削除するキー名。
 * @returns {void}
 */
function deleteLocalStorage(key) {
    try {
        localStorage.removeItem(key);
    } catch (_error) {
        console.error(_error);
    }
}



// ==============================
// 汎用処理
// ==============================

/**
 * 値を整数に正規化する。"13" 等の数値文字列は数値化し、無効値は 0 にフォールバックする。
 * @param {string} v - 変換対象の値。
 * @returns {number} - 有効な整数値。NaN/undefined/nullは0。
 */
function toInt(v) {
    const n = typeof v === "number" ? v : parseInt(v, 10);
    return Number.isFinite(n) ? n : 0;
};

/**
 * 値を数値型に正規化する。小数も許容し、無効値は 0 にフォールバックする。
 * @param {string} v - 変換対象の値。
 * @returns {number} - 有効な数値。NaN/undefined/nullは0。
 */
function toNum(v) {
    const n = typeof v === "number" ? v : Number(v);
    return Number.isFinite(n) ? n : 0;
};

/**
 * 指定範囲の整数乱数を返す。両端を含む閉区間 [min, max] を生成する。
 * @param {number} min - 生成範囲の下限（小数は切り上げ）。
 * @param {number} max - 生成範囲の上限（小数は切り捨て）。
 * @returns {number} - min以上max以下の整数。
 */
function getRandomInt(min, max) {
    // min, max を整数に丸める
    min = Math.ceil(min);
    max = Math.floor(max);

    // Math.random() は 0以上1未満
    // → (max - min + 1) を掛けて範囲を作り、min を足す
    return Math.floor(Math.random() * (max - min + 1)) + min;
};

/**
 * <meta name="theme-color"> のcontentを動的に更新する。タグが無ければ生成する。
 * @param {string} colorHEX - 設定する色（例: "#ffffff"）。
 * @param {number} delayTime - 設定を行うまでの遅延ミリ秒。
 * @returns {void}
 */
function setThemeColor(colorHEX, delayTime) {
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

/**
 * ISO8601文字列を "YYYY年M月D日" の日本語表記に変換する。
 * 無効または空文字の場合は空文字を返す。
 * @param {string} isoString - ISO8601形式の日時文字列。
 * @returns {string} - 日本語日付表記。無効時は ''。
 */
function formatIsoToJapaneseDate(isoString) {
    if (!isoString) return '';

    const date = new Date(isoString);
    if (isNaN(date)) return '';

    const year = date.getFullYear();
    const month = date.getMonth() + 1; // 月は0始まり
    const day = date.getDate();

    return `${year}年${month}月${day}日`;
};

/**
 * 指定URLへForm POSTし、JSONレスポンスを取得する。
 * dataがオブジェクトの場合はFormDataへ自動変換する。
 * @param {string} url - 送信先URL。
 * @param {Object|FormData} data - POSTするデータ。オブジェクトまたはFormData。
 * @param {RequestInit} [options={}] - fetchオプション（headers等を上書き可能）。
 * @returns {Promise<Object>} - パース済みJSONオブジェクト。
 * @throws {Error} - HTTPエラーやJSONパース失敗時。
 */
async function fetchJsonPost(url, data, options = {}) {
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

/**
 * class="auto-resize" を持つtextareaの高さを内容に合わせて自動調整する。
 * 初期化時と入力イベントで高さを更新する。
 * @param {function} onResize - リサイズ時のコールバック
 * @returns {void}
 */
function autoResizeTextareas(onResize = null) {
    const textareas = document.querySelectorAll('textarea.auto-resize');
    textareas.forEach(textarea => {
        const resize = () => {
            textarea.style.height = 'auto'; // 一旦リセット
            textarea.style.height = `${textarea.scrollHeight + 16}px`; // 実際の内容に合わせる
            
            if (!onResize) {return}

            onResize()
        };

        // 入力時に高さ更新
        textarea.addEventListener('input', resize);

        // 初期表示時にも一度実行
        resize();
    });
};

/**
 * class="auto-resize" を持つtextareaの高さを内容に合わせて自動調整する。
 * 初期化時と入力イベントで高さを更新する。
 * @returns {void}
 */
function syncTextareas(onResize = null) {
    const textareas = document.querySelectorAll('textarea.auto-resize');
    textareas.forEach(textarea => {
        const resize = () => {
            textarea.style.height = 'auto'; // 一旦リセット
            textarea.style.height = `${textarea.scrollHeight}px`; // 実際の内容に合わせる
            
            if (!onResize) {return}

            onResize()
        };

        // 初期表示時にも一度実行
        resize();
    });
};


// ==============================
// 時刻関連
// ==============================

/**
 * 「論理日付ID」を返す。日付区切りをAM4:00とし、"YYYYMMDD" 文字列で返却。
 * @param {Date} [date=new Date()] - 基準とする日時。省略時は現在時刻。
 * @returns {string} - 4時区切りでの "YYYYMMDD"。
 */
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

/**
 * (非同期)CSVを取得・デコードし、ヘッダー行をキーとしたオブジェクト配列へ変換する。
 * @param {string} url - CSVの取得先URL。
 * @param {{encoding?: string, delimiter?: ('auto'|string)}} [options] - 文字コード/区切りの指定。
 * @returns {Promise<Array<Object>>} - レコードの配列。各要素は{header:value}のオブジェクト。
 * @throws {Error} - HTTPステータス異常時。
 */
function loadCsvAsJsonAsync(url, options) {loadCsvAsJson(url, options)}
/**
 * CSVを取得・デコードし、ヘッダー行をキーとしたオブジェクト配列へ変換する。
 * @param {string} url - CSVの取得先URL。
 * @param {{encoding?: string, delimiter?: ('auto'|string)}} [options] - 文字コード/区切りの指定。
 * @returns {Promise<Array<Object>>} - レコードの配列。各要素は{header:value}のオブジェクト。
 * @throws {Error} - HTTPステータス異常時。
 */
async function loadCsvAsJson(url, { encoding = 'utf-8', delimiter = 'auto' } = {}) {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = await res.arrayBuffer();
    const text = new TextDecoder(encoding).decode(buf);
    const { rows, headers } = parseCSV(text, delimiter);
    console.log(rows);
    
    // ヘッダーをキーにしてオブジェクト化
    return rows.map(r => {
        const obj = {};
        headers.forEach((h, i) => (obj[h] = r[i] ?? ''));
        return obj;
    });
}

/**
 * CSVテキストをパースして行配列とヘッダーを返す。クォートや改行を考慮する。
 * @param {string} text - CSVテキスト。
 * @param {('auto'|string)} [delimiter='auto'] - 区切り文字。auto時は1行目から推定。
 * @returns {{rows: string[][], headers: string[], delimiter: string}} - 本文行、ヘッダー、使用区切り。
 */
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
    // 全てのフィールドが空でなければ行を追加
    if (! row.every((cell) => cell == ""))
    {
        rows.push(row);
    }

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

/**
 * 1行を簡易に分割する補助関数。
 * @param {string} line - 分割対象の1行テキスト。
 * @param {string} d - 区切り文字。
 * @returns {string[]} - 分割後のフィールド配列。
 */
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

/**
 * Clipboard API非対応時のフォールバックとして、textareaを用いて文字列をコピーする。
 * @param {string} text - コピーする文字列。
 * @returns {boolean} - コピー試行の成否。
 */
function legacyCopy(text) {
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

/**
 * 文字列をクリップボードへコピーする。可能ならClipboard APIを使用し、失敗時はフォールバックする。
 * @param {string} text - コピーする文字列。
 * @returns {Promise<boolean>} - コピーの成否。例外はフォールバック内で吸収。
 */
async function copyText(text) {
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
// ローディング関連
// ==============================

/**
 * API通信時のローディング画面を切り替え
 * @param {bool} isLoading
 * @returns {void}
 */
function setLoadingOverlay(isLoading) {
    const overlay = document.querySelector("#loading-block-overlay");
    overlay.classList.toggle("show", isLoading)
}


// ==============================
// チュートリアル関連
// ==============================

/**
 * チュートリアルを管理するクラス
 * HTMLに所定のDOMを配置した上で、インスタンス化して使用する
 * 
 * 使用箇所では下記のようにクラスごと初期化しておく
 * let tutorialManager = null;
 * 
 * // チュートリアルを初期化
 * function initializeTutorial() {
 *     tutorialManager = new TutorialManager({
 *         rootSel: "#tutorial",
 *         windowSel: ".tutorial-window",
 *         helpBtnSel: ".help-button",
 *         skipBtnSel: ".skip-button",
 *         optoutCheckboxSel: "#hidden-checkbox",
 *         keyLast: "tutorial_last_shown",
 *         keyOptout: "tutorial_optout",
 *     });
 *     tutorialManager.init();
 * }
 * 
 * @param {string} text - コピーする文字列。
 * @param {string} rootSel - ルートDOMのセレクタ
 * @param {string} windowSel - チュートリアルウィンドウのセレクタ
 * @param {string} helpBtnSel - ヘルプ表示ボタンのセレクタ
 * @param {string} skipBtnSel - スキップボタンのセレクタ
 * @param {string} optoutCheckboxSel - 再表示制御のチェックボックスのセレクタ
 * @param {string} keyLast - 最後に表示した時刻の保存用cookieのキー
 * @param {string} keyOptout - 自動表示の制御cookie保存用キー
 * @param {string} defaultThemeColor - 非表示時のテーマカラー(モバイル表示用)
 * @param {string} tutorialThemeColor - 表示時のテーマカラー(モバイル表示用)
 * @returns {TutorialManager} - インスタンス
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
    
    /**
     * TutorialManagerの初期化。DOM要素の取得、イベントバインド、自動表示判定などを行う。
     * @returns {void}
     */
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

    /**
     * チュートリアルを最初のウィンドウから開始し、オーバーレイを表示する。
     * @returns {void}
     */
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

    /**
     * チュートリアルを閉じ、表示状態とtheme-colorを元に戻す。
     * @returns {void}
     */
    closeTutorial = () => {
        if (!this.tutorial) return;
        this.tutorialWindows?.forEach((win) => win.classList.remove("show"));
        this.tutorial.classList.remove("show");
        setThemeColor(this.defaultThemeColor, 0);
    };


    /**
     * 現在のウィンドウを閉じ、次のインデックスのウィンドウを表示する。末尾ではチュートリアルを終了する。
     * @param {number} index - 現在のウィンドウのインデックス。
     * @returns {void}
 */
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

    /**
     * 自動表示条件に該当する場合、遅延後にチュートリアルを開始し、本日表示済みとして記録する。
     * @returns {void}
     */
    runAutoTutorial = () => {
        const autoRun = this.shouldAutoShowToday();
        if (autoRun) {
            setTimeout(() => {
                this.startTutorial();
                this.markShownToday();
            }, this.autoShowDelayMs);
        }
    };

    /**
     * 本日表示すべきかを判定する。オプトアウト状態と最終表示日のCookieを参照する。
     * @returns {boolean} - 自動表示すべきならtrue。
     */
    shouldAutoShowToday = () => {
        return !this.getOptOut() && getCookie(this.KEY_LAST) !== getLogicalDayId();
    };

    /**
     * 本日表示済みとしてCookieに論理日付IDを保存する。
     * @returns {void}
     */
    markShownToday = () => {
        setCookie(this.KEY_LAST, getLogicalDayId());
    };

    // ============ オプトアウト ============
    /**
     * 自動表示をオプトアウト/解除する。オン時はCookieに"1"を記録、オフ時は削除。
     * @param {boolean} [on=true] - オプトアウト有効ならtrue。
     * @returns {void}
     */
    setOptOut = (on = true) => {
        if (on) setCookie(this.KEY_OPTOUT, "1");
        else deleteCookie(this.KEY_OPTOUT);
    };

    /**
     * 自動表示のオプトアウト状態を取得する。
     * @returns {boolean} - オプトアウト中ならtrue。
     */
    getOptOut = () => {
        return getCookie(this.KEY_OPTOUT) === "1";
    };
}

// ==============================
// モーダル関連
// ==============================

/**
 * モーダルの表示・非表示を制御するクラス。
 * 
 * 指定されたDOM構造を基に、スライドイン型モーダルの開閉処理を統括する。
 * 
 * 主な機能:
 * - モーダルの初期化（要素取得・イベント設定）
 * - トリガーボタンによるモーダル表示
 * - 閉じるボタンおよび背景クリックによる閉鎖
 * 
 * 使用例:
 * let modalManager = null;
 * function initializeModal() {
 *     // モーダルを初期化
 *     modalManager = new ModalManager({
 *         rootSel: ".slide-modal",
 *         windowSel: ".modal-window",
 *         closeBtnSel: ".modal-close-button",
 *     });
 *     modalManager.init();
 *     modalManager.bindShowButton(".modal-show-button")
 * }
 * 
 * @param {Object} [options={}] - 設定オプション。
 * @param {string} [rootSel] - モーダル全体を包むルート要素のセレクタ。
 * @param {string} [windowSel] - モーダル本体ウィンドウのセレクタ。
 * @param {string} [closeBtnSel] - 閉じるボタンのセレクタ。
 * @returns {ModalManager} インスタンス
 */
class ModalManager {
    constructor(options = {}) {
        // DOMセレクタ
        this.rootSel = options.rootSel ?? ".slide-modal";
        this.windowSel = options.windowSel ?? ".modal-window";
        this.closeBtnSel = options.closeBtnSel ?? ".modal-close-button";
    }

    // ============ 公開メソッド ============
    /**
     * ModalManagerクラスの初期化処理。
     * DOM要素を取得し、閉じるボタンおよび背景クリックによるモーダル閉鎖イベントを設定する。
     * 対象要素が存在しない場合は何も行わない。
     * @returns {void}
     */
    init = () => {
        // 必要な要素取得
        this.modalRoot = document.querySelector(this.rootSel);
        if (!this.modalRoot) return; // 画面にない場合は何もしない
        
        this.modalWindow = this.modalRoot.querySelector(this.windowSel);
        if (!this.modalWindow) return; // 画面にない場合は何もしない

        this.closeBtn = this.modalRoot.querySelector(this.closeBtnSel);

        // 閉じるボタン
        if (this.closeBtn) {
            this.closeBtn.addEventListener("click", this.closeModal);
        }

        // 背景クリックで閉じる
        this.modalRoot.addEventListener("click", this.closeModal);
        this.modalWindow.addEventListener("click", (event) => {event.stopPropagation()});
    };

    // ============ 表示系 ============
    /**
     * 指定したボタンにモーダル表示イベントをバインドする。
     * ボタンをクリックするとモーダルを開く。
     * @param {string} showButtonSel - モーダル表示トリガーとなるボタンのセレクタ。
     * @returns {void}
     */
    bindShowButton = (showButtonSel) => {
        // 必要な要素取得
        const showButton = document.querySelector(showButtonSel);
        if (!showButton) return;
        // 全体表示
        showButton.addEventListener("click", this.showModal);
    };

    /**
     * モーダルを表示状態にする。
     * ルート要素に "show" クラスを付与して画面上に表示する。
     * @returns {void}
     */
    showModal = () => {
        if (!this.modalRoot) return;
        // 全体表示
        this.modalRoot.classList.add("show");
    };

    /**
     * モーダルを非表示にする。
     * ルート要素から "show" クラスを削除して画面から隠す。
     * @returns {void}
     */
    closeModal = () => {
        if (!this.modalRoot) return;
        this.modalRoot.classList.remove("show");
    };
}

/**
 * 引数として渡されたinputからvalueを一括抽出
 * @param {Array} inputElements - 抽出対象インプット配列
 * @returns {Array}
 */
function getMultiInputValues(inputElements) {
    if (!inputElements) {
        return [];
    }

    return inputElements.map((inputElement) => {
        if (!inputElement) {
            return "";
        }
        return inputElement.value ?? "";
    }).filter((value) => value !== "");
}

/**
 * 引数として渡されたinputにvalueを一括セット
 * @param {Array} inputElements - セット対象インプット配列
 * @param {Array} inputValueList - セット内容配列
 * @returns {void}
 */
function setMultiInputValues(inputElements, inputValueList) {
    if (!inputElements) {
        return;
    }

    inputElements.forEach((element, index) => {
        element.value = "";
    });

    inputValueList.forEach((inputValue, index) => {
        if (!inputElements[index]) return;
        inputElements[index].value = inputValue ?? "";
    });
}


// ==============================
// ボタン式セレクトの管理クラス
// ==============================

class CustomSelectManager {
    /**
     * @param {HTMLElement} containerElement - 選択肢ボタン群を内包するコンテナ
     * @param {string} optionSelector - 各ボタンのセレクタ（例: ".category-select-button"）
     * @param {string} dataIdentifier - 価値取得に使う data-* のキー（例: "value" → data-value）
     */
    constructor(options = {}) {
        this.containerElement = options.containerElement;
        this.optionSelector = options.optionSelector;
        this.dataIdentifier = options.dataIdentifier;
    }

    /**
     * 現在 active の値を取得
     * @returns {string|null}
     */
    getSelectedValue() {
        if (!this.containerElement) return null;

        const activeOptionElement = this.containerElement.querySelector(`${this.optionSelector}.active`);
        if (!activeOptionElement) return null;

        const selectedValue = activeOptionElement.dataset[this.dataIdentifier];
        return selectedValue ?? null;
    }

    /**
     * 指定した値を active に設定し、それ以外からは active を外す
     * 元コードのロジックをそのまま踏襲
     * @param {string|number} targetValue
     * @returns {void}
     */
    setSelectedValue(targetValue) {
        if (!this.containerElement) return;

        const optionNodeList = this.containerElement.querySelectorAll(`${this.optionSelector}`);

        optionNodeList.forEach((element, index) => {
            // 対象のオプションのvalueを取得
            const optionValue = element.dataset[this.dataIdentifier];

            // 対象値とオプション値が合致しているかどうか？
            const shouldActivate = (optionValue === String(targetValue));

            element.classList.toggle("active", shouldActivate);
        });
    }

    /**
     * クリックで選択を切り替えるハンドラをバインド
     * onChange が関数なら選択値を渡して呼び出す
     * 元コードのイベント処理（各要素へ addEventListener）をそのまま踏襲
     * @param {(value: string) => void|null} onChange
     * @returns {void}
     */
    bindSelect() {
        // コンテナ不在の場合スキップ
        if (!this.containerElement) return;

        // イベントデリゲーションで click を一括処理（元コードのコメントを維持）
        function handleContainerClick(eventObject) {
            console.log("クリックされました");

            // 実際にクリックされた要素を取得（元コード通り e.target を使用）
            const clickedElement = eventObject.target;

            // クリックされた要素の値を取得（元コード通り data-* を直接参照）
            const clickedValue = clickedElement.dataset[this.dataIdentifier];
            if (!clickedValue) return;

            this.setSelectedValue(clickedValue);

            // コールバック
            this.onChangeCallbacks.forEach((onChange) => {
                if (typeof onChange === "function") {
                    onChange(clickedValue);
                }
            })
        }

        // this を保持したまま元の関数構造を維持
        const boundHandleContainerClick = handleContainerClick.bind(this);

        this.containerElement
            .querySelectorAll(`${this.optionSelector}`)
            .forEach((element) => {
                element.addEventListener("click", boundHandleContainerClick);
            });
    }

    /**
     * 変更時のハンドラを追加。複数格納でき、変更時に同時実行
     * @param {(value: string) => void|null} onChange
     * @returns {void}
     */
    addOnChange(onChange) {
        if (!this.onChangeCallbacks) {
            this.onChangeCallbacks = [];
        }
        this.onChangeCallbacks.push(onChange);
    }

    /**
     * 変更時のハンドラをクリア
     * @returns {void}
     */
    clearOnChange() {
        this.onChangeCallbacks = [];
    }
}



function BindHorizontalScroll() {
    const scrollTargetElements = document.querySelectorAll('.scroll-horizontal');

    scrollTargetElements.forEach((targetElement) => {
        targetElement.addEventListener('wheel', (event) => {
            // 元の縦スクロールを無効化
            event.preventDefault();

            // 横方向にスクロールさせる
            targetElement.scrollLeft += event.deltaY;
        }, { passive: false }); // preventDefault のために passive を false
    });
}

function setGrobalLoading(isLoading){
    const loadingOverlay = document.querySelector("#loading-overlay");

    if (! loadingOverlay)
    {
        return;
    }

    loadingOverlay.classList.toggle("show", isLoading);
}

function bindPageReturn() {
    console.log("ページ表示検知をセット");
    window.addEventListener('pageshow', (event) => {
        console.log("ページ表示を検知");
        
        if (event.persisted) {
            setGrobalLoading(false);
        }
    });
}