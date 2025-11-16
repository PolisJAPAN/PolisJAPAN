
// ==============================
// グローバル変数
// ==============================
let createModalManager = null;
let categorySelectManager = null;
let controllNo = 1; // 現在のコントロール番号（グローバル管理）

let mode = "AI_ASSIST"

let parentNode = null;
let themeInput = null;
let axisInputList = null;
let commentInputList = null;
let descriptionInput = null;
let categorySelect = null;

const splitter = "###br###"

// ==============================
// API実行メソッド
// ==============================

/**
 * テーマ対立軸生成APIを呼び出す。
 * 
 * @async
 * @returns {Promise<Array<Object>|undefined>} レスポンスJSON
 */
async function requestThemeGenerateAxisAPI() {
    const access_key = USER_ACCESS_KEY;
    const theme = themeInput.value;

    const url = `${API_URL}theme/generate_axis`;
    const payload = {
        access_key : access_key,
        theme : theme,
    };

    const button = parentNode.querySelector(`#axis-stepper`).querySelector('.ai-generate-button');
    
    button.classList.add("loading");
    setInputLoading(axisInputList, true);
    setLoadingOverlay(true);

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
        console.log(result["axis"]);

        setMultiInputValues(axisInputList, result["axis"].map(value => value?.trim?.() ?? "").filter(value => value !== ""));

        button.classList.remove("loading");
        button.classList.add("complete");
        setInputLoading(axisInputList, false);
        setLoadingOverlay(false);
        setTimeout(() => {
            button.classList.remove("complete");
        }, 1500);

        syncStepperInputValidation();
        syncTextareas(() => {syncAccordionHeight();});

        setLocalStorage(`${mode}_CREATE_DRAFT_AXIS`, getMultiInputValues(axisInputList).join(splitter));
        
        return result;
    } catch (err) {
        console.error('通信エラー:', err.message);
        button.classList.remove("loading");
        setInputLoading(axisInputList, false);
        setLoadingOverlay(false);
    }
};

/**
 * テーマコメント生成APIを呼び出す。
 * 
 * @async
 * @returns {Promise<Array<Object>|undefined>} レスポンスJSON
 */
async function requestThemeGenerateCommentsAPI() {
    const access_key = USER_ACCESS_KEY;
    const theme = themeInput.value;
    const axis = getMultiInputValues(axisInputList);

    const url = `${API_URL}theme/generate_comments`;
    const payload = {
        access_key : access_key,
        theme : theme,
        axis : axis.join(splitter),
    };

    const button = parentNode.querySelector(`#comments-stepper`).querySelector('.ai-generate-button');
    
    button.classList.add("loading");
    setInputLoading(commentInputList, true);
    setLoadingOverlay(true);

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);

        setMultiInputValues(commentInputList, result["comments"].map(value => value?.trim?.() ?? "").filter(value => value !== ""));

        button.classList.remove("loading");
        button.classList.add("complete");
        setInputLoading(commentInputList, false);
        setLoadingOverlay(false);
        setTimeout(() => {
            button.classList.remove("complete");
        }, 1500);

        syncStepperInputValidation();
        syncTextareas(() => {syncAccordionHeight();});

        setLocalStorage(`${mode}_CREATE_DRAFT_COMMENTS`, getMultiInputValues(commentInputList).join(splitter));

        return result;
    } catch (err) {
        console.error('通信エラー:', err.message);
        button.classList.remove("loading");
        setInputLoading(commentInputList, false);
        setLoadingOverlay(false);
    }
};

/**
 * テーマ説明生成APIを呼び出す。
 * 
 * @async
 * @returns {Promise<Array<Object>|undefined>} レスポンスJSON
 */
async function requestThemeGenerateDescriptionsAPI() {
    const access_key = USER_ACCESS_KEY;
    const theme = themeInput.value;
    const axis = getMultiInputValues(axisInputList);
    const comments = getMultiInputValues(commentInputList);
    const button = parentNode.querySelector(`#description-stepper`).querySelector('.ai-generate-button');
    
    button.classList.add("loading");
    setInputLoading([descriptionInput], true);
    setLoadingOverlay(true);

    const url = `${API_URL}theme/generate_descriptions`;
    const payload = {
        access_key : access_key,
        theme : theme,
        axis : axis.join(splitter),
        comments : comments.join(splitter),
    };

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
        console.log(result["description"]);

        if (!descriptionInput)
        {
            return;
        }
        descriptionInput.value = result["description"];

        button.classList.remove("loading");
        button.classList.add("complete");
        setInputLoading([descriptionInput], false);
        setLoadingOverlay(false);
        setTimeout(() => {
            button.classList.remove("complete");
        }, 1500);

        syncStepperInputValidation();
        syncTextareas(() => {syncAccordionHeight();});

        setLocalStorage(`${mode}_CREATE_DRAFT_DESCRIPTION`, result["description"]);

        return result;
    } catch (err) {
        console.error('通信エラー:', err.message);
        button.classList.remove("loading");
        setInputLoading([descriptionInput], false);
        setLoadingOverlay(false);
    }
};


/**
 * テーマ下書き投稿APIを呼び出す。
 * 
 * @async
 * @returns {Promise<Array<Object>|undefined>} レスポンスJSON
 */
