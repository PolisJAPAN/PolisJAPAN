// ==============================
// API実行関連
// ==============================

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
        getThemeInnerHTML();
        
        return result.t_draft;
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};

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
    payload.theme_comments = theme_comments.replace(/\n/g, "#####");
    payload.theme_category = Number(theme_category);

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
                
        mergeToTDraftList(result.t_draft);
        getThemeInnerHTML();
        
        return result.t_draft;
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};

async function requestBatchGenerateAPI() {
    // アクセスキー
    const accessKeyInput = document.querySelector('#identify-html-textarea');
    const htmlInput = document.querySelector('#convert-html-textarea');

    if (accessKeyInput.value === undefined || accessKeyInput.value === "")
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
        html: htmlInput.value,
    };

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
        
        // mergeToTDraftList(result.t_draft);
        // getThemeInnerHTML();
        
        return result.t_draft;
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};

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


// ==============================
// テーマ一覧関連
// ==============================

let tDraftList = []

// JSON配列から記事HTML文字列を組み立て、innerHTMLで挿入
function getThemeInnerHTML() {
    // 生成用の親要素取得
    const container = document.querySelector('.theme-container');
    if (!container) throw new Error(`親要素が見つかりません: .theme-container`);
    container.innerHTML = '';
    console.log(tDraftList)

    const html = tDraftList.map(item => {
        if(!item || !item.id)
        {
            return "";
        } 

        // DOMに当てはめる各要素をCSVJSONの要素から取り出し。
        const theme_name = item.theme_name;
        const theme_description = item.theme_description;
        const theme_comments = item.theme_comments.replace(/#####/g, "\n");
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
                    <button class="approve-button button primary ${post_status > 2 ? "disabled" : ""}">承認</button>
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
        const approve_button = theme_parent.querySelector(`.approve-button`);

        edit_button.addEventListener('click', (e) => {
            console.log("fetch開始");
            
            e.preventDefault();
            requestAdminEditAPI(item.id);
        });
        approve_button.addEventListener('click', (e) => {
            console.log("fetch開始");
            
            e.preventDefault();
            requestAdminApproveAPI(item.id);
        });
    })

    autoResizeTextareas();
}

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

async function buildThemeElements() {
    const tDraftListTemp = await requestAdminInfoAPI();
    tDraftList = tDraftListTemp;
    console.log(tDraftList);
    
    getThemeInnerHTML();
}

let resizeTimer = null;
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

