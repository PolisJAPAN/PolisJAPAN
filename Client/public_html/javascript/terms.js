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
        threshold: 0
    });

    elements.forEach((el) => observer.observe(el));
}

// ウィンドウ初期化時にイベントを割り当て
document.addEventListener("DOMContentLoaded", () => {
    bindScroll();
});