async function requestThemePostDraftAPI(onComplete) {
    const access_key = USER_ACCESS_KEY;
    const theme = themeInput.value;
    const comments = getMultiInputValues(commentInputList).join(splitter);

    const description = descriptionInput.value;
    const category = categorySelectManager.getSelectedValue();

    const url = `${API_URL}theme/post_draft`;
    const payload = {
        access_key : access_key,
        theme : theme,
        comments : comments,
        description : description,
        category : category,
    };

    setLoadingOverlay(true);

    try {
        const result = await fetchJsonPost(url, payload);
        console.log('取得結果:', result);
        console.log(result["is_success"]);

        onComplete();
        setLoadingOverlay(false);

        return result;
    } catch (err) {
        console.error('通信エラー:', err.message);
        setLoadingOverlay(false);
    }
};


// ==============================
// モードに関わらない初期化処理
// ==============================

/**
 * テーマ作成モーダルの初期化と起動トリガーのバインドを行う。
 * モードに関わらないモーダル表示の処理のみ
 *
 * @returns {void}
 */
function bindCreateModal() {
    // モーダルを初期化
    createModalManager = new ModalManager({
        rootSel: "#theme-create-modal",
        windowSel: ".modal-window",
        closeBtnSel: ".modal-close-button",
    });
    createModalManager.init();

    // ボタンクリックで モーダルを開く
    const createOpenButton = document.querySelector('.create-button');
    
    // モーダル表示用のハンドラ
    const handler = async (ev) => {
        ev.preventDefault();
        createModalManager.showModal();

        const closeButton = document.querySelector('.modal-window').querySelector('.complete-overlay').querySelector('.complete-close-button');
        closeButton.addEventListener("click", () => {createModalManager.closeModal();});

        switchComplete(false);
    };

    // クリック・タップ双方を網羅
    createOpenButton.addEventListener('click', handler, { passive: false });
    createOpenButton.addEventListener('touchend', handler, { passive: false });

    bindModeButton();
    switchMode("AI_ASSIST");
}

/**
 * モード切替（AI補助/手動）ボタンにイベントをバインドする。
 *
 * @returns {void}
 */
function bindModeButton(){
    const aiModeButton = document.querySelector('.modal-window').querySelector('#ai-mode-button');
    const manualModeButton = document.querySelector('.modal-window').querySelector('#manual-mode-button');

    aiModeButton.addEventListener("click", () => {
        switchMode("AI_ASSIST");
        aiModeButton.classList.remove("secondary-border");
        aiModeButton.classList.add("secondary");
        manualModeButton.classList.remove("secondary");
        manualModeButton.classList.add("secondary-border");

        manualModeButton.removeAttribute("disabled");
        aiModeButton.setAttribute("disabled", "true");
    });

    manualModeButton.addEventListener("click", () => {
        switchMode("MANUAL");
        aiModeButton.classList.remove("secondary");
        aiModeButton.classList.add("secondary-border");
        manualModeButton.classList.remove("secondary-border");
        manualModeButton.classList.add("secondary");

        aiModeButton.removeAttribute("disabled");
        manualModeButton.setAttribute("disabled", "true");
    });
}

/**
 * 完了オーバーレイの表示/非表示を切り替える。
 *
 * @param {boolean} isComplete - true で表示（show 付与）、false で非表示。
 * @returns {void}
 */
function switchComplete(isComplete){
    const completeOverlay = document.querySelector('.modal-window').querySelector('.complete-overlay');
    completeOverlay.classList.toggle("show", isComplete);
}

// ==============================
// モード変更処理
// ==============================

/**
 * 入力フォームのモードを切り替え、各種バインドと同期処理を再実行する。
 *
 * @param {"AI_ASSIST"|"MANUAL"} targetMode - 切替先モード。
 * @returns {void}
 */
function switchMode(targetMode){
    // モード変更
    mode = targetMode;

    // モードに関わる初期化処理
    renderFormMode(targetMode)
    findElements();
    autoResizeTextareas(() => {syncAccordionHeight();});
    bindNextButtonEvents();
    bindPostButtonEvents();

    bindAIGenerateButton("#axis-stepper", requestThemeGenerateAxisAPI)
    bindAIGenerateButton("#comments-stepper", requestThemeGenerateCommentsAPI)
    bindAIGenerateButton("#description-stepper", requestThemeGenerateDescriptionsAPI)

    initCategorySelect();
    
    restoreDraft();
    bindDraftRecorder();

    bindClearButtonEvents();
    
    initializeStepperInputValidation();

    controllNo = seekCurrentControlNo();
    
    updateSteppers(controllNo);
    // アコーディオンを開閉
    syncTextareas();
    syncAccordionHeight();
}

/**
 * モーダル内容とローカルストレージを初期状態に戻す。
 *
 * - 入力値クリア、カテゴリ未選択化、バリデーション・アコーディオンの再同期を実施
 *
 * @returns {void}
 */
function clearModal() {
    controllNo = 1;
    updateSteppers(controllNo);

    // キャッシュ削除
    deleteLocalStorage(`${mode}_CREATE_DRAFT_THEME`)
    deleteLocalStorage(`${mode}_CREATE_DRAFT_AXIS`)
    deleteLocalStorage(`${mode}_CREATE_DRAFT_COMMENTS`)
    deleteLocalStorage(`${mode}_CREATE_DRAFT_DESCRIPTION`)
    deleteLocalStorage(`${mode}_CREATE_DRAFT_CATEGORY`)

    // 投稿済み内容を削除
    themeInput.value = "";
    setMultiInputValues(axisInputList, []);
    setMultiInputValues(commentInputList, []);
    descriptionInput.value = "";
    categorySelectManager.setSelectedValue(0);

    // バリデーション状態を更新
    syncStepperInputValidation();

    // アコーディオンを開閉
    syncTextareas();
    syncAccordionHeight();
}


