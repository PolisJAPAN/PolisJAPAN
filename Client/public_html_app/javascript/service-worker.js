// sw.js
const CACHE_NAME = 'img-cache-v1';

// プリキャッシュしたい画像のリスト
const PRECACHE_IMAGES = [
    "/images/tutorial/home_tutorial_01.png",
    "/images/tutorial/home_tutorial_02.png",
    "/images/tutorial/home_tutorial_03.png",
    "/images/tutorial/home_tutorial_04.png",
    "/images/tutorial/home_tutorial_05.png",
    "/images/tutorial/home_tutorial_06.png",
    "/images/tutorial/make-comments.png",
    "/images/tutorial/tutorial_01.png",
    "/images/tutorial/tutorial_02.png",
    "/images/tutorial/tutorial_03.png",
    "/images/tutorial/tutorial_04.png",
    "/images/tutorial/tutorial_05.png",
    "/images/report/men_01.png",
    "/images/report/men_02.png",
    "/images/report/men_03.png",
    "/images/report/women_01.png",
    "/images/report/women_02.png",
    "/images/report/women_03.png",
];

// install時にキャッシュ
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_IMAGES))
    );
    self.skipWaiting();
});

// activate時に古いキャッシュを削除
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => key !== CACHE_NAME)
                    .map((key) => caches.delete(key))
            )
        )
    );
    self.clients.claim();
});

// fetch時はCache Firstで対応
self.addEventListener('fetch', (event) => {
    const { request } = event;

    // プリキャッシュ対象のみ応答
    if (PRECACHE_IMAGES.some((path) => request.url.includes(path))) {
        event.respondWith(
            caches.match(request).then((cached) => {
                return cached || fetch(request).then((res) => {
                    // ネットから取れた場合もキャッシュ更新
                    return caches.open(CACHE_NAME).then((cache) => {
                        cache.put(request, res.clone());
                        return res;
                    });
                });
            })
        );
    }
});
