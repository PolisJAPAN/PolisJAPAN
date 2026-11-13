// 4.8 表示の崩れ・エラー（全画面共通）
const { test, expect, APP_URL, LP_URL, IS_LOCAL, firstCid, openDetail, openReports } = require('../lib/fixtures');

const OWN_HOSTS = [new URL(APP_URL).hostname, new URL(LP_URL).hostname];

test('TC-CM01 画面に必要なファイルが読み込めている', async ({ page }) => {
  const failed = [];
  page.on('response', (res) => {
    const url = new URL(res.url());
    if (OWN_HOSTS.includes(url.hostname) && res.status() >= 400) failed.push(`${res.status()} ${res.url()}`);
  });
  const cid = await firstCid(page);
  await openDetail(page, cid);
  await page.waitForLoadState('networkidle');
  await page.goto(`${LP_URL}/`, { waitUntil: 'networkidle' });
  expect(failed).toEqual([]);
});

test('TC-CM02 スクリプトのエラーが出ていない', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (err) => errors.push(String(err)));
  const cid = await firstCid(page);
  await openDetail(page, cid);
  await openReports(page);
  await page.goto(`${LP_URL}/`, { waitUntil: 'load' });
  await page.waitForTimeout(1000);
  expect(errors).toEqual([]);
});

test('TC-CM03 デプロイ後に古いファイルが混ざっていない', async ({ request }) => {
  test.skip(IS_LOCAL, 'バージョンの値はデプロイ時に入るため、ローカルでは実行しない');
  const html = await (await request.get(`${APP_URL}/`)).text();
  const versions = [...html.matchAll(/(?:href|src)="[^"]+\.(?:css|js)\?v=([^"&]+)"/g)].map((m) => m[1]);
  expect(versions.length).toBeGreaterThan(0);
  expect(new Set(versions).size, `バージョン: ${[...new Set(versions)].join(', ')}`).toBe(1);
  expect(versions[0]).not.toBe('__ASSET_VERSION__');
});