// ==============================
// モード別初期化処理
// ==============================

/**
 * 指定モードに応じてフォームDOMを差し替える。
 *
 * - 未使用モードのDOMはラッパーごと入れ替え
 *
 * @param {"AI_ASSIST"|"MANUAL"} targetMode - 描画対象のモード。
 * @returns {void}
 */
function renderFormMode(targetMode) {
    const formContainerElement = document.querySelector('.modal-window').querySelector('.create-form-container');
    if (!formContainerElement) return;

    // ラッパーごと入れ替える（未使用モードはDOMから消える）
    if (targetMode === 'MANUAL') {
        formContainerElement.innerHTML = manualModeHtml;
    } else if (targetMode === 'AI_ASSIST') {
        // デフォルトは AI モード
        formContainerElement.innerHTML = aiAssistModeHtml;
    }
}

/**
 * 現在のモードに応じて必要なDOM要素を探索し、グローバル参照に保持する。
 *
 * @returns {void}
 */
function findElements(){
    parentNode = (mode == "AI_ASSIST") ? document.querySelector('#ai-assist-mode') : document.querySelector('#manual-mode');
    themeInput = parentNode.querySelector('#theme-title-textarea');
    axisInputList = (mode == "AI_ASSIST") ? Array.from(parentNode.querySelector('#axis-stepper').querySelectorAll('.axis-input')) : [];
    commentInputList = Array.from(parentNode.querySelector('#comments-stepper').querySelectorAll('.comment-input'));
    descriptionInput = parentNode.querySelector('#description-textarea');
    categorySelect = parentNode.querySelector('#category-select');
}

/**
 * 現在の入力充足状況から表示すべきステップ番号（controlNo）を算出する。
 *
 * - 各ステッパーの入力状態を順に確認
 * - カテゴリ選択状態も考慮
 *
 * @returns {number} - 現在位置として採用する制御番号。
 */
function seekCurrentControlNo(){
    const themeStepper = parentNode.querySelector("#theme-stepper");
    if (! isInputsFilled(themeStepper)){
        return 1;
    }

    const axisStepper = parentNode.querySelector("#axis-stepper");
    if (mode == "AI_ASSIST" && ! isInputsFilled(axisStepper)){
        return 2;
    }

    const commentsStepper = parentNode.querySelector("#comments-stepper");
    if (! isInputsFilled(commentsStepper)){
        
        return (mode == "AI_ASSIST") ? 3 : 2;
    }

    const descriptionStepper = parentNode.querySelector("#description-stepper");
    if (! isInputsFilled(descriptionStepper)){
        return (mode == "AI_ASSIST") ? 4 : 3;
    }
    
    const category = categorySelectManager.getSelectedValue();
    if (! category || category == 0){
        return (mode == "AI_ASSIST") ? 5 : 4;
    }

    return (mode == "AI_ASSIST") ? 6 : 5;
}

/**
 * ローカルストレージに保持している下書きをフォームに復元する。
 *
 * @returns {void}
 */
function restoreDraft(){
    const themeDraft = getLocalStorage(`${mode}_CREATE_DRAFT_THEME`);
    const axisDraft = getLocalStorage(`${mode}_CREATE_DRAFT_AXIS`);
    const commentsDraft = getLocalStorage(`${mode}_CREATE_DRAFT_COMMENTS`);
    const descriptionDraft = getLocalStorage(`${mode}_CREATE_DRAFT_DESCRIPTION`);
    const categoryDraft = getLocalStorage(`${mode}_CREATE_DRAFT_CATEGORY`);

    if (themeDraft) {themeInput.value = themeDraft;}
    if (axisDraft) {setMultiInputValues(axisInputList, axisDraft.split(splitter));}
    if (commentsDraft) {setMultiInputValues(commentInputList, commentsDraft.split(splitter));}
    if (descriptionDraft) {descriptionInput.value = descriptionDraft;}
    if (categorySelectManager) {categorySelectManager.setSelectedValue(categoryDraft);}
}

/**
 * 各入力に input などのイベントを付与し、入力内容をローカルストレージに保存する。
 *
 * @returns {void}
 */
function bindDraftRecorder(){
    themeInput.addEventListener("input", (e) => {
        setLocalStorage(`${mode}_CREATE_DRAFT_THEME`, e.target.value);
    });
    axisInputList.forEach((input) => {
        input.addEventListener("input", (e) => {
            setLocalStorage(`${mode}_CREATE_DRAFT_AXIS`, getMultiInputValues(axisInputList).join(splitter));
        });
    });
    commentInputList.forEach((input) => {
        input.addEventListener("input", (e) => {
            setLocalStorage(`${mode}_CREATE_DRAFT_COMMENTS`, getMultiInputValues(commentInputList).join(splitter));
        });
    });
    descriptionInput.addEventListener("input", (e) => {
        setLocalStorage(`${mode}_CREATE_DRAFT_DESCRIPTION`, e.target.value);
    });

    categorySelectManager.addOnChange((categoryNo) => {
        setLocalStorage(`${mode}_CREATE_DRAFT_CATEGORY`, categoryNo);
    })
}


