/**
 * ローディング画面の要素を順次アニメーション表示する。
 * 
 * 各 `.mask-reveal` 要素の `data-delay` 属性に基づいて表示タイミングを制御し、
 * すべてのアニメーション完了後に `#loading` 要素へ `show` クラスを付与する。
 * 
 * @async
 * @returns {Promise<void>} - すべてのマスク表示完了後に解決されるPromise。
 */
async function bindLoading() {
    const elements = [...document.querySelectorAll("#loading .mask-reveal")];
    const start = performance.now();

    const tasks = elements.map((el) => {
        const delay = Number(el.dataset.delay * 1000 || 0);
        const elapsed = performance.now() - start;
        const fireIn = Math.max(0, delay - elapsed);

        return new Promise((resolve) => {
            setTimeout(() => {
                el.classList.add("show");
                resolve();
            }, fireIn);
        });
    });

    // ここで全マスクのshow付与完了を待てる
    await Promise.all(tasks);

    setTimeout(() => {
        document.querySelector("#loading")?.classList.add("show");
    }, 800);
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
 * メニュー表示／非表示をスクロール位置に応じて切り替える。
 * 
 * `body.scrollTop` の位置により、`#menu` および `.menu-expand-button` の
 * `hidden` クラスをトグルする。
 * 
 * @returns {void}
 */
function bindMenuVisiblity() {
    const body = document.body;
    const menu = document.querySelector("#menu");
    const menuExpandButton = document.querySelector(".menu-expand-button");

    body.addEventListener("scroll", () => {
        menu.classList.toggle("hidden", (body.scrollTop > window.innerHeight));
        menuExpandButton.classList.toggle("hidden", (body.scrollTop < window.innerHeight));
    });
}

/**
 * スクロールボタンのクリックで、対象セクションへスムーススクロールする。
 * 
 * 各 `.scroll-button` の `data-target` 属性で指定された要素にスクロール。
 * クリック時にはオーバーレイメニューを閉じる。
 * 
 * @returns {void}
 */
function bindScrollButtons() {
    // data-target を持つボタンを全て拾う
    const buttons = document.querySelectorAll(".scroll-button");

    buttons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetSelector = btn.dataset.target; // "#section1" のような値
            const target = document.querySelector(targetSelector);

            const menuExpandButton = document.querySelector(".menu-expand-button");
            menuExpandButton.classList.remove('active');
            const overlayMenu = document.querySelector(".overlay-menu");
            overlayMenu.classList.remove('show');

            if (target) {
                target.scrollIntoView({
                    behavior: "smooth", // スムーススクロール
                    block: "start"      // 上端に揃える
                });
            } else {
                console.warn(`ターゲット要素が見つかりません: ${targetSelector}`);
            }
        });
    });
}

/**
 * メニュー展開ボタンの開閉処理を設定する。
 * 
 * `.menu-expand-button` クリック時に、ボタンと `.overlay-menu` 双方へ
 * `active`／`show` クラスをトグルする。
 * 
 * @returns {void}
 */
function bindMenuExpandButton() {
    const menuExpandButton = document.querySelector(".menu-expand-button");
    const overlayMenu = document.querySelector(".overlay-menu");

    menuExpandButton.addEventListener("click", () => {
        menuExpandButton.classList.toggle('active');
        overlayMenu.classList.toggle('show');
        return false;
    });
}

/**
 * 問題アニメーション開始フラグ
 */
let problemsAnimationStarted = false;

/**
 * `.problems-posts-group` が可視範囲に入った際に、投稿群アニメーションを一度だけ開始する。
 * 
 * IntersectionObserverを利用し、最初に可視になったタイミングで
 * `bindProblemsAnimation()` を呼び出す。
 * 以降は監視を解除する。
 * 
 * @returns {void}
 */
function observeProblemsGroups() {
    const groups = document.querySelectorAll(".problems-posts-group");
    if (!groups.length) return;

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (!entry.isIntersecting) return;

                // すでに開始済みなら何もしない
                if (problemsAnimationStarted) {
                    observer.unobserve(entry.target);
                    return;
                }

                problemsAnimationStarted = true;

                // 既存メソッドを呼ぶだけ（中は編集しない）
                bindProblemsAnimation();

                // 全グループに対して一度だけで良いならdisconnect
                observer.disconnect();
            });
        },
        { threshold: 0.5 }
    );

    groups.forEach((g) => observer.observe(g));
};

/**
 * `.problems-posts-group .post` 要素を順にアニメーション表示する。
 * 
 * 各要素の `data-order` 属性に基づいてソート後、一定間隔で `show` クラスを付与。
 * 最後の要素表示完了後、`.problems-person-text` にも `show` クラスを付与する。
 * 
 * @returns {void}
 */
function bindProblemsAnimation() {
    const posts = Array.from(
        document.querySelectorAll(".problems-posts-group .post")
    );

    // data-order順に並び替え
    posts.sort((a, b) => {
        return Number(a.dataset.order) - Number(b.dataset.order);
    });

    // アニメーション開始
    const maxDelay = 400; // 最初の間隔(ms)
    const minDelay = 100; // 最後の間隔(ms)
    const count = posts.length;

    let totalDelay = 0;

    posts.forEach((post, index) => {
        // 後になるほど間隔を短くする補間
        const delay =
            maxDelay - ((maxDelay - minDelay) * index) / (count - 1);

        if (!post.dataset.order) {
            return;
        }

        setTimeout(() => {
            post.classList.add("show");
        }, index * delay);

        // 最後の要素のディレイ時間を記録
        totalDelay = (index * delay);
    });
    
    setTimeout(() => {
        document.querySelector(".problems-person-text").classList.add("show");
    }, totalDelay + 1000);
}


// ウィンドウ初期化時にイベントを割り当て
document.addEventListener("DOMContentLoaded", () => {
    bindScroll();
    bindMenuVisiblity();
    bindScrollButtons();
    bindMenuExpandButton();
    observeProblemsGroups();
    bindLoading();
});

