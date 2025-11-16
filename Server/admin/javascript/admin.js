// ==============================
// API実行関連
// ==============================

/**
 * 管理情報一覧を取得するAPIを呼び出す。
 * 
 * #identify-html-textarea から access_key を読み取り、`/admin/info` へPOST。
 * 成功時はキーをCookieへ保存し、取得した `t_draft_list` を返す。
 * 空入力時は何もせず終了する。
 * 
 * 依存: fetchJsonPost, setCookie
 * 
 * @async
 * @returns {Promise<Array<Object>|undefined>} - 下書き配列 `t_draft_list`。失敗・未入力時は undefined。
 */
async function requestAdminInfoAPI() {
    const input = document.querySelector('#identify-html-textarea');

    if (input.value === undefined || input.value === "")
    {
        return;
    }

    const url = 'https://api.pol-is.jp/admin/info';
    const payload = { access_key: input.value};

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);

        // キーがあっていれば,Cookieに保存
        setCookie("admin_access_key", input.value, 30)

        return result.t_draft_list;
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};

/**
 * 指定IDの下書きを承認するAPIを呼び出す。
 * 
 * #identify-html-textarea から access_key を読み取り、`/admin/approve` へPOST。
 * 成功時は返却された `t_draft` を `tDraftList` にマージし、一覧DOMを再描画する。
 * 空入力時は何もせず終了する。
 * 
 * 依存: fetchJsonPost, mergeToTDraftList, buildThemeInnerHTML
 * 
 * @async
 * @param {number|string} target_t_draft_id - 承認対象の下書きID。
 * @returns {Promise<Object|undefined>} - 更新後の `t_draft`。失敗・未入力時は undefined。
 */
async function requestAdminApproveAPI(target_t_draft_id) {
    // アクセスキー
    const input = document.querySelector('#identify-html-textarea');

    if (input.value === undefined || input.value === "")
    {
        return;
    }

    const url = 'https://api.pol-is.jp/admin/approve';
    const payload = { 
        access_key: input.value,
        t_draft_id: target_t_draft_id,
    };

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
        
        mergeToTDraftList(result.t_draft);
        buildThemeInnerHTML();
        location.reload();
        
        return result.t_draft;
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};

/**
 * 指定IDの下書きを更新するAPIを呼び出す。
 * 
 * 画面上の該当 `.theme-item` から各入力値を収集し、`/admin/edit` へPOST。
 * 成功時は返却された `t_draft` を `tDraftList` にマージし、一覧DOMを再描画する。
 * 空入力時は何もせず終了する。
 * 
 * 依存: fetchJsonPost, mergeToTDraftList, buildThemeInnerHTML
 * 
 * @async
 * @param {number|string} target_t_draft_id - 更新対象の下書きID。
 * @returns {Promise<Object|undefined>} - 更新後の `t_draft`。失敗・未入力時は undefined。
 */
async function requestAdminEditAPI(target_t_draft_id) {
    // アクセスキー
    const input = document.querySelector('#identify-html-textarea');

    if (input.value === undefined || input.value === "")
    {
        return;
    }

    const url = 'https://api.pol-is.jp/admin/edit';
    const payload = { 
        access_key: input.value,
        t_draft_id: target_t_draft_id,
    };

    // ターゲットIDのDOMを取得
    const theme_parent = document.querySelector(`.theme-item[data-id="${target_t_draft_id}"]`);
    const theme_name_element = theme_parent.querySelector('#theme-title-textarea');
    const theme_description_element = theme_parent.querySelector('#theme-description-textarea');
    const theme_comments_element = theme_parent.querySelector('#theme-comments-textarea');
    const theme_category_element = theme_parent.querySelector('#theme-category-select');

    const theme_name = theme_name_element ? theme_name_element.value : null;
    const theme_description = theme_description_element ? theme_description_element.value : null;
    const theme_comments = theme_comments_element ? theme_comments_element.value : null;
    const theme_category = theme_category_element ? theme_category_element.value : null;

    payload.theme_name = theme_name;
    payload.theme_description = theme_description;
    payload.theme_comments = theme_comments.replace(/\n/g, "###br###");
    payload.theme_category = Number(theme_category);

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
                
        mergeToTDraftList(result.t_draft);
        buildThemeInnerHTML();
        
        return result.t_draft;
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};

/**
 * バッチ生成APIを呼び出す。
 * 
 * #identify-html-textarea の access_key と、#convert-html-textarea の HTML を
 * 収集して `/batch/generate` へPOST。成功時は `t_draft` を返す。
 * 入力が空の場合は何もせず終了する。
 * 
 * 依存: fetchJsonPost
 * 
 * @async
 * @returns {Promise<Object|undefined>} - 生成結果の `t_draft`。失敗・未入力時は undefined。
 */