// ==============================
// ステッパー表示更新関連
// ==============================

/**
 * 現在の制御番号に応じて各ステッパーの状態（complete/current/hidden）を更新する。
 *
 * - show クラスや高さの同期、アコーディオン展開を制御
 *
 * @param {number} currentControlNo - 現在の制御番号。
 * @returns {void}
 */
function updateSteppers(currentControlNo) {
    // すべての .slide-modal 要素を取得
    const steppers = parentNode.querySelectorAll('.modal-stepper');

    steppers.forEach((stepperElement) => {
        const stepperControlNo = Number(stepperElement.dataset.controlNo);
        const stepperContent = stepperElement.querySelector('.modal-stepper-content');
        
        // controlNo 以下のものを表示、それ以外は非表示
        if (stepperControlNo < currentControlNo) {
            // 表示方法を完了済みに切り替え
            stepperElement.classList.remove('current');
            stepperElement.classList.add('complete');
            
            // 高さを更新
            adjustTargetAcordion(stepperElement);

            // アコーディオンの展開部分のコンテンツ処理
            if (stepperContent) {
                stepperContent.classList.add('show');
            }
        } 
        else if (stepperControlNo == currentControlNo) {
            // 表示方法を表示中に切り替え
            stepperElement.classList.remove('complete');
            stepperElement.classList.add('current');

            // アコーディオンの展開部分のコンテンツ処理
            if (stepperContent) {
                stepperContent.classList.add('show');
                openAccordion(stepperElement);
            }
        } 
        else {
            stepperElement.classList.remove('current');
            stepperElement.classList.remove('complete');
            if (stepperContent) {
                stepperContent.classList.remove('show');
                stepperContent.removeAttribute('style');
            }
        }
    });
}

/**
 * 各ステッパー内の「次へ」ボタンにクリックイベントを付与し、制御番号を進める。
 *
 * - 初期表示のアコーディオン開閉と state 反映も行う
 *
 * @returns {void}
 */
function bindNextButtonEvents() {
    // すべての .slide-modal 内の .next-button を取得
    const nextButtons = parentNode.querySelectorAll('.modal-stepper .next-button');

    nextButtons.forEach((buttonElement) => {
        buttonElement.addEventListener('click', () => {
            
            // ボタン自身が持つ data-control-no を数値で取得
            const buttonControlNo = Number(buttonElement.dataset.controlNo);
            
            // グローバル変数 controllNo をインクリメント
            controllNo = buttonControlNo + 1;

            // モーダル表示を更新
            updateSteppers(controllNo);
        });
    });

    const steppers = parentNode.querySelectorAll('.modal-stepper');
    openAccordion(steppers[0]);
    updateSteppers(controllNo);
}

/**
 * 単一のアコーディオンを開く。
 *
 * - max-height を 0 → コンテンツ高 → fit-content に遷移
 *
 * @param {HTMLElement} panelElement - 開く対象のパネル要素（.modal-stepper）。
 * @returns {void}
 */
function openAccordion(panelElement) {
    const innerContentElement = panelElement.querySelector('.modal-stepper-content');
    const innerElement = panelElement.querySelector('.modal-stepper-content-wrapper');
    const targetHeight = (innerElement.scrollHeight + 8);

    innerContentElement.style.maxHeight = '0px';

    // リフロー発生でアニメーション開始
    innerContentElement.getBoundingClientRect();
    innerContentElement.style.maxHeight = targetHeight + 'px';

    // トランジション後に height:auto に戻す
    var onTransitionEnd = function (event) {
        if (event.propertyName !== 'height') return;
        innerContentElement.style.maxHeight = 'fit-content';
        innerContentElement.removeEventListener('transitionend', onTransitionEnd);
    };
    innerContentElement.addEventListener('transitionend', onTransitionEnd);
}

/**
 * 現在開いているすべてのアコーディオンの高さを、内部コンテンツに合わせて同期する。
 *
 * @returns {void}
 */
function syncAccordionHeight() {
    // すべての .slide-modal 要素を取得
    const slideModals = parentNode.querySelectorAll('.modal-stepper');
    slideModals.forEach((panelElement) => {
        adjustTargetAcordion(panelElement)
    });
}

/**
 * 指定のアコーディオン（パネル）の高さを、内部コンテンツの高さに合わせて更新する。
 *
 * @param {HTMLElement} panelElement - 対象のパネル要素（.modal-stepper）。
 * @returns {void}
 */
function adjustTargetAcordion(panelElement) {
    const innerContentElement = panelElement.querySelector('.modal-stepper-content');
    const innerElement = panelElement.querySelector('.modal-stepper-content-wrapper');
    
    if (!innerElement) return;
    if (!innerContentElement.classList.contains("show")) return;

    innerContentElement.style.maxHeight = (innerElement.scrollHeight + 8) + 'px';
    innerContentElement.style.minHeight = (innerElement.scrollHeight + 8) + 'px';
    
    requestAnimationFrame(function () {
        innerContentElement.style.maxHeight = (innerElement.scrollHeight + 8) + 'px';
        innerContentElement.style.minHeight = (innerElement.scrollHeight + 8) + 'px';
    });
}

// ==============================
// 各セクションのバリデーション
// ==============================

/**
 * 各ステッパー内の入力/選択状態に応じて「次へ」ボタンの活性/非活性を管理する。
 *
 * - 入力イベント/カテゴリ変更イベントを監視し、ボタンの disabled を更新
 *
 * @returns {void}
 */
