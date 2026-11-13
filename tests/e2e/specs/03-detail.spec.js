// 4.4 テーマ詳細画面
const { test, expect, APP_URL, SHARE_URL, IS_LOCAL, firstCid, openDetail, openReports } = require('../lib/fixtures');

test('TC-DT01 「みんなの意見」タブで分析が表示される', async ({ page }) => {
  await openDetail(page, await firstCid(page));
  const tab = page.locator('.tab[data-tab="reports"]');
  await tab.click();
  await expect(tab).toHaveClass(/active/);
  await expect(page.locator('#app')).toHaveClass(/on-reports/);
  await expect(page.locator('.report-list-container .comment-wrapper').first()).toBeVisible();
  const comment = page.locator('.report-list-container .comments-item').first();
  await expect(comment).toBeVisible();
  await expect(comment.locator('.comment-text-content')).not.toBeEmpty();
});

test.describe('pol.is への通信を許可', () => {
  test.use({ guard: { allowPolis: true } });

  test('TC-DT02 pol.is の投票画面が埋め込まれ、投票と意見投稿の画面が出ている @warn', async ({ page }) => {
    await openDetail(page, await firstCid(page));
    const iframe = page.locator('#app .polis iframe');
    await expect(iframe).toHaveCount(1, { timeout: 20_000 });
    expect(await iframe.getAttribute('src')).toMatch(/^https?:\/\/pol\.is\//);

    // iframe の中は読み取るだけで、クリックも入力もしない（N1）
    const frame = page.frameLocator('#app .polis iframe');
    await expect(frame.locator('#agreeButton')).toBeVisible({ timeout: 30_000 });
    await expect(frame.locator('#disagreeButton')).toBeVisible();
    await expect(frame.locator('#passButton')).toBeVisible();
    await expect(frame.locator('#comment_form_textarea')).toBeVisible();
  });
});

test('TC-DT03 意見の一覧の「もっと見る」を開閉できる', async ({ page, context }) => {
  // 分析の CSV の読み込みが遅くても動くこと（ボタンは読み込み後に生成される）
  await context.route('**/csv/report/**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  });
  await openDetail(page, await firstCid(page));
  await openReports(page);
  const button = page.locator('.report-list-container .accordion-button').first();
  test.skip((await button.count()) === 0, '意見が 6 件未満のテーマには「もっと見る」が無い');

  const target = page.locator(await button.getAttribute('data-target'));
  await button.click();
  await expect(target).toHaveClass(/show/);
  await expect(button).toHaveText('閉じる');
  await button.click();
  await expect(target).not.toHaveClass(/show/);
  await expect(button).toHaveText('もっと見る');
});

test('TC-DT04 意見グループの図を押すと説明が出て、閉じられる', async ({ page }) => {
  await openDetail(page, await firstCid(page));
  await openReports(page);
  const circle = page.locator('.report-list-container .graph-circle').first();
  test.skip((await circle.count()) === 0, 'グループが無いテーマ');

  await circle.click();
  const tooltip = page.locator('.group-tooltip');
  await expect(tooltip).toBeVisible();
  await tooltip.locator('.group-tooltip-close').click();
  await expect(tooltip).toBeHidden();
});

test('TC-DT05 本家の詳細レポートへのリンクが正しく作られている', async ({ page }) => {
  await openDetail(page, await firstCid(page));
  await openReports(page);
  await expect(page.locator('#detail-report-button')).toHaveAttribute('href', /^https:\/\/pol\.is\/report\/.+/);
});

test('TC-DT06 分析から「テーマ」タブへ戻るボタンが動く', async ({ page }) => {
  await openDetail(page, await firstCid(page));
  await openReports(page);
  await page.locator('.goto-theme-button').click();
  await expect(page.locator('.tab[data-tab="conversations"]')).toHaveClass(/active/);
});

test('TC-DT07 共有モーダルに正しい共有リンクと SNS 用の文面が出て、コピーできる', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: APP_URL });
  const cid = await firstCid(page);
  await openDetail(page, cid);
  await page.locator('.share-button').click();
  const modal = page.locator('#copy-complete-modal');
  await expect(modal).toHaveClass(/show/);

  const link = `https://share.pol-is.jp/link?conversation_id=${cid}`;
  const inputs = modal.locator('.share-input');
  await expect(inputs.nth(0)).toHaveValue(link);
  const message = await inputs.nth(1).inputValue();
  expect(message).toMatch(/^テーマ : /);
  expect(message).toContain(link);
  expect(message).toContain('#Polis #ブロードリスニング');

  await modal.locator('#simple-link-share-input-group .copy-button').click();
  await expect(modal.locator('#simple-link-share-input-group .copy-complete-tip')).toHaveClass(/show/);
  await modal.locator('.modal-close-button').click();
  await expect(modal).not.toHaveClass(/show/);
});

test('TC-DT08 詳細画面でお気に入りに入れたテーマが、ホームのお気に入りタブに出る', async ({ page }) => {
  const cid = await firstCid(page);
  await openDetail(page, cid);
  const button = page.locator('.favorite-button');
  await button.click();
  await expect(button).toHaveAttribute('aria-pressed', 'true');
  await expect(button.locator('i')).toHaveClass(/bi-star-fill/);
  const ok = page.locator('.favorite-notice-ok');
  if (await ok.isVisible()) await ok.click();

  await page.locator('.back').click();
  await page.waitForURL((url) => url.pathname === '/');
  await page.locator('.article-item.show').first().waitFor();
  await page.locator('.category-button[data-category="fav"]').click();
  await expect(page.locator(`.article-item.show[data-cid="${cid}"]`)).toBeVisible();
});

test('TC-DT09 共有リンクが OGP を返し、開くと詳細画面にたどり着く', async ({ page, request }) => {
  test.skip(IS_LOCAL, '共有リンクは本番のアプリへ移動するため、ローカルでは実行しない');
  const cid = await firstCid(page);
  const res = await request.get(`${SHARE_URL}/link?conversation_id=${cid}`);
  expect(res.status()).toBe(200);
  expect(await res.text()).toContain(`https://app.pol-is.jp/detail/?conversation_id=${cid}`);

  await page.goto(`${SHARE_URL}/link?conversation_id=${cid}`);
  await page.waitForURL(`https://app.pol-is.jp/detail/?conversation_id=${cid}`);
  await expect(page.locator('.tab[data-tab="reports"]')).toBeVisible();
});

test('TC-DT10 存在しないテーマの URL を開いても画面が壊れない', async ({ page }) => {
  await openDetail(page, 'zzzzzzzzzz');
  const reports = page.locator('.tab[data-tab="reports"]');
  await reports.click();
  await expect(reports).toHaveClass(/active/);
  await expect(page.locator('.report-list-container .comment-wrapper')).toHaveCount(0);
  await page.locator('.tab[data-tab="conversations"]').click();
  await expect(page.locator('.tab[data-tab="conversations"]')).toHaveClass(/active/);
  await page.locator('.back').click();
  await page.waitForURL((url) => url.pathname === '/');
});