async function requestBatchGenerateAPI() {
    // アクセスキー
    const accessKeyInput = document.querySelector('#identify-html-textarea');
    const themeInput = document.querySelector('#convert-theme-textarea');
    const htmlInput = document.querySelector('#convert-html-textarea');

    if (accessKeyInput.value === undefined || accessKeyInput.value === "")
    {
        return;
    }
    if (themeInput.value === undefined)
    {
        return;
    }
    if (htmlInput.value === undefined || htmlInput.value === "")
    {
        return;
    }

    const url = 'https://api.pol-is.jp/batch/generate';
    const payload = { 
        access_key: accessKeyInput.value,
        theme: themeInput.value,
        html: htmlInput.value,
    };

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
        
        // mergeToTDraftList(result.t_draft);
        // buildThemeInnerHTML();
        
        return result.t_draft;
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};

/**
 * バッチ一括作成APIを呼び出す。
 * 
 * #identify-html-textarea の access_key を用いて `/batch/create_all` へPOST。
 * レスポンスはログ出力のみを行う（返却値なし）。
 * 入力が空の場合は何もせず終了する。
 * 
 * 依存: fetchJsonPost
 * 
 * @async
 * @returns {Promise<void>} - 通信完了時に解決。
 */
async function requestBatchCreateAPI() {
    const input = document.querySelector('#identify-html-textarea');

    if (input.value === undefined || input.value === "")
    {
        return;
    }

    const url = 'https://api.pol-is.jp/batch/create_all';
    const payload = { access_key: input.value};

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};


/**
 * テーマ削除APIを呼び出す。
 * 
 * @async
 * @returns {Promise<Array<Object>|undefined>} レスポンスJSON
 */
async function requestBatchDeleteAPI(target_t_draft_id) {
    // アクセスキー
    const accessKeyInput = document.querySelector('#identify-html-textarea');

    if (accessKeyInput.value === undefined || accessKeyInput.value === "")
    {
        return;
    }

    const url = `https://api.pol-is.jp/batch/delete`;
    const payload = {
        access_key : accessKeyInput.value,
        t_draft_id: target_t_draft_id,
    };

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
        console.log(result["is_success"]);

        location.reload();

        return result;
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};



// ==============================
// テーマ一覧関連
// ==============================

let tDraftList = []

/**
 * 取得済みの `tDraftList` をもとに、テーマ一覧のHTMLを構築・差し替えする。
 * 
 * `.theme-container` 内へ各 `.theme-item` を生成し、編集/承認ボタンに
 * イベントを割り当てる。作成日を日本語表記へ整形し、テキストエリアの
 * 自動リサイズ初期化も行う。
 * 
 * 依存: formatIsoToJapaneseDate, autoResizeTextareas, requestAdminEditAPI, requestAdminApproveAPI
 * 
 * @returns {void}
 * @throws {Error} - 親要素 `.theme-container` が見つからない場合。
 */