function initializeStepperInputValidation() {
    // すべてのモーダルステッパーを取得
    const modalSteppers = parentNode.querySelectorAll(".modal-stepper");
    if (!modalSteppers.length) return;

    modalSteppers.forEach((modalStepper) => {
        const targetInputs = modalStepper.querySelectorAll(".target-input");
        const targetSelects = modalStepper.querySelectorAll(".target-select");
        const nextButton = modalStepper.querySelector(".next-button");

        if (!targetInputs.length && !targetSelects.length) return;
        if (!nextButton) return;

        // 各 input にイベントを付与
        targetInputs.forEach((inputElement) => {
            inputElement.addEventListener("input", () => {
                // checkInputsFilled(modalStepper);
                syncStepperInputValidation();
            });
        });
        
        if (targetSelects.length){
            categorySelectManager.addOnChange(() => {
                // checkInputsFilled(modalStepper);
                syncStepperInputValidation();
            })
        }
    });

    syncStepperInputValidation();
}

/**
 * 投稿ボタンの活性/非活性を全体の入力充足状況から同期する。
 *
 * @returns {void}
 */
function syncPostButtonValidation() {
    const postButton = parentNode.querySelector(".post-button");
    
    const isAllStepperFilled = getAllStepperInputFilled();
    
    // すべて入力されていれば disabled を外す、そうでなければ付ける
    if (isAllStepperFilled) {
        postButton.removeAttribute("disabled");
    } else {
        postButton.setAttribute("disabled", "true");
    }
}

/**
 * 全ステッパーの入力/選択状態を走査し、各「次へ」ボタンの disabled を一括で再評価する。
 *
 * @returns {void}
 */
function syncStepperInputValidation() {
    // すべてのモーダルステッパーを取得
    const modalSteppers = parentNode.querySelectorAll(".modal-stepper");
    if (!modalSteppers.length) return;

    console.log("ステッパーのinputを検収");

    let allStepperFilledArray = []
    modalSteppers.forEach((modalStepper) => {
        const targetInputs = modalStepper.querySelectorAll(".target-input");
        const targetSelects = modalStepper.querySelectorAll(".target-select");
        const nextButton = modalStepper.querySelector(".next-button");

        if (!targetInputs.length && !targetSelects.length) return;
        if (!nextButton) return;

        // 初期状態もチェック
        const allFilled = checkInputsFilled(modalStepper);

        const allStepperFilled = allStepperFilledArray.every(value => value === true);
        const aiGenerateButton = modalStepper.querySelector('.ai-generate-button');

        if (aiGenerateButton) {
            if (allStepperFilled) {
                aiGenerateButton.removeAttribute("disabled");
            } else {
                aiGenerateButton.setAttribute("disabled", "true");
            }
        }

        // 過去ステッパーが全て満たされているかを記録
        allStepperFilledArray.push(allFilled)
    });
}

/**
 * すべてのステッパーが入力/選択済みかを集計する。
 *
 * @returns {boolean} - 全ステッパーが充足していれば true、未充足があれば false。
 */
function getAllStepperInputFilled() {
    // すべてのモーダルステッパーを取得
    const modalSteppers = parentNode.querySelectorAll(".modal-stepper");
    if (!modalSteppers.length) {
        return false
    };

    let isAllStepperFilled = true;
    modalSteppers.forEach((modalStepper) => {
        const targetInputs = modalStepper.querySelectorAll(".target-input");
        const targetSelects = modalStepper.querySelectorAll(".target-select");
        const nextButton = modalStepper.querySelector(".next-button");

        if (!targetInputs.length && !targetSelects.length) return;
        if (!nextButton) return;

        // 初期状態もチェック
        const isStepperFilled = isInputsFilled(modalStepper);
        if (!isStepperFilled) {
            isAllStepperFilled = false;
        }
    });

    return isAllStepperFilled;
}

/**
 * 指定ステッパーの入力/選択がすべて埋まっているかを評価し、次へボタンの disabled を切り替える。
 * 併せて投稿ボタンの活性状態も同期する。
 *
 * @param {HTMLElement} modalStepper - 対象のステッパー要素。
 * @returns {void}
 */
function checkInputsFilled(modalStepper) {
    const nextButton = modalStepper.querySelector(".next-button");
    
    const allFilled = isInputsFilled(modalStepper);

    // すべて入力されていれば disabled を外す、そうでなければ付ける
    if (allFilled) {
        nextButton.removeAttribute("disabled");
    } else {
        nextButton.setAttribute("disabled", "true");
    }

    syncPostButtonValidation();

    return allFilled;
};

/**
 * 指定ステッパーの target-input / target-select がすべて入力済みかを判定する。
 *
 * - テキスト入力は空白トリムで判定
 * - セレクトはカテゴリ選択の有無を参照
 *
 * @param {HTMLElement} modalStepper - 対象のステッパー要素。
 * @returns {boolean} - すべて入力済みなら true、未入力があれば false。
 */
function isInputsFilled(modalStepper) {
    const targetInputs = modalStepper.querySelectorAll(".target-input");

    const targetSelects = modalStepper.querySelectorAll(".target-select");

    // 全入力が空でないかを判定
    let allFilled = Array.from(targetInputs).every(
        (inputElement) => inputElement.value.trim() !== ""
    );
    
    if (targetSelects && Array.from(targetSelects).length > 0){
        const category = categorySelectManager.getSelectedValue();
        allFilled = allFilled && (category > 0);
    }

    return allFilled;
};

