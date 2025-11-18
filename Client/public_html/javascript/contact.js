
/**
 * テーマ対立軸生成APIを呼び出す。
 * 
 * @async
 * @returns {Promise<Array<Object>|undefined>} レスポンスJSON
 */
async function requestContactAPI() {
    const emailValue = readInputValue('mail-input-group');
    const nameValue = readInputValue('name-input-group');
    const contentValue = readInputValue('content-input-group');

    const url = `https://contact.pol-is.jp/contact`;
    const payload = {
        mail : emailValue,
        name : nameValue,
        content : contentValue,
    };

    try {
        const result = await fetchJsonPostAsJson(url, payload);
        // console.log('取得結果:', result);

        return result;
    } catch (err) {
        console.error('通信エラー:', err.message);
    }
};


/**
 * スクロール時に要素をフェードイン表示する。
 * 
 * `.scroll-fade-in` クラスを持つ要素を監視し、可視範囲に入った際に `show` クラスを付与。
 * また、`data-delay`・`data-dur` 属性をCSS変数として設定する。
 * 一度表示された要素は監視を解除する。
 * 
 * @returns {void}
 */
function bindScroll() {
    const elements = document.querySelectorAll(".scroll-fade-in");

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;

            const el = entry.target;

            // data-delay と data-dur（任意）を CSS変数で渡す
            const delay = el.dataset.delay || 0;
            const dur = el.dataset.dur || 0.8;
            el.style.setProperty("--delay", `${delay}s`);
            el.style.setProperty("--dur", `${dur}s`);

            el.classList.add("show");

            // 一度発火したら監視解除（表示しっぱなし）
            observer.unobserve(el);
        });
    }, {
        threshold: 0.1
    });

    elements.forEach((el) => observer.observe(el));
}

/**
 * 指定グループID内の .contact-input から値を取得
 * @param {string} groupId
 * @returns {string}
 */
const readInputValue = (groupId) => {
    const groupElement = document.getElementById(groupId);
    if (!groupElement) { return ""; }
    const inputElement = groupElement.querySelector('.contact-input');
    return (inputElement?.value ?? "").trim();
};

/**
 * 指定グループID内の .contact-input から値を取得
 * @param {string} groupId
 * @returns {string}
 */
const clearInputValue = (groupId) => {
    const groupElement = document.getElementById(groupId);
    if (!groupElement) { return ""; }
    const inputElement = groupElement.querySelector('.contact-input');
    if (inputElement) {
        inputElement.value = "";
    }
};

/**
 * お問い合わせフォームの「確認」処理を束ねる。
 * - 入力値（メール・名前・内容）を確認用エリアへ転記
 * - 入力ラッパー/確認ラッパーの show クラスを入れ替え
 * - 確認ボタンクリック時の遷移を抑止
 */
function bindContactConfirm() {
    // ラッパーとボタンを取得
    const inputWrapper = document.querySelector('.contact-form-wrapper');
    const confirmWrapper = document.querySelector('.contact-confirm-wrapper');
    const completeWrapper = document.querySelector('.contact-complete-wrapper');
    const confirmButton = document.getElementById('contact-confirm-button');
    const backButton = document.getElementById('contact-back-button');
    const sendButton = document.getElementById('contact-send-button');
    const completeBackButton = document.getElementById('contact-complete-back-button');

    if (!inputWrapper || !confirmWrapper || !confirmButton) {
        return;
    }

    /**
     * 指定グループID内の .contact-input-confirm に値を反映
     * @param {string} groupId
     * @param {string} value
     * @returns {void}
     */
    const writeConfirmText = (groupId, value) => {
        const groupElement = document.getElementById(groupId);
        if (!groupElement) { return; }
        const confirmElement = groupElement.querySelector('.contact-input-confirm');
        if (!confirmElement) { return; }
        // XSS防止のため textContent を使う（改行は CSS の white-space で制御）
        confirmElement.textContent = value;
    };

    // 確認ボタンクリックで入力値を転記して画面を切り替え
    confirmButton.addEventListener('click', (event) => {
        event.preventDefault();

        const emailValue = readInputValue('mail-input-group');
        const nameValue = readInputValue('name-input-group');
        const contentValue = readInputValue('content-input-group');

        writeConfirmText('mail-contact-group', emailValue);
        writeConfirmText('name-confirm-group', nameValue);
        writeConfirmText('content-confirm-group', contentValue);

        // 表示切り替え（show クラスの付け外し）
        inputWrapper.classList.remove('show');
        confirmWrapper.classList.add('show');
        completeWrapper.classList.remove('show');
    });
    
    // 確認ボタンクリックで入力値を転記して画面を切り替え
    sendButton.addEventListener('click', (event) => {
        event.preventDefault();

        requestContactAPI();

        // 表示切り替え（show クラスの付け外し）
        inputWrapper.classList.remove('show');
        confirmWrapper.classList.remove('show');
        completeWrapper.classList.add('show');
    });

    backButton.addEventListener('click', (event) => {
        event.preventDefault();

        // 表示切り替え（show クラスの付け外し）
        inputWrapper.classList.add('show');
        confirmWrapper.classList.remove('show');
        completeWrapper.classList.remove('show');
    });
    
    completeBackButton.addEventListener('click', (event) => {
        event.preventDefault();

        // 完了後戻るときはインプットをクリア
        clearInputValue('mail-input-group');
        clearInputValue('name-input-group');
        clearInputValue('content-input-group');

        // 表示切り替え（show クラスの付け外し）
        inputWrapper.classList.add('show');
        confirmWrapper.classList.remove('show');
        completeWrapper.classList.remove('show');
    });
}

// ウィンドウ初期化時にイベントを割り当て
document.addEventListener("DOMContentLoaded", () => {
    bindScroll();
    bindContactConfirm();
});

