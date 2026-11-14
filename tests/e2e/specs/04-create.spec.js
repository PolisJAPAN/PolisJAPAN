// 4.5 テーマ作成（送信の直前まで）
// .post-button は押さない（N3）。.ai-generate-button は TC-AI01 の対立軸のステップでだけ押す（N2）。
const { test, expect, openHome } = require('../lib/fixtures');

const TITLE = '【自動テスト】送信されていたら不具合です';
// 例外として実際に AI 生成へ送るテーマ（docs/本番定期テストケース.md §1.2）
const AI_TITLE = '【自動テスト】在宅勤務を標準の働き方にすべきか';

async function openCreate(page) {
  await openHome(page);
  await page.locator('.create-button').click();
  await expect(page.locator('#theme-create-modal')).toHaveClass(/show/);
}

const stepper = (page, mode, id) => page.locator(`${mode} #${id}`);
const next = (page, mode, id) => stepper(page, mode, id).locator('.next-button');

/** 欄を 1 つずつ埋め、すべて埋めるまで「次へ」が押せないことを確かめてから進む */
async function fillAllAndNext(page, mode, id, selector, values) {
  const inputs = stepper(page, mode, id).locator(selector);
  await expect(inputs).toHaveCount(values.length);
  for (let i = 0; i < values.length; i++) {
    await expect(next(page, mode, id)).toBeDisabled();
    await inputs.nth(i).fill(values[i]);
  }
  await expect(next(page, mode, id)).toBeEnabled();
  await next(page, mode, id).click();
}

const AI = '#ai-assist-mode';
const MANUAL = '#manual-mode';
const comments = (n) => Array.from({ length: n }, (_, i) => `自動テスト用の意見 ${i + 1}`);

test('TC-CR01 テーマ作成モーダルが開き、AI アシストとマニュアルを切り替えられる', async ({ page }) => {
  await openCreate(page);
  await expect(page.locator(AI)).toHaveCount(1);
  await expect(stepper(page, AI, 'theme-stepper')).toHaveClass(/current/);

  await page.locator('#manual-mode-button').click();
  await expect(page.locator(MANUAL)).toHaveCount(1);
  await expect(page.locator(AI)).toHaveCount(0);
  await page.locator('#ai-mode-button').click();
  await expect(page.locator(AI)).toHaveCount(1);

  await page.locator('#theme-create-modal .modal-close-button').first().click();
  await expect(page.locator('#theme-create-modal')).not.toHaveClass(/show/);
});

test('TC-CR02 タイトルの文字数カウントと 80 文字の上限チェックが働く', async ({ page }) => {
  await openCreate(page);
  const input = page.locator(`${AI} #theme-title-textarea`);
  const counter = page.locator(`${AI} .char-counter[data-counter-for="theme-title-textarea"]`);
  const nextButton = next(page, AI, 'theme-stepper');

  await expect(nextButton).toBeDisabled();
  await input.fill('あ'.repeat(10));
  await expect(counter).toHaveText('10/80');
  await expect(nextButton).toBeEnabled();

  // maxlength を越える値は入力できないため、値を直接書き換えて入力イベントを発火する
  await input.evaluate((el) => { el.value = 'あ'.repeat(81); el.dispatchEvent(new Event('input', { bubbles: true })); });
  await nextButton.click();
  await expect(stepper(page, AI, 'theme-stepper').locator('.stepper-error')).toHaveClass(/show/);
  await expect(stepper(page, AI, 'theme-stepper').locator('.stepper-error')).toHaveText('タイトルは80文字以内で入力してください');
  await expect(stepper(page, AI, 'axis-stepper')).not.toHaveClass(/current/);

  await input.fill('あ'.repeat(80));
  await nextButton.click();
  await expect(stepper(page, AI, 'axis-stepper')).toHaveClass(/current/);
});

async function fillUntilDescription(page) {
  await fillAllAndNext(page, AI, 'theme-stepper', '#theme-title-textarea', [TITLE]);
  await fillAllAndNext(page, AI, 'axis-stepper', '.axis-input', ['自動テストの立場 A', '自動テストの立場 B']);
  await fillAllAndNext(page, AI, 'comments-stepper', '.comment-input', comments(8));
  await expect(stepper(page, AI, 'description-stepper')).toHaveClass(/current/);
  await stepper(page, AI, 'description-stepper').locator('#description-textarea').fill('自動テスト用の説明です。');
}