// ==============================
// 各UIの初期化関連
// ==============================

/**
 * 指定IDのステッパー内にある .ai-generate-button にクリックイベントを割り当てる。
 *
 * @param {string} id - ステッパーのセレクタID（例: "#axis-stepper"）。
 * @param {Function} handler - クリック時に実行するコールバック。
 * @returns {void}
 */
function bindAIGenerateButton(id, handler) {
    // 対象となる .modal-stepper 要素を取得
    const modalStepperElement = parentNode.querySelector(`${id}.modal-stepper`);
    if (!modalStepperElement) {
        console.warn(`指定された id=${id} の .modal-stepper が見つかりません。`);
        return;
    }

    // 子孫の .ai-generate-button 要素を取得
    const aiGenerateButton = modalStepperElement.querySelector('.ai-generate-button');
    if (!aiGenerateButton) {
        console.warn(`.ai-generate-button が id=${id} の内に存在しません。`);
        return;
    }

    // イベントを割り当て
    aiGenerateButton.addEventListener('click', handler);
}

/**
 * 指定の入力群にスケルトン表示クラスを付け外しする。
 *
 * @param {NodeListOf<HTMLElement>|HTMLElement[]|null} inputList - 対象の入力要素群。
 * @param {boolean} isLoading - true で付与、false で削除。
 * @returns {void}
 */
function setInputLoading(inputList, isLoading) {
    if (inputList) {
        Array.from(inputList).forEach((input) => {
            input.classList.toggle("skeleton-loading", isLoading);
        })
    };
}

/**
 * 投稿ステッパーの投稿ボタンにクリックイベントを割り当て、投稿処理と完了表示を行う。
 *
 * - API 呼び出し完了後に完了オーバーレイを表示し、クリア処理を実行
 *
 * @returns {void}
 */
function bindPostButtonEvents() {
    // すべての .slide-modal 内の .next-button を取得
    const postButton = parentNode.querySelector('#post-stepper.modal-stepper').querySelector('.post-button');
    postButton.addEventListener('click', () => {
        
        // ボタン自身が持つ data-control-no を数値で取得
        const buttonControlNo = Number(postButton.dataset.controlNo);
        // グローバル変数 controllNo をインクリメント
        controllNo = buttonControlNo + 1;

        requestThemePostDraftAPI(onComplete = (() => {
            // モーダル表示を更新
            switchComplete(true);

            setTimeout(() => {
                clearModal();
            }, 300);
        }))
    });
}

/**
 * カスタムカテゴリセレクトを初期化し、選択操作を可能にする。
 *
 * @returns {void}
 */
function initCategorySelect(){
    // モーダルを初期化
    categorySelectManager = new CustomSelectManager({
        containerElement: categorySelect,
        optionSelector: ".category-select-button",
        dataIdentifier: "value",
    });
    categorySelectManager.bindSelect();
}

/**
 * クリアボタン群にイベントを割り当て、対象入力の内容をクリアする。
 *
 * - クリア後は高さ/バリデーション/アコーディオンを再同期
 *
 * @returns {void}
 */
function bindClearButtonEvents() {
    const clearButtons = parentNode.querySelectorAll(".clear-button");
    
    clearButtons.forEach((clearButton) => {
        clearButton.addEventListener("click", () => {
            // ボタンのターゲット情報を辿り、インプット内容の削除を実施
            const targetSelector = clearButton.dataset.target;
            const targetInput = parentNode.querySelector(`#${targetSelector}`);
            targetInput.value = "";

            // 高さ系の情報を再同期
            syncStepperInputValidation();

            // アコーディオンを開閉
            syncTextareas();
            syncAccordionHeight();
        });
    });
}

// ウィンドウ初期化時にイベントを割り当て
document.addEventListener("DOMContentLoaded", () => {
    bindCreateModal();
});

// ==============================
// 各モードのHTML
// ==============================