function buildThemeInnerHTML() {
    // 生成用の親要素取得
    const container = document.querySelector('.theme-container');
    if (!container) throw new Error(`親要素が見つかりません: .theme-container`);
    container.innerHTML = '';
    console.log(tDraftList)

    const sortedTDraftList = [...tDraftList].sort((a, b) => b.id - a.id);

    const html = sortedTDraftList.map(item => {
        if(!item || !item.id)
        {
            return "";
        } 

        // DOMに当てはめる各要素をCSVJSONの要素から取り出し。
        const theme_name = item.theme_name;
        const theme_description = item.theme_description;
        const theme_comments = item.theme_comments.replace(/###br###/g, "\n");
        const theme_category = item.theme_category;
        const create_date = item.create_date;
        const post_status = item.post_status;

        // ここで `${...}` による差し込みがすべて見えます
        return `
            <div class="theme-item" data-id="${item.id}">
                <div class="theme-title">
                    <div class="title-text">タイトル</div>
                    <textarea id="theme-title-textarea" name="theme-title" class="hidden-input auto-resize">${theme_name}</textarea>
                </div>
                <div class="theme-info">
                    <div class="theme-category">
                        <div class="title-text">カテゴリ</div>
                        <select name="" id="theme-category-select">
                            <option value="1" ${theme_category == 1 ? "selected" : ""}>社会・政治</option>
                            <option value="2" ${theme_category == 2 ? "selected" : ""}>お金・資産</option>
                            <option value="3" ${theme_category == 3 ? "selected" : ""}>男女・性別</option>
                            <option value="4" ${theme_category == 4 ? "selected" : ""}>外国人問題</option>
                            <option value="5" ${theme_category == 5 ? "selected" : ""}>テクノロジー</option>
                            <option value="6" ${theme_category == 6 ? "selected" : ""}>医療・福祉</option>
                            <option value="7" ${theme_category == 7 ? "selected" : ""}>生活</option>
                            <option value="8" ${theme_category == 8 ? "selected" : ""}>その他</option>
                        </select>
                    </div>
                    <div class="theme-category">
                        <div class="title-text">作成日</div>
                        <div class="date-text">${formatIsoToJapaneseDate(create_date)}</div>
                    </div>
                    <div class="new-tag">NEW!</div>
                </div>
                <div class="theme-description">
                    <div class="title-text">説明</div>
                    <textarea id="theme-description-textarea" name="textarea" class="hidden-input auto-resize" rows="5" cols="15">${theme_description}</textarea>
                </div>
                <div class="theme-comments">
                    <div class="title-text">コメント</div>
                    <textarea id="theme-comments-textarea" name="textarea" class="hidden-input auto-resize" rows="20" cols="15">${theme_comments}</textarea>
                </div>
                <div class="button-row">
                    <button class="edit-button button secondary">更新</button>
                    <button class="delete-button button primary">削除</button>
                    <button class="approve-button button primary ${post_status >= 2 ? "disabled" : ""}">承認</button>
                </div>
            </div>
    `;
    }).join('');

    container.innerHTML += html;

    tDraftList.forEach(item => {
        if(!item || !item.id)
        {
            return "";
        }

        const theme_parent = document.querySelector(`.theme-item[data-id="${item.id}"]`);
        const edit_button = theme_parent.querySelector(`.edit-button`);
        const delete_button = theme_parent.querySelector(`.delete-button`);
        const approve_button = theme_parent.querySelector(`.approve-button`);

        edit_button.addEventListener('click', (e) => {
            console.log("fetch開始");
            
            e.preventDefault();
            requestAdminEditAPI(item.id);
        });
        delete_button.addEventListener('click', (e) => {
            console.log("fetch開始");
            
            e.preventDefault();
            requestBatchDeleteAPI(item.id);
        });
        approve_button.addEventListener('click', (e) => {
            console.log("fetch開始");
            
            e.preventDefault();
            requestAdminApproveAPI(item.id);
        });
    })

    autoResizeTextareas();
}

/**
 * 単一の `t_draft` を `tDraftList` にマージする。
 * 
 * 既存IDがなければ末尾へ追加、存在する場合は同じインデックスを上書きする。
 * 
 * @param {Object} tDraft - マージ対象の下書きオブジェクト（`id` を必須と想定）。
 * @returns {void}
 */
function mergeToTDraftList(tDraft) {
    const index = tDraftList.findIndex(item => item.id === tDraft.id);

    // id重複がない場合はマージ
    if (index < 0)
    {
        tDraftList.push(tDraft);
        return;
    }

    tDraftList[index] = tDraft;
}

/**
 * テーマ一覧の取得と描画を行う高位関数。
 * 
 * `requestAdminInfoAPI()` で一覧を取得し、`tDraftList` に反映後、
 * DOMを `buildThemeInnerHTML()` で再構築する。
 * 
 * 依存: requestAdminInfoAPI, buildThemeInnerHTML
 * 
 * @async
 * @returns {Promise<void>} - 処理完了時に解決。
 */
async function buildThemeElements() {
    const tDraftListTemp = await requestAdminInfoAPI();
    tDraftList = tDraftListTemp;
    console.log(tDraftList);
    
    buildThemeInnerHTML();
}

/**
 * リサイズの更新間隔を管理するタイマー
 */
let resizeTimer = null;

/**
 * ウィンドウのリサイズ終了を検知し、テキストエリアの高さ再計算を行う。
 * 
 * 300ms のデバウンスで `autoResizeTextareas()` を呼び出す。
 * 初期化の競合を避けるため、1秒後にイベントバインドを開始する。
 * 
 * 依存: autoResizeTextareas
 * 
 * @returns {void}
 */
function bindWindowResize() {
    setTimeout(() => {
        window.addEventListener('resize', () => {
            // すでにタイマーが動いていたらリセット
            if (resizeTimer) {
                clearTimeout(resizeTimer);
            }
    
            // リサイズ終了後 300ms 経過したら発火
            resizeTimer = setTimeout(() => {
                console.log('リサイズ完了');
                autoResizeTextareas(); //
            }, 300);
        });
    }, 1000);
}

// ==============================
// 認証関連
// ==============================

/**
 * 認証ボタンとaccess_key入力の初期化を行う。
 * 
 * クリック時に `buildThemeElements()` を呼び出すほか、
 * Cookie の `admin_access_key` があれば入力へ復元して自動実行する。
 * 
 * 依存: buildThemeElements, getCookie
 * 
 * @returns {void}
 */
function bindIdentifyButton() {
    // クリック
    const button = document.querySelector('#identify-submit-button');
    button.addEventListener('click', (e) => {
        console.log("fetch開始");
        
        e.preventDefault();
        buildThemeElements();
    });

    const input = document.querySelector('#identify-html-textarea');
    const access_key = getCookie("admin_access_key");
    if (access_key != null) {
        input.value = access_key;
        buildThemeElements();
    }
}

function bindGenerateButton() {
    // クリック
    const button = document.querySelector('#convert-submit-button');
    button.addEventListener('click', (e) => {
        console.log("fetch開始");
        
        e.preventDefault();
        requestBatchGenerateAPI();
    });
}
function bindCreateButton() {
    // クリック
    const button = document.querySelector('#create-submit-button');
    button.addEventListener('click', (e) => {
        console.log("fetch開始");
        
        e.preventDefault();
        requestBatchCreateAPI();
    });
}

// ウィンドウ初期化時にイベントを割り当て
document.addEventListener("DOMContentLoaded", () => {
    bindIdentifyButton();
    bindGenerateButton();
    bindCreateButton();
    bindWindowResize();
});

