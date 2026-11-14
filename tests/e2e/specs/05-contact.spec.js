// 4.6 お問い合わせモーダル
// #contact-send-button は押さない（N4）。実際に送信する TC-CT04 は 05-contact-send.spec.js。
const { test, expect, openHome } = require('../lib/fixtures');

const DUMMY = { mail: 'autotest@example.invalid', content: '【自動テスト】送信されていたら不具合です' };
async function openContact(page) {
  await page.locator('.hamburger-trigger').click();
  await expect(page.locator('#hamburger-menu')).toHaveClass(/open/);
  await page.locator('#contact-menu-button').click();
  await expect(page.locator('#hamburger-menu')).not.toHaveClass(/open/);
  await expect(page.locator('#contact-modal')).toHaveClass(/show/);
}

const form = (page) => page.locator('#contact-modal .contact-form-wrapper');
const confirm = (page) => page.locator('#contact-modal .contact-confirm-wrapper');

test('TC-CT01 お問い合わせの必須項目とメール形式の入力チェックが働く', async ({ page }) => {
  await openHome(page);
  await openContact(page);
  await expect(form(page)).toHaveClass(/show/);
  const error = page.locator('#contact-form-error');
  const button = page.locator('#contact-confirm-button');

  await button.click();
  await expect(error).toHaveText('お問い合わせ内容を入力してください');
  await page.locator('#contact-content-input').fill(DUMMY.content);
  await button.click();
  await expect(error).toHaveText('メールアドレスを入力してください');
  await page.locator('#contact-mail-input').fill('at-mark-nashi');
  await button.click();
  await expect(error).toHaveText('メールアドレスを入力してください');
  await expect(confirm(page)).not.toHaveClass(/show/);
});

async function fillAndConfirm(page, values) {
  await page.locator('#contact-mail-input').fill(values.mail);
  if (values.name) await page.locator('#contact-name-input').fill(values.name);
  await page.locator('#contact-content-input').fill(values.content);
  await page.locator('#contact-confirm-button').click();
  await expect(confirm(page)).toHaveClass(/show/);
}

test('TC-CT02 確認画面に入力内容が正しく出て、入力画面へ戻れる', async ({ page }) => {
  await openHome(page);
  await openContact(page);
  await fillAndConfirm(page, DUMMY);
  await expect(page.locator('#contact-mail-confirm')).toHaveText(DUMMY.mail);
  await expect(page.locator('#contact-content-confirm')).toHaveText(DUMMY.content);
  await expect(page.locator('#contact-name-confirm')).toHaveText('（未入力）');
  await expect(page.locator('#contact-send-button')).toBeVisible();

  await page.locator('#contact-back-button').click();
  await expect(form(page)).toHaveClass(/show/);
  await expect(page.locator('#contact-content-input')).toHaveValue(DUMMY.content);
  await page.locator('#contact-confirm-button').click();
  await expect(confirm(page)).toHaveClass(/show/);
  // ここで止める。送信が発生していれば、共通の遮断の検査で失敗する
});

test('TC-CT03 入力途中の内容が、再読み込みしても残る', async ({ page }) => {
  await openHome(page);
  await openContact(page);
  await fillAndConfirm(page, DUMMY);
  await page.waitForTimeout(500); // 保存は入力の 300ms 後
  await page.reload();
  await page.locator('.article-item.show').first().waitFor();
  await openContact(page);
  await expect(page.locator('#contact-mail-input')).toHaveValue(DUMMY.mail);
  await expect(page.locator('#contact-content-input')).toHaveValue(DUMMY.content);
});