/** AIアシスト有りモードでのHTML */
const aiAssistModeHtml =`
<div id="ai-assist-mode" class="modal-inner-content-group">
    <div class="modal-section-title">作成のステップ</div>
    <div id="theme-stepper" class="modal-stepper" data-control-no="1">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">1</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">テーマの入力</div>
        </div>
        <div class="modal-stepper-content show">
            <div class="modal-stepper-content-wrapper">
                <div class="input-group">
                    <textarea id="theme-title-textarea" class="hidden-input auto-resize target-input" rows="1" placeholder="テーマを入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="theme-title-textarea">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">40字程度までのシンプルな内容にしてみましょう。</div>
                    <div class="modal-content-description">意見や議論の余地があるオープンな問いがおすすめです。</div>
                    <div class="modal-content-description">議論を誘導する恣意的なテーマは承認されません。</div>
                </div>
                <button class="next-button button secondary" data-control-no="1">
                    <div class="text">次へ</div>
                </button>
            </div>
        </div>
    </div>
    <div id="axis-stepper" class="modal-stepper" data-control-no="2">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">2</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">想定する立場の入力</div>
        </div>
        <div class="modal-stepper-content">
            <div class="modal-stepper-content-wrapper">
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">テーマに対して、どのような立場で意見が出されるか、</div>
                    <div class="modal-content-description">想定される立場を記入してください。</div>
                </div>
                <button class="ai-generate-button button secondary-border">
                    <div class="normal-label">
                        <i class="bi bi-stars"></i>
                        <div class="text">AIで下書きを生成</div>
                    </div>
                    <div class="loading-label">
                        <div class="ring-loader"></div>
                        <div class="text loading-text">下書きを生成中</div>
                    </div>
                    <div class="complete-label">
                        <div class="text complete-text">生成完了</div>
                    </div>
                </button>
                <div class="input-group">
                    <textarea id="axis-title-textarea-1" class="axis-input hidden-input auto-resize target-input" rows="1" placeholder="想定する立場を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="axis-title-textarea-1">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="axis-title-textarea-2" class="axis-input hidden-input auto-resize target-input" rows="1" placeholder="想定する立場を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="axis-title-textarea-2">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <button class="next-button button secondary" data-control-no="2">
                    <div class="text">次へ</div>
                </button>
            </div>
        </div>
    </div>
    <div id="comments-stepper" class="modal-stepper" data-control-no="3">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">3</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">意見の入力</div>
        </div>
        <div class="modal-stepper-content">
            <div class="modal-stepper-content-wrapper">
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">テーマに対して、それぞれの立場から</div>
                    <div class="modal-content-description">どのような意見があるか記入してください。</div>
                    <div class="modal-content-description">※ 15個の意見が必要です。</div>
                </div>
                <button class="ai-generate-button button secondary-border">
                    <div class="normal-label">
                        <i class="bi bi-stars"></i>
                        <div class="text">AIで下書きを生成</div>
                    </div>
                    <div class="loading-label">
                        <div class="ring-loader"></div>
                        <div class="text loading-text">下書きを生成中</div>
                    </div>
                    <div class="complete-label">
                        <div class="text complete-text">生成完了</div>
                    </div>
                </button>
                <div class="input-group">
                    <textarea id="comment-textarea-1" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-1">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-2" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-2">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-3" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-3">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-4" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-4">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-5" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-5">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-6" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-6">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-7" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-7">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-8" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-8">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <button class="next-button button secondary" data-control-no="3">
                    <div class="text">次へ</div>
                </button>
            </div>
        </div>
    </div>
    <div id="description-stepper" class="modal-stepper" data-control-no="4">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">4</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">テーマの説明を入力</div>
        </div>
        <div class="modal-stepper-content">
            <div class="modal-stepper-content-wrapper">
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">テーマについての説明を記入します。</div>
                    <div class="modal-content-description">議論に訪れた人が目にする文章になるので、背景や</div>
                    <div class="modal-content-description">理由などをわかりやすく記載してください。</div>
                </div>
                <button class="ai-generate-button button secondary-border">
                    <div class="normal-label">
                        <i class="bi bi-stars"></i>
                        <div class="text">AIで下書きを生成</div>
                    </div>
                    <div class="loading-label">
                        <div class="ring-loader"></div>
                        <div class="text loading-text">下書きを生成中</div>
                    </div>
                    <div class="complete-label">
                        <div class="text complete-text">生成完了</div>
                    </div>
                </button>
                <div class="input-group">
                    <textarea id="description-textarea" class="hidden-input auto-resize target-input" rows="1" placeholder="テーマの説明を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="description-textarea">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <button class="next-button button secondary" data-control-no="4">
                    <div class="text">次へ</div>
                </button>
            </div>
        </div>
    </div>
    <div id="category-stepper" class="modal-stepper" data-control-no="5">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">5</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">カテゴリを選択</div>
        </div>
        <div class="modal-stepper-content">
            <div class="modal-stepper-content-wrapper">
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">テーマにぴったりのカテゴリを選択してください。</div>
                </div>
                <div id="category-select" class="target-select">
                    <button class="category-select-button button secondary-border" data-value="1"><div class="text">社会・政治</div></button>
                    <button class="category-select-button button secondary-border" data-value="2"><div class="text">お金・資産</div></button>
                    <button class="category-select-button button secondary-border" data-value="3"><div class="text">男女・性別</div></button>
                    <button class="category-select-button button secondary-border" data-value="4"><div class="text">外国人問題</div></button>
                    <button class="category-select-button button secondary-border" data-value="5"><div class="text">テクノロジー</div></button>
                    <button class="category-select-button button secondary-border" data-value="6"><div class="text">医療・福祉</div></button>
                    <button class="category-select-button button secondary-border" data-value="7"><div class="text">生活</div></button>
                    <button class="category-select-button button secondary-border" data-value="8"><div class="text">その他</div></button>
                </div>
                <button class="next-button button secondary" data-control-no="5">
                    <div class="text">次へ</div>
                </button>
            </div>
        </div>
    </div>
    <div id="post-stepper" class="modal-stepper" data-control-no="6">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">6</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">テーマを作成</div>
        </div>
        <div class="modal-stepper-content">
            <div class="modal-stepper-content-wrapper">
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">お疲れ様でした。すべての項目が記入できました。</div>
                    <div class="modal-content-description">現在の内容で問題がなければ、作成ボタンを押して</div>
                    <div class="modal-content-description">テーマを作成してください。</div>
                </div>
                <button class="post-button button secondary" data-control-no="6">
                    <div class="text">テーマを作成</div>
                </button>
            </div>
        </div>
    </div>
    <div id="complete-stepper" class="modal-stepper" data-control-no="7">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">7</div>
            </div>
            <div class="modal-stepper-title">完了</div>
        </div>
    </div>
</div>
`;

