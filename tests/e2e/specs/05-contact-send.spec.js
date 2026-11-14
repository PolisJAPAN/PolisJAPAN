// 4.6 お問い合わせの送信（例外として実際に送信する。docs/本番定期テストケース.md §1.2）
const { test, expect, IS_LOCAL, openHome } = require('../lib/fixtures');

// 入力するアドレスを残さないため、このファイルでは画面の記録を取らない
test.use({ guard: { allowContact: true }, trace: 'off', screenshot: 'off', video: 'off' });

const REAL = {
  name: '【自動テスト】PolisJAPAN 定期テスト',
  content: '【自動テスト】これは定期テストによる自動送信です。対応は不要です。',
};

test('TC-CT04 アプリからお問い合わせを送信できる', async ({ page, net }) => {
  test.skip(IS_LOCAL, '実際にメールが送られるため、ローカルでは実行しない');
  const mail = process.env.E2E_CONTACT_EMAIL;
  expect(mail, '環境変数 E2E_CONTACT_EMAIL（テスト用の受信アドレス）が必要').toBeTruthy();

  await openHome(page);
  await page.locator('.hamburger-trigger').click();
  await page.locator('#contact-menu-button').click();
  await expect(page.locator('#contact-modal')).toHaveClass(/show/);
  await page.locator('#contact-mail-input').fill(mail);
  await page.locator('#contact-name-input').fill(REAL.name);
  await page.locator('#contact-content-input').fill(REAL.content);
  await page.locator('#contact-confirm-button').click();
  await expect(page.locator('#contact-modal .contact-confirm-wrapper')).toHaveClass(/show/);
  const [response] = await Promise.all([
    page.waitForResponse((res) => new URL(res.url()).hostname === 'contact.pol-is.jp' && res.request().method() === 'POST', { timeout: 30_000 }),
    page.locator('#contact-send-button').click(),
  ]);
  expect(response.status()).toBe(200);

  const complete = page.locator('#contact-modal .contact-complete-wrapper');
  await expect(complete).toHaveClass(/show/);
  await expect(complete).toContainText('送信しました。');
  await page.locator('#contact-complete-close-button').click();
  await expect(page.locator('#contact-modal')).not.toHaveClass(/show/);
  expect(net.allowed.filter((entry) => entry.startsWith('POST ')).length, '送信は 1 回だけ').toBe(1);
});