test('TC-CR03 AI アシストの全ステップを手入力で投稿の直前まで進められ、その間 API を呼ばない', async ({ page }) => {
  await openCreate(page);
  await fillUntilDescription(page);
  await next(page, AI, 'description-stepper').click();

  await expect(next(page, AI, 'category-stepper')).toBeDisabled();
  await page.locator(`${AI} .category-select-button[data-value="8"]`).click();
  await next(page, AI, 'category-stepper').click();

  await expect(stepper(page, AI, 'post-stepper')).toHaveClass(/current/);
  await expect(stepper(page, AI, 'post-stepper').locator('.post-button')).toBeEnabled();
  // ここで止める。API への送信が 1 件でも発生していれば、共通の遮断の検査で失敗する
});

test('TC-CR04 入力途中の内容が、モーダルを閉じても再読み込みしても残る', async ({ page }) => {
  await openCreate(page);
  await fillUntilDescription(page);
  const check = async () => {
    await expect(page.locator(`${AI} #theme-title-textarea`)).toHaveValue(TITLE);
    await expect(page.locator(`${AI} .axis-input`).nth(1)).toHaveValue('自動テストの立場 B');
    await expect(page.locator(`${AI} .comment-input`).nth(7)).toHaveValue('自動テスト用の意見 8');
    await expect(page.locator(`${AI} #description-textarea`)).toHaveValue('自動テスト用の説明です。');
  };

  await page.locator('#theme-create-modal .modal-close-button').first().click();
  await expect(page.locator('#theme-create-modal')).not.toHaveClass(/show/);
  await page.locator('.create-button').click();
  await check();
  // 閉じて開き直したときは、同じステップのまま
  await expect(stepper(page, AI, 'description-stepper')).toHaveClass(/current/);

  expect(await page.evaluate(() => localStorage.getItem('AI_ASSIST_CREATE_DRAFT_THEME'))).toBe(TITLE);

  await page.reload();
  await page.locator('.article-item.show').first().waitFor();
  await page.locator('.create-button').click();
  await check();
  // 再読み込みのあとは、入力済みのステップを飛ばして、未入力の最初のステップ（カテゴリ）から再開する
  await expect(stepper(page, AI, 'category-stepper')).toHaveClass(/current/);
});

test('TC-CR05 マニュアルモードで、意見を 8 個入れるまで先へ進めず、8 個で進める', async ({ page }) => {
  await openCreate(page);
  await page.locator('#manual-mode-button').click();
  await fillAllAndNext(page, MANUAL, 'theme-stepper', '#theme-title-textarea', [TITLE]);

  const inputs = stepper(page, MANUAL, 'comments-stepper').locator('.comment-input');
  await expect(inputs).toHaveCount(15);
  const values = comments(8);
  for (let i = 0; i < 8; i++) {
    await expect(next(page, MANUAL, 'comments-stepper')).toBeDisabled();
    await inputs.nth(i).fill(values[i]);
  }
  // 9 個目以降は空のまま進める
  await expect(next(page, MANUAL, 'comments-stepper')).toBeEnabled();
  await next(page, MANUAL, 'comments-stepper').click();
  await expect(stepper(page, MANUAL, 'description-stepper')).toHaveClass(/current/);
});

test.describe('対立軸の AI 生成を許可', () => {
  test.use({ guard: { allowGenerateAxis: true } });

  test('TC-AI01 AI 生成が動いている', async ({ page, net }) => {
    test.setTimeout(180_000);
    await openCreate(page);
    await fillAllAndNext(page, AI, 'theme-stepper', '#theme-title-textarea', [AI_TITLE]);
    await expect(stepper(page, AI, 'axis-stepper')).toHaveClass(/current/);

    const button = stepper(page, AI, 'axis-stepper').locator('.ai-generate-button');
    await expect(button).toBeEnabled();
    const [response] = await Promise.all([
      page.waitForResponse((res) => new URL(res.url()).pathname.endsWith('/theme/generate_axis'), { timeout: 120_000 }),
      button.click(),
    ]);
    expect(response.status()).toBe(200);

    const inputs = stepper(page, AI, 'axis-stepper').locator('.axis-input');
    await expect(inputs.nth(0)).not.toHaveValue('');
    await expect(inputs.nth(1)).not.toHaveValue('');
    await expect(next(page, AI, 'axis-stepper')).toBeEnabled();
    // ここで止める。意見と説明の生成は実行しない
    expect(net.allowed.length, '対立軸の生成は 1 回だけ').toBe(1);
  });
});
