// 共通の前提（docs/本番定期テストケース.md §2）を実装する。
// - 通信の遮断（§2.2）: 送信を伴う通信を止め、発生したらテストを失敗にする
// - オーバーレイ抑止（§2.3）
const { test: base, expect } = require('@playwright/test');

const trim = (u) => u.replace(/\/$/, '');
const APP_URL = trim(process.env.APP_URL || 'https://app.pol-is.jp');
const LP_URL = trim(process.env.LP_URL || 'https://pol-is.jp');
const API_URL = trim(process.env.API_URL || 'https://api.pol-is.jp');
const ADMIN_URL = trim(process.env.ADMIN_URL || 'https://admin.pol-is.jp');
const SHARE_URL = trim(process.env.SHARE_URL || 'https://share.pol-is.jp');
const IS_LOCAL = new URL(APP_URL).hostname === 'localhost';

const APP_HOST = new URL(APP_URL).hostname;
const API_HOST = new URL(API_URL).hostname;

/** 通信を分類する。'api' | 'contact' | 'polis' | null */
function classify(url) {
  let u;
  try { u = new URL(url); } catch { return null; }
  if (u.hostname === API_HOST) return 'api';
  // ローカルの画面は /api/ を本番 API へ中継する
  if (u.hostname === APP_HOST && u.pathname.startsWith('/api/')) return 'api';
  if (u.hostname === 'contact.pol-is.jp') return 'contact';
  if (u.hostname === 'pol.is' || u.hostname.endsWith('.pol.is')) return 'polis';
  return null;
}

const test = base.extend({
  // テストごとの許可。test.use({ guard: { allowPolis: true } }) のように指定する
  guard: [{ allowPolis: false, allowGenerateAxis: false, allowContact: false }, { option: true }],
  // false にすると、チュートリアルとお知らせの自動表示を止めない
  suppressOverlay: [true, { option: true }],

  // 遮断の対象になった通信（発生したらテストは失敗）と、通した送信の記録
  net: async ({}, use) => {
    await use({ violations: [], allowed: [] });
  },

  context: async ({ context, guard, suppressOverlay, net }, use) => {
    await context.route((url) => classify(url.toString()) !== null, async (route) => {
      const request = route.request();
      const url = request.url();
      const method = request.method();
      const kind = classify(url);
      const path = new URL(url).pathname;

      if (kind === 'polis') {
        // 遮断しても失敗にはしない（詳細画面を開けば必ず発生するため）
        return guard.allowPolis ? route.continue() : route.abort();
      }
      if (kind === 'api') {
        if (method === 'GET' || method === 'HEAD' || method === 'OPTIONS') return route.continue();
        if (guard.allowGenerateAxis && path.endsWith('/theme/generate_axis')) {
          net.allowed.push(`${method} ${url}`);
          return route.continue();
        }
      }
      if (kind === 'contact' && guard.allowContact) {
        net.allowed.push(`${method} ${url}`);
        return route.continue();
      }
      net.violations.push(`${method} ${url}`);
      return route.abort();
    });

    if (suppressOverlay) {
      await context.addCookies([
        { name: 'tutorial_optout', value: '1', domain: APP_HOST, path: '/' },
        { name: 'notice_last_seen_id', value: '999', domain: APP_HOST, path: '/' },
      ]);
    }

    await use(context);

    expect(net.violations, '送信を伴う通信が発生した（docs/本番定期テストケース.md §2.2）').toEqual([]);
  },
});

/** ホームを開き、カードの表示を待つ */
async function openHome(page) {
  await page.goto(`${APP_URL}/`);
  await page.locator('.article-item.show').first().waitFor();
}

/** ホームの先頭のカードの conversation_id を返す（§2.4） */
async function firstCid(page) {
  await openHome(page);
  return page.locator('.article-item.show').first().getAttribute('data-cid');
}

/** 詳細画面を開く */
async function openDetail(page, cid) {
  await page.goto(`${APP_URL}/detail/?conversation_id=${cid}`);
  await page.locator('.tab[data-tab="reports"]').waitFor();
}

/** 詳細画面で「みんなの意見」タブを開き、分析の表示を待つ */
async function openReports(page) {
  await page.locator('.tab[data-tab="reports"]').click();
  await page.locator('.report-list-container .comment-wrapper').first().waitFor();
}

module.exports = {
  test, expect,
  APP_URL, LP_URL, API_URL, ADMIN_URL, SHARE_URL, APP_HOST, IS_LOCAL,
  openHome, firstCid, openDetail, openReports,
};
