// 4.7 LP
const { test, expect, APP_URL, LP_URL } = require('../lib/fixtures');

const DEMO = '#demo a.article-item';

test('TC-LP01 LP のトップが主要なセクションをそろえてエラー無く表示される', async ({ page }) => {
  const errors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', (err) => errors.push(String(err)));
  await page.goto(`${LP_URL}/`, { waitUntil: 'load' });
  for (const id of ['hero', 'problems', 'features', 'demo', 'info', 'footer']) {
    await expect(page.locator(`#${id}`)).toHaveCount(1);
  }
  expect(errors).toEqual([]);
});

test('TC-LP02 LP からアプリ・プライベート版・デモのテーマへのリンクが正しい', async ({ page }) => {
  await page.goto(`${LP_URL}/`);
  await expect(page.locator('#hero a.button')).toHaveAttribute('href', 'https://app.pol-is.jp/');
  await expect(page.locator('#menu a.menu-button', { hasText: 'プライベート版について' })).toHaveAttribute('href', '/private');
  const hrefs = await page.locator(DEMO).evaluateAll((els) => els.map((e) => e.getAttribute('href')));
  expect(hrefs).toHaveLength(3);
  for (const href of hrefs) expect(href).toMatch(/^https:\/\/app\.pol-is\.jp\/detail\/\?conversation_id=.+/);
});

test('TC-LP03 LP のデモで案内しているテーマが実在する', async ({ page, request }) => {
  await page.goto(`${LP_URL}/`);
  const hrefs = await page.locator(DEMO).evaluateAll((els) => els.map((e) => e.getAttribute('href')));
  const csv = await (await request.get(`${APP_URL}/csv/themes.csv`)).text();
  for (const href of hrefs) {
    const cid = new URL(href).searchParams.get('conversation_id');
    expect(csv, `themes.csv に ${cid} がある`).toContain(`,${cid},`);
  }
});

test.describe('PC 幅', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test('TC-LP04 LP のページ内リンクとハンバーガーメニューが動く', async ({ page }) => {
    await page.goto(`${LP_URL}/`);
    await page.locator('#menu .menu-button.scroll-button[data-target="#features"]').click();
    await expect(page.locator('#features')).toBeInViewport({ timeout: 15_000 });

    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    const expand = page.locator('.menu-expand-button');
    await expect(expand).toBeVisible();
    await expand.click();
    const overlay = page.locator('.overlay-menu');
    await expect(overlay).toHaveClass(/show/);
    const hrefs = await overlay.locator('a').evaluateAll((els) => els.map((e) => e.getAttribute('href')));
    for (const href of ['/contact', '/terms', '/policy', '/license']) expect(hrefs).toContain(href);
    await expand.click();
    await expect(overlay).not.toHaveClass(/show/);
  });
});

test('TC-LP05 LP の下層ページがすべて開き、画像が欠けていない', async ({ page, request }) => {
  for (const path of ['/private/', '/terms/', '/policy/', '/license/', '/contact/']) {
    const res = await page.goto(`${LP_URL}${path}`, { waitUntil: 'load' });
    expect(res.status(), path).toBe(200);
    await expect(page.locator('main, #main').first()).not.toBeEmpty();
  }

  await page.goto(`${LP_URL}/private/`, { waitUntil: 'load' });
  // 遅延読み込みの画像は画面外では読み込まれないため、画像の URL を直接取得して確かめる
  const sources = await page.locator('img').evaluateAll((imgs) => [...new Set(imgs.map((i) => i.src).filter(Boolean))]);
  expect(sources.length).toBeGreaterThan(0);
  const broken = [];
  for (const src of sources) {
    const res = await request.get(src);
    if (res.status() !== 200 || !(res.headers()['content-type'] || '').startsWith('image/')) broken.push(`${res.status()} ${src}`);
  }
  expect(broken).toEqual([]);
});

test('TC-LP06 LP のお問い合わせフォームで確認画面へ進み、戻れる', async ({ page }) => {
  const values = { mail: 'autotest@example.invalid', name: '自動テスト', content: '【自動テスト】送信されていたら不具合です' };
  await page.goto(`${LP_URL}/contact/`);
  await page.locator('#mail-input-group .contact-input').fill(values.mail);
  await page.locator('#name-input-group .contact-input').fill(values.name);
  await page.locator('#content-input-group .contact-input').fill(values.content);
  await page.locator('#contact-confirm-button').click();

  const confirm = page.locator('.contact-confirm-wrapper');
  await expect(confirm).toHaveClass(/show/);
  await expect(confirm.locator('#mail-contact-group .contact-input-confirm')).toHaveText(values.mail);
  await expect(confirm.locator('#name-confirm-group .contact-input-confirm')).toHaveText(values.name);
  await expect(confirm.locator('#content-confirm-group .contact-input-confirm')).toHaveText(values.content);

  // 「お問い合わせ送信」は押さない（N5）
  await page.locator('#contact-back-button').click();
  await expect(page.locator('.contact-form-wrapper')).toHaveClass(/show/);
});
