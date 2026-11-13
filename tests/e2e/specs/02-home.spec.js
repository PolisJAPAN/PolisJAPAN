// 4.2 ホーム画面、4.3 お知らせの自動表示
const { test, expect, APP_URL, APP_HOST, openHome } = require('../lib/fixtures');

const cards = (page) => page.locator('.article-item.show');
const attrs = (page, name) => cards(page).evaluateAll((els, n) => els.map((e) => e.getAttribute(n) || ''), name);

test('TC-HM01 ホームを開くとテーマの一覧が表示される', async ({ page }) => {
  await openHome(page);
  const first = cards(page).first();
  await expect(first.locator('.article-title')).not.toBeEmpty();
  await expect(first.locator('.category-label')).toHaveText(/^#.+/);
  await expect(first.locator('.article-opinion-group .text')).toHaveText(/^\d+$/);
  await expect(first.locator('.article-vote-group .text')).toHaveText(/^\d+$/);
  await expect(page.locator('.sort-label')).toHaveText('更新順');
});

test.describe('オーバーレイ抑止なし', () => {
  test.use({ suppressOverlay: false });

  test('TC-HM02 チュートリアルが初回に出て、同じ日や「今後表示しない」のあとは出ない', async ({ page, context }) => {
    const tutorial = page.locator('#tutorial');
    await page.goto(`${APP_URL}/`);
    await expect(tutorial).toHaveClass(/show/);
    for (let n = 1; n <= 5; n++) {
      const win = tutorial.locator(`.tutorial-window[data-number="${n}"]`);
      await expect(win).toBeVisible();
      await win.locator('.next-button').click();
    }
    await expect(tutorial).not.toHaveClass(/show/);

    // 同じ日は出ない
    await page.reload();
    await page.waitForTimeout(3000);
    await expect(tutorial).not.toHaveClass(/show/);

    // Cookie を消して開き直し、「次回から表示しない」で閉じる
    await context.clearCookies();
    await page.evaluate(() => { try { localStorage.clear(); } catch (e) {} });
    await page.goto(`${APP_URL}/`);
    await expect(tutorial).toHaveClass(/show/);
    await page.locator('label[for="hidden-checkbox"]').click();
    await expect(page.locator('#hidden-checkbox')).toBeChecked();
    await tutorial.locator('.skip-button').click();
    await expect(tutorial).not.toHaveClass(/show/);
    const cookies = await context.cookies(APP_URL);
    expect(cookies.find((c) => c.name === 'tutorial_optout')?.value).toBe('1');

    await page.reload();
    await page.waitForTimeout(3000);
    await expect(tutorial).not.toHaveClass(/show/);
  });

  test('TC-NT01 未読のお知らせがあると自動で開き、一度見たあとは開かない', async ({ page, context }) => {
    await context.addCookies([{ name: 'tutorial_optout', value: '1', domain: APP_HOST, path: '/' }]);
    const modal = page.locator('#notice-modal');
    await page.goto(`${APP_URL}/`);
    await expect(modal).toHaveClass(/show/);
    const cookies = await context.cookies(APP_URL);
    expect(cookies.find((c) => c.name === 'notice_last_seen_id')?.value).toMatch(/^\d+$/);

    await modal.locator('.modal-close-button').click();
    await expect(modal).not.toHaveClass(/show/);
    await page.reload();
    await page.waitForTimeout(3000);
    await expect(modal).not.toHaveClass(/show/);
  });
});

test('TC-HM03 ヘルプボタンからチュートリアルを開き直せる', async ({ page }) => {
  await openHome(page);
  await page.locator('.help-button').click();
  await expect(page.locator('#tutorial')).toHaveClass(/show/);
  await page.locator('#tutorial .skip-button').click();
  await expect(page.locator('#tutorial')).not.toHaveClass(/show/);
});

test('TC-HM04 キーワード検索で一覧を絞り込め、解除すると元に戻る', async ({ page }) => {
  await openHome(page);
  const total = await cards(page).count();
  const word = (await cards(page).first().locator('.article-title').innerText()).trim().slice(0, 4);
  const input = page.locator('#search-input');

  await input.fill(word);
  await input.press('Enter');
  await expect.poll(() => cards(page).count()).toBeLessThanOrEqual(total);
  const texts = await cards(page).evaluateAll((els) => els.map((e) => e.textContent));
  expect(texts.length).toBeGreaterThanOrEqual(1);
  for (const t of texts) expect(t).toContain(word);

  await input.fill('zzqqxxテスト不一致');
  await input.press('Enter');
  await expect(cards(page)).toHaveCount(0);

  await input.fill('');
  await input.press('Enter');
  await expect(cards(page)).toHaveCount(total);
});

test('TC-HM05 カテゴリのタブで一覧を絞り込め、もう一度押すと解除される', async ({ page }) => {
  await openHome(page);
  const total = await cards(page).count();
  const tab = page.locator('.category-button[data-category="1"]');

  await tab.click();
  await expect(tab).toHaveClass(/active/);
  const categories = await attrs(page, 'data-category');
  expect(categories.length).toBeGreaterThanOrEqual(1);
  expect(new Set(categories)).toEqual(new Set(['1']));

  await tab.click();
  await expect(page.locator('.category-button[data-category="0"]')).toHaveClass(/active/);
  await expect(cards(page)).toHaveCount(total);
});

test('TC-HM06 並び替えの 5 種類が、それぞれ正しい順にカードを並べる', async ({ page }) => {
  await openHome(page);
  const choose = async (value) => {
    await page.locator('.sort-button').click();
    await expect(page.locator('.sort-select')).toHaveClass(/show/);
    await page.locator(`.select-element[data-value="${value}"]`).click();
  };
  const isSorted = (list, cmp) => list.every((v, i) => i === 0 || cmp(list[i - 1], v) <= 0);
  const numDesc = (a, b) => Number(b) - Number(a);
  const numAsc = (a, b) => Number(a) - Number(b);
  // 日時は「YYYY-MM-DD HH:MM」。空は末尾
  const dateDesc = (a, b) => (a === b ? 0 : a === '' ? 1 : b === '' ? -1 : (a < b ? 1 : -1));

  await choose('popular');
  await expect(page.locator('.sort-label')).toHaveText('人気順');
  expect(isSorted(await attrs(page, 'data-population'), numDesc)).toBe(true);

  await choose('new');
  expect(isSorted(await attrs(page, 'data-id'), numDesc)).toBe(true);
  await choose('old');
  expect(isSorted(await attrs(page, 'data-id'), numAsc)).toBe(true);
  await choose('commented');
  expect(isSorted(await attrs(page, 'data-commented'), dateDesc)).toBe(true);
  await choose('updated');
  expect(isSorted(await attrs(page, 'data-updated'), dateDesc)).toBe(true);
});

test('TC-HM07 お気に入りの登録・解除ができ、再読み込みしても残る', async ({ page }) => {
  await openHome(page);
  const favTab = page.locator('.category-button[data-category="fav"]');
  const allTab = page.locator('.category-button[data-category="0"]');

  await favTab.click();
  await expect(page.locator('.favorites-empty')).toHaveClass(/show/);
  await expect(cards(page)).toHaveCount(0);

  await allTab.click();
  const first = cards(page).nth(0);
  await first.locator('.favorite-toggle').click();
  expect(new URL(page.url()).pathname).toBe('/');
  await expect(page.locator('.favorite-notice-overlay')).toBeVisible();
  await expect(first.locator('.favorite-toggle i')).toHaveClass(/bi-star-fill/);
  await page.locator('.favorite-notice-ok').click();
  await expect(page.locator('.favorite-notice-overlay')).toBeHidden();

  await cards(page).nth(1).locator('.favorite-toggle').click();
  await expect(page.locator('.favorite-toast')).toHaveClass(/show/);
  await expect(page.locator('.favorite-toast')).toContainText('お気に入りに追加しました');
  await expect(page.locator('.favorite-notice-overlay')).toBeHidden();

  await favTab.click();
  await expect(cards(page)).toHaveCount(2);
  await cards(page).nth(0).locator('.favorite-toggle').click();
  await expect(cards(page)).toHaveCount(1);

  await page.reload();
  await cards(page).first().waitFor();
  await page.locator('.category-button[data-category="fav"]').click();
  await expect(cards(page)).toHaveCount(1);
});

test('TC-HM08 カードを押すと、そのテーマの詳細画面へ移動する', async ({ page }) => {
  await openHome(page);
  const cid = await cards(page).first().getAttribute('data-cid');
  await cards(page).first().click();
  await expect(page.locator('#loading-overlay')).toHaveClass(/show/);
  await page.waitForURL(`**/detail/?conversation_id=${cid}`);
});

test('TC-HM09 メニューが開き、お知らせの一覧を読み込んで開閉できる', async ({ page }) => {
  await openHome(page);
  const menu = page.locator('#hamburger-menu');
  const trigger = page.locator('.hamburger-trigger');
  await trigger.click();
  await expect(menu).toHaveClass(/open/);
  await expect(trigger).toHaveAttribute('aria-expanded', 'true');
  for (const label of ['お知らせ', '改善要望', 'プライベート版について', 'お問い合わせ', '利用規約', 'プライバシーポリシー']) {
    await expect(menu).toContainText(label);
  }

  await page.locator('#notice-menu-button').click();
  await expect(menu).not.toHaveClass(/open/);
  const modal = page.locator('#notice-modal');
  await expect(modal).toHaveClass(/show/);
  const items = modal.locator('.notice-item');
  await expect(items.first()).toHaveClass(/open/);
  await expect(modal).not.toContainText('読み込めませんでした');
  const count = await items.count();
  expect(count).toBeGreaterThanOrEqual(1);
  expect(await modal.locator('.notice-item.open').count()).toBe(1);

  if (count >= 2) {
    await items.nth(1).locator('.notice-header').click();
    await expect(items.nth(1)).toHaveClass(/open/);
  }
  await modal.locator('.modal-close-button').click();
  await expect(modal).not.toHaveClass(/show/);
});

test('TC-HM10 メニューの各リンクと「改善要望」が正しい行き先を指している', async ({ page }) => {
  await openHome(page);
  await page.locator('.hamburger-trigger').click();
  const menu = page.locator('#hamburger-menu');
  await expect(menu).toHaveClass(/open/);
  const hrefs = await menu.locator('a').evaluateAll((els) => els.map((e) => e.getAttribute('href')));
  expect(hrefs).toContain('https://pol-is.jp/private/');
  expect(hrefs).toContain('https://pol-is.jp/terms/');
  expect(hrefs).toContain('https://pol-is.jp/policy/');

  await page.locator('#feedback-menu-button').click();
  await page.waitForURL('**/detail/?conversation_id=9knucbecnr');
});

test('TC-HM11 メニューを Esc キーと背景のクリックで閉じられる', async ({ page }) => {
  await openHome(page);
  const menu = page.locator('#hamburger-menu');
  await page.locator('.hamburger-trigger').click();
  await expect(menu).toHaveClass(/open/);
  await page.keyboard.press('Escape');
  await expect(menu).not.toHaveClass(/open/);

  await page.locator('.hamburger-trigger').click();
  await expect(menu).toHaveClass(/open/);
  await page.locator('.hamburger-backdrop').click({ position: { x: 5, y: 400 } });
  await expect(menu).not.toHaveClass(/open/);
});