/** マニュアルモードでのHTML */
const manualModeHtml =`
<div id="manual-mode" class="modal-inner-content-group">
    <div class="modal-section-title">作成のステップ</div>
    <div id="theme-stepper" class="modal-stepper" data-control-no="1">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">1</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">テーマの入力</div>
        </div>
        <div class="modal-stepper-content show">
            <div class="modal-stepper-content-wrapper">
                <div class="input-group">
                    <textarea id="theme-title-textarea" class="hidden-input auto-resize target-input" rows="1" placeholder="テーマを入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="theme-title-textarea">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">40字程度までのシンプルな内容にしてみましょう。</div>
                    <div class="modal-content-description">意見や議論の余地があるオープンな問いがおすすめです。</div>
                    <div class="modal-content-description">議論を誘導する恣意的なテーマは承認されません。</div>
                </div>
                <button class="next-button button secondary" data-control-no="1">
                    <div class="text">次へ</div>
                </button>
            </div>
        </div>
    </div>
    <div id="comments-stepper" class="modal-stepper" data-control-no="2">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">2</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">意見の入力</div>
        </div>
        <div class="modal-stepper-content">
            <div class="modal-stepper-content-wrapper">
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">テーマに対して、それぞれの立場から</div>
                    <div class="modal-content-description">どのような意見があるか記入してください。</div>
                    <div class="modal-content-description">※ 15個の意見が必要です。</div>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-1" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-1">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-2" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-2">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-3" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-3">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-4" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-4">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-5" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-5">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-6" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-6">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-7" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-7">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-8" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-8">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-9" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-9">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-10" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-10">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-11" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-11">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-12" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-12">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-13" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-13">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-14" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-14">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <div class="input-group">
                    <textarea id="comment-textarea-15" class="comment-input hidden-input auto-resize target-input" rows="1" placeholder="意見を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="comment-textarea-15">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <button class="next-button button secondary" data-control-no="2">
                    <div class="text">次へ</div>
                </button>
            </div>
        </div>
    </div>
    <div id="description-stepper" class="modal-stepper" data-control-no="3">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">3</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">テーマの説明を入力</div>
        </div>
        <div class="modal-stepper-content">
            <div class="modal-stepper-content-wrapper">
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">テーマについての説明を記入します。</div>
                    <div class="modal-content-description">議論に訪れた人が目にする文章になるので、背景や</div>
                    <div class="modal-content-description">理由などをわかりやすく記載してください。</div>
                </div>
                <div class="input-group">
                    <textarea id="description-textarea" class="hidden-input auto-resize target-input" rows="1" placeholder="テーマの説明を入力"></textarea>
                    <button class="button secondary-border clear-button" data-target="description-textarea">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
                <button class="next-button button secondary" data-control-no="3">
                    <div class="text">次へ</div>
                </button>
            </div>
        </div>
    </div>
    <div id="category-stepper" class="modal-stepper" data-control-no="4">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">4</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">カテゴリを選択</div>
        </div>
        <div class="modal-stepper-content">
            <div class="modal-stepper-content-wrapper">
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">テーマにぴったりのカテゴリを選択してください。</div>
                </div>
                <div id="category-select" class="target-select">
                    <button class="category-select-button button secondary-border" data-value="1"><div class="text">社会・政治</div></button>
                    <button class="category-select-button button secondary-border" data-value="2"><div class="text">お金・資産</div></button>
                    <button class="category-select-button button secondary-border" data-value="3"><div class="text">男女・性別</div></button>
                    <button class="category-select-button button secondary-border" data-value="4"><div class="text">外国人問題</div></button>
                    <button class="category-select-button button secondary-border" data-value="5"><div class="text">テクノロジー</div></button>
                    <button class="category-select-button button secondary-border" data-value="6"><div class="text">医療・福祉</div></button>
                    <button class="category-select-button button secondary-border" data-value="7"><div class="text">生活</div></button>
                    <button class="category-select-button button secondary-border" data-value="8"><div class="text">その他</div></button>
                </div>
                <button class="next-button button secondary" data-control-no="4">
                    <div class="text">次へ</div>
                </button>
            </div>
        </div>
    </div>
    <div id="post-stepper" class="modal-stepper" data-control-no="5">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">5</div>
            </div>
            <div class="modal-stepper-status"><span class="task-text">やること</span><span class="complete-text">完了</span></div>
            <div class="modal-stepper-title">テーマを作成</div>
        </div>
        <div class="modal-stepper-content">
            <div class="modal-stepper-content-wrapper">
                <div class="stack center spacing-8px width-full">
                    <div class="modal-content-description">お疲れ様でした。すべての項目が記入できました。</div>
                    <div class="modal-content-description">現在の内容で問題がなければ、作成ボタンを押して</div>
                    <div class="modal-content-description">テーマを作成してください。</div>
                </div>
                <button class="post-button button secondary" data-control-no="5">
                    <div class="text">テーマを作成</div>
                </button>
            </div>
        </div>
    </div>
    <div id="complete-stepper" class="modal-stepper" data-control-no="6">
        <div class="modal-stepper-header">
            <div class="check-base">
                <i class="bi bi-check"></i>
                <div class="check-number">6</div>
            </div>
            <div class="modal-stepper-title">完了</div>
        </div>
    </div>
</div>
`;